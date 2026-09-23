# -*- coding: utf-8 -*-
"""
fetch_top_thumbnails.py — 官方頂層專屬縮圖下載與轉檔工具
從 So-net CDN 的 icon2_assetmanifest 解析官方專屬頂層縮圖：
1. 公會頂層縮圖：icon_thumb_guild_story_top_*.unity3d -> dashboard/icon/guild_top/*.webp
2. 額外劇情頂層縮圖：icon_thumb_exstory_top_*.unity3d -> dashboard/icon/exstory_top/*.webp
3. 露娜之塔頂層縮圖：icon_thumb_tower_story_top_*.unity3d -> dashboard/icon/tower_top/*.webp

使用 UnityPy 提取 Texture2D 並轉換為高品質 WebP。
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = BASE_DIR / "dashboard"
MANIFEST_PATH = BASE_DIR / "icon2_assetmanifest"

SONET_CDN = "https://img-pc.so-net.tw/dl"
SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

CONFIGS = [
    {
        "category": "guild_top",
        "prefix": "icon_thumb_guild_story_top_",
        "output_dir": DASHBOARD_DIR / "icon" / "guild_top",
        "label": "公會頂層縮圖"
    },
    {
        "category": "exstory_top",
        "prefix": "icon_thumb_exstory_top_",
        "output_dir": DASHBOARD_DIR / "icon" / "exstory_top",
        "label": "額外劇情分類縮圖"
    },
    {
        "category": "tower_top",
        "prefix": "icon_thumb_tower_story_top_",
        "output_dir": DASHBOARD_DIR / "icon" / "tower_top",
        "label": "露娜之塔期數縮圖"
    }
]


def load_manifest_targets(manifest_path: Path = MANIFEST_PATH) -> Dict[str, List[Tuple[str, str, Path]]]:
    """
    從 icon2_assetmanifest 中解析各分類的目標 bundle：
    回傳：{ category: [(id, pool_hash, output_file), ...] }
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"找不到 manifest 檔案: {manifest_path}")

    results = {cfg["category"]: [] for cfg in CONFIGS}

    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            bundle_name = parts[0]
            pool_hash = parts[2]

            for cfg in CONFIGS:
                pfx = cfg["prefix"]
                if pfx in bundle_name:
                    stem = bundle_name.replace(f"a/{pfx}", "").replace(".unity3d", "")
                    out_file = cfg["output_dir"] / f"{stem}.webp"
                    results[cfg["category"]].append((stem, pool_hash, out_file))
                    break

    for cfg in CONFIGS:
        results[cfg["category"]].sort(key=lambda x: int(x[0]) if x[0].isdigit() else x[0])

    return results


def download_and_extract_thumb(item_id: str, pool_hash: str, out_file: Path, force: bool = False) -> Tuple[str, bool, Optional[str]]:
    """
    下載單個 AssetBundle 並使用 UnityPy 提取 Texture2D 轉為 WebP
    """
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return item_id, True, "cached"

    url = f"{SONET_CDN}/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            bundle_bytes = resp.read()
    except Exception as e:
        return item_id, False, f"HTTP error: {e}"

    try:
        import UnityPy
        UnityPy.config.FALLBACK_UNITY_VERSION = "2020.3.34f1"
        env = UnityPy.load(bundle_bytes)

        found_img = None
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                t2d = obj.read()
                found_img = t2d.image
                break

        if not found_img:
            return item_id, False, "No Texture2D in bundle"

        out_file.parent.mkdir(parents=True, exist_ok=True)
        found_img.save(out_file, format="WEBP", quality=85)
        return item_id, True, None
    except Exception as e:
        return item_id, False, f"UnityPy error: {e}"


def fetch_top_thumbnails(force: bool = False, max_workers: int = 8):
    print("=" * 60)
    print("🔍 開始解析並下載官方頂層縮圖 (Guild / ExStory / Tower)...")
    print("=" * 60)

    targets = load_manifest_targets()
    summary = {}

    for cfg in CONFIGS:
        cat = cfg["category"]
        items = targets[cat]
        out_dir = cfg["output_dir"]
        label = cfg["label"]
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{label}] 共發現 {len(items)} 個官方目標，開始處理...")

        success_count = 0
        cached_count = 0
        fail_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(download_and_extract_thumb, item_id, pool_hash, out_file, force): item_id
                for item_id, pool_hash, out_file in items
            }

            for future in concurrent.futures.as_completed(future_to_item):
                item_id = future_to_item[future]
                try:
                    tid, ok, err = future.result()
                    if ok:
                        if err == "cached":
                            cached_count += 1
                        else:
                            success_count += 1
                            print(f"  ✅ 下載成功: {tid}.webp")
                    else:
                        fail_count += 1
                        print(f"  ❌ 失敗 {tid}: {err}", file=sys.stderr)
                except Exception as e:
                    fail_count += 1
                    print(f"  ❌ 例外 {item_id}: {e}", file=sys.stderr)

        print(f"[{label}] 完成: 下載 {success_count} 筆，快取 {cached_count} 筆，失敗 {fail_count} 筆")
        summary[cat] = {
            "total": len(items),
            "downloaded": success_count,
            "cached": cached_count,
            "failed": fail_count
        }

    print("\n" + "=" * 60)
    print("📊 頂層縮圖處理總覽:")
    for cat, res in summary.items():
        print(f"  {cat}: 總數 {res['total']} (新下載: {res['downloaded']}, 快取: {res['cached']}, 失敗: {res['failed']})")
    print("=" * 60)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下載公會、額外劇情與露娜塔官方頂層縮圖")
    parser.add_argument("--force", action="store_true", help="強制重新下載覆蓋現有檔案")
    parser.add_argument("--workers", type=int, default=8, help="最大並發下載線程數 (預設: 8)")
    args = parser.parse_args()

    fetch_top_thumbnails(force=args.force, max_workers=args.workers)
