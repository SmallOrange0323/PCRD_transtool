#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/restore_part1_part2_movies.py
Restore official movie commands for Part 1 & Part 2 stories while preserving enriched story identity.
Writes strictly to source (dashboard/story/), never to dist_story_map/.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
from tools.movie_restore_core import restore_story_file

try:
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
except ImportError:
    print("Error: UnityPy is required: pip install UnityPy", file=sys.stderr)
    sys.exit(1)


def process_story(sid, h, story_dir):
    url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
    req = urllib.request.Request(url, headers=WEB_HEADER)
    with urllib.request.urlopen(req, timeout=30) as res:
        bundle_bytes = res.read()

    raw_dialogues, _ = _parse_bundle_dialogues(bundle_bytes, extract_metadata=True)
    merged = restore_story_file(sid, raw_dialogues, story_dir=story_dir)
    movies = [d for d in merged if isinstance(d, dict) and d.get("type") == "movie"]
    return sid, len(movies), [m["movie_id"] for m in movies]


def main():
    print("Loading story manifest hash map...")
    hashes = load_story_manifest_hash_map()
    if not hashes:
        print("Error: No manifest found.", file=sys.stderr)
        sys.exit(1)

    p1_sids = sorted([sid for sid in hashes if 2000000 <= sid < 2100000])
    p2_sids = sorted([sid for sid in hashes if 2100000 <= sid < 2200000])
    all_sids = p1_sids + p2_sids
    print(f"Part 1 stories: {len(p1_sids)}, Part 2 stories: {len(p2_sids)}, Total: {len(all_sids)}")

    story_dir = ROOT / "dashboard" / "story"
    story_dir.mkdir(parents=True, exist_ok=True)

    total_movies = 0
    stories_with_movies = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_story, sid, hashes[sid], story_dir): sid for sid in all_sids}
        completed = 0
        for future in as_completed(futures):
            sid = futures[future]
            completed += 1
            try:
                sid_res, movie_count, movie_ids = future.result()
                if movie_count > 0:
                    stories_with_movies += 1
                    total_movies += movie_count
                    print(f"  [{completed}/{len(all_sids)}] Story {sid_res}: {movie_count} movie(s): {movie_ids}")
            except Exception as e:
                print(f"  [{completed}/{len(all_sids)}] Story {sid}: Error: {e}", file=sys.stderr)

    print(f"Part 1 & 2 restoration complete. Stories with movies: {stories_with_movies}, Total movies: {total_movies}")


if __name__ == "__main__":
    main()
