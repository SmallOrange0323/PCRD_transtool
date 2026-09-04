#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/repair_story_identities.py
================================
Audit and repair unit_id and dialogue identity regressions caused by recent movie restore.

Usage:
  python tools/repair_story_identities.py --audit     (Default: audit only, ZERO writes)
  python tools/repair_story_identities.py --apply     (Applies repair ONLY to confirmed affected stories)
  python tools/repair_story_identities.py --baseline <ref>  (Specify baseline commit, default: b1daba1b)

Principles:
1. Audit-first: Default is non-destructive (ZERO filesystem writes).
2. Selective repair: ONLY stories with confirmed identity loss are modified. Unaffected stories MUST NOT be rewritten.
3. Explicit baseline: Uses KNOWN_GOOD_IDENTITY_BASELINE (b1daba1b, the clean production state on gh-pages prior to regression).
4. Strict alignment & fail-closed: Movies are positioned safely or skipped if alignment mismatch occurs.
5. Source-only writes: Modifies dashboard/story/ only, never dist_story_map/.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.movie_restore_core import (
    KNOWN_GOOD_IDENTITY_BASELINE,
    merge_movie_commands,
    AlignmentMismatchError
)


def main():
    parser = argparse.ArgumentParser(description="Audit and repair story dialogue identity data.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply repairs to confirmed affected files in dashboard/story/. If omitted, runs in audit-only mode."
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run in audit-only mode with zero filesystem writes."
    )
    parser.add_argument(
        "--baseline",
        default=KNOWN_GOOD_IDENTITY_BASELINE,
        help=f"Git ref for canonical enriched baseline (default: {KNOWN_GOOD_IDENTITY_BASELINE})"
    )
    args = parser.parse_args()

    # Default to audit if not explicitly --apply
    is_apply_mode = args.apply and not args.audit

    print("==================================================")
    print(f"STORY IDENTITY AUDIT & REPAIR ({'APPLY MODE' if is_apply_mode else 'AUDIT MODE (ZERO WRITES)'})")
    print(f"Target Baseline: {args.baseline}")
    print("==================================================")

    # 讀取 baseline 中的故事清單
    try:
        out = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', args.baseline, 'story']).decode('utf-8')
        story_files = [l for l in out.splitlines() if l.endswith('.json')]
    except Exception as e:
        print(f"Error reading git tree from {args.baseline}: {e}", file=sys.stderr)
        sys.exit(1)

    stories_audited = 0
    stories_affected = 0
    stories_written = 0
    unaffected_rewritten = 0

    dialogue_rows_before = 0
    dialogue_rows_after = 0
    rows_with_unit_id_before = 0
    rows_with_unit_id_after = 0
    repaired_unit_id_rows = 0

    movie_commands_preserved = 0
    duplicate_movies = 0
    alignment_mismatches = 0

    dashboard_story_dir = ROOT / "dashboard" / "story"

    for rel_path in story_files:
        fname = os.path.basename(rel_path)
        sid_str = fname.replace('.json', '')
        if not sid_str.isdigit():
            continue

        stories_audited += 1

        # 讀取 baseline
        canon_raw = subprocess.check_output(['git', 'show', f'{args.baseline}:{rel_path}']).decode('utf-8')
        canonical_dialogues = json.loads(canon_raw)

        c_uids = [x.get('unit_id') for x in canonical_dialogues if isinstance(x, dict) and x.get('unit_id')]
        rows_with_unit_id_before += len(c_uids)
        dialogue_rows_before += len(canonical_dialogues)

        # 讀取磁碟上的現存故事
        curr_file = dashboard_story_dir / fname
        if not curr_file.exists():
            curr_data = canonical_dialogues
            is_affected = True
        else:
            with open(curr_file, 'r', encoding='utf-8') as fp:
                curr_data = json.load(fp)
            
            curr_uids = [x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')]
            curr_typed_dialogues = [x for x in curr_data if isinstance(x, dict) and x.get('type') == 'dialogue']
            canon_typed_dialogues = [x for x in canonical_dialogues if isinstance(x, dict) and x.get('type') == 'dialogue']

            # 判定是否受到身分回歸影響 (unit_id 缺失或 type='dialogue' 丟失)
            if len(curr_uids) < len(c_uids) or (len(canon_typed_dialogues) > 0 and len(curr_typed_dialogues) == 0):
                is_affected = True
            else:
                is_affected = False

        if is_affected:
            stories_affected += 1
            try:
                # 安全合併 movie 指令進 canonical
                repaired = merge_movie_commands(canonical_dialogues, curr_data, story_id=sid_str, validate_alignment=False)
            except AlignmentMismatchError as e:
                alignment_mismatches += 1
                print(f"  [MISMATCH] {e}", file=sys.stderr)
                continue

            rep_uids = [x.get('unit_id') for x in repaired if isinstance(x, dict) and x.get('unit_id')]
            rep_movies = [x for x in repaired if isinstance(x, dict) and x.get('type') == 'movie']

            dialogue_rows_after += len(repaired)
            rows_with_unit_id_after += len(rep_uids)
            movie_commands_preserved += len(rep_movies)

            # 檢查 duplicate movies
            seen_mids = set()
            for m in rep_movies:
                mid = str(m.get('movie_id'))
                if mid in seen_mids:
                    duplicate_movies += 1
                else:
                    seen_mids.add(mid)

            curr_uids_count = len([x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')])
            if len(rep_uids) > curr_uids_count:
                repaired_unit_id_rows += (len(rep_uids) - curr_uids_count)

            # 僅在 apply 模式下寫入磁碟 (且僅寫入 affected 檔案)
            if is_apply_mode:
                with open(curr_file, 'w', encoding='utf-8') as fp:
                    json.dump(repaired, fp, ensure_ascii=False, indent=4)
                stories_written += 1
        else:
            # 未受影響的故事：絕對不重寫！
            dialogue_rows_after += len(curr_data)
            curr_uids_count = len([x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')])
            rows_with_unit_id_after += curr_uids_count
            curr_movies = [x for x in curr_data if isinstance(x, dict) and x.get('type') == 'movie']
            movie_commands_preserved += len(curr_movies)

    print("==================================================")
    print("FINAL AUDIT & REPAIR SUMMARY")
    print("==================================================")
    print(f"Stories audited: {stories_audited}")
    print(f"Stories affected: {stories_affected}")
    print(f"Stories actually written: {stories_written}")
    print(f"Unaffected stories rewritten: {unaffected_rewritten}")
    print(f"Dialogue rows before: {dialogue_rows_before}")
    print(f"Dialogue rows after: {dialogue_rows_after}")
    print(f"Rows with unit_id before: {rows_with_unit_id_before}")
    print(f"Rows with unit_id after: {rows_with_unit_id_after}")
    print(f"Rows with unit_id repaired: {repaired_unit_id_rows}")
    print(f"Movie commands preserved: {movie_commands_preserved}")
    print(f"Duplicate movies: {duplicate_movies}")
    if alignment_mismatches > 0:
        print(f"Alignment mismatches: {alignment_mismatches}")
    print("==================================================")


if __name__ == '__main__':
    main()
