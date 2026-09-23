#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Focused unit tests for extra_story_index validator (Phase 3 Part B, C, D).
驗證:
PASS:
- 現有 extra_story_index.json 完全合約通過

FAIL:
- duplicate story ID across categories
- expected_count mismatch
- invalid representative path
- representative file missing
- story entry 出現 still_id / bg_id / thumbnail_id (Asset mixing 防禦)
- Anniversary anchors != 10
- Anniversary child expansion != 126
- special 1001～1005 被加上 representativeStoryThumbnail
"""

import sys
import copy
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.validate import validate_extra_story_index, DASHBOARD_DIR


class TestExtraStoryValidator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.index_path = DASHBOARD_DIR / "data" / "extra_story_index.json"
        with open(cls.index_path, "r", encoding="utf-8") as f:
            cls.canonical_data = json.load(f)
        cls.db_path = DASHBOARD_DIR / "redive_tw.db"
        cls.story_dir = DASHBOARD_DIR / "story"

    def test_canonical_extra_story_index_passes(self):
        """驗證現有 extra_story_index.json 完全符合契約 PASS"""
        ok, errors = validate_extra_story_index(
            self.canonical_data,
            base_dir=DASHBOARD_DIR,
            db_path=self.db_path,
            story_dir=self.story_dir
        )
        self.assertTrue(ok, f"Canonical data failed validation: {errors}")
        self.assertEqual(len(errors), 0)

    def test_future_growth_story_count_increase_passes(self):
        """PASS: 驗證未來營運中 official category 增加話數時，validator 正常放行 (不鎖定 432/14/5 全域總數)"""
        data = copy.deepcopy(self.canonical_data)
        luna_cat = next(c for c in data["official_categories"] if c["id"] == "luna_tower")
        synthetic_story_id = 7099999
        luna_cat["stories"].append({
            "id": synthetic_story_id,
            "title": "未來擴充期數第 1 話",
            "provenance": "future expansion test"
        })
        luna_cat["expected_count"] += 1

        ok, errors = validate_extra_story_index(
            data,
            base_dir=DASHBOARD_DIR,
            db_path=self.db_path,
            story_dir=self.story_dir
        )
        self.assertTrue(ok, f"Future growth index failed validation: {errors}")
        self.assertEqual(len(errors), 0)

    def test_fail_duplicate_story_id_across_categories(self):
        """FAIL: 跨分類出現重複的 story ID"""
        data = copy.deepcopy(self.canonical_data)
        # 把 dimension_fault 的 4009001 複製加入到 arena 中
        dup_id = 4009001
        arena_cat = next(c for c in data["official_categories"] if c["id"] == "arena")
        arena_cat["stories"].append({"id": dup_id, "title": "重複話數", "provenance": "test"})
        arena_cat["expected_count"] += 1
        data["official_categories"] = [c if c["id"] != "arena" else arena_cat for c in data["official_categories"]]

        ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
        self.assertFalse(ok)
        self.assertTrue(any("重複出現" in err and str(dup_id) in err for err in errors), errors)

    def test_fail_expected_count_mismatch(self):
        """FAIL: expected_count 與實際 stories 數量不符"""
        data = copy.deepcopy(self.canonical_data)
        # 修改 luna_tower expected_count
        luna_cat = next(c for c in data["official_categories"] if c["id"] == "luna_tower")
        luna_cat["expected_count"] = 999

        ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
        self.assertFalse(ok)
        self.assertTrue(any("expected_count" in err and "999" in err for err in errors), errors)

    def test_fail_invalid_representative_path_format(self):
        """FAIL: representativeStoryThumbnail 路徑格式不合法"""
        data = copy.deepcopy(self.canonical_data)
        # 設定非合法 prefix 或副檔名
        dungeon_cat = next(c for c in data["official_categories"] if c["id"] == "dungeon")
        dungeon_cat["representativeStoryThumbnail"] = "images/dungeon.png"

        ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
        self.assertFalse(ok)
        self.assertTrue(any("representativeStoryThumbnail 路徑格式不合法" in err for err in errors), errors)

    def test_fail_representative_file_missing(self):
        """FAIL: representativeStoryThumbnail 指向不存在的本地檔案"""
        data = copy.deepcopy(self.canonical_data)
        dungeon_cat = next(c for c in data["official_categories"] if c["id"] == "dungeon")
        dungeon_cat["representativeStoryThumbnail"] = "icon/exstory_top/999999.webp"

        ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
        self.assertFalse(ok)
        self.assertTrue(any("本地檔案不存在" in err and "999999.webp" in err for err in errors), errors)

    def test_fail_story_entry_with_forbidden_asset_fields(self):
        """FAIL: story entry 出現 still_id / bg_id / thumbnail_id / representativeStoryThumbnail"""
        for forbidden_key in ["still_id", "bg_id", "thumbnail_id", "representativeStoryThumbnail"]:
            with self.subTest(forbidden_key=forbidden_key):
                data = copy.deepcopy(self.canonical_data)
                first_cat = data["official_categories"][0]
                first_cat["stories"][0][forbidden_key] = 12345

                ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
                self.assertFalse(ok)
                self.assertTrue(any("違規包含混合資產欄位" in err and forbidden_key in err for err in errors), errors)

    def test_fail_anniversary_anchors_not_ten(self):
        """FAIL: Anniversary anchors 數量不為 10"""
        data = copy.deepcopy(self.canonical_data)
        anniv_cat = next(c for c in data["official_categories"] if c["id"] == "anniversary_countdown")
        anniv_cat["stories"] = anniv_cat["stories"][:9]
        anniv_cat["expected_count"] = 9

        ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
        self.assertFalse(ok)
        self.assertTrue(any("anniversary_countdown" in err and "10" in err for err in errors), errors)

    def test_fail_anniversary_child_expansion_not_126(self):
        """FAIL: Anniversary child expansion 展開數量不為 126"""
        data = copy.deepcopy(self.canonical_data)
        anniv_cat = next(c for c in data["official_categories"] if c["id"] == "anniversary_countdown")
        # 把最後一個 anchor 改為一個不存在或只對應極少話數的 anchor (如 9100001)
        anniv_cat["stories"][9] = {"id": 9100001, "title": "偽造 anchor", "provenance": "test"}

        ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
        self.assertFalse(ok)
        self.assertTrue(any("展開 child episodes 總數不符 126" in err or "story_group_id 數量不符 10" in err for err in errors), errors)

    def test_fail_special_categories_given_representative_thumbnail(self):
        """FAIL: 特殊分類 1001~1005 (grand_masters, karyl_yabaival, gindaco_oedo_summer) 被違規加上 representativeStoryThumbnail"""
        for special_id in ["grand_masters", "karyl_yabaival", "gindaco_oedo_summer"]:
            with self.subTest(special_id=special_id):
                data = copy.deepcopy(self.canonical_data)
                sp_cat = next(c for c in data["special_categories"] if c["id"] == special_id)
                sp_cat["representativeStoryThumbnail"] = "icon/story/1001001.webp"

                ok, errors = validate_extra_story_index(data, base_dir=DASHBOARD_DIR, db_path=self.db_path, story_dir=self.story_dir)
                self.assertFalse(ok)
                self.assertTrue(any("為 text-only，嚴禁設定 representativeStoryThumbnail" in err and special_id in err for err in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
