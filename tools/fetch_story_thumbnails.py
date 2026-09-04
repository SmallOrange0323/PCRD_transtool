# -*- coding: utf-8 -*-
"""
fetch_story_thumbnails.py — 官方劇情專屬縮圖下載與轉檔工具
從 So-net CDN 的 icon2_assetmanifest 解析官方劇情話數專屬縮圖 (256x128)，
使用 UnityPy 提取 Texture2D 並轉換為高品質 WebP 儲存至 dashboard/icon/story/。
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
OUTPUT_DIR = DASHBOARD_DIR / "icon" / "story"
MANIFEST_PATH = BASE_DIR / "icon2_assetmanifest"


def get_latest_truth_version() -> str:
    """嘗試從 So-net 探測最新 TruthVersion，預設 00500015"""
    candidates = ["00500015", "00500012", "00500010"]
    for ver in candidates:
        url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
        req = urllib.request.Request(url, headers=SONET_HEADER)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return ver
        except Exception:
            continue
    return "00500015"


def ensure_manifest(manifest_path: Path = MANIFEST_PATH) -> Path:
    """確保本地存在 icon2_assetmanifest，若不存在則從 CDN 下載"""
    if manifest_path.exists() and manifest_path.stat().st_size > 0:
        return manifest_path
    
    ver = get_latest_truth_version()
    url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
    print(f"[FetchThumb] 正在從 CDN 下載 icon2_assetmanifest (版本: {ver})...")
    req = urllib.request.Request(url, headers=SONET_HEADER)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(manifest_path, "wb") as f:
        f.write(data)
    print(f"[FetchThumb] manifest 下載完成: {len(data)} bytes")
    return manifest_path


def load_manifest_story_thumbs(manifest_path: Path = MANIFEST_PATH) -> Dict[str, str]:
    """
    從 manifest 中解析出所有 a/icon_thumb_story_{story_id}.unity3d 的 hash。
    回傳字典: {story_id: bundle_hash}
    """
    ensure_manifest(manifest_path)
    thumbs = {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 3 and "icon_thumb_story_" in parts[0]:
                bundle_name = parts[0]
                bundle_hash = parts[2]
                stem = bundle_name.replace("a/icon_thumb_story_", "").replace(".unity3d", "")
                thumbs[stem] = bundle_hash
    return thumbs


def collect_target_story_ids() -> List[str]:
    """收集目前 Story Map 支援的所有話數 ID (主線 + 第 3 部分支)"""
    target_ids = set()

    # 1. 主線話數
    summaries_path = DASHBOARD_DIR / "data" / "main_story_chapter_summaries.json"
    if summaries_path.exists():
        with open(summaries_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k in data.keys():
                if len(k) == 7 and k.isdigit():
                    target_ids.add(k)

    # 2. 分支話數
    branches_path = DASHBOARD_DIR / "data" / "branch_stories.json"
    if branches_path.exists():
        with open(branches_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for s in data.get("stories", []):
                target_ids.add(str(s["story_id"]))

    return sorted(list(target_ids))


def download_and_extract_thumb(story_id: str, bundle_hash: str, output_dir: Path = OUTPUT_DIR, force: bool = False) -> Tuple[str, bool, Optional[str]]:
    """
    下載單一話數縮圖 AssetBundle 並使用 UnityPy 提取 Texture2D 轉成 WebP。
    :return: (story_id, success, error_message)
    """
    out_file = output_dir / f"{story_id}.webp"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return story_id, True, "cached"

    url = f"{SONET_CDN}/pool/AssetBundles/{bundle_hash[:2]}/{bundle_hash}"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            bundle_bytes = resp.read()
    except Exception as e:
        return story_id, False, f"HTTP error: {e}"

    try:
        import UnityPy
        from PIL import Image

        UnityPy.config.FALLBACK_UNITY_VERSION = "2021.3.20f1"
        env = UnityPy.load(bundle_bytes)

        found_img = None
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                t2d = obj.read()
                found_img = t2d.image
                break

        if not found_img:
            return story_id, False, "No Texture2D found in bundle"

        out_file.parent.mkdir(parents=True, exist_ok=True)
        found_img.save(out_file, format="WEBP", quality=85)
        return story_id, True, None
    except Exception as e:
        return story_id, False, f"UnityPy extract error: {e}"


def fetch_all_story_thumbnails(force: bool = False, max_workers: int = 8) -> Dict[str, Any]:
    """批次抓取並轉檔所有目標話數官方專屬縮圖"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_thumbs = load_manifest_story_thumbs()
    target_ids = collect_target_story_ids()

    print(f"[FetchThumb] 目標話數總計: {len(target_ids)} 話")
    print(f"[FetchThumb] CDN Manifest 中包含的縮圖數: {len(manifest_thumbs)} 筆")

    tasks = []
    skipped_no_manifest = []

    for sid in target_ids:
        if sid in manifest_thumbs:
            tasks.append((sid, manifest_thumbs[sid]))
        else:
            skipped_no_manifest.append(sid)

    print(f"[FetchThumb] 待處理官方縮圖: {len(tasks)} 筆, CDN 尚未上架: {len(skipped_no_manifest)} 筆")

    success_count = 0
    cached_count = 0
    failed_list = []

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_and_extract_thumb, sid, bhash, OUTPUT_DIR, force): sid
            for sid, bhash in tasks
        }

        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            sid, ok, err = future.result()
            if ok:
                if err == "cached":
                    cached_count += 1
                else:
                    success_count += 1
            else:
                failed_list.append({"story_id": sid, "error": err})

            if completed % 50 == 0 or completed == total:
                print(f"  ▶ 進度: {completed}/{total} (成功: {success_count}, 快取: {cached_count}, 失敗: {len(failed_list)})")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"[FetchThumb] 官方專屬縮圖抓取完成！總耗時: {elapsed:.2f} 秒")
    print(f"  - 新下載轉檔: {success_count} 張")
    print(f"  - 本地快取保留: {cached_count} 張")
    print(f"  - 抓取失敗: {len(failed_list)} 張")
    print(f"  - CDN 無對應 Bundle: {len(skipped_no_manifest)} 話 (將自動透過前端 fallback 降級)")
    print("=" * 60)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_targets": len(target_ids),
        "manifest_matched": len(tasks),
        "downloaded": success_count,
        "cached": cached_count,
        "failed": failed_list,
        "no_manifest": skipped_no_manifest,
        "output_dir": str(OUTPUT_DIR)
    }

    report_path = BASE_DIR / "tools" / "story_thumb_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def main():
    parser = argparse.ArgumentParser(description="PCRD 官方劇情話數專屬縮圖抓取工具")
    parser.add_argument("--force", action="store_true", help="強制重新下載並覆蓋現有 WebP")
    parser.add_argument("--workers", type=int, default=8, help="並行執行緒數 (預設: 8)")
    args = parser.parse_args()

    fetch_all_story_thumbnails(force=args.force, max_workers=args.workers)


if __name__ == "__main__":
    main()
