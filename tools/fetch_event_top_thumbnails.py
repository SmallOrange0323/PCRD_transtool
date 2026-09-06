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

SONET_CDN = "https://img-pc.so-net.tw/dl"
SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

BASE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = BASE_DIR / "dashboard"
OUTPUT_DIR = DASHBOARD_DIR / "icon" / "event_top"
MANIFEST_PATH = BASE_DIR / "icon2_assetmanifest"


def get_latest_truth_version(specified_ver: Optional[str] = None) -> str:
    """嘗試從 So-net 探測最新 TruthVersion，若有指定則優先使用"""
    if specified_ver and str(specified_ver).strip():
        return str(specified_ver).strip()

    candidates = ["00600025", "00600024", "00600023", "00600020", "00500015", "00500012", "00500010"]
    for ver in candidates:
        url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
        req = urllib.request.Request(url, headers=SONET_HEADER)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return ver
        except Exception:
            continue
    return "00600025"


def ensure_manifest(manifest_path: Path = MANIFEST_PATH, force_update: bool = False, truth_version: Optional[str] = None) -> Path:
    """確保本地存在最新 icon2_assetmanifest，若不存在或要求強制更新則從 CDN 下載"""
    if not force_update and manifest_path.exists() and manifest_path.stat().st_size > 0:
        return manifest_path
    
    ver = get_latest_truth_version(truth_version)
    url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
    print(f"[FetchEventTop] 正在從 CDN 下載 icon2_assetmanifest (版本: {ver})...")
    req = urllib.request.Request(url, headers=SONET_HEADER)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(manifest_path, "wb") as f:
        f.write(data)
    print(f"[FetchEventTop] manifest 下載完成: {len(data)} bytes")
    return manifest_path


def load_manifest_event_top_thumbs(manifest_path: Path = MANIFEST_PATH, force_update: bool = False, truth_version: Optional[str] = None) -> Dict[str, str]:
    """
    從 manifest 中解析出所有 a/icon_thumb_event_story_top_{event_id}.unity3d 的 pool hash。
    回傳字典: {event_id: bundle_hash}
    """
    ensure_manifest(manifest_path, force_update=force_update, truth_version=truth_version)
    thumbs = {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 3 and "icon_thumb_event_story_top_" in parts[0]:
                bundle_name = parts[0]
                bundle_hash = parts[2]
                stem = bundle_name.replace("a/icon_thumb_event_story_top_", "").replace(".unity3d", "")
                thumbs[stem] = bundle_hash
    return thumbs


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


def fetch_all_event_top_thumbnails(
    force: bool = False,
    max_workers: int = 8,
    truth_version: Optional[str] = None,
    update_manifest: bool = False
) -> Dict[str, Any]:
    """批次抓取並轉檔所有活動頂層專屬縮圖"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_thumbs = load_manifest_event_top_thumbs(force_update=update_manifest, truth_version=truth_version)

    print(f"[FetchEventTop] CDN Manifest 中包含的活動頂層縮圖數: {len(manifest_thumbs)} 筆")

    tasks = [(eid, bhash) for eid, bhash in manifest_thumbs.items()]

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
    print(f"[FetchEventTop] 活動頂層專屬縮圖抓取完成！總耗時: {elapsed:.2f} 秒")
    print(f"  - 新下載轉檔: {success_count} 張")
    print(f"  - 本地快取保留: {cached_count} 張")
    print(f"  - 抓取失敗: {len(failed_list)} 張")
    print("=" * 60)

    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_targets": len(tasks),
        "downloaded": success_count,
        "cached": cached_count,
        "failed": failed_list,
        "output_dir": str(OUTPUT_DIR)
    }

    report_file = BASE_DIR / "tools" / "event_top_thumb_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"[FetchEventTop] 執行報告已儲存至: {report_file}")

    return report_data


def main():
    parser = argparse.ArgumentParser(description="下載並轉檔 So-net 官方活動頂層專屬縮圖 (WebP 256x128)")
    parser.add_argument("--force", action="store_true", help="強制重新下載現有已快取的縮圖")
    parser.add_argument("--workers", type=int, default=8, help="下載線程數 (預設: 8)")
    parser.add_argument("--truth-version", type=str, default=None, help="指定 So-net TruthVersion")
    parser.add_argument("--update-manifest", action="store_true", help="強制從 CDN 重新下載 icon2_assetmanifest")

    args = parser.parse_args()
    fetch_all_event_top_thumbnails(
        force=args.force,
        max_workers=args.workers,
        truth_version=args.truth_version,
        update_manifest=args.update_manifest
    )


if __name__ == "__main__":
    main()
