#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/restore_part3_movie_dialogues.py
Restore official movie commands for Part 3 stories while preserving enriched story identity.
Writes strictly to source (dashboard/story/), never to dist_story_map/.
Fails closed on semantic anchor alignment mismatch.
"""

import os
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
from tools.movie_restore_core import (
    restore_story_file,
    AlignmentMismatchError
)

try:
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
except ImportError:
    print("Error: UnityPy is required: pip install UnityPy", file=sys.stderr)
    sys.exit(1)


def main():
    print("Loading story manifest hash map...")
    hashes = load_story_manifest_hash_map()
    if not hashes:
        print("Error: No manifest found.", file=sys.stderr)
        sys.exit(1)

    p3_sids = sorted([sid for sid in hashes if 2201000 <= sid < 2217000])
    print(f"Total Part 3 stories: {len(p3_sids)}")

    story_dir = ROOT / "dashboard" / "story"
    story_dir.mkdir(parents=True, exist_ok=True)

    total_movies = 0
    updated_stories = 0
    skipped_mismatch = 0

    for idx, sid in enumerate(p3_sids, 1):
        h = hashes[sid]
        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        try:
            req = urllib.request.Request(url, headers=WEB_HEADER)
            with urllib.request.urlopen(req, timeout=25) as res:
                bundle_bytes = res.read()
            raw_dialogues, _ = _parse_bundle_dialogues(bundle_bytes, extract_metadata=False)
            
            merged = restore_story_file(sid, raw_dialogues, story_dir=story_dir)
            movies = [d for d in merged if isinstance(d, dict) and d.get("type") == "movie"]
            if movies:
                updated_stories += 1
                total_movies += len(movies)
                print(f"  [{idx}/{len(p3_sids)}] Story {sid}: {len(movies)} movie(s) merged.")
        except AlignmentMismatchError as ame:
            skipped_mismatch += 1
            print(f"  [{idx}/{len(p3_sids)}] Story {sid}: [FAIL CLOSED] {ame}", file=sys.stderr)
        except Exception as e:
            print(f"  [{idx}/{len(p3_sids)}] Story {sid}: Error: {e}", file=sys.stderr)

    print(f"Part 3 restoration complete. Updated stories: {updated_stories}, Total movies: {total_movies}, Skipped due to mismatch: {skipped_mismatch}")


if __name__ == "__main__":
    main()
