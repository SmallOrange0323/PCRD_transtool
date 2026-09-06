# -*- coding: utf-8 -*-
"""
fetch_event_top_thumbnails.py — 官方活動頂層專屬縮圖下載與轉檔工具
從 So-net CDN 的 icon2_assetmanifest 解析官方活動頂層專屬縮圖 (256x128)，
使用 UnityPy 提取 Texture2D 並轉換為高品質 WebP 儲存至 dashboard/icon/event_top/。
"""

import argparse
import concurrent.futures
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.extract_chapter_titles import get_current_truth_version

SONET_CDN = "https://img-pc.so-net.tw/dl"
SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

BASE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = BASE_DIR / "dashboard"
OUTPUT_DIR = DASHBOARD_DIR / "icon" / "event_top"
MANIFEST_CONTRACT_PATH = BASE_DIR / "pipeline" / "manifests" / "official_event_top_manifest.json"
REPORT_PATH = BASE_DIR / "tools" / "event_top_thumb_report.json"
MANIFEST_TEMP_PATH = BASE_DIR / "icon2_assetmanifest"


def resolve_truth_version(specified_ver: Optional[str] = None) -> str:
    """
    決定當前使用的 TruthVersion。
    若使用者未手動指定，則調用官方線上探測 API (Fail-Closed)。
    嚴禁使用歷史快取或硬編碼預設值。
    """
    if specified_ver and str(specified_ver).strip():
        return str(specified_ver).strip()

    return get_current_truth_version()


def ensure_manifest(manifest_path: Path = MANIFEST_TEMP_PATH, force_update: bool = False, truth_version: Optional[str] = None) -> Path:
    """確保本地存在最新 icon2_assetmanifest，若不存在或要求強制更新則從 CDN 下載 (Fail-Closed)"""
    if not force_update and manifest_path.exists() and manifest_path.stat().st_size > 0:
        return manifest_path

    ver = resolve_truth_version(truth_version)
    url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
    print(f"[FetchEventTop] 正在從 CDN 下載 icon2_assetmanifest (版本: {ver})...")
    req = urllib.request.Request(url, headers=SONET_HEADER)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(manifest_path, "wb") as f:
        f.write(data)
    print(f"[FetchEventTop] manifest 下載完成: {len(data)} bytes")
    return manifest_path


def load_manifest_event_top_thumbs(
    manifest_path: Path = MANIFEST_TEMP_PATH,
    force_update: bool = False,
    truth_version: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    載入活動專屬縮圖目標清單。
    若存在已追蹤的 official_event_top_manifest.json 且未要求 force_update，優先以此為決定性來源；
    否則自 CDN 下載/讀取 icon2_assetmanifest 並即時更新 official_event_top_manifest.json。
    """
    if not force_update and MANIFEST_CONTRACT_PATH.exists():
        with open(MANIFEST_CONTRACT_PATH, "r", encoding="utf-8") as f:
            contract_data = json.load(f)
            targets = contract_data.get("targets", {})
            if targets:
                return targets

    ensure_manifest(manifest_path, force_update=force_update, truth_version=truth_version)
    ver = resolve_truth_version(truth_version)
    targets = {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 5 and "icon_thumb_event_story_top_" in parts[0]:
                bundle_name = parts[0]
                bundle_md5 = parts[1]
                bundle_hash = parts[2]
                bundle_size = int(parts[4]) if parts[4].isdigit() else None
                stem = bundle_name.replace("a/icon_thumb_event_story_top_", "").replace(".unity3d", "")
                targets[stem] = {
                    "bundle_name": bundle_name,
                    "bundle_md5": bundle_md5,
                    "pool_hash": bundle_hash,
                    "bundle_size": bundle_size,
                    "relative_output_path": f"dashboard/icon/event_top/{stem}.webp"
                }

    # 更新 tracked contract 檔案
    contract_data = {
        "title": "PCRD Official TW Event Story Top Thumbnail Source Manifest",
        "description": "官方台版活動頂層專屬縮圖來源與資源對照清單",
        "schema_version": "1.0.0",
        "locale": "zh-TW",
        "source_type": "official_tw_localized_asset",
        "truth_version": ver,
        "manifest_name": "icon2_assetmanifest",
        "total_targets": len(targets),
        "asset_relative_dir": "dashboard/icon/event_top",
        "targets": dict(sorted(targets.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]))
    }
    MANIFEST_CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_CONTRACT_PATH, "w", encoding="utf-8") as f:
        json.dump(contract_data, f, ensure_ascii=False, indent=2)

    return targets


def download_and_extract_event_top(event_id: str, bundle_hash: str, output_dir: Path = OUTPUT_DIR, force: bool = False) -> Tuple[str, bool, Optional[str]]:
    """
    下載單一活動頂層縮圖 AssetBundle 並使用 UnityPy 提取 Texture2D 轉成 WebP。
    :return: (event_id, success, error_message)
    """
    out_file = output_dir / f"{event_id}.webp"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return event_id, True, "cached"

    url = f"{SONET_CDN}/pool/AssetBundles/{bundle_hash[:2]}/{bundle_hash}"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            bundle_bytes = resp.read()
    except Exception as e:
        return event_id, False, f"HTTP error: {e}"

    try:
        import UnityPy
        from PIL import Image

        UnityPy.config.FALLBACK_UNITY_VERSION = "2020.3.34f1"
        env = UnityPy.load(bundle_bytes)

        found_img = None
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                t2d = obj.read()
                found_img = t2d.image
                break

        if not found_img:
            return event_id, False, "No Texture2D found in bundle"

        out_file.parent.mkdir(parents=True, exist_ok=True)
        found_img.save(out_file, format="WEBP", quality=85)
        return event_id, True, None
    except Exception as e:
        return event_id, False, f"UnityPy extract error: {e}"


def verify_local_assets(
    contract_path: Path = MANIFEST_CONTRACT_PATH,
    asset_dir: Path = OUTPUT_DIR
) -> Dict[str, Any]:
    """
    離線/無破壞驗證本地 event_top 素材是否與官方規格清單完全一致。
    :return: 包含 matched, missing, extra 清單與統計
    """
    if not contract_path.exists():
        raise FileNotFoundError(f"找不到官方規格清單: {contract_path}")

    with open(contract_path, "r", encoding="utf-8") as f:
        contract_data = json.load(f)

    expected_targets = contract_data.get("targets", {})
    expected_ids = set(expected_targets.keys())

    local_files = set()
    if asset_dir.exists():
        for p in asset_dir.glob("*.webp"):
            if p.is_file() and p.stat().st_size > 0:
                local_files.add(p.stem)

    matched = sorted(list(expected_ids.intersection(local_files)))
    missing = sorted(list(expected_ids.difference(local_files)))
    extra = sorted(list(local_files.difference(expected_ids)))

    result = {
        "status": "PASS" if len(missing) == 0 else "FAIL",
        "total_expected": len(expected_ids),
        "matched_count": len(matched),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "missing_ids": missing,
        "extra_ids": extra,
        "asset_relative_dir": "dashboard/icon/event_top"
    }

    print("\n" + "=" * 60)
    print(f"[FetchEventTop:Verify] 本地 event_top 素材驗證結果: {result['status']}")
    print(f"  - 預期總數: {result['total_expected']}")
    print(f"  - 完整匹配: {result['matched_count']}")
    print(f"  - 缺失數量: {result['missing_count']}")
    print(f"  - 額外數量: {result['extra_count']}")
    if missing:
        print(f"  - 缺失清單: {missing}")
    if extra:
        print(f"  - 額外清單: {extra}")
    print("=" * 60)

    return result


def fetch_all_event_top_thumbnails(
    force: bool = False,
    max_workers: int = 8,
    truth_version: Optional[str] = None,
    update_manifest: bool = False
) -> Dict[str, Any]:
    """批次抓取並轉檔所有活動頂層專屬縮圖 (支援 clean-clone 確定性重建)"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = load_manifest_event_top_thumbs(force_update=update_manifest, truth_version=truth_version)

    print(f"[FetchEventTop] 目標清單中包含的活動頂層縮圖數: {len(targets)} 筆")

    tasks = []
    for eid, info in targets.items():
        bhash = info["pool_hash"] if isinstance(info, dict) else info
        tasks.append((eid, bhash))

    success_count = 0
    cached_count = 0
    failed_list = []

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_and_extract_event_top, eid, bhash, OUTPUT_DIR, force): eid
            for eid, bhash in tasks
        }

        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            eid, ok, err = future.result()
            if ok:
                if err == "cached":
                    cached_count += 1
                else:
                    success_count += 1
            else:
                failed_list.append({"event_id": eid, "error": err})

            if completed % 20 == 0 or completed == total:
                print(f"  ▶ 進度: {completed}/{total} (成功: {success_count}, 快取: {cached_count}, 失敗: {len(failed_list)})")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"[FetchEventTop] 活動頂層專屬縮圖處理完成！總耗時: {elapsed:.2f} 秒")
    print(f"  - 新下載轉檔: {success_count} 張")
    print(f"  - 本地快取保留: {cached_count} 張")
    print(f"  - 處理失敗: {len(failed_list)} 張")
    print("=" * 60)

    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "truth_version": resolve_truth_version(truth_version),
        "total_targets": len(tasks),
        "downloaded": success_count,
        "cached": cached_count,
        "failed": failed_list,
        "output_dir": "dashboard/icon/event_top"
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"[FetchEventTop] 執行報告已儲存至: {REPORT_PATH}")

    return report_data


def main():
    parser = argparse.ArgumentParser(description="下載、轉檔與驗證 So-net 官方活動頂層專屬縮圖 (WebP 256x128)")
    parser.add_argument("--force", action="store_true", help="強制重新下載現有已快取的縮圖")
    parser.add_argument("--workers", type=int, default=8, help="下載線程數 (預設: 8)")
    parser.add_argument("--truth-version", type=str, default=None, help="指定 So-net TruthVersion")
    parser.add_argument("--update-manifest", action="store_true", help="強制從 CDN 重新下載 icon2_assetmanifest")
    parser.add_argument("--verify-only", action="store_true", help="僅執行本地素材一致性驗證，不發送下載請求")

    args = parser.parse_args()

    if args.verify_only:
        res = verify_local_assets()
        if res["missing_count"] > 0:
            sys.exit(1)
        return

    fetch_all_event_top_thumbnails(
        force=args.force,
        max_workers=args.workers,
        truth_version=args.truth_version,
        update_manifest=args.update_manifest
    )


if __name__ == "__main__":
    main()
