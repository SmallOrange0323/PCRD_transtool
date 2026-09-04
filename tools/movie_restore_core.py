# -*- coding: utf-8 -*-
"""
tools/movie_restore_core.py
===========================
Safe movie command restoration module with strict semantic anchor alignment.

Contract:
1. Baseline is existing enriched JSON (preserving unit_id, type='dialogue', text).
2. Fresh AssetBundle parse is authoritative ONLY for official movie commands.
3. Strict semantic anchor validation on non-movie elements before insertion.
4. Fail-closed on alignment mismatch (no fallback append).
5. Source-only writes to dashboard/story/, never writes to dist_story_map/.
6. Portable ROOT = Path(__file__).resolve().parent.parent.
"""

import os
import sys
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Known-good production snapshot baseline:
# b1daba1b was the clean production state on gh-pages right before raw restore overwrites.
# It contains all 9,033 canonical stories with verified unit_id and type='dialogue'.
KNOWN_GOOD_IDENTITY_BASELINE = "b1daba1b"


class AlignmentMismatchError(ValueError):
    """Raised when raw non-movie sequence fails semantic anchor alignment with existing sequence."""
    def __init__(self, story_id, raw_len, existing_len, mismatch_index, reason):
        super().__init__(
            f"ALIGNMENT_MISMATCH for Story {story_id}: "
            f"raw_len={raw_len}, existing_len={existing_len}, "
            f"first mismatch at idx {mismatch_index}: {reason}"
        )
        self.story_id = story_id
        self.raw_len = raw_len
        self.existing_len = existing_len
        self.mismatch_index = mismatch_index
        self.reason = reason


def normalize_text(text):
    """
    Normalizes dialogue text using ONLY explicitly documented normalization differences:
    - Player placeholder variants: {0} / {player} -> 主角
    - Official So-net translation normalization: 主公大人 -> 主人 (Kokkoro address)
    - Normalized whitespace & escaped newlines
    """
    if text is None:
        return ""
    w = str(text)
    w = w.replace("{0}", "主角").replace("{player}", "主角")
    w = w.replace("主公大人", "主人")
    w = w.replace("\\n", chr(10))
    w = re.sub(r"\s+", "", w)
    return w


def match_semantic_anchor(raw_elem, existing_elem):
    """
    Compares deterministic semantic anchors between raw and existing non-movie elements.
    Does NOT compare unit_id because raw intentionally lacks it.
    """
    r_type = raw_elem.get("type")
    e_type = existing_elem.get("type")

    # 1. Background
    if r_type == "background" or e_type == "background":
        if r_type != e_type:
            return False, f"type mismatch (raw={r_type}, existing={e_type})"
        r_bg = str(raw_elem.get("bg_id") or raw_elem.get("background") or "")
        e_bg = str(existing_elem.get("bg_id") or existing_elem.get("background") or "")
        if r_bg != e_bg:
            return False, f"bg_id mismatch ({r_bg} != {e_bg})"
        return True, "ok"

    # 2. Still
    if r_type == "still" or e_type == "still":
        if r_type != e_type:
            return False, f"type mismatch (raw={r_type}, existing={e_type})"
        r_st = str(raw_elem.get("still") or raw_elem.get("still_id") or "")
        e_st = str(existing_elem.get("still") or existing_elem.get("still_id") or "")
        if r_st != e_st:
            return False, f"still mismatch ({r_st} != {e_st})"
        return True, "ok"

    # 3. Dialogue
    r_is_diag = (r_type == "dialogue" or "words" in raw_elem or "name" in raw_elem)
    e_is_diag = (e_type == "dialogue" or "words" in existing_elem or "name" in existing_elem)
    if r_is_diag and e_is_diag:
        r_words = normalize_text(raw_elem.get("words"))
        e_words = normalize_text(existing_elem.get("words"))
        
        # Check voice if both present
        r_voice = raw_elem.get("voice")
        e_voice = existing_elem.get("voice")
        if r_voice and e_voice and r_voice != e_voice:
            return False, f"voice mismatch ({r_voice} != {e_voice})"

        if r_words == e_words:
            return True, "ok"

        # Check speaker name
        r_name = (raw_elem.get("name") or "").strip()
        e_name = (existing_elem.get("name") or "").strip()
        if r_name == e_name and (r_words in e_words or e_words in r_words):
            return True, "ok"
        if not r_words and not e_words:
            return True, "ok"

        return False, f"words mismatch (raw='{r_words[:25]}' != existing='{e_words[:25]}')"

    # Other matching command types
    if r_type == e_type:
        return True, "ok"

    return False, f"incompatible types (raw={r_type}, existing={e_type})"


def validate_sequence_alignment(existing_non_movies, raw_non_movies, story_id="unknown"):
    """
    Validates that non-movie elements in raw and existing sequences match 1:1.
    Returns (True, "ok") or raises AlignmentMismatchError.
    """
    if len(existing_non_movies) != len(raw_non_movies):
        raise AlignmentMismatchError(
            story_id,
            len(raw_non_movies),
            len(existing_non_movies),
            min(len(existing_non_movies), len(raw_non_movies)),
            f"length mismatch: raw={len(raw_non_movies)}, existing={len(existing_non_movies)}"
        )

    for idx, (r_elem, e_elem) in enumerate(zip(raw_non_movies, existing_non_movies)):
        ok, reason = match_semantic_anchor(r_elem, e_elem)
        if not ok:
            raise AlignmentMismatchError(
                story_id,
                len(raw_non_movies),
                len(existing_non_movies),
                idx,
                reason
            )

    return True, "ok"


def merge_movie_commands(existing_dialogues, raw_dialogues, story_id="unknown", validate_alignment=True):
    """
    Merge official movie commands from raw_dialogues into existing_dialogues.
    
    Fail-closed policy:
    - If sequence alignment cannot be confirmed, raises AlignmentMismatchError.
    - NEVER falls back to blind append.
    - Preserves all existing dialogue objects and enriched fields unchanged.
    - Idempotent: repeated runs produce identical output.
    """
    if not existing_dialogues:
        return [copy.deepcopy(x) for x in (raw_dialogues or []) if isinstance(x, dict) and x.get("type") == "movie"]
    if not raw_dialogues:
        return copy.deepcopy(existing_dialogues)

    raw_movies = []
    raw_non_movies = []
    for item in raw_dialogues:
        if isinstance(item, dict) and item.get("type") == "movie":
            raw_movies.append((len(raw_non_movies), item))
        else:
            raw_non_movies.append(item)

    if not raw_movies:
        return copy.deepcopy(existing_dialogues)

    existing_non_movies = [
        item for item in existing_dialogues 
        if not (isinstance(item, dict) and item.get("type") == "movie")
    ]

    # Validate semantic anchor alignment
    if validate_alignment:
        validate_sequence_alignment(existing_non_movies, raw_non_movies, story_id=story_id)

    # Collect existing movie IDs for deduplication
    existing_movie_ids = set()
    for item in existing_dialogues:
        if isinstance(item, dict) and item.get("type") == "movie":
            mid = item.get("movie_id")
            if mid is not None:
                existing_movie_ids.add(str(mid))

    # Group pending movies by insertion position
    movies_to_insert_at = {}
    for pos, m_item in raw_movies:
        mid = str(m_item.get("movie_id"))
        if mid not in existing_movie_ids:
            if pos not in movies_to_insert_at:
                movies_to_insert_at[pos] = []
            movies_to_insert_at[pos].append(m_item)

    if not movies_to_insert_at:
        return copy.deepcopy(existing_dialogues)

    merged = []
    curr_non_movie_count = 0

    for item in existing_dialogues:
        if isinstance(item, dict) and item.get("type") != "movie":
            if curr_non_movie_count in movies_to_insert_at:
                for m in movies_to_insert_at[curr_non_movie_count]:
                    merged.append(copy.deepcopy(m))
                    existing_movie_ids.add(str(m.get("movie_id")))
                del movies_to_insert_at[curr_non_movie_count]
            curr_non_movie_count += 1
            merged.append(copy.deepcopy(item))
        else:
            merged.append(copy.deepcopy(item))

    # Tail movie (after all non-movie elements)
    if curr_non_movie_count in movies_to_insert_at:
        for m in movies_to_insert_at[curr_non_movie_count]:
            merged.append(copy.deepcopy(m))
            existing_movie_ids.add(str(m.get("movie_id")))
        del movies_to_insert_at[curr_non_movie_count]

    # STRICT FAIL-CLOSED: if any movie remains uninserted, fail instead of blind append!
    if movies_to_insert_at:
        uninserted = [m.get("movie_id") for sublist in movies_to_insert_at.values() for m in sublist]
        raise AlignmentMismatchError(
            story_id,
            len(raw_non_movies),
            len(existing_non_movies),
            curr_non_movie_count,
            f"Unplaced movie commands cannot be positioned safely: {uninserted}"
        )

    return merged


def restore_story_file(sid, raw_dialogues, story_dir=None, canonical_dialogues=None):
    """
    Restores movie commands for a single story file safely.
    Writes strictly to dashboard/story/ (or given story_dir).
    Never writes to dist_story_map/.
    """
    target_dir = Path(story_dir) if story_dir else (ROOT / "dashboard" / "story")
    
    normalized_path = str(target_dir).replace("\\", "/")
    if "dist_story_map" in normalized_path:
        raise ValueError(f"Security violation: Cannot write to dist_story_map ({target_dir}).")

    target_file = target_dir / f"{sid}.json"

    if canonical_dialogues is not None:
        baseline_data = canonical_dialogues
    elif target_file.exists():
        with open(target_file, "r", encoding="utf-8") as fp:
            baseline_data = json.load(fp)
    else:
        baseline_data = raw_dialogues

    merged_data = merge_movie_commands(baseline_data, raw_dialogues, story_id=str(sid))

    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target_file, "w", encoding="utf-8") as fp:
        json.dump(merged_data, fp, ensure_ascii=False, indent=4)

    return merged_data
