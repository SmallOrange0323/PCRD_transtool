# -*- coding: utf-8 -*-
"""
tests/test_movie_restore.py
===========================
Comprehensive regression tests for safe movie restoration and story identity preservation.

Covers all 10 specifications from External Review:
1. Unaffected story is NOT written by repair
2. Affected story is repaired
3. Audit mode performs zero writes
4. Alignment mismatch refuses modification
5. No fallback append on mismatch
6. Known aligned sequence inserts movie at correct position
7. Idempotence
8. unit_id/type preservation
9. Repeated movie_id behavior matches raw audit result
10. dist_story_map writes remain strictly prohibited
"""

import unittest
import sys
import copy
import json
import tempfile
import subprocess
from pathlib import Path

from tools.repair_story_identities import audit_and_repair
from tools.movie_restore_core import (
    ROOT,
    KNOWN_GOOD_IDENTITY_BASELINE,
    merge_movie_commands,
    restore_story_file,
    validate_sequence_alignment,
    AlignmentMismatchError
)


class TestMovieRestoreComprehensive(unittest.TestCase):

    def test_01_unaffected_story_not_written_by_repair(self):
        """1. Unaffected story is NOT written by repair (apply=True): files with complete unit_ids are touched 0 times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir)
            test_file = story_dir / "2201002.json"
            clean_data = [
                {"type": "dialogue", "name": "佩可", "words": "嗨！", "unit_id": 105812}
            ]
            test_file.write_text(json.dumps(clean_data), encoding="utf-8")
            mtime_before = test_file.stat().st_mtime_ns
            content_before = test_file.read_text(encoding="utf-8")

            def mock_loader(ref, rel):
                return copy.deepcopy(clean_data)

            stats = audit_and_repair(
                story_dir=story_dir,
                apply=True,
                baseline_loader=mock_loader,
                story_files=["story/2201002.json"],
                verbose=False
            )

            self.assertEqual(stats["stories_audited"], 1)
            self.assertEqual(stats["stories_affected"], 0)
            self.assertEqual(stats["stories_written"], 0)
            self.assertEqual(stats["unaffected_rewritten"], 0)
            self.assertEqual(test_file.stat().st_mtime_ns, mtime_before)
            self.assertEqual(test_file.read_text(encoding="utf-8"), content_before)

    def test_02_affected_story_is_repaired(self):
        """2. Affected story is repaired (apply=True): degraded story lacking unit_id is restored from canonical baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir)
            test_file = story_dir / "2201002.json"
            canonical = [
                {"type": "background", "bg_id": "500030"},
                {"type": "dialogue", "name": "佩可", "words": "很好吃！", "unit_id": 105812}
            ]
            degraded = [
                {"type": "background", "bg_id": "500030"},
                {"type": "movie", "movie_id": "200100001"},
                {"name": "佩可", "words": "很好吃！"}
            ]
            test_file.write_text(json.dumps(degraded), encoding="utf-8")

            def mock_loader(ref, rel):
                return copy.deepcopy(canonical)

            stats = audit_and_repair(
                story_dir=story_dir,
                apply=True,
                baseline_loader=mock_loader,
                story_files=["story/2201002.json"],
                verbose=False
            )

            self.assertEqual(stats["stories_audited"], 1)
            self.assertEqual(stats["stories_affected"], 1)
            self.assertEqual(stats["stories_repairable"], 1)
            self.assertEqual(stats["stories_skipped_alignment"], 0)
            self.assertEqual(stats["stories_written"], 1)

            repaired_on_disk = json.loads(test_file.read_text(encoding="utf-8"))
            self.assertEqual(len(repaired_on_disk), 3)
            self.assertEqual(repaired_on_disk[1]["type"], "movie")
            self.assertEqual(repaired_on_disk[1]["movie_id"], "200100001")
            self.assertEqual(repaired_on_disk[2]["type"], "dialogue")
            self.assertEqual(repaired_on_disk[2]["unit_id"], 105812)

    def test_03_audit_mode_zero_writes(self):
        """3. Audit mode performs zero writes (apply=False): --audit produces zero filesystem modifications even on affected stories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir)
            test_file = story_dir / "2201002.json"
            canonical = [
                {"type": "background", "bg_id": "500030"},
                {"type": "dialogue", "name": "佩可", "words": "很好吃！", "unit_id": 105812}
            ]
            degraded = [
                {"type": "background", "bg_id": "500030"},
                {"type": "movie", "movie_id": "200100001"},
                {"name": "佩可", "words": "很好吃！"}
            ]
            test_file.write_text(json.dumps(degraded), encoding="utf-8")
            mtime_before = test_file.stat().st_mtime_ns
            content_before = test_file.read_text(encoding="utf-8")

            def mock_loader(ref, rel):
                return copy.deepcopy(canonical)

            stats = audit_and_repair(
                story_dir=story_dir,
                apply=False,
                baseline_loader=mock_loader,
                story_files=["story/2201002.json"],
                verbose=False
            )

            self.assertEqual(stats["stories_audited"], 1)
            self.assertEqual(stats["stories_affected"], 1)
            self.assertEqual(stats["stories_repairable"], 1)
            self.assertEqual(stats["stories_written"], 0)
            self.assertEqual(test_file.stat().st_mtime_ns, mtime_before)
            self.assertEqual(test_file.read_text(encoding="utf-8"), content_before)

    def test_04_alignment_mismatch_refuses_modification(self):
        """4. Alignment mismatch refuses modification: raises AlignmentMismatchError and leaves data untouched on disk (apply=True)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            story_dir = Path(tmpdir)
            test_file = story_dir / "2201002.json"
            canonical = [
                {"type": "background", "bg_id": "500030"},
                {"type": "dialogue", "name": "佩可", "words": "吃飽了！", "unit_id": 105812}
            ]
            mismatched_raw = [
                {"type": "background", "bg_id": "999999"},  # Mismatch
                {"type": "movie", "movie_id": "200100001"},
                {"name": "佩可", "words": "吃飽了！"}
            ]
            test_file.write_text(json.dumps(mismatched_raw), encoding="utf-8")
            mtime_before = test_file.stat().st_mtime_ns
            content_before = test_file.read_text(encoding="utf-8")

            def mock_loader(ref, rel):
                return copy.deepcopy(canonical)

            stats = audit_and_repair(
                story_dir=story_dir,
                apply=True,
                baseline_loader=mock_loader,
                story_files=["story/2201002.json"],
                verbose=False
            )

            self.assertEqual(stats["stories_audited"], 1)
            self.assertEqual(stats["stories_affected"], 1)
            self.assertEqual(stats["stories_repairable"], 0)
            self.assertEqual(stats["stories_skipped_alignment"], 1)
            self.assertEqual(stats["stories_written"], 0)
            self.assertEqual(len(stats["mismatch_details"]), 1)
            self.assertEqual(stats["mismatch_details"][0][0], "2201002")

            # File on disk must remain strictly untouched
            self.assertEqual(test_file.stat().st_mtime_ns, mtime_before)
            self.assertEqual(test_file.read_text(encoding="utf-8"), content_before)

            # Direct unit assertion for merge_movie_commands
            with self.assertRaises(AlignmentMismatchError):
                merge_movie_commands(canonical, mismatched_raw, story_id="2201002", validate_alignment=True)

    def test_05_no_fallback_append_on_mismatch(self):
        """5. No fallback append on mismatch: fail closed instead of blindly appending movies."""
        canonical = [
            {"type": "dialogue", "name": "A", "words": "Line 1", "unit_id": 100111}
        ]
        mismatched_raw = [
            {"type": "dialogue", "name": "B", "words": "Line 2"}, # Content mismatch
            {"type": "movie", "movie_id": "mov_err"}
        ]

        with self.assertRaises(AlignmentMismatchError):
            merge_movie_commands(canonical, mismatched_raw, story_id="test_05")

    def test_06_known_aligned_sequence_inserts_movie_at_correct_position(self):
        """6. Known aligned sequence inserts movie at correct relative position (head, mid, tail)."""
        existing = [
            {"type": "background", "bg_id": "500010"},
            {"type": "dialogue", "name": "凱留", "words": "什麼啊？", "unit_id": 106011},
            {"type": "still", "still": "st_01"}
        ]
        raw = [
            {"type": "movie", "movie_id": "head_mov"},
            {"type": "background", "bg_id": "500010"},
            {"type": "movie", "movie_id": "mid_mov"},
            {"name": "凱留", "words": "什麼啊？"},
            {"type": "still", "still": "st_01"},
            {"type": "movie", "movie_id": "tail_mov"}
        ]

        merged = merge_movie_commands(existing, raw)
        self.assertEqual(len(merged), 6)
        self.assertEqual(merged[0]["movie_id"], "head_mov")
        self.assertEqual(merged[2]["movie_id"], "mid_mov")
        self.assertEqual(merged[5]["movie_id"], "tail_mov")
        # Existing attributes intact
        self.assertEqual(merged[3]["unit_id"], 106011)

    def test_07_idempotence(self):
        """7. Idempotence: running movie merge multiple times produces identical output."""
        existing = [
            {"type": "background", "bg_id": "500010"},
            {"type": "dialogue", "name": "可可蘿", "words": "主人。", "unit_id": 105911}
        ]
        raw = [
            {"type": "movie", "movie_id": "200100001"},
            {"type": "background", "bg_id": "500010"},
            {"name": "可可蘿", "words": "主人。"}
        ]

        res1 = merge_movie_commands(existing, raw)
        res2 = merge_movie_commands(res1, raw)
        self.assertEqual(res1, res2)

    def test_08_unit_id_type_preservation(self):
        """8. unit_id and type preservation: enriched attributes are 100% preserved."""
        existing = [
            {
                "type": "dialogue",
                "name": "貪吃佩可",
                "words": "好棒！",
                "unit_id": 105812,
                "voice": "vo_101",
                "custom_field": "preserved"
            }
        ]
        raw = [
            {"name": "貪吃佩可", "words": "好棒！"}
        ]
        merged = merge_movie_commands(existing, raw)
        self.assertEqual(merged[0]["type"], "dialogue")
        self.assertEqual(merged[0]["unit_id"], 105812)
        self.assertEqual(merged[0]["custom_field"], "preserved")

    def test_09_repeated_movie_id_behavior_matches_raw_audit(self):
        """9. Repeated movie_id behavior: deduplicates when duplicate movie command is passed."""
        existing = [
            {"type": "movie", "movie_id": "dup_mov"},
            {"type": "dialogue", "name": "優衣", "words": "佑樹君。", "unit_id": 100211}
        ]
        raw = [
            {"type": "movie", "movie_id": "dup_mov"},
            {"name": "優衣", "words": "佑樹君。"}
        ]
        merged = merge_movie_commands(existing, raw)
        movies = [x for x in merged if isinstance(x, dict) and x.get("type") == "movie"]
        self.assertEqual(len(movies), 1)

    def test_10_dist_story_map_writes_remain_prohibited(self):
        """10. dist_story_map writes remain strictly prohibited."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dist_path = Path(tmpdir) / "dist_story_map" / "story"
            dist_path.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(ValueError) as ctx:
                restore_story_file(2001001, [], story_dir=dist_path)
            self.assertIn("Security violation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
