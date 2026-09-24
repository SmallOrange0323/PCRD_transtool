#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Canonical So-net Master DB Acquisition Primitive (Phase F2A)

責任範圍：
1. 依顯式傳入之 TruthVersion (8 碼格式校驗) 下載 So-net 官方 masterdata2_assetmanifest
2. 解析並比對 masterdata_master.unity3d 之 bundle MD5、pool hash、bundle size
3. 下載官方 Pool AssetBundle，進行二進位 MD5 完整性檢驗
4. 透過 UnityPy 解密提取原始混淆 SQLite (v1_* 實體表)
5. 執行原始 SQLite 核心結構與完整性門禁：
   - SQLite Magic Header (16 bytes)
   - PRAGMA integrity_check == 'ok'
   - 實體表總數基礎健全性檢查 (sanity checks, 拒絕異常空庫)
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
    對原始混淆 SQLite 檔案進行核心完整性與結構校驗 (Magic Header, PRAGMA integrity_check, 實體表總數)。
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


@dataclass
class CdnCandidateProbeResult:
    version: str
    exists: bool
    http_code: Optional[int] = None
    manifest_url: Optional[str] = None
    manifest_length: Optional[int] = None
    manifest_sha256: Optional[str] = None
    bundle_name: Optional[str] = None
    bundle_md5: Optional[str] = None
    pool_hash: Optional[str] = None
    bundle_size: Optional[int] = None
    # 保持向後相容欄位
    master_bundle_md5: Optional[str] = None
    master_pool_hash: Optional[str] = None
    manifest_size: int = 0
    error: Optional[str] = None


@dataclass
class CdnDiscoveryResult:
    highest_observed_cdn_version: Optional[str]
    candidates: Dict[str, CdnCandidateProbeResult]
    scan_bounds: Dict[str, Any]
    error: Optional[str] = None


def probe_single_cdn_candidate(version: str, timeout: int = 6) -> CdnCandidateProbeResult:
    """
    輕量探測單一 TruthVersion 之 masterdata2_assetmanifest。
    僅下載幾十 bytes 之 Manifest，不下載大型 Bundle。
    """
    manifest_url = f"{SONET_CDN}/Resources/{version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    result = CdnCandidateProbeResult(
        version=version,
        exists=False,
        manifest_url=manifest_url
    )

    try:
        req = urllib.request.Request(manifest_url, headers=WEB_HEADER, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as res:
            result.http_code = res.status
            content = res.read()
            result.manifest_size = len(content)
            result.manifest_length = len(content)
            result.manifest_sha256 = hashlib.sha256(content).hexdigest()

            content_text = content.decode('utf-8', errors='ignore')
            for line in content_text.splitlines():
                if "masterdata_master.unity3d" in line:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        result.bundle_name = parts[0].strip()
                        result.bundle_md5 = parts[1].strip()
                        result.master_bundle_md5 = parts[1].strip()
                        result.pool_hash = parts[2].strip()
                        result.master_pool_hash = parts[2].strip()
                        if len(parts) > 4 and parts[4].strip().isdigit():
                            result.bundle_size = int(parts[4].strip())
                        break

            if result.manifest_size > 0 and result.pool_hash:
                result.exists = True
            else:
                result.error = "manifest 格式異常或未包含 masterdata_master"

    except urllib.error.HTTPError as e:
        result.http_code = e.code
        if e.code != 404:
            result.error = f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        result.error = str(e)

    return result


def discover_cdn_candidate_snapshots(
    base_version: Optional[str] = None,
    lookahead_limit: int = 5,
    family_seed_limit: int = 2,
    known_versions: Optional[List[str]] = None,
    timeout: int = 6
) -> CdnDiscoveryResult:
    """
    有界探索 So-net 官方 CDN 候選快照。
    原則：
    - 不假設版本嚴格連續，不因單一 404 停止。
    - 移除 consecutive-miss 提前終止：在宣告的 lookahead_limit 範圍內進行窮舉探測 (Exhaustive within bound)。
    - 支援跨家族探索 (Client-Family Transition Probe)：主動探測下一版本家族之種子視窗 (如 0061 -> 00620001, 00620002)。
      【語意邊界約束】
      1. 跨家族種子探測僅為啟發式有界探索 (bounded heuristic discovery only)。
      2. 探測命中僅證明該具體快照存在；未命中 (misses) 絕不構成「下一家族不存在」之證明。
      3. 探測範圍 scan_bounds 必須完整回報供審計。
      4. 未知家族即便被發現，後續正規化仍嚴格維持 NEEDS_NEW_SCHEMA_MAPPING 拒絕策略，嚴禁複用 0061 mapping。
    - 回報 highest_observed_cdn_version 與完整可審計之 scan_bounds。
    """
    candidates: Dict[str, CdnCandidateProbeResult] = {}
    effective_base = base_version if (base_version and re.fullmatch(r"\d{8}", base_version)) else "00610008"

    prefix = effective_base[:4]
    try:
        base_seq = int(effective_base[4:])
    except ValueError:
        base_seq = 1

    tested_ranges: Dict[str, List[int]] = {}

    # 1. 探測基準版本
    base_res = probe_single_cdn_candidate(effective_base, timeout=timeout)
    candidates[effective_base] = base_res
    highest_version = effective_base if base_res.exists else None
    tested_ranges[prefix] = [base_seq, base_seq]

    # 2. 探測額外提供的已知候選版本 (例如第三方參考版號或特定指定版號)
    if known_versions:
        for kv in known_versions:
            if kv and kv not in candidates and re.fullmatch(r"\d{8}", kv):
                kr = probe_single_cdn_candidate(kv, timeout=timeout)
                candidates[kv] = kr
                if kr.exists:
                    if highest_version is None or int(kv) > int(highest_version):
                        highest_version = kv

    # 3. 當前家族向前有界窮舉探索 (Forward Bounded Exhaustive Probe)
    curr_seq = base_seq + 1
    max_seq = base_seq + lookahead_limit

    while curr_seq <= max_seq:
        ver_str = f"{prefix}{curr_seq:04d}"
        if ver_str not in candidates:
            pr = probe_single_cdn_candidate(ver_str, timeout=timeout)
            candidates[ver_str] = pr
            if pr.exists:
                if highest_version is None or int(ver_str) > int(highest_version):
                    highest_version = ver_str
        curr_seq += 1

    tested_ranges[prefix][1] = max_seq

    # 4. 跨家族前綴探索 (Client-Family Transition Probe)
    # 例如當前為 0061，探測下一個家族 0062 之初始種子 (00620001, 00620002...)
    try:
        current_family_int = int(prefix)
        next_family_prefix = f"{current_family_int + 1:04d}"
        tested_ranges[next_family_prefix] = [1, family_seed_limit]

        for seed_seq in range(1, family_seed_limit + 1):
            seed_ver = f"{next_family_prefix}{seed_seq:04d}"
            if seed_ver not in candidates:
                sr = probe_single_cdn_candidate(seed_ver, timeout=timeout)
                candidates[seed_ver] = sr
                if sr.exists:
                    if highest_version is None or int(seed_ver) > int(highest_version):
                        highest_version = seed_ver
    except Exception:
        pass

    scan_bounds = {
        "base_version": effective_base,
        "lookahead_limit": lookahead_limit,
        "family_seed_limit": family_seed_limit,
        "tested_ranges": tested_ranges,
        "total_probed": len(candidates),
        "total_existing": sum(1 for c in candidates.values() if c.exists),
    }

    return CdnDiscoveryResult(
        highest_observed_cdn_version=highest_version,
        candidates=candidates,
        scan_bounds=scan_bounds,
    )
