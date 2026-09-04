#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/restore_part3_movie_dialogues.py
全量還原《公主連結 Re:Dive》主線第三部 (Part 3) 劇本中官方過場動畫指令 (type: movie)
從 So-net CDN 最新 AssetBundle 解密二進位命令，修復歷史快取缺失的過場動畫，
並同步至 dashboard/story/ 與 dist_story_map/story/。
"""

import os
import re
import sys
import json
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.pcrd_fetch import (
    WEB_HEADER,
    SONET_CDN,
    load_story_manifest_hash_map,
    _parse_bundle_dialogues
)

try:
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
except ImportError:
    print("❌ 請先安裝 UnityPy: pip install UnityPy", file=sys.stderr)
    sys.exit(1)


def main():
    print("🔍 載入台版官方 storydata manifest 快取...")
    hashes = load_story_manifest_hash_map()
    if not hashes:
        print("❌ 未找到可用的 storydata manifest 快取！", file=sys.stderr)
        sys.exit(1)

    # 篩選第三部主線話數 (2201000 ~ 2217000)
    p3_sids = sorted([sid for sid in hashes if 2201000 <= sid < 2217000])
    print(f"📊 第三部主線總話數: {len(p3_sids)} 話")

    out_dirs = [
        ROOT / "dashboard" / "story",
        ROOT / "dist_story_map" / "story"
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    total_movies_restored = 0
    stories_updated = 0
    skipped_count = 0
    failed_count = 0

    print("🚀 開始從官方 CDN 下載解密並還原第三部劇本...\n")

    for idx, sid in enumerate(p3_sids, 1):
        h = hashes[sid]
        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"

        # 檢查本地是否已經有完整的 movie 指令
        local_json_path = out_dirs[0] / f"{sid}.json"
        dist_json_path = out_dirs[1] / f"{sid}.json"

        try:
            req = urllib.request.Request(url, headers=WEB_HEADER)
            with urllib.request.urlopen(req, timeout=20) as res:
                bundle_bytes = res.read()

            dialogues, meta = _parse_bundle_dialogues(bundle_bytes, extract_metadata=True)
            movies = [d for d in dialogues if d.get("type") == "movie"]

            # 讀取原本的本地檔案做對比
            old_movies_count = 0
            if local_json_path.exists():
                try:
                    old_data = json.load(open(local_json_path, encoding="utf-8"))
                    old_movies_count = len([d for d in old_data if d.get("type") == "movie"])
                except:
                    pass

            # 寫入更新
            with open(local_json_path, "w", encoding="utf-8") as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=4)
            with open(dist_json_path, "w", encoding="utf-8") as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=4)

            if len(movies) > 0:
                print(f"  [{idx}/{len(p3_sids)}] Story {sid}: ✅ 包含 {len(movies)} 部過場動畫: {[m['movie_id'] for m in movies]} (原舊版: {old_movies_count})")
                total_movies_restored += len(movies)
                stories_updated += 1
            else:
                skipped_count += 1

        except Exception as e:
            print(f"  [{idx}/{len(p3_sids)}] Story {sid}: ❌ 下載解密失敗: {e}", file=sys.stderr)
            failed_count += 1

    print(f"\n✨ 第三部劇本還原完成！")
    print(f"  - 總話數: {len(p3_sids)}")
    print(f"  - 包含過場動畫的話數: {stories_updated}")
    print(f"  - 成功還原過場動畫總數: {total_movies_restored} 部")
    print(f"  - 純對白話數 (無動畫): {skipped_count}")
    print(f"  - 失敗話數: {failed_count}")


if __name__ == "__main__":
    main()
