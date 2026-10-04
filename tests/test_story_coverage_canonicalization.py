# -*- coding: utf-8 -*-
"""
測試 Canonical Story Universe 的 Story ID 型態規整化 (Story ID Canonicalization Regression Tests)

驗證範圍：
1. canonical_story_id 能正確將 int、str 解析為 canonical int。
2. canonical_story_id 面對 None、空字串、含文字的非法 ID 時嚴格 fail-closed 拋出 ValueError。
3. build_canonical_story_universe 回傳之所有 story_id 均為 int 型態。
4. 消除 799 個 false-positive missing stories（如 2000001, 2000002 不會因為 str vs int 被誤判為 missing）。
5. 驗證當 SQLite 回傳字串格式之 story_id 時，與 local_present 集合 (int) 能正確命中且不會產生 false missing。
"""

import unittest
import sqlite3
import tempfile
import json
from pathlib import Path

from pipeline.coverage import (
    canonical_story_id,
    build_canonical_story_universe,
    analyze_coverage,
    CanonicalStoryUniverse,
    CoverageResult,
)


class TestStoryCoverageCanonicalization(unittest.TestCase):
    """驗證 coverage 模組中的 canonical story ID contract。"""

    def test_canonical_story_id_valid_values(self):
        """驗證有效整數與數字字串均正確轉型為 int。"""
        self.assertEqual(canonical_story_id(2000001), 2000001)
        self.assertEqual(canonical_story_id("2000001"), 2000001)
        self.assertEqual(canonical_story_id(" 2000001 "), 2000001)
        self.assertEqual(canonical_story_id(100101), 100101)
        self.assertEqual(canonical_story_id("00600025"), 600025)

    def test_canonical_story_id_fail_closed_on_invalid(self):
        """驗證非法值、None、空字串必須 fail-closed 拋出 ValueError。"""
        with self.assertRaises(ValueError):
            canonical_story_id(None)

        with self.assertRaises(ValueError):
            canonical_story_id("")

        with self.assertRaises(ValueError):
            canonical_story_id("   ")

        with self.assertRaises(ValueError):
            canonical_story_id("2000001_extra")

        with self.assertRaises(ValueError):
            canonical_story_id("abc")

    def test_universe_required_ids_contract(self):
        """驗證全量 build_canonical_story_universe 的 required_ids 集合元素型態全為 int。"""
        univ = build_canonical_story_universe()
        self.assertIsInstance(univ, CanonicalStoryUniverse)
        
        for sid in univ.required_ids:
            self.assertIsInstance(sid, int, f"required_id {sid!r} 必須為 int，實際為 {type(sid)}")

        for sid in univ.optional_ids:
            self.assertIsInstance(sid, int, f"optional_id {sid!r} 必須為 int，實際為 {type(sid)}")

    def test_no_false_positive_missing_for_existing_stories(self):
        """驗證 2000001、2000002 等已存在劇本不在 missing_required_ids 之中，且 missing_required_count 必為 0。"""
        res = analyze_coverage()
        self.assertIsInstance(res, CoverageResult)

        # 2000001 與 2000002 是主線第一章第 1、2 話，repo 中必定存在
        self.assertNotIn(2000001, res.missing_required_ids)
        self.assertNotIn(2000002, res.missing_required_ids)
        self.assertNotIn("2000001", res.missing_required_ids)
        self.assertNotIn("2000002", res.missing_required_ids)

        # 核心必備劇本缺失數必須為 0（徹底消除 799 false positives）
        self.assertEqual(res.missing_required_count, 0, f"必備劇本缺失數必須為 0，實際為 {res.missing_required_count}")

    def test_mock_isolated_coverage_string_db_interop(self):
        """
        在完全隔離的暫存環境下驗證：
        當 SQLite 中的 story_id 以 TEXT 存儲時，
        coverage 分析與磁碟上的 <story_id>.json (int 解析) 比對，
        能精確識別已存在者，不會產生型態不匹配的假缺失。
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            data_dir = tmp_path / "data"
            story_dir = tmp_path / "story"
            data_dir.mkdir(parents=True)
            story_dir.mkdir(parents=True)

            # 建立隔離 SQLite，寫入 TEXT 格式之 story_id
            db_path = tmp_path / "redive_tw.db"
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("CREATE TABLE story_detail (story_id TEXT PRIMARY KEY, title TEXT)")
            cur.execute("CREATE TABLE chara_story_status (story_id TEXT PRIMARY KEY, status INTEGER)")
            # 插入兩筆 TEXT 格式主線 (2000001, 2000002)
            cur.execute("INSERT INTO story_detail VALUES ('2000001', '第一話')")
            cur.execute("INSERT INTO story_detail VALUES ('2000002', '第二話')")
            conn.commit()
            conn.close()

            # 建立空的 json metadata 檔案以通過分析驗證
            with open(data_dir / "tracked_characters.json", "w", encoding="utf-8") as f:
                json.dump({"characters": []}, f)
            with open(data_dir / "branch_stories.json", "w", encoding="utf-8") as f:
                json.dump({"stories": []}, f)
            with open(data_dir / "extra_events.json", "w", encoding="utf-8") as f:
                json.dump({"stories": []}, f)

            # 在 story 目錄下建立 2000001.json (代表本機已存在 2000001，但缺少 2000002)
            with open(story_dir / "2000001.json", "w", encoding="utf-8") as f:
                json.dump({"id": 2000001, "lines": []}, f)

            # 執行分析
            res = analyze_coverage(dashboard_dir=tmp_path)

            # 2000001 已存在，不可在 missing 中
            self.assertNotIn(2000001, res.missing_required_ids)
            # 2000002 真正缺失，必須在 missing 中且型態為 int
            self.assertIn(2000002, res.missing_required_ids)
            self.assertEqual(res.missing_required_count, 1)


if __name__ == "__main__":
    unittest.main()
