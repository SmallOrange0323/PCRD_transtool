# -*- coding: utf-8 -*-
"""
tests/test_movie_restore.py
===========================
Focused regression tests for movie restoration and identity preservation.

Tests cover:
A. Movie merge preservation: unit_id and type are preserved when merging raw dialogues
B. Idempotence: running movie merge twice produces identical output
C. No duplicate movie commands
D. Correct relative movie position
E. Restore scripts must not write dist_story_map
F. ROOT must be repository-relative (not hardcoded)
"""

import unittest
import copy
import json
import tempfile
from pathlib import Path

from tools.movie_restore_core import (
    ROOT,
    merge_movie_commands,
    restore_story_file
)


class TestMovieRestore(unittest.TestCase):

    def test_A_movie_merge_preservation(self):
        """
        A. Movie merge preservation:
        Given an existing dialogue with unit_id: 105812, type: 'dialogue',
        and raw AssetBundle dialogue lacking unit_id,
        merge MUST preserve unit_id == 105812 and type == 'dialogue',
        while inserting the official movie command.
        """
        existing = [
            {"type": "background", "bg_id": "500030"},
            {
                "type": "dialogue",
                "name": "貪吃佩可",
                "words": "好吃到要融化了～！",
                "unit_id": 105812,
                "voice": "vo_test_001"
            }
        ]
        raw = [
            {"type": "background", "bg_id": "500030"},
            {"type": "movie", "movie_id": "200100001"},
            {
                "name": "貪吃佩可",
                "words": "好吃到要融化了～！",
                "voice": "vo_test_001"
            }
        ]

        merged = merge_movie_commands(existing, raw)

        # 驗證總長度為 3
        self.assertEqual(len(merged), 3)
        # 驗證 movie 成功插入在第 1 個位置
        self.assertEqual(merged[1].get("type"), "movie")
        self.assertEqual(merged[1].get("movie_id"), "200100001")
        # 驗證 dialogue 屬性完好保留
        dialogue_item = merged[2]
        self.assertEqual(dialogue_item.get("type"), "dialogue")
        self.assertEqual(dialogue_item.get("unit_id"), 105812)
        self.assertEqual(dialogue_item.get("name"), "貪吃佩可")
        self.assertEqual(dialogue_item.get("words"), "好吃到要融化了～！")
        self.assertEqual(dialogue_item.get("voice"), "vo_test_001")

    def test_B_idempotence(self):
        """
        B. Idempotence:
        Running movie merge twice MUST produce identical results.
        """
        existing = [
            {"type": "background", "bg_id": "500030"},
            {"type": "dialogue", "name": "可可蘿", "words": "主人。", "unit_id": 105911}
        ]
        raw = [
            {"type": "movie", "movie_id": "200100001"},
            {"type": "background", "bg_id": "500030"},
            {"name": "可可蘿", "words": "主人。"}
        ]

        first_run = merge_movie_commands(existing, raw)
        second_run = merge_movie_commands(first_run, raw)

        self.assertEqual(first_run, second_run)

    def test_C_no_duplicate_movie_commands(self):
        """
        C. No duplicate movie commands:
        If a movie already exists in the dialogue sequence, it must not be re-inserted.
        """
        existing = [
            {"type": "movie", "movie_id": "200100001"},
            {"type": "dialogue", "name": "凱留", "words": "真拿你沒辦法。", "unit_id": 106011}
        ]
        raw = [
            {"type": "movie", "movie_id": "200100001"},
            {"name": "凱留", "words": "真拿你沒辦法。"}
        ]

        merged = merge_movie_commands(existing, raw)
        movie_items = [x for x in merged if isinstance(x, dict) and x.get("type") == "movie"]

        self.assertEqual(len(movie_items), 1)
        self.assertEqual(movie_items[0].get("movie_id"), "200100001")

    def test_D_correct_relative_movie_position(self):
        """
        D. Correct relative movie position:
        Test head, middle, and tail movie positions.
        """
        existing = [
            {"type": "dialogue", "name": "A", "words": "line 1", "unit_id": 100111},
            {"type": "dialogue", "name": "B", "words": "line 2", "unit_id": 100211},
            {"type": "dialogue", "name": "C", "words": "line 3", "unit_id": 100311}
        ]
        raw = [
            {"type": "movie", "movie_id": "head_mov"},
            {"name": "A", "words": "line 1"},
            {"type": "movie", "movie_id": "mid_mov"},
            {"name": "B", "words": "line 2"},
            {"name": "C", "words": "line 3"},
            {"type": "movie", "movie_id": "tail_mov"}
        ]

        merged = merge_movie_commands(existing, raw)

        self.assertEqual(len(merged), 6)
        self.assertEqual(merged[0], {"type": "movie", "movie_id": "head_mov"})
        self.assertEqual(merged[1].get("name"), "A")
        self.assertEqual(merged[2], {"type": "movie", "movie_id": "mid_mov"})
        self.assertEqual(merged[3].get("name"), "B")
        self.assertEqual(merged[4].get("name"), "C")
        self.assertEqual(merged[5], {"type": "movie", "movie_id": "tail_mov"})

    def test_E_restore_scripts_must_not_write_dist_story_map(self):
        """
        E. Restore scripts must not write dist_story_map:
        Passing a path containing 'dist_story_map' to restore_story_file MUST raise ValueError.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            dist_path = Path(tmpdir) / "dist_story_map" / "story"
            dist_path.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(ValueError):
                restore_story_file(2001001, [], story_dir=dist_path)

    def test_F_root_must_be_repository_relative(self):
        """
        F. ROOT must be repository-relative:
        ROOT must exist, contain 'dashboard' and 'pipeline', and not contain hardcoded OneDrive paths
        if checked from source files.
        """
        self.assertTrue(ROOT.exists())
        self.assertTrue((ROOT / "dashboard").is_dir())
        self.assertTrue((ROOT / "pipeline").is_dir())

        # 檢查 restore 工具腳本內無硬編碼路徑
        tool_files = [
            ROOT / "tools" / "movie_restore_core.py",
            ROOT / "tools" / "restore_part1_part2_movies.py",
            ROOT / "tools" / "restore_part3_movie_dialogues.py",
            ROOT / "tools" / "repair_story_identities.py"
        ]
        for tf in tool_files:
            if tf.exists():
                content = tf.read_text(encoding="utf-8")
                self.assertNotIn("OneDrive - 寰宇知識科技", content, f"Hardcoded path found in {tf.name}")


if __name__ == "__main__":
    unittest.main()
