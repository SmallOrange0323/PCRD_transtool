# -*- coding: utf-8 -*-
"""
tools/movie_restore_core.py
===========================
Safe movie command restoration module.

Preserves dialogue unit_id across dialogue merges:
1. Baseline is existing enriched JSON (preserving unit_id, type='dialogue', text).
2. Fresh AssetBundle parse is authoritative ONLY for official movie commands.
3. No whole-file replacement of canonical enriched dialogue objects.
4. Source-only writes to dashboard/story/, never writes to dist_story_map/.
5. Portable ROOT = Path(__file__).resolve().parent.parent.
"""

import os
import sys
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def merge_movie_commands(existing_dialogues, raw_dialogues):
    """
    Merge official movie commands from raw_dialogues into existing_dialogues.
    - Preserves all existing dialogue objects and enriched fields (unit_id, type, etc.)
    - Inserts missing movie commands at their correct relative positions
    - Avoids duplicates (idempotent)
    - Never removes unit_id or replaces enriched objects wholesale
    """
    if not existing_dialogues:
        return [copy.deepcopy(x) for x in (raw_dialogues or []) if isinstance(x, dict) and x.get('type') == 'movie']
    if not raw_dialogues:
        return copy.deepcopy(existing_dialogues)

    # 1. Collect all movie commands in raw and their non-movie relative position
    raw_movie_entries = []
    non_movie_count = 0
    for item in raw_dialogues:
        if isinstance(item, dict) and item.get('type') == 'movie':
            raw_movie_entries.append((non_movie_count, item))
        else:
            non_movie_count += 1

    if not raw_movie_entries:
        return copy.deepcopy(existing_dialogues)

    # 2. Collect existing movie IDs
    existing_movie_ids = set()
    for item in existing_dialogues:
        if isinstance(item, dict) and item.get('type') == 'movie':
            mid = item.get('movie_id')
            if mid is not None:
                existing_movie_ids.add(str(mid))

    # 3. Group new movies by their non_movie insertion position
    movies_to_insert_at = {}
    for pos, m_item in raw_movie_entries:
        mid = str(m_item.get('movie_id'))
        if mid not in existing_movie_ids:
            if pos not in movies_to_insert_at:
                movies_to_insert_at[pos] = []
            movies_to_insert_at[pos].append(m_item)

    if not movies_to_insert_at:
        return copy.deepcopy(existing_dialogues)

    # 4. Traverse existing and insert movies at corresponding non_movie index
    merged = []
    curr_non_movie_count = 0

    for item in existing_dialogues:
        if isinstance(item, dict) and item.get('type') != 'movie':
            if curr_non_movie_count in movies_to_insert_at:
                for m in movies_to_insert_at[curr_non_movie_count]:
                    merged.append(copy.deepcopy(m))
                    existing_movie_ids.add(str(m.get('movie_id')))
                del movies_to_insert_at[curr_non_movie_count]
            curr_non_movie_count += 1
            merged.append(copy.deepcopy(item))
        else:
            merged.append(copy.deepcopy(item))

    # Any trailing movie at or after the end
    if curr_non_movie_count in movies_to_insert_at:
        for m in movies_to_insert_at[curr_non_movie_count]:
            merged.append(copy.deepcopy(m))
            existing_movie_ids.add(str(m.get('movie_id')))
        del movies_to_insert_at[curr_non_movie_count]

    for pos in sorted(movies_to_insert_at.keys()):
        for m in movies_to_insert_at[pos]:
            merged.append(copy.deepcopy(m))

    return merged


def restore_story_file(sid, raw_dialogues, story_dir=None, canonical_dialogues=None):
    """
    Restores movie commands for a single story file safely.
    Writes only to dashboard/story/ (or given story_dir).
    Never writes to dist_story_map/.
    """
    target_dir = Path(story_dir) if story_dir else (ROOT / 'dashboard' / 'story')
    
    # Enforce source-only rule
    normalized_path = str(target_dir).replace('\\', '/')
    if 'dist_story_map' in normalized_path:
        raise ValueError(f'Security violation: Cannot write to dist_story_map ({target_dir}).')

    target_file = target_dir / f'{sid}.json'

    # Determine identity baseline
    if canonical_dialogues is not None:
        baseline_data = canonical_dialogues
    elif target_file.exists():
        with open(target_file, 'r', encoding='utf-8') as fp:
            baseline_data = json.load(fp)
    else:
        baseline_data = raw_dialogues

    merged_data = merge_movie_commands(baseline_data, raw_dialogues)

    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target_file, 'w', encoding='utf-8') as fp:
        json.dump(merged_data, fp, ensure_ascii=False, indent=4)

    return merged_data
