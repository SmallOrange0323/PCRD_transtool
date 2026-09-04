#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_story_parity_validation.py
=====================================
Unit tests for the permanent source <-> dist story parity validation gate.
Covers all requirements A through J plus historical regression failure injection.
"""

import unittest
import json
import tempfile
from pathlib import Path

from pipeline.validate import validate_story_source_dist_parity, ValidationResult


class TestStoryParityValidation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.src_dir = self.base_path / "source_story"
        self.dist_dir = self.base_path / "dist_story"
        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.dist_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_story(self, target_dir: Path, sid: int, content: list, indent: int = 2):
        file_path = target_dir / f"{sid}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=indent)

    def test_A_identical_source_dist_pass(self):
        """A. identical source/dist -> PASS"""
        story_data = [
            {"type": "background", "bg_id": "500010"},
            {"type": "dialogue", "name": "佩可", "words": "嗨！", "unit_id": 105812},
            {"type": "movie", "movie_id": "2001001"}
        ]
        self._write_story(self.src_dir, 2001001, story_data)
        self._write_story(self.dist_dir, 2001001, story_data)

        # Include auxiliary non-numeric file which must be ignored
        (self.src_dir / "speaker_appearance.json").write_text("{}", encoding="utf-8")

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertTrue(passed)
        self.assertTrue(res.is_valid)
        self.assertEqual(stats["source_stories"], 1)
        self.assertEqual(stats["dist_stories"], 1)
        self.assertEqual(stats["unit_id_mismatches"], 0)
        self.assertEqual(stats["dialogue_mismatches"], 0)
        self.assertEqual(stats["movie_mismatches"], 0)

    def test_B_dist_missing_numeric_story_fail(self):
        """B. dist missing numeric story -> FAIL"""
        story_data = [{"type": "dialogue", "name": "佩可", "words": "嗨！", "unit_id": 105812}]
        self._write_story(self.src_dir, 2001001, story_data)
        self._write_story(self.src_dir, 2001002, story_data)
        self._write_story(self.dist_dir, 2001001, story_data)  # 2001002 missing in dist

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertIn(2001002, stats["missing_in_dist"])

    def test_C_dist_contains_extra_numeric_story_fail(self):
        """C. dist contains extra numeric story -> FAIL"""
        story_data = [{"type": "dialogue", "name": "佩可", "words": "嗨！", "unit_id": 105812}]
        self._write_story(self.src_dir, 2001001, story_data)
        self._write_story(self.dist_dir, 2001001, story_data)
        self._write_story(self.dist_dir, 2001003, story_data)  # Extra story in dist

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertIn(2001003, stats["extra_in_dist"])

    def test_D_source_has_unit_id_but_dist_loses_it_fail(self):
        """D. source has unit_id but dist loses it -> FAIL"""
        src_data = [
            {"type": "dialogue", "name": "凱留", "words": "什麼？", "unit_id": 106011}
        ]
        dist_data = [
            {"type": "dialogue", "name": "凱留", "words": "什麼？"}  # unit_id lost
        ]
        self._write_story(self.src_dir, 2001001, src_data)
        self._write_story(self.dist_dir, 2001001, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["unit_id_mismatches"], 1)

    def test_E_same_unit_id_count_but_different_sequence_value_fail(self):
        """E. same unit_id count but different sequence/value -> FAIL"""
        src_data = [
            {"type": "dialogue", "name": "A", "words": "1", "unit_id": 100111},
            {"type": "dialogue", "name": "B", "words": "2", "unit_id": 100211}
        ]
        dist_data = [
            {"type": "dialogue", "name": "A", "words": "1", "unit_id": 100211},  # Swapped values
            {"type": "dialogue", "name": "B", "words": "2", "unit_id": 100111}
        ]
        self._write_story(self.src_dir, 2001001, src_data)
        self._write_story(self.dist_dir, 2001001, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["unit_id_mismatches"], 1)

    def test_F_source_dialogue_rows_exist_but_dist_loses_type_dialogue_fail(self):
        """F. source dialogue rows exist but dist loses type='dialogue' -> FAIL"""
        src_data = [
            {"type": "dialogue", "name": "可可蘿", "words": "主人。", "unit_id": 105911}
        ]
        dist_data = [
            {"name": "可可蘿", "words": "主人。", "unit_id": 105911}  # Missing type="dialogue"
        ]
        self._write_story(self.src_dir, 2001001, src_data)
        self._write_story(self.dist_dir, 2001001, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["dialogue_mismatches"], 1)

    def test_G_movie_missing_from_dist_fail(self):
        """G. movie missing from dist -> FAIL"""
        src_data = [
            {"type": "movie", "movie_id": "200100001"},
            {"type": "dialogue", "name": "佩可", "words": "好吃！", "unit_id": 105812}
        ]
        dist_data = [
            {"type": "dialogue", "name": "佩可", "words": "好吃！", "unit_id": 105812}
        ]
        self._write_story(self.src_dir, 2001001, src_data)
        self._write_story(self.dist_dir, 2001001, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["movie_mismatches"], 1)

    def test_H_movie_added_only_in_dist_fail(self):
        """H. movie added only in dist -> FAIL"""
        src_data = [
            {"type": "dialogue", "name": "佩可", "words": "好吃！", "unit_id": 105812}
        ]
        dist_data = [
            {"type": "movie", "movie_id": "extra_mov"},
            {"type": "dialogue", "name": "佩可", "words": "好吃！", "unit_id": 105812}
        ]
        self._write_story(self.src_dir, 2001001, src_data)
        self._write_story(self.dist_dir, 2001001, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["movie_mismatches"], 1)

    def test_I_movie_order_changed_fail(self):
        """I. movie order changed -> FAIL"""
        src_data = [
            {"type": "movie", "movie_id": "mov_1"},
            {"type": "movie", "movie_id": "mov_2"}
        ]
        dist_data = [
            {"type": "movie", "movie_id": "mov_2"},
            {"type": "movie", "movie_id": "mov_1"}
        ]
        self._write_story(self.src_dir, 2001001, src_data)
        self._write_story(self.dist_dir, 2001001, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["movie_mismatches"], 1)

    def test_J_unrelated_formatting_or_indentation_difference_pass(self):
        """J. unrelated formatting / harmless JSON indentation difference -> PASS"""
        data = [
            {"type": "dialogue", "name": "佩可", "words": "好吃！", "unit_id": 105812, "custom_flag": True}
        ]
        # Source formatted with indent=4, dist formatted with compact indent=0
        self._write_story(self.src_dir, 2001001, data, indent=4)
        self._write_story(self.dist_dir, 2001001, data, indent=0)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertTrue(passed)
        self.assertTrue(res.is_valid)
        self.assertEqual(stats["unit_id_mismatches"], 0)
        self.assertEqual(stats["dialogue_mismatches"], 0)
        self.assertEqual(stats["movie_mismatches"], 0)

    def test_10_failure_injection_historical_regression_detected(self):
        """10. Failure injection test: prove validator detects the exact historical regression fixture."""
        # Source is enriched Story Map JSON:
        src_data = [
            {
                "type": "dialogue",
                "name": "佩可",
                "words": "好久不見！",
                "unit_id": 105812,
                "voice": "vo_1001"
            }
        ]
        # Dist was overwritten by raw AssetBundle parser output (lacking type="dialogue" and unit_id):
        dist_data = [
            {
                "name": "佩可",
                "words": "好久不見！",
                "voice": "vo_1001"
            }
        ]
        self._write_story(self.src_dir, 2201002, src_data)
        self._write_story(self.dist_dir, 2201002, dist_data)

        res = ValidationResult()
        passed, stats = validate_story_source_dist_parity(self.src_dir, self.dist_dir, result=res, verbose=False)

        self.assertFalse(passed)
        self.assertFalse(res.is_valid)
        self.assertEqual(stats["unit_id_mismatches"], 1)
        self.assertEqual(stats["dialogue_mismatches"], 1)
        self.assertTrue(any("unit_id parity mismatch" in err for err in res.errors))


if __name__ == "__main__":
    unittest.main()
