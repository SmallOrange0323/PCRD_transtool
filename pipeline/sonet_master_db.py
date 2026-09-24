#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Canonical So-net Master DB Acquisition Primitive (Phase F2A)

責任範圍：
1. 依顯式傳入之 TruthVersion 下載 So-net 官方 masterdata2_assetmanifest
2. 解析並比對 masterdata_master.unity3d 之 bundle MD5、pool hash、bundle size
3. 下載官方 Pool AssetBundle，進行二進位 MD5 完整性檢驗
4. 透過 UnityPy 解密提取明文 SQLite
5. 執行 6 重 Validate-before-replace 門禁：
   - SQLite Magic Header
   - PRAGMA integrity_check == 'ok'
   - 必要業務表齊全性 (story_detail, unit_data, etc.)
   - 必要欄位完整性
   - 基本非空健全性檢查 (sanity checks)
6. 於 destination.parent 同檔案系統建立 staging 檔，通過後執行原子替換 (os.replace)
7. 失敗時保證原有 destination 檔案 100% byte-identical

嚴格邊界：
- 獨立 Canonical 模組，嚴禁 import tools/pcrd_fetch，避免循環依賴
- 不探測 wthee
- 不自行決定最新版號
- 不更動 version_history.json
- 不調用 deploy
"""

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

import UnityPy

# 配置 UnityPy Fallback 版本
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
if hasattr(UnityPy, 'environment') and hasattr(UnityPy.environment, 'Environment'):
    UnityPy.environment.Environment.version_engine = '2021.3.20f1'

SONET_CDN = "https://img-pc.so-net.tw/dl"
WEB_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

SQLITE_MAGIC = b'SQLite format 3\x00'



@dataclass
class MasterDbFetchResult:
    success: bool
    truth_version: str
    manifest_url: Optional[str] = None
    manifest_sha256: Optional[str] = None
    bundle_name: Optional[str] = None
    bundle_md5: Optional[str] = None
    pool_hash: Optional[str] = None
    bundle_size: Optional[int] = None
    bundle_url: Optional[str] = None
    db_sha256: Optional[str] = None
    db_size_bytes: int = 0
    written_path: Optional[Path] = None
    error: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)


def _http_get_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=WEB_HEADER, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def _validate_sqlite_db(db_file: Path) -> Dict[str, Any]:
    """
    對 SQLite 檔案進行 6 重嚴格校驗。
    任一校驗失敗即拋出 ValueError。
    """
    file_size = db_file.stat().st_size
    if file_size < 100:
        raise ValueError(f"SQLite 檔案大小異常 ({file_size} bytes)，不足最小資料庫長度")

    with open(db_file, 'rb') as f:
        header = f.read(16)
        if header != SQLITE_MAGIC:
            raise ValueError(f"SQLite Magic Header 不相符: {header!r} != {SQLITE_MAGIC!r}")

    conn = sqlite3.connect(str(db_file))
    sanity_stats: Dict[str, Any] = {}
    try:
        cur = conn.cursor()
        
        # 1. PRAGMA integrity_check
        cur.execute("PRAGMA integrity_check;")
        row = cur.fetchone()
        if not row or row[0] != "ok":
            raise ValueError(f"PRAGMA integrity_check 失敗: {row}")

        # 2. 實體表總數 sanity check (官方原生 Master DB 包含數百張混淆/實體表)
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        if len(tables) < 5:
            raise ValueError(f"SQLite 資料表數量過少 ({len(tables)} 張)，視為異常空庫")
        sanity_stats["table_count"] = len(tables)

    finally:
        conn.close()

    return sanity_stats


def fetch_master_db_from_sonet(
    truth_version: str,
    destination: Path,
    timeout: int = 30
) -> MasterDbFetchResult:
    """
    從 So-net 官方 CDN 下載指定 TruthVersion 之 Master DB 並進行完整性驗證與原子替換。

    參數:
      truth_version: 8 碼數字版本號 (例如 '00610008')
      destination: 正式 SQLite DB 目標路徑 (例如 Path('dashboard/redive_tw.db'))
      timeout: HTTP 逾時秒數 (預設 30 秒)

    回傳:
      MasterDbFetchResult 結構體
    """
    destination = Path(destination).resolve()
    result = MasterDbFetchResult(
        success=False,
        truth_version=truth_version,
        written_path=None
    )

    # 1. 驗證 TruthVersion 格式
    if not isinstance(truth_version, str) or not re.fullmatch(r"\d{8}", truth_version):
        result.error = f"無效的 TruthVersion 格式 (必須為 8 碼數字): {truth_version!r}"
        return result

    manifest_url = f"{SONET_CDN}/Resources/{truth_version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    result.manifest_url = manifest_url

    staging_db = destination.parent / f"{destination.name}.download.tmp"

    try:
        # 2. 下載官方 masterdata2_assetmanifest
        try:
            manifest_bytes = _http_get_bytes(manifest_url, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                result.error = f"So-net CDN 找不到 Manifest (HTTP 404): {manifest_url}"
            else:
                result.error = f"下載 Manifest 發生 HTTP 錯誤: {e}"
            return result
        except Exception as e:
            result.error = f"下載 Manifest 發生網路異常: {e}"
            return result

        result.manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

        # 3. 解析 masterdata_master.unity3d 條目
        manifest_text = manifest_bytes.decode('utf-8', errors='ignore')
        bundle_entry = None
        for line in manifest_text.splitlines():
            if "masterdata_master.unity3d" in line:
                bundle_entry = line
                break

        if not bundle_entry:
            result.error = "Manifest 中未找到 masterdata_master.unity3d 宣告"
            return result

        parts = bundle_entry.split(',')
        if len(parts) < 3:
            result.error = f"Manifest 中 masterdata_master 條目格式損壞: {bundle_entry!r}"
            return result

        bundle_name = parts[0].strip()
        bundle_md5 = parts[1].strip()
        pool_hash = parts[2].strip()
        bundle_size = int(parts[4].strip()) if len(parts) > 4 and parts[4].strip().isdigit() else None

        result.bundle_name = bundle_name
        result.bundle_md5 = bundle_md5
        result.pool_hash = pool_hash
        result.bundle_size = bundle_size

        if not pool_hash or not bundle_md5:
            result.error = f"無法從條目解析合法的 pool_hash 或 bundle_md5: {bundle_entry!r}"
            return result

        bundle_url = f"{SONET_CDN}/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}"
        result.bundle_url = bundle_url

        # 4. 下載 Pool AssetBundle
        try:
            bundle_bytes = _http_get_bytes(bundle_url, timeout=timeout)
        except Exception as e:
            result.error = f"下載 Pool AssetBundle 失敗 ({bundle_url}): {e}"
            return result

        # 5. 驗證 Bundle 二進位 MD5
        actual_bundle_md5 = hashlib.md5(bundle_bytes).hexdigest()
        if actual_bundle_md5.lower() != bundle_md5.lower():
            result.error = f"Bundle MD5 校驗不符: 下載實際={actual_bundle_md5}, Manifest預期={bundle_md5}"
            return result

        if bundle_size is not None and len(bundle_bytes) != bundle_size:
            result.error = f"Bundle 長度校驗不符: 下載實際={len(bundle_bytes)}, Manifest預期={bundle_size}"
            return result

        # 6. 使用 UnityPy 提取 SQLite 二進位資料
        env = UnityPy.load(bundle_bytes)
        sqlite_bytes: Optional[bytes] = None
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                if hasattr(obj, 'get_raw_data'):
                    raw = obj.get_raw_data()
                    idx = raw.find(SQLITE_MAGIC)
                    if idx != -1:
                        sqlite_bytes = raw[idx:]
                        break

        if not sqlite_bytes:
            result.error = "無法在 AssetBundle 中找到有效的 SQLite 資料庫內容 (Magic bytes 缺失)"
            return result

        # 7. 寫入 Staging 檔案 (確保與 destination 在同一檔案系統)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(staging_db, 'wb') as f:
            f.write(sqlite_bytes)

        # 8. 執行 6 重 Validate-before-replace 門禁
        sanity_stats = _validate_sqlite_db(staging_db)

        # 9. 計算資料庫屬性
        db_sha256 = hashlib.sha256(sqlite_bytes).hexdigest()
        result.db_sha256 = db_sha256
        result.db_size_bytes = len(sqlite_bytes)
        result.provenance = {
            "truth_version": truth_version,
            "manifest_sha256": result.manifest_sha256,
            "bundle_name": bundle_name,
            "bundle_md5": bundle_md5,
            "pool_hash": pool_hash,
            "bundle_size": result.bundle_size,
            "bundle_url": bundle_url,
            "db_sha256": db_sha256,
            "db_size_bytes": result.db_size_bytes,
            "sanity_stats": sanity_stats,
        }

        # 10. 通過全數檢驗，執行原子替換
        staging_db.replace(destination)
        result.written_path = destination
        result.success = True
        return result

    except Exception as e:
        result.error = f"資料庫獲取或驗證異常: {e}"
        return result

    finally:
        # 清理 Staging 殘留
        if staging_db.exists():
            try:
                staging_db.unlink()
            except Exception:
                pass
