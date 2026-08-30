# -*- coding: utf-8 -*-
"""
單元測試：_get_story_ids_from_db 邏輯驗證
測試 DB-backed 路徑與 DB 查無資料時之 fallback 契約。
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.pcrd_fetch import _get_story_ids_from_db

class TestStoryIdFallback(unittest.TestCase):
    def test_db_backed_ids(self):
        """DB 中有資料的角色 (美穗 139201, 真穗 139301) 應回傳標準 4 話 7 位數 ID"""
        ids_1392 = _get_story_ids_from_db(139201)
        self.assertEqual(ids_1392, [1392001, 1392002, 1392003, 1392004])

        ids_1393 = _get_story_ids_from_db(139301)
        self.assertEqual(ids_1393, [1393001, 1393002, 1393003, 1393004])

    def test_fallback_canonical_7_digit_only(self):
        """DB 中無資料的角色 (如 艾麗卡 139401) fallback 應只回傳標準 4 話 7 位數 ID"""
        ids_1394 = _get_story_ids_from_db(139401)
        self.assertEqual(ids_1394, [1394001, 1394002, 1394003, 1394004])
        self.assertEqual(len(ids_1394), 4)

        # 驗證完全不包含 8 位數 legacy IDs (1394011 ~ 1394014)
        for legacy_id in [1394011, 1394012, 1394013, 1394014]:
            self.assertNotIn(legacy_id, ids_1394)

    def test_fallback_arbitrary_unit_id(self):
        """任意未實裝之 unit_id 均應回傳正確之 7 位數推算 ID"""
        ids_dummy = _get_story_ids_from_db(199901)
        self.assertEqual(ids_dummy, [1999001, 1999002, 1999003, 1999004])

if __name__ == '__main__':
    unittest.main()
