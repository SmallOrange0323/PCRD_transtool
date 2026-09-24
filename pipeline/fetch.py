#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Fetcher
負責與 So-net CDN 進行資料探測、下載與解密。
提供與 tools/pcrd_fetch.py 100% 相容之模組函式與 CLI 入口。
"""

import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
CANONICAL_DB_PATH = DASHBOARD_DIR / "redive_tw.db"

sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.sonet_master_db import fetch_master_db_from_sonet
from pipeline.sonet_normalized_db import (
    generate_normalized_db,
    get_client_family,
    load_schema_mapping,
    validate_mapping_contract,
)

# 匯入現有成熟之 pcrd_fetch 核心功能 (除 update_db 外)
try:
    from pcrd_fetch import (
        cmd_fetch_story as fetch_story,
        cmd_fetch_stories as fetch_stories,
        cmd_fetch_assets as fetch_assets,
        cmd_scan_cdn as scan_cdn,
        cmd_fetch_story_voices as fetch_story_voices,
        cmd_fetch_story_images as fetch_story_images,
        cmd_sync_episode as sync_episode,
        cmd_fetch_story_thumbnails as fetch_story_thumbnails,
        extract_canonical_background_image,
        fetch_story_json_by_id,
        sync_story_batch_with_metadata,
        StoryFetchResult,
        load_story_manifest_hash_map,
        TruthVersionProbeResult,
        probe_truth_version,
        _get_story_ids_from_db,
        main as pcrd_fetch_main
    )
except ImportError as e:
    print(f"[ERROR] 無法載入 tools/pcrd_fetch.py: {e}", file=sys.stderr)
    sys.exit(1)


def _validate_normalized_db_pre_promotion(staging_db_path: Path, truth_version: str):
    """
    在原子替換至正式資料庫前，執行全量資料完整性與生產查詢門禁驗證。
    """
    client_family, mapping = load_schema_mapping(get_client_family(truth_version))
    validate_mapping_contract(mapping)

    conn = sqlite3.connect(str(staging_db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        # 1. PRAGMA integrity_check
        cur.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        if not row or row[0] != "ok":
            raise ValueError(f"PRAGMA integrity_check 失敗: {row[0] if row else 'empty'}")

        # 2. 驗證 11 張業務表與 mapped columns
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = set(r[0] for r in cur.fetchall())
        expected_tables = set(mapping["tables"].keys())
        missing_tables = expected_tables - existing_tables
        if missing_tables:
            raise ValueError(f"缺失必要業務表: {missing_tables}")

        total_mapped = 0
        for tbl_name, tbl_meta in mapping["tables"].items():
            cur.execute(f'SELECT COUNT(*) FROM "{tbl_name}"')
            cnt = cur.fetchone()[0]
            if cnt == 0:
                raise ValueError(f"表 {tbl_name} 筆數為 0，視為異常資料庫")

            cur.execute(f'PRAGMA table_info("{tbl_name}")')
            col_names = set(r["name"] for r in cur.fetchall())
            exp_cols = set(tbl_meta["columns"].keys())
            missing_cols = exp_cols - col_names
            if missing_cols:
                raise ValueError(f"表 {tbl_name} 缺失必要欄位: {missing_cols}")
            total_mapped += len(exp_cols)

        if total_mapped != 99:
            raise ValueError(f"Mapped columns 總數不符: 預期 99，實際 {total_mapped}")

        # 3. 生產查詢模擬門禁 (CharactersModule.render)
        render_sql = """
            SELECT 
                t.max_id as unit_id,
                u.unit_name,
                u.rarity,
                u.search_area_width as pos,
                p.race,
                p.guild
            FROM (
                SELECT MAX(unit_id) as max_id, unit_name 
                FROM unit_data 
                WHERE unit_id < 200000 AND unit_id > 100000
                AND unit_name NOT LIKE '%怪物%'
                AND unit_id IN (SELECT DISTINCT unit_id FROM unit_rarity)
                GROUP BY unit_name
            ) as t
            JOIN unit_data as u ON u.unit_id = t.max_id
            LEFT JOIN unit_profile as p ON u.unit_id = p.unit_id
            ORDER BY unit_id DESC
        """
        cur.execute(render_sql)
        render_rows = cur.fetchall()
        if len(render_rows) < 200:
            raise ValueError(f"CharactersModule.render 角色總數異常: {len(render_rows)} (預期 > 200)")

        # 4. 生產查詢模擬門禁 (CharactersModule.showDetail 數值、技能與動作循環)
        sample_unit_id = 105801  # 佩可
        cur.execute("SELECT * FROM unit_rarity WHERE unit_id = ? ORDER BY rarity DESC LIMIT 1", (sample_unit_id,))
        if not cur.fetchone():
            raise ValueError(f"樣本角色 {sample_unit_id} 查無 unit_rarity")

        cur.execute("SELECT search_area_width FROM unit_data WHERE unit_id = ?", (sample_unit_id,))
        if not cur.fetchone():
            raise ValueError(f"樣本角色 {sample_unit_id} 查無 search_area_width")

        cur.execute("SELECT * FROM unit_skill_data WHERE unit_id = ?", (sample_unit_id,))
        s_row = cur.fetchone()
        if not s_row or not s_row["union_burst"]:
            raise ValueError(f"樣本角色 {sample_unit_id} 查無 unit_skill_data 或 UB")

        cur.execute("SELECT name, description, icon_type FROM skill_data WHERE skill_id = ?", (s_row["union_burst"],))
        if not cur.fetchone():
            raise ValueError(f"樣本技能 {s_row['union_burst']} 查無 skill_data")

        cur.execute("SELECT * FROM unit_attack_pattern WHERE unit_id = ? ORDER BY pattern_id ASC LIMIT 1", (sample_unit_id,))
        pat = cur.fetchone()
        if not pat or not str(pat["pattern_id"]).endswith("01"):
            raise ValueError(f"樣本角色 {sample_unit_id} 查無基本常態攻擊循環")

        # 5. 生產查詢模擬門禁 (CharactersModule.renderStoryList)
        cur.execute("SELECT story_id, title, sub_title FROM story_detail WHERE CAST(story_id AS TEXT) LIKE ? ORDER BY story_id ASC", ("1058%",))
        story_rows = cur.fetchall()
        if len(story_rows) < 4:
            raise ValueError(f"樣本角色 {sample_unit_id} 個人劇情數異常: {len(story_rows)}")

        # 6. 維護查詢門禁 (pcrd_fetch 查詢)
        cur.execute(
            "SELECT u.unit_id, u.unit_name FROM unit_data u "
            "WHERE u.unit_id >= 100000 AND u.unit_id < 180000 "
            "AND EXISTS (SELECT 1 FROM unit_rarity r WHERE r.unit_id = u.unit_id) "
            "ORDER BY u.unit_id DESC LIMIT 5"
        )
        if len(cur.fetchall()) == 0:
            raise ValueError("維護查詢 _query_game_snapshot latest_chars 為空")

        cur.execute("SELECT COUNT(*) FROM chara_story_status WHERE chara_id_1 = ?", (1058,))
        if cur.fetchone()[0] == 0:
            raise ValueError("維護查詢 chara_story_status 筆數為 0")

        cur.execute("SELECT story_id, title, sub_title FROM story_detail ORDER BY story_id DESC LIMIT 5")
        if len(cur.fetchall()) == 0:
            raise ValueError("主線故事查詢為空")

        cur.execute("SELECT story_group_id, title, start_time FROM event_story_data ORDER BY story_group_id DESC LIMIT 5")
        if len(cur.fetchall()) == 0:
            raise ValueError("活動故事查詢為空")

    finally:
        conn.close()


def update_db(
    truth_version: str,
    output: Optional[str] = "tools/db_update_report.json",
    db_path: Optional[Path] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    從 So-net 官方 CDN 下載指定 TruthVersion 之加密 Master DB Bundle，
    於臨時目錄解包並依據 Canonical Schema Mapping 正規化，
    通過全套執行期門禁檢驗後原子替換正式資料庫。
    """
    target_path = Path(db_path) if db_path else CANONICAL_DB_PATH
    staging_path = target_path.with_name(f"{target_path.name}.download.tmp")

    report: Dict[str, Any] = {
        "status": "pending",
        "truth_version": truth_version,
        "source": "sonet_official_cdn",
        "target_db_path": str(target_path),
    }

    # 1. 顯式版號契約檢驗
    if not isinstance(truth_version, str) or not re.fullmatch(r"\d{8}", truth_version):
        error_msg = f"無效的 TruthVersion 格式 (要求 8 碼數字字串): {truth_version!r}"
        report["status"] = "error"
        report["error"] = error_msg
        if output:
            _write_report(output, report)
        return report

    client_family = get_client_family(truth_version)
    report["client_family"] = client_family

    # 1.1 嚴格檢查 client family schema mapping 是否存在，未知家族立即 Fail-Closed
    try:
        load_schema_mapping(client_family)
    except KeyError as e:
        report["status"] = "error"
        report["error"] = f"NEEDS_NEW_SCHEMA_MAPPING: {e}"
        if output:
            _write_report(output, report)
        return report

    temp_dir = tempfile.TemporaryDirectory()
    try:
        raw_db_path = Path(temp_dir.name) / f"raw_master_{truth_version}.db"

        # 2. 從 So-net 官方 CDN 獲取原始加密資料庫
        fetch_res = fetch_master_db_from_sonet(
            truth_version=truth_version,
            destination=raw_db_path
        )
        if not fetch_res.success:
            report["status"] = "error"
            report["error"] = f"So-net 原始 Master DB 獲取失敗: {fetch_res.error}"
            if output:
                _write_report(output, report)
            return report

        report["manifest"] = {
            "name": "masterdata2_assetmanifest",
        }
        report["bundle"] = {
            "bundle_name": "a/masterdata_master.unity3d",
            "bundle_md5": fetch_res.bundle_md5,
            "pool_hash": fetch_res.pool_hash,
        }
        raw_size = raw_db_path.stat().st_size if raw_db_path.exists() else 0
        report["raw_db"] = {
            "sha256": fetch_res.db_sha256 or "unknown",
            "size": raw_size
        }

        # 3. 確保 staging 目錄存在，並生成正規化資料庫
        staging_path.parent.mkdir(parents=True, exist_ok=True)
        if staging_path.exists():
            staging_path.unlink()

        norm_res = generate_normalized_db(
            raw_db_path=raw_db_path,
            truth_version=truth_version,
            output_path=staging_path,
        )
        if not norm_res.success:
            report["status"] = "error"
            report["error"] = f"正規化資料庫生成失敗: {norm_res.error}"
            if output:
                _write_report(output, report)
            return report

        report["mapping"] = {
            "contract_file": f"pipeline/manifests/sonet_db_schema_map_{client_family}.json",
            "schema_version": client_family,
        }

        # 4. 替換前全套門禁檢驗 (Pre-Promotion Multi-Query Gate)
        try:
            _validate_normalized_db_pre_promotion(staging_path, truth_version)
        except Exception as e:
            report["status"] = "error"
            report["error"] = f"替換前門禁驗證失敗: {e}"
            if output:
                _write_report(output, report)
            return report

        # 5. 原子替換正式資料庫 (同檔案系統原子 replace)
        staging_path.replace(target_path)

        norm_size = target_path.stat().st_size
        with open(target_path, "rb") as f:
            norm_sha256 = hashlib.sha256(f.read()).hexdigest()

        report["normalized_db"] = {
            "sha256": norm_sha256,
            "size": norm_size,
            "table_count": len(norm_res.table_stats),
            "mapped_column_count": 99,
            "table_stats": norm_res.table_stats,
        }
        report["status"] = "ok"

    except Exception as e:
        report["status"] = "error"
        report["error"] = f"執行 update_db 時發生未預期異常: {e}"
    finally:
        # 清理暫存環境與殘留 staging 檔案
        if staging_path.exists():
            try:
                staging_path.unlink()
            except Exception:
                pass
        temp_dir.cleanup()

    if output:
        _write_report(output, report)

    return report


def _write_report(path_str: str, data: Dict[str, Any]):
    """將報告寫入磁碟 JSON 檔案。"""
    try:
        p = Path(path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 寫入報告失敗 ({path_str}): {e}", file=sys.stderr)


def get_truth_version():
    """Remote-only convenience API for freshness decisions; None means unconfirmed."""
    probe = probe_truth_version()
    return probe.version if probe.confirmed_remote else None


def get_story_ids_for_unit(unit_id: int) -> list[int]:
    """
    取得指定角色的標準劇情話數 ID 列表 (使用 legacy canonical 規則，包含 7/8 位相容與 fallback)。
    """
    return _get_story_ids_from_db(unit_id)


def run_fetch_cli():
    """CLI 入口"""
    pcrd_fetch_main()


if __name__ == "__main__":
    run_fetch_cli()
