#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/audit_movie_positions.py
Full semantic anchor alignment audit across all movie-bearing stories in Part 1, 2, 3.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.pcrd_fetch import (
    WEB_HEADER,
    SONET_CDN,
    load_story_manifest_hash_map,
    _parse_bundle_dialogues
)
from tools.movie_restore_core import (
    validate_sequence_alignment,
    AlignmentMismatchError
)


def audit_story(sid, h):
    url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
    req = urllib.request.Request(url, headers=WEB_HEADER)
    with urllib.request.urlopen(req, timeout=30) as res:
        raw_dialogues = _parse_bundle_dialogues(res.read(), extract_metadata=False)

    local_path = ROOT / "dashboard" / "story" / f"{sid}.json"
    if not local_path.exists():
        return None

    with open(local_path, "r", encoding="utf-8") as fp:
        existing_dialogues = json.load(fp)

    raw_movies = [x for x in raw_dialogues if isinstance(x, dict) and x.get("type") == "movie"]
    if not raw_movies:
        return None

    raw_non_movies = [x for x in raw_dialogues if not (isinstance(x, dict) and x.get("type") == "movie")]
    existing_non_movies = [x for x in existing_dialogues if not (isinstance(x, dict) and x.get("type") == "movie")]

    alignment_ok = True
    reason = "ok"

    try:
        validate_sequence_alignment(existing_non_movies, raw_non_movies, story_id=str(sid))
    except AlignmentMismatchError as e:
        alignment_ok = False
        reason = str(e)

    existing_movies = [x for x in existing_dialogues if isinstance(x, dict) and x.get("type") == "movie"]

    return {
        "sid": sid,
        "movie_count": len(raw_movies),
        "existing_movie_count": len(existing_movies),
        "alignment_ok": alignment_ok,
        "reason": reason
    }


def main():
    print("==================================================")
    print("STARTING FULL MOVIE POSITION AUDIT (Part 1, 2, 3)")
    print("==================================================")

    hashes = load_story_manifest_hash_map()
    sids = sorted([s for s in hashes if 2000000 <= s < 2300000])

    print(f"Total main stories scanned: {len(sids)}")

    results = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(audit_story, sid, hashes[sid]): sid for sid in sids}
        for f in as_completed(futures):
            res = f.result()
            if res is not None:
                results.append(res)

    results.sort(key=lambda x: x["sid"])

    movie_bearing_count = len(results)
    aligned_count = len([r for r in results if r["alignment_ok"]])
    mismatch_count = len([r for r in results if not r["alignment_ok"]])

    movies_expected = sum(r["movie_count"] for r in results)
    movies_preserved = sum(r["existing_movie_count"] for r in results if r["alignment_ok"])

    print("==================================================")
    print("FULL POSITION AUDIT REPORT")
    print("==================================================")
    print(f"Movie-bearing stories audited: {movie_bearing_count}")
    print(f"Alignment exact/accepted: {aligned_count}")
    print(f"Alignment mismatch: {mismatch_count}")
    if mismatch_count > 0:
        for r in results:
            if not r["alignment_ok"]:
                print(f"  [MISMATCH] {r['reason']}")
    print(f"Movies expected from raw: {movies_expected}")
    print(f"Movies inserted/preserved: {movies_preserved}")
    print(f"Stories skipped due mismatch: {mismatch_count}")
    print("==================================================")


if __name__ == "__main__":
    main()
