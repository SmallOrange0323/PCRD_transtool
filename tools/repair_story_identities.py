#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/repair_story_identities.py
================================
Audit and repair unit_id and dialogue identity regressions caused by recent movie restore.

Usage:
  python tools/repair_story_identities.py --audit     (Default: audit only, ZERO writes)
  python tools/repair_story_identities.py --apply     (Applies repair ONLY to confirmed affected & aligned stories)
  python tools/repair_story_identities.py --baseline <ref>  (Specify baseline commit, default: b1daba1b)

Principles:
1. Audit-first: Default is non-destructive (ZERO filesystem writes).
2. Selective repair: ONLY stories with confirmed identity loss are modified. Unaffected stories MUST NOT be rewritten.
3. Explicit baseline: Uses KNOWN_GOOD_IDENTITY_BASELINE (b1daba1b, the clean production state on gh-pages prior to regression).
4. Strict alignment enforcement: merge_movie_commands is called with validate_alignment=True.
5. Fail-closed: If AlignmentMismatchError occurs, the story is skipped and left completely untouched.
6. Source-only writes: Modifies dashboard/story/ only, never dist_story_map/.
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


def default_git_baseline_loader(baseline_ref, rel_path):
    """Reads canonical story json from git tree."""
    raw = subprocess.check_output(['git', 'show', f'{baseline_ref}:{rel_path}']).decode('utf-8')
    return json.loads(raw)


def audit_and_repair(
    story_dir=None,
    baseline_ref=KNOWN_GOOD_IDENTITY_BASELINE,
    apply=False,
    baseline_loader=None,
    story_files=None,
    verbose=True
):
    """
    Reusable and testable identity audit and repair engine.
    
    Returns a dict containing:
    - stories_audited
    - stories_affected
    - stories_repairable
    - stories_skipped_alignment
    - stories_written
    - unaffected_rewritten
    - dialogue_rows_before
    - dialogue_rows_after
    - rows_with_unit_id_before
    - rows_with_unit_id_after
    - repaired_unit_id_rows
    - movie_commands_preserved
    - duplicate_movies
    - mismatch_details: list of (story_id, reason)
    """
    target_story_dir = Path(story_dir) if story_dir else (ROOT / "dashboard" / "story")
    
    # Enforce source-only rule
    normalized_path = str(target_story_dir).replace('\\', '/')
    if 'dist_story_map' in normalized_path:
        raise ValueError(f"Security violation: Cannot write to dist_story_map ({target_story_dir}).")

    loader = baseline_loader or default_git_baseline_loader

    if story_files is None:
        try:
            out = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline_ref, 'story']).decode('utf-8')
            story_files = [l for l in out.splitlines() if l.endswith('.json')]
        except Exception as e:
            if verbose:
                print(f"Error reading git tree from {baseline_ref}: {e}", file=sys.stderr)
            raise

    stats = {
        "stories_audited": 0,
        "stories_affected": 0,
        "stories_repairable": 0,
        "stories_skipped_alignment": 0,
        "stories_written": 0,
        "unaffected_rewritten": 0,
        "dialogue_rows_before": 0,
        "dialogue_rows_after": 0,
        "rows_with_unit_id_before": 0,
        "rows_with_unit_id_after": 0,
        "repaired_unit_id_rows": 0,
        "movie_commands_preserved": 0,
        "duplicate_movies": 0,
        "mismatch_details": []
    }

    for rel_path in story_files:
        fname = os.path.basename(rel_path)
        sid_str = fname.replace('.json', '')
        if not sid_str.isdigit():
            continue

        stats["stories_audited"] += 1

        # 讀取 baseline 資料
        try:
            canonical_dialogues = loader(baseline_ref, rel_path)
        except Exception as e:
            if verbose:
                print(f"  [WARN] Cannot load baseline for {fname}: {e}", file=sys.stderr)
            continue

        c_uids = [x.get('unit_id') for x in canonical_dialogues if isinstance(x, dict) and x.get('unit_id')]
        stats["rows_with_unit_id_before"] += len(c_uids)
        stats["dialogue_rows_before"] += len(canonical_dialogues)

        curr_file = target_story_dir / fname
        if not curr_file.exists():
            curr_data = canonical_dialogues
            is_affected = True
        else:
            try:
                with open(curr_file, 'r', encoding='utf-8') as fp:
                    curr_data = json.load(fp)
            except Exception as e:
                if verbose:
                    print(f"  [WARN] Corrupt or unreadable file {curr_file}: {e}", file=sys.stderr)
                continue

            curr_uids = [x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')]
            curr_typed = [x for x in curr_data if isinstance(x, dict) and x.get('type') == 'dialogue']
            canon_typed = [x for x in canonical_dialogues if isinstance(x, dict) and x.get('type') == 'dialogue']

            # 判定是否發生身分回歸 (unit_id 數量減少，或整檔缺失 type='dialogue')
            if len(curr_uids) < len(c_uids) or (len(canon_typed) > 0 and len(curr_typed) == 0):
                is_affected = True
            else:
                is_affected = False

        if is_affected:
            stats["stories_affected"] += 1

            # 嚴格對齊驗證：validate_alignment=True (BLOCKING REQUIREMENT)
            try:
                repaired = merge_movie_commands(
                    canonical_dialogues,
                    curr_data,
                    story_id=sid_str,
                    validate_alignment=True
                )
            except AlignmentMismatchError as ame:
                stats["stories_skipped_alignment"] += 1
                stats["mismatch_details"].append((sid_str, str(ame)))
                if verbose:
                    print(f"  [SKIPPED_ALIGNMENT_MISMATCH] {ame}", file=sys.stderr)
                # FAIL-CLOSED: 絕不修改該故事，保留原檔
                stats["dialogue_rows_after"] += len(curr_data)
                stats["rows_with_unit_id_after"] += len([x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')])
                continue

            # 通過對齊檢查，標記為可修復
            stats["stories_repairable"] += 1

            rep_uids = [x.get('unit_id') for x in repaired if isinstance(x, dict) and x.get('unit_id')]
            rep_movies = [x for x in repaired if isinstance(x, dict) and x.get('type') == 'movie']

            stats["dialogue_rows_after"] += len(repaired)
            stats["rows_with_unit_id_after"] += len(rep_uids)
            stats["movie_commands_preserved"] += len(rep_movies)

            # Duplicate movie count
            seen_mids = set()
            for m in rep_movies:
                mid = str(m.get('movie_id'))
                if mid in seen_mids:
                    stats["duplicate_movies"] += 1
                else:
                    seen_mids.add(mid)

            curr_uids_count = len([x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')])
            if len(rep_uids) > curr_uids_count:
                stats["repaired_unit_id_rows"] += (len(rep_uids) - curr_uids_count)

            # 僅在 apply 模式下寫入磁碟 (且僅寫入通過對齊的受影響檔案)
            if apply:
                target_story_dir.mkdir(parents=True, exist_ok=True)
                with open(curr_file, 'w', encoding='utf-8') as fp:
                    json.dump(repaired, fp, ensure_ascii=False, indent=4)
                stats["stories_written"] += 1
        else:
            # 未受影響的故事：絕對不寫入磁碟！
            stats["dialogue_rows_after"] += len(curr_data)
            curr_uids_count = len([x.get('unit_id') for x in curr_data if isinstance(x, dict) and x.get('unit_id')])
            stats["rows_with_unit_id_after"] += curr_uids_count
            curr_movies = [x for x in curr_data if isinstance(x, dict) and x.get('type') == 'movie']
            stats["movie_commands_preserved"] += len(curr_movies)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Audit and repair story dialogue identity data.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply repairs ONLY to confirmed affected and aligned files in dashboard/story/. If omitted, runs in audit-only mode."
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run in audit-only mode with ZERO filesystem writes."
    )
    parser.add_argument(
        "--baseline",
        default=KNOWN_GOOD_IDENTITY_BASELINE,
        help=f"Git ref for canonical enriched baseline (default: {KNOWN_GOOD_IDENTITY_BASELINE})"
    )
    args = parser.parse_args()

    is_apply_mode = args.apply and not args.audit

    print("==================================================")
    print(f"STORY IDENTITY AUDIT & REPAIR ({'APPLY MODE' if is_apply_mode else 'AUDIT MODE (ZERO WRITES)'})")
    print(f"Target Baseline: {args.baseline}")
    print("Alignment Enforcement: STRICT (validate_alignment=True)")
    print("==================================================")

    stats = audit_and_repair(
        baseline_ref=args.baseline,
        apply=is_apply_mode,
        verbose=True
    )

    print("\n==================================================")
    print("FINAL AUDIT & REPAIR SUMMARY")
    print("==================================================")
    print(f"Stories audited: {stats['stories_audited']}")
    print(f"Stories affected: {stats['stories_affected']}")
    print(f"Stories repairable: {stats['stories_repairable']}")
    print(f"Stories skipped alignment: {stats['stories_skipped_alignment']}")
    print(f"Stories actually written: {stats['stories_written']}")
    print(f"Unaffected stories rewritten: {stats['unaffected_rewritten']}")
    print(f"Dialogue rows before: {stats['dialogue_rows_before']}")
    print(f"Dialogue rows after: {stats['dialogue_rows_after']}")
    print(f"Rows with unit_id before: {stats['rows_with_unit_id_before']}")
    print(f"Rows with unit_id after: {stats['rows_with_unit_id_after']}")
    print(f"Rows with unit_id repaired: {stats['repaired_unit_id_rows']}")
    print(f"Movie commands preserved: {stats['movie_commands_preserved']}")
    print(f"Duplicate movies: {stats['duplicate_movies']}")
    if stats['stories_skipped_alignment'] > 0:
        print(f"Exact mismatch stories count: {len(stats['mismatch_details'])}")
        for sid, reason in stats['mismatch_details']:
            print(f"  - Story {sid}: {reason}")
    print("==================================================")


if __name__ == '__main__':
    main()
