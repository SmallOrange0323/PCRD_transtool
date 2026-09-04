#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/repair_story_identities.py
Audit and repair unit_id and dialogue identity regressions caused by recent movie restore.
Uses canonical Git history (b1daba1b) as the baseline for enriched identity data,
and safely merges all official movie commands back into the enriched dialogues.
Writes strictly to dashboard/story/ (source only).
"""

import os
import sys
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.movie_restore_core import merge_movie_commands

def main():
    print("==================================================")
    print("STARTING STORY IDENTITY AUDIT & REPAIR")
    print("==================================================")

    try:
        out = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', 'b1daba1b', 'story']).decode('utf-8')
        all_story_files = [l for l in out.splitlines() if l.endswith('.json')]
    except Exception as e:
        print(f"Error reading git tree from b1daba1b: {e}", file=sys.stderr)
        sys.exit(1)

    stories_audited = 0
    dialogue_rows_before = 0
    dialogue_rows_after = 0
    rows_with_unit_id_before = 0
    rows_with_unit_id_after = 0
    repaired_unit_id_rows = 0
    movie_commands_preserved = 0
    duplicate_movies = 0

    repaired_stories_count = 0
    dashboard_story_dir = ROOT / "dashboard" / "story"

    for rel_path in all_story_files:
        fname = os.path.basename(rel_path)
        sid_str = fname.replace('.json', '')
        if not sid_str.isdigit():
            continue

        stories_audited += 1

        canon_raw = subprocess.check_output(['git', 'show', f'b1daba1b:{rel_path}']).decode('utf-8')
        canonical_dialogues = json.loads(canon_raw)

        c_uids = [x.get('unit_id') for x in canonical_dialogues if isinstance(x, dict) and x.get('unit_id')]
        rows_with_unit_id_before += len(c_uids)
        dialogue_rows_before += len(canonical_dialogues)

        curr_file = dashboard_story_dir / fname
        if not curr_file.exists():
            curr_data = canonical_dialogues
        else:
            with open(curr_file, 'r', encoding='utf-8') as fp:
                curr_data = json.load(fp)

        repaired_dialogues = merge_movie_commands(canonical_dialogues, curr_data)

        rep_uids = [x.get('unit_id') for x in repaired_dialogues if isinstance(x, dict) and x.get('unit_id')]
        rep_movies = [x for x in repaired_dialogues if isinstance(x, dict) and x.get('type') == 'movie']
        
        dialogue_rows_after += len(repaired_dialogues)
        rows_with_unit_id_after += len(rep_uids)
        movie_commands_preserved += len(rep_movies)

        movie_ids_seen = set()
        for m in rep_movies:
            mid = str(m.get('movie_id'))
            if mid in movie_ids_seen:
                duplicate_movies += 1
            else:
                movie_ids_seen.add(mid)

        curr_uids = [x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')]
        if len(rep_uids) > len(curr_uids):
            repaired_unit_id_rows += (len(rep_uids) - len(curr_uids))
            repaired_stories_count += 1

        with open(curr_file, 'w', encoding='utf-8') as fp:
            json.dump(repaired_dialogues, fp, ensure_ascii=False, indent=4)

    print("==================================================")
    print("IDENTITY LOSS AUDIT & REPAIR SUMMARY")
    print("==================================================")
    print(f"Stories audited: {stories_audited}")
    print(f"Dialogue rows before: {dialogue_rows_before}")
    print(f"Dialogue rows after: {dialogue_rows_after}")
    print(f"Rows with unit_id before: {rows_with_unit_id_before}")
    print(f"Rows with unit_id after: {rows_with_unit_id_after}")
    print(f"Rows with unit_id repaired: {repaired_unit_id_rows}")
    print(f"Movie commands preserved: {movie_commands_preserved}")
    print(f"Duplicate movies: {duplicate_movies}")
    print(f"Repaired stories count: {repaired_stories_count}")
    print("==================================================")

if __name__ == "__main__":
    main()
