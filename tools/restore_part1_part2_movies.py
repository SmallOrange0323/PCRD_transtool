import os
import sys
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"e:\OneDrive - 寰宇知識科技股份有限公司\PCRD_tool")
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
    print("❌ 請先安裝 UnityPy", file=sys.stderr)
    sys.exit(1)


def process_story(sid, h, out_dirs):
    url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
    req = urllib.request.Request(url, headers=WEB_HEADER)
    
    with urllib.request.urlopen(req, timeout=30) as res:
        bundle_bytes = res.read()

    dialogues, _ = _parse_bundle_dialogues(bundle_bytes, extract_metadata=True)
    movies = [d for d in dialogues if d.get("type") == "movie"]

    for d in out_dirs:
        dest_path = d / f"{sid}.json"
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(dialogues, f, ensure_ascii=False, indent=4)

    return sid, len(movies), [m["movie_id"] for m in movies]


def main():
    print("🔍 載入台版官方 storydata manifest 快取...")
    hashes = load_story_manifest_hash_map()
    if not hashes:
        print("❌ 未找到可用的 storydata manifest 快取！", file=sys.stderr)
        sys.exit(1)

    p1_sids = sorted([sid for sid in hashes if 2000000 <= sid < 2100000])
    p2_sids = sorted([sid for sid in hashes if 2100000 <= sid < 2200000])
    all_sids = p1_sids + p2_sids
    print(f"📊 主線第一部話數: {len(p1_sids)} 話")
    print(f"📊 主線第二部話數: {len(p2_sids)} 話")
    print(f"📊 合計待還原總話數: {len(all_sids)} 話")

    out_dirs = [
        ROOT / "dashboard" / "story",
        ROOT / "dist_story_map" / "story"
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    total_movies_restored = 0
    stories_with_movie = 0
    stories_without_movie = 0
    failed_stories = []

    print("\n🚀 開始並行下載、解密並還原第一部與第二部劇本 (8 Workers)...")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_story, sid, hashes[sid], out_dirs): sid for sid in all_sids}
        completed = 0

        for future in as_completed(futures):
            sid = futures[future]
            completed += 1
            try:
                sid_res, movie_count, movie_ids = future.result()
                if movie_count > 0:
                    stories_with_movie += 1
                    total_movies_restored += movie_count
                    print(f"  [{completed}/{len(all_sids)}] Story {sid_res}: 🎬 還原 {movie_count} 部動畫: {movie_ids}")
                else:
                    stories_without_movie += 1
            except Exception as e:
                print(f"  [{completed}/{len(all_sids)}] Story {sid}: ❌ 失敗: {e}", file=sys.stderr)
                failed_stories.append(sid)

    print("\n" + "=" * 60)
    print("✨ 第一部與第二部劇本過場動畫還原完成！")
    print(f"  - 處理話數: {completed}/{len(all_sids)}")
    print(f"  - 包含過場動畫話數: {stories_with_movie}")
    print(f"  - 成功還原動畫總數: {total_movies_restored} 部")
    print(f"  - 純對白話數: {stories_without_movie}")
    if failed_stories:
        print(f"  - 失敗話數: {len(failed_stories)} (IDs: {failed_stories})")
    print("=" * 60)


if __name__ == "__main__":
    main()
