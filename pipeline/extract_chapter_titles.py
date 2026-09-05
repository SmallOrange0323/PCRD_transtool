#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Official TW Chapter Title Extractor (Schema 2.0.0 Architecture)
官方台版主線劇情章節標題獨立標準提取器

職責：
1. 動態探索 So-net CDN 最新 TruthVersion 與 masterdata2_assetmanifest，動態定位 a/masterdata_master.unity3d 之 Pool Hash。
2. 遵循 VERSION-PINNED 實體資料庫混淆表結構安全契約；未經驗證之新版號一律 Fail-Closed 拒絕猜測。
3. 採用官方結構欄位 story_group_type == 2 與 ID family 雙重過濾主線章節，杜絕粗暴區間帶入無關資料。
4. 通用提取邏輯支援未來合法章節擴展（如 2217 等），基準測試與通用提取徹底解耦。
5. 嚴格採用 prefix, sep, title = raw_title.partition("_") 保留原生字元與後綴，禁止 Unicode 正規化。
6. 提取輸出完整記錄 ACTUAL 執行階段元數據 (truth_version, pool_hash, sha256, schema columns)。
"""

import os
import sys
import json
import sqlite3
import hashlib
import argparse
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT / "pipeline" / "manifests" / "official_chapter_title_source.json"

DEFAULT_SONET_CDN = "https://img-pc.so-net.tw/dl"
DEFAULT_SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}
WEB_HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

SQLITE_HEADER = b"SQLite format 3\x00"


def load_source_contract(contract_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """讀取官方母檔來源契約規格"""
    target = Path(contract_path) if contract_path else CONTRACT_PATH
    if not target.exists():
        raise FileNotFoundError(f"來源契約規格檔案不存在: {target}")
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_truth_version(timeout: int = 15) -> str:
    """
    透過台版上游或本地備援探測當前 TruthVersion。
    優先使用 pipeline.fetch (若可用)，其次透過 wthee API 探測。
    """
    try:
        from pipeline.fetch import get_truth_version
        tv = get_truth_version()
        if tv:
            return str(tv)
    except Exception:
        pass

    try:
        payload = json.dumps({"regionCode": "tw"}).encode("utf-8")
        req = urllib.request.Request(
            "https://wthee.xyz/pcr/api/v1/db/info/v2",
            data=payload,
            headers={"Content-Type": "application/json", **WEB_HEADER},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
        version = data.get("data", {}).get("truthVersion")
        if version:
            return str(version)
    except Exception as e:
        raise RuntimeError(f"無法探測當前台版 TruthVersion: {e}")

    raise RuntimeError("無法獲取有效之 TruthVersion")


def discover_bundle_from_cdn_manifest(
    truth_version: str,
    manifest_name: str = "masterdata2_assetmanifest",
    target_bundle: str = "a/masterdata_master.unity3d",
    cdn_base: str = DEFAULT_SONET_CDN,
    platforms: Tuple[str, ...] = ("Android", "Windows"),
    timeout: int = 20
) -> Dict[str, Any]:
    """
    動態下載指定 TruthVersion 之 assetmanifest，並解析目標 bundle 之當前 pool hash 與大小。
    依序嘗試 platforms 平台路徑 (預設優先 Android，備援 Windows)。
    """
    last_err = None
    content = None
    used_platform = None

    for platform in platforms:
        manifest_url = f"{cdn_base}/Resources/{truth_version}/Jpn/AssetBundles/{platform}/manifest/{manifest_name}"
        req = urllib.request.Request(manifest_url, headers=DEFAULT_SONET_HEADER)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                content = res.read().decode("utf-8", errors="ignore")
                used_platform = platform
                break
        except Exception as e:
            last_err = e
            continue

    if content is None:
        raise RuntimeError(f"下載 manifest 失敗 (TruthVersion {truth_version}, platforms {platforms}): {last_err}")

    # 逐行解析 manifest (格式: bundle_path,hash1,pool_hash,stage,compressed_size,...)
    for line in content.splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 3 and parts[0] == target_bundle:
            pool_hash = parts[2]
            comp_size = int(parts[4]) if len(parts) >= 5 and parts[4].isdigit() else (
                int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
            )
            return {
                "truth_version": truth_version,
                "platform": used_platform,
                "manifest_name": manifest_name,
                "bundle_path": target_bundle,
                "bundle_pool_hash": pool_hash,
                "bundle_compressed_size": comp_size
            }

    raise KeyError(f"在 {manifest_name} (TruthVersion {truth_version}, {used_platform}) 中未找到目標 Bundle: {target_bundle}")


def download_bundle_by_pool_hash(
    pool_hash: str,
    cdn_base: str = DEFAULT_SONET_CDN,
    timeout: int = 30
) -> bytes:
    """依據 pool_hash 從 So-net CDN pool 下載 AssetBundle 二進位內容"""
    if len(pool_hash) < 2:
        raise ValueError(f"無效之 pool_hash: {pool_hash}")
    url = f"{cdn_base}/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}"
    req = urllib.request.Request(url, headers=DEFAULT_SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read()
    except Exception as e:
        raise RuntimeError(f"從 CDN pool 下載 Bundle 失敗 ({url}): {e}")


def extract_master_sqlite_from_bundle(bundle_source: Union[str, Path, bytes]) -> bytes:
    """
    從 Unity3D AssetBundle (a/masterdata_master.unity3d) 提取原生 SQLite 資料庫二進位資料。
    跳過 TextAsset 前 16 位元組偏移量，並驗證 SQLite 3 標頭。
    """
    try:
        import UnityPy
        UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
    except ImportError as e:
        raise ImportError(f"提取 AssetBundle 需要 UnityPy 套件: {e}")

    if isinstance(bundle_source, Path):
        bundle_source = str(bundle_source)
    env = UnityPy.load(bundle_source)
    sqlite_bytes = None

    for obj in env.objects:
        if obj.type.name == "TextAsset":
            try:
                raw_bytes = obj.get_raw_data()
                idx = raw_bytes.find(SQLITE_HEADER)
                if idx != -1:
                    sqlite_bytes = raw_bytes[idx:]
                    break
            except Exception:
                continue

    if sqlite_bytes is None:
        raise ValueError("AssetBundle 中未找到包含 SQLite 3 標頭之 TextAsset")

    if not sqlite_bytes.startswith(SQLITE_HEADER):
        raise ValueError(
            f"解出的資料非標準 SQLite 3 格式 (標頭: {sqlite_bytes[:16]!r}, 預期: {SQLITE_HEADER!r})"
        )

    return sqlite_bytes


def _calculate_part_and_chapter(story_group_id: int) -> Tuple[int, int]:
    """
    根據官方主線 story_group_id 區間計算部數與章數。
    通用設計：支援第 1 部、第 2 部、第 3 部，以及未來可能的第 4 部等主線章節。
    """
    if story_group_id == 2000:
        return 1, 0  # 序章
    elif 2001 <= story_group_id <= 2099:
        return 1, story_group_id - 2000
    elif 2101 <= story_group_id <= 2199:
        return 2, story_group_id - 2100
    elif 2201 <= story_group_id <= 2299:
        return 3, story_group_id - 2200
    elif 2301 <= story_group_id <= 2399:
        return 4, story_group_id - 2300
    else:
        raise ValueError(f"story_group_id {story_group_id} 不在已知主線 ID family 範圍 (2000-2099, 2101-2199, 2201-2299, 2301-2399)")


def resolve_physical_schema_for_version(
    truth_version: Optional[str],
    contract: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, str]]:
    """
    VERSION-PINNED 實體資料表結構解析。
    若傳入之 TruthVersion 尚未登錄於契約之 physical_schema_by_truth_version，
    嚴格 Fail-Closed 拋出例外，禁止隨機猜測或默認重用舊版結構。
    """
    if contract is None:
        contract = load_source_contract()

    schema_map = contract.get("physical_schema_by_truth_version", {})
    if not schema_map:
        raise ValueError("契約中未定義 physical_schema_by_truth_version")

    # 若未指定 version，嘗試使用 last_verified 的 version
    target_ver = truth_version or contract.get("last_verified", {}).get("truth_version")
    if not target_ver or target_ver not in schema_map:
        raise ValueError(f"Unsupported masterdata schema for TruthVersion {target_ver}")

    return target_ver, schema_map[target_ver]


def extract_official_chapter_titles_from_db(
    db_source: Union[str, Path, bytes, sqlite3.Connection],
    contract: Optional[Dict[str, Any]] = None,
    truth_version: Optional[str] = None,
    run_source_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    從官方母檔 SQLite 資料庫提取決定性的主線章節標題。
    包含 ACTUAL run metadata 紀錄與結構化主線章節過濾。
    回傳字典結構：
      {
        "source_metadata": { ... },
        "chapters": [ ... ]
      }
    """
    if contract is None:
        contract = load_source_contract()

    # 解析 VERSION-PINNED 實體 schema
    resolved_ver, physical_schema = resolve_physical_schema_for_version(truth_version, contract)
    table_name = physical_schema.get("physical_table")
    col_group_id = physical_schema.get("story_group_id_column")
    col_story_type = physical_schema.get("story_group_type_column")
    col_title = physical_schema.get("title_column")

    if not (table_name and col_group_id and col_story_type and col_title):
        raise ValueError(f"TruthVersion {resolved_ver} 缺少完整的實體欄位映射 (table, id, type, title)")

    conn: sqlite3.Connection
    close_conn = False
    sqlite_bytes_for_hash: Optional[bytes] = None

    if isinstance(db_source, sqlite3.Connection):
        conn = db_source
    elif isinstance(db_source, bytes):
        if not db_source.startswith(SQLITE_HEADER):
            raise ValueError(f"提供的二進位資料非標準 SQLite 3 格式 (標頭: {db_source[:16]!r})")
        sqlite_bytes_for_hash = db_source
        conn = sqlite3.connect(":memory:")
        conn.deserialize(db_source)
        close_conn = True
    else:
        db_path = Path(db_source)
        if not db_path.exists() or not db_path.is_file():
            raise FileNotFoundError(f"SQLite 資料庫檔案不存在: {db_path}")
        with open(db_path, "rb") as f:
            header = f.read(16)
            if header != SQLITE_HEADER:
                raise ValueError(f"檔案非標準 SQLite 3 格式: {db_path} (標頭: {header!r})")
            f.seek(0)
            sqlite_bytes_for_hash = f.read()
        conn = sqlite3.connect(str(db_path))
        close_conn = True

    try:
        cur = conn.cursor()

        # 驗證實體資料表是否存在
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            raise KeyError(f"資料庫中未找到混淆實體表: {table_name}")

        # 驗證實體欄位是否存在
        cur.execute(f"PRAGMA table_info('{table_name}')")
        existing_cols = {row[1] for row in cur.fetchall()}
        for col_alias, col_phys in [
            ("story_group_id", col_group_id),
            ("story_group_type", col_story_type),
            ("title", col_title)
        ]:
            if col_phys not in existing_cols:
                raise KeyError(f"表 {table_name} 中缺少欄位 {col_alias} ({col_phys})")

        # 查詢主線章節記錄：
        # 嚴格使用官方結構欄位 story_group_type == 2，搭配主線 ID family 範圍 (2000 <= id < 3000)
        query = f"""
            SELECT "{col_group_id}", "{col_story_type}", "{col_title}"
            FROM "{table_name}"
            WHERE "{col_story_type}" = 2
              AND "{col_group_id}" >= 2000
              AND "{col_group_id}" < 3000
            ORDER BY "{col_group_id}" ASC
        """
        cur.execute(query)
        rows = cur.fetchall()

        if not rows:
            raise ValueError(f"表 {table_name} 中未檢索到任何符合 story_group_type == 2 的主線章節記錄")

        chapters = []
        seen_ids = set()

        for group_id, story_type, raw_title in rows:
            if not isinstance(group_id, int):
                raise ValueError(f"story_group_id 非整數類型: {group_id!r}")
            if group_id in seen_ids:
                raise ValueError(f"主線章節 ID 重複出現: {group_id}")
            seen_ids.add(group_id)

            if story_type != 2:
                raise ValueError(f"章節 {group_id} 的 story_group_type 非 2 (實際: {story_type})")

            if not isinstance(raw_title, str):
                raise ValueError(f"章節 {group_id} 之 raw_title 非字串類型: {raw_title!r}")

            # 嚴格分割規格: prefix, sep, title = raw_title.partition("_")
            prefix, sep, official_title = raw_title.partition("_")
            if sep != "_":
                raise ValueError(f"章節 {group_id} 之 raw_title 缺少底線分隔符 '_': {raw_title!r}")

            if not official_title:
                raise ValueError(f"章節 {group_id} 在分隔符後之官方標題為空字串: {raw_title!r}")

            part, chapter_num = _calculate_part_and_chapter(group_id)

            chapters.append({
                "chapter_id": group_id,
                "story_group_id": group_id,
                "part": part,
                "chapter_num": chapter_num,
                "official_title": official_title,
                "raw_title": raw_title,
                "provenance": "official_tw_masterdata"
            })

        # 計算實際產出的 metadata
        sqlite_sha256 = (
            hashlib.sha256(sqlite_bytes_for_hash).hexdigest()
            if sqlite_bytes_for_hash is not None else None
        )

        run_info = run_source_info or {}
        source_metadata = {
            "truth_version": resolved_ver,
            "manifest_name": run_info.get("manifest_name", "masterdata2_assetmanifest"),
            "bundle_path": run_info.get("bundle_path", "a/masterdata_master.unity3d"),
            "bundle_pool_hash": run_info.get("bundle_pool_hash"),
            "sqlite_sha256": sqlite_sha256,
            "physical_table": table_name,
            "story_group_id_column": col_group_id,
            "story_group_type_column": col_story_type,
            "title_column": col_title,
            "logical_table_resolution": "VERSION-PINNED",
            "selection_filter": "story_group_type == 2 AND (2000 <= story_group_id < 3000)",
            "extracted_chapter_count": len(chapters)
        }

        return {
            "source_metadata": source_metadata,
            "chapters": chapters
        }

    finally:
        if close_conn:
            conn.close()


def generate_review_table(
    extracted_chapters: List[Dict[str, Any]],
    current_chapters_path: Optional[Union[str, Path]] = None
) -> List[Dict[str, Any]]:
    """
    比對官方提取結果與現有 chapters.json，產出安全審查報表。
    僅回傳審查數據結構，絕對不變更 chapters.json。
    """
    target = Path(current_chapters_path) if current_chapters_path else (PROJECT_ROOT / "dashboard" / "data" / "chapters.json")
    current_data = {}
    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            current_data = json.load(f)

    # 展開目前 chapters.json 中的 game_world 章節
    current_chapters = {}
    for part_key in ["1", "2", "3"]:
        gw = current_data.get(part_key, {}).get("game_world", {})
        for cid_str, info in gw.items():
            try:
                cid = int(cid_str)
                current_chapters[cid] = info
            except ValueError:
                continue

    review_rows = []
    for item in extracted_chapters:
        cid = item["chapter_id"]
        cur_info = current_chapters.get(cid, {})
        cur_title = cur_info.get("title")
        cur_prov = cur_info.get("title_provenance")
        cur_legacy = cur_info.get("legacy_title")

        official_title = item["official_title"]
        would_change = (cur_title != official_title)

        row = {
            "chapter_id": cid,
            "part": item["part"],
            "chapter_num": item["chapter_num"],
            "current_title": cur_title,
            "current_provenance": cur_prov,
            "current_legacy_title": cur_legacy,
            "official_title": official_title,
            "official_raw_title": item["raw_title"],
            "would_change": would_change
        }
        review_rows.append(row)

    return review_rows


def main():
    parser = argparse.ArgumentParser(
        description="PCRD 官方台版主線章節標題提取器 (Schema 2.0.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--db-path", type=str, help="已解壓之官方 master SQLite 資料庫路徑")
    src_group.add_argument("--bundle-path", type=str, help="官方 masterdata_master.unity3d AssetBundle 檔案路徑")
    src_group.add_argument("--from-cdn", action="store_true", help="自 So-net CDN 動態探索最新版號與 Bundle 下載提取")

    parser.add_argument("--truth-version", type=str, help="指定 TruthVersion (預設自動探測最新版號)")
    parser.add_argument("--output", type=str, help="輸出章節標題 JSON 檔案路徑")
    parser.add_argument("--review-output", type=str, help="輸出與 chapters.json 之比對審查報表路徑 (JSON)")
    parser.add_argument("--contract", type=str, help="自訂來源契約 JSON 路徑")

    args = parser.parse_args()

    contract = load_source_contract(args.contract)

    target_tv = args.truth_version
    run_source_info = {}

    if args.db_path:
        db_path = Path(args.db_path)
        print(f"[INFO] 讀取本機 SQLite 資料庫: {db_path}")
        extraction_result = extract_official_chapter_titles_from_db(
            db_path, contract=contract, truth_version=target_tv
        )
    elif args.bundle_path:
        bundle_path = Path(args.bundle_path)
        print(f"[INFO] 解析本機 AssetBundle: {bundle_path}")
        sqlite_bytes = extract_master_sqlite_from_bundle(bundle_path)
        extraction_result = extract_official_chapter_titles_from_db(
            sqlite_bytes, contract=contract, truth_version=target_tv
        )
    elif args.from_cdn:
        if not target_tv:
            print("[INFO] 探測當前台版最新 TruthVersion...")
            target_tv = get_current_truth_version()
        print(f"[INFO] 當前 TruthVersion: {target_tv}")

        print(f"[INFO] 下載並解析 masterdata2_assetmanifest...")
        bundle_info = discover_bundle_from_cdn_manifest(truth_version=target_tv)
        pool_hash = bundle_info["bundle_pool_hash"]
        print(f"[INFO] 動態解析到 AssetBundle Pool Hash: {pool_hash} (壓縮大小: {bundle_info['bundle_compressed_size']:,} bytes)")

        print(f"[INFO] 從 CDN pool 下載 Bundle ({pool_hash})...")
        bundle_bytes = download_bundle_by_pool_hash(pool_hash)
        print(f"[INFO] 下載完成 ({len(bundle_bytes):,} bytes)，正在提取 SQLite...")
        sqlite_bytes = extract_master_sqlite_from_bundle(bundle_bytes)

        run_source_info = {
            "manifest_name": bundle_info["manifest_name"],
            "bundle_path": bundle_info["bundle_path"],
            "bundle_pool_hash": pool_hash
        }
        extraction_result = extract_official_chapter_titles_from_db(
            sqlite_bytes, contract=contract, truth_version=target_tv, run_source_info=run_source_info
        )
    else:
        parser.error("必須指定輸入來源")

    chapters = extraction_result["chapters"]
    meta = extraction_result["source_metadata"]

    print(f"✅ 成功提取 {len(chapters)} 個官方主線章節標題。")
    print(f"   [Metadata] TruthVersion: {meta['truth_version']}, Table: {meta['physical_table'][:16]}..., SQLite SHA-256: {meta['sqlite_sha256'][:16] if meta['sqlite_sha256'] else 'N/A'}...")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(extraction_result, f, ensure_ascii=False, indent=2)
        print(f"📝 完整結果 (含 metadata) 已寫入: {out_path}")

    if args.review_output:
        review_rows = generate_review_table(chapters)
        rev_path = Path(args.review_output)
        rev_path.parent.mkdir(parents=True, exist_ok=True)
        with open(rev_path, "w", encoding="utf-8") as f:
            json.dump(review_rows, f, ensure_ascii=False, indent=2)
        print(f"📊 比對審查報表已寫入: {rev_path}")


if __name__ == "__main__":
    main()
