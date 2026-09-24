#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
So-net Master DB Normalizer Primitive (Phase F2A.3)

責任範圍：
1. 根據 TruthVersion 派生 Client Family（例如 00610008 -> 0061）
2. 載入對應之 schema mapping 契約（pipeline/manifests/sonet_db_schema_map_{family}.json）
3. 嚴格 Fail-Closed 門禁：
   - 未知 Client Family 拒絕執行（NEEDS_NEW_SCHEMA_MAPPING）
   - 實體混淆表或實體欄位 Token 缺失立即拒絕
   - Mapping 存在重複或衝突立即拒絕
4. 從原生混淆 DB 僅選取 Story Map 與角色圖鑑核心 11 表（共 99 個 mapped columns），生成全新乾淨的 Normalized SQLite
5. 建立主鍵索引，並通過 PRAGMA integrity_check 驗收

邊界規範：
- 獨立 Canonical 模組，不修改 dashboard/redive_tw.db
- 不依賴 wthee 或任何第三方服務
- 零啟發式猜測（Fail-Closed on any drift）
"""

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

SQLITE_MAGIC = b'SQLite format 3\x00'


@dataclass
class NormalizedDbResult:
    success: bool
    truth_version: str
    client_family: str
    mapping_file: Optional[Path] = None
    output_path: Optional[Path] = None
    output_size_bytes: int = 0
    table_stats: Dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    raw_db_sha256: Optional[str] = None
    normalized_db_sha256: Optional[str] = None
    mapping_schema_version: str = "1.0.0"
    provenance: Dict[str, Any] = field(default_factory=dict)


def get_client_family(truth_version: str) -> str:
    """
    從 TruthVersion 解析出 Client Family 前綴。
    例如: "00610008" -> "0061"
    """
    if not truth_version or len(truth_version) < 4:
        raise ValueError(f"無效的 TruthVersion 格式: {truth_version!r}")
    return truth_version[:4]


def load_schema_mapping(client_family: str, manifest_dir: Optional[Path] = None) -> Tuple[Path, Dict[str, Any]]:
    """
    載入指定 Client Family 的 Schema Mapping 契約。
    若不存在則 Fail-Closed。
    """
    if manifest_dir is None:
        manifest_dir = Path(__file__).resolve().parent / "manifests"
    
    mapping_file = manifest_dir / f"sonet_db_schema_map_{client_family}.json"
    if not mapping_file.is_file():
        raise KeyError(
            f"FAIL_CLOSED: NEEDS_NEW_SCHEMA_MAPPING: No schema mapping found for client family '{client_family}' "
            f"at {mapping_file}"
        )
    
    with open(mapping_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if data.get("client_family") != client_family:
        raise ValueError(
            f"Mapping 檔案 client_family 不符: 預期={client_family}, 檔案內={data.get('client_family')}"
        )
    
    return mapping_file, data


def validate_mapping_contract(mapping_data: Dict[str, Any]) -> None:
    """
    對 mapping contract 進行結構自檢與防重複門禁。
    """
    tables = mapping_data.get("tables", {})
    if not tables:
        raise ValueError("Mapping 契約中未定義任何資料表")
    
    seen_plaintext = set()
    seen_physical = set()
    
    for tbl_name, tbl_meta in tables.items():
        if tbl_name in seen_plaintext:
            raise ValueError(f"Mapping 存在重複的明文表名: {tbl_name}")
        seen_plaintext.add(tbl_name)
        
        phys_table = tbl_meta.get("physical_table")
        if not phys_table:
            raise ValueError(f"資料表 {tbl_name} 未指定 physical_table")
        if phys_table in seen_physical:
            raise ValueError(f"Mapping 存在重複的實體表指向: {phys_table} (表: {tbl_name})")
        seen_physical.add(phys_table)
        
        cols = tbl_meta.get("columns", {})
        if not cols:
            raise ValueError(f"資料表 {tbl_name} 未指定任何欄位 mapping")
        
        seen_phys_cols = set()
        for col_plain, col_phys in cols.items():
            if not col_phys:
                raise ValueError(f"表 {tbl_name} 欄位 {col_plain} 的 physical token 為空")
            if col_phys in seen_phys_cols:
                raise ValueError(f"表 {tbl_name} 存在重複的實體欄位指向: {col_phys}")
            seen_phys_cols.add(col_phys)


def generate_normalized_db(
    raw_db_path: Path,
    truth_version: str,
    output_path: Path,
    manifest_dir: Optional[Path] = None,
    batch_size: int = 1000
) -> NormalizedDbResult:
    """
    核心生成函式：
    從原生混淆 SQLite，依嚴格 mapping 契約生成乾淨的 Normalized SQLite。
    """
    start_time = time.perf_counter()
    client_family = get_client_family(truth_version)
    result = NormalizedDbResult(
        success=False,
        truth_version=truth_version,
        client_family=client_family
    )
    
    raw_db_path = Path(raw_db_path)
    output_path = Path(output_path)
    
    # 1. 檢查原始 DB 是否存在且合法
    if not raw_db_path.is_file():
        result.error = f"原始混淆資料庫檔案不存在: {raw_db_path}"
        return result
    
    with open(raw_db_path, "rb") as f:
        raw_header = f.read(16)
        if raw_header != SQLITE_MAGIC:
            result.error = f"原始檔案非有效的 SQLite 格式 (Magic Header 不符): {raw_db_path}"
            return result
        f.seek(0)
        hasher = hashlib.sha256()
        while chunk := f.read(65536):
            hasher.update(chunk)
        result.raw_db_sha256 = hasher.hexdigest()
            
    # 2. 載入並驗證 Mapping 契約 (Fail-Closed)
    try:
        mapping_file, mapping_data = load_schema_mapping(client_family, manifest_dir=manifest_dir)
        validate_mapping_contract(mapping_data)
        result.mapping_file = mapping_file
    except Exception as e:
        result.error = str(e)
        return result
        
    tables_config = mapping_data["tables"]
    
    # 3. 檢查原始 DB 中的實體表與實體欄位存在性 (Fail-Closed)
    conn_raw = sqlite3.connect(str(raw_db_path))
    try:
        cur_raw = conn_raw.cursor()
        cur_raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_raw_tables = set(r[0] for r in cur_raw.fetchall())
        
        for tbl_name, tbl_meta in tables_config.items():
            phys_tbl = tbl_meta["physical_table"]
            if phys_tbl not in existing_raw_tables:
                result.error = f"FAIL_CLOSED: 原始庫中缺失實體表 {phys_tbl} (對應明文表: {tbl_name})"
                return result
            
            cur_raw.execute(f'PRAGMA table_info("{phys_tbl}")')
            existing_phys_cols = set(r[1] for r in cur_raw.fetchall())
            
            for col_plain, col_phys in tbl_meta["columns"].items():
                if col_phys not in existing_phys_cols:
                    result.error = (
                        f"FAIL_CLOSED: 表 {tbl_name} (實體: {phys_tbl}) 中缺失實體欄位 {col_phys} "
                        f"(對應明文欄位: {col_plain})"
                    )
                    return result
    finally:
        conn_raw.close()
        
    # 4. 於同目錄建立臨時檔開始生成 Normalized DB
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_db_path = tempfile.mkstemp(
        prefix=f".tmp_norm_{client_family}_",
        suffix=".db",
        dir=str(output_path.parent)
    )
    os.close(temp_fd)
    temp_db = Path(temp_db_path)
    
    try:
        conn_raw = sqlite3.connect(str(raw_db_path))
        cur_raw = conn_raw.cursor()
        
        conn_out = sqlite3.connect(str(temp_db))
        cur_out = conn_out.cursor()
        
        # 性能優化 PRAGMA
        cur_out.execute("PRAGMA synchronous = OFF")
        cur_out.execute("PRAGMA journal_mode = MEMORY")
        
        table_stats = {}
        
        for tbl_name, tbl_meta in tables_config.items():
            phys_tbl = tbl_meta["physical_table"]
            col_map = tbl_meta["columns"]
            pk_col = tbl_meta.get("primary_key")
            
            plain_cols = list(col_map.keys())
            phys_cols = [col_map[c] for c in plain_cols]
            
            # A. 建表
            col_defs = ", ".join(f'"{c}" TEXT' for c in plain_cols) # SQLite 是動態型態，欄位定義乾淨宣告
            cur_out.execute(f'CREATE TABLE "{tbl_name}" ({col_defs})')
            
            # B. 串流抽取與寫入
            select_cols = ", ".join(f'"{pc}"' for pc in phys_cols)
            cur_raw.execute(f'SELECT {select_cols} FROM "{phys_tbl}"')
            
            insert_placeholders = ", ".join("?" for _ in plain_cols)
            insert_sql = f'INSERT INTO "{tbl_name}" VALUES ({insert_placeholders})'
            
            row_count = 0
            while True:
                batch = cur_raw.fetchmany(batch_size)
                if not batch:
                    break
                cur_out.executemany(insert_sql, batch)
                row_count += len(batch)
                
            # C. 建立主鍵與常用查詢索引
            if pk_col:
                if isinstance(pk_col, list):
                    if all(c in plain_cols for c in pk_col):
                        cols_sql = ", ".join(f'"{c}"' for c in pk_col)
                        idx_name = f'idx_{tbl_name}_{"_".join(pk_col)}'
                        cur_out.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{tbl_name}"({cols_sql})')
                elif isinstance(pk_col, str) and pk_col in plain_cols:
                    cur_out.execute(
                        f'CREATE INDEX IF NOT EXISTS "idx_{tbl_name}_{pk_col}" ON "{tbl_name}"("{pk_col}")'
                    )
            
            # 特別為常用查詢欄位建立輔助索引
            if tbl_name == "story_detail" and "story_group_id" in plain_cols:
                cur_out.execute('CREATE INDEX IF NOT EXISTS "idx_story_detail_group" ON "story_detail"("story_group_id")')
            if tbl_name == "event_story_detail" and "story_group_id" in plain_cols:
                cur_out.execute('CREATE INDEX IF NOT EXISTS "idx_event_story_detail_group" ON "event_story_detail"("story_group_id")')
            if tbl_name == "unit_attack_pattern" and "unit_id" in plain_cols:
                cur_out.execute('CREATE INDEX IF NOT EXISTS "idx_unit_attack_pattern_unit" ON "unit_attack_pattern"("unit_id")')
            if tbl_name == "unit_rarity" and "unit_id" in plain_cols:
                cur_out.execute('CREATE INDEX IF NOT EXISTS "idx_unit_rarity_unit" ON "unit_rarity"("unit_id")')
                
            table_stats[tbl_name] = row_count
            
        conn_out.commit()
        
        # 5. 生成後校驗 (PRAGMA integrity_check)
        cur_out.execute("PRAGMA integrity_check")
        row = cur_out.fetchone()
        if not row or row[0] != "ok":
            raise ValueError(f"Normalized DB PRAGMA integrity_check 失敗: {row}")
            
        # 檢查每張表 row count
        for tbl_name, count in table_stats.items():
            if count <= 0:
                raise ValueError(f"Normalized 表 {tbl_name} 筆數為 0，視為異常生成")
                
        conn_out.close()
        conn_raw.close()
        
        # 6. 原子替換
        os.replace(temp_db, output_path)
        
        # 7. 計算產出 SHA-256 與 Provenance
        hasher_out = hashlib.sha256()
        with open(output_path, "rb") as f:
            while chunk := f.read(65536):
                hasher_out.update(chunk)
        result.normalized_db_sha256 = hasher_out.hexdigest()
        
        mapped_col_count = sum(len(m.get("columns", {})) for m in tables_config.values())
        result.provenance = {
            "truth_version": truth_version,
            "client_family": client_family,
            "raw_db_sha256": result.raw_db_sha256,
            "normalized_db_sha256": result.normalized_db_sha256,
            "normalized_db_size": output_path.stat().st_size,
            "mapping_contract": mapping_file.name if mapping_file else None,
            "mapping_schema_version": result.mapping_schema_version,
            "table_count": len(table_stats),
            "mapped_column_count": mapped_col_count,
        }
        
        elapsed = time.perf_counter() - start_time
        result.success = True
        result.output_path = output_path
        result.output_size_bytes = output_path.stat().st_size
        result.table_stats = table_stats
        result.elapsed_seconds = elapsed
        return result
        
    except Exception as e:
        if temp_db.exists():
            try:
                temp_db.unlink()
            except Exception:
                pass
        result.error = f"生成 Normalized DB 過程失敗: {e}"
        return result
    finally:
        try:
            conn_raw.close()
        except Exception:
            pass
        try:
            conn_out.close()
        except Exception:
            pass
