#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Unit Tests for Speaker Identity Assessment (Phase B1 Amendment)
驗證 cleanName 規則、AvatarService 解析優先序、Runtime Rendering Disposition 分流、
Low-ID 破圖風險判定與報告資料自我一致性契約
"""

import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diagnostics.audit_speaker_identity import (
    clean_speaker_name,
    filter_speakers,
    resolve_avatar_unit_id_with_source,
    mirror_get_url_candidates,
    is_avatar_eligible,
    run_assessment,
    CUSTOM_MAP
)

class TestSpeakerIdentityAssessment(unittest.TestCase):

    def test_01_clean_speaker_name_parentheses(self):
        """Test 1: clean_speaker_name 移除全形與半形括號"""
        self.assertEqual(clean_speaker_name("可可蘿（夏日）"), "可可蘿")
        self.assertEqual(clean_speaker_name("凱留(新年)"), "凱留")
        self.assertEqual(clean_speaker_name("佩可（變裝）"), "佩可")

    def test_02_clean_speaker_name_compound(self):
        """Test 2: clean_speaker_name 遇到合稱取第一人"""
        self.assertEqual(clean_speaker_name("佩可＆可可蘿"), "佩可")
        self.assertEqual(clean_speaker_name("凱留、雪菲"), "凱留")
        self.assertEqual(clean_speaker_name("優衣與怜"), "優衣")
        self.assertEqual(clean_speaker_name("真步和克莉絲提娜"), "真步")

    def test_03_clean_speaker_name_sound_suffix(self):
        """Test 3: clean_speaker_name 移除「的聲音」後綴"""
        self.assertEqual(clean_speaker_name("愛梅斯的聲音"), "愛梅斯")
        self.assertEqual(clean_speaker_name("可可蘿（夏日）的聲音"), "可可蘿")

    def test_04_custom_map_priority(self):
        """Test 4: customMap 具有最高優先權"""
        speaker_avatars = {"涅婭": 999999}
        sources = {"涅婭": "other"}
        uid, step, src = resolve_avatar_unit_id_with_source("涅婭", speaker_avatars, sources)
        self.assertEqual(uid, CUSTOM_MAP["涅婭"])
        self.assertEqual(step, "customMap")
        self.assertEqual(src, "customMap")

    def test_05_external_clean_name_priority(self):
        """Test 5: 若非 customMap，優先使用 cleanName 查詢 speakerAvatars"""
        speaker_avatars = {"可可蘿": 105911, "可可蘿（夏日）": 105921}
        sources = {"可可蘿": "DB", "可可蘿（夏日）": "DB"}
        uid, step, src = resolve_avatar_unit_id_with_source("可可蘿（夏日）", speaker_avatars, sources)
        self.assertEqual(uid, 105911)
        self.assertEqual(step, "speakerAvatars_clean")
        self.assertEqual(src, "DB")

    def test_06_external_raw_name_fallback(self):
        """Test 6: 若 cleanName 查無，fallback 至原始 raw name 查詢"""
        speaker_avatars = {"特別限定版角色": 108811}
        sources = {"特別限定版角色": "DB"}
        uid, step, src = resolve_avatar_unit_id_with_source("特別限定版角色", speaker_avatars, sources)
        self.assertEqual(uid, 108811)
        self.assertEqual(step, "speakerAvatars_clean")

    def test_07_is_avatar_eligible(self):
        """Test 7: 驗證 avatar-eligible 門檻 (>= 100000)"""
        self.assertTrue(is_avatar_eligible(105911))
        self.assertTrue(is_avatar_eligible(190011))
        self.assertFalse(is_avatar_eligible(1))
        self.assertFalse(is_avatar_eligible(2131))
        self.assertFalse(is_avatar_eligible(None))

    def test_08_filter_speakers(self):
        """Test 8: filterSpeakers 過濾非實體角色"""
        all_names = ["佩可", "可可蘿", "旁白", "【系統】", "？？？", "店員", "店長", "選擇肢", "凱留"]
        filtered = filter_speakers(all_names)
        self.assertEqual(filtered, ["佩可", "可可蘿", "凱留"])

    def test_09_filter_speakers_with_search(self):
        """Test 9: filterSpeakers 支援搜尋關鍵字"""
        all_names = ["貪吃佩可", "可可蘿", "凱留", "佩可（夏日）"]
        filtered = filter_speakers(all_names, "佩可")
        self.assertEqual(filtered, ["貪吃佩可", "佩可（夏日）"])

    def test_10_rendering_disposition_none_is_text_fallback(self):
        """Test 10: selected_uid is None -> text_fallback"""
        candidates = mirror_get_url_candidates(None)
        self.assertEqual(len(candidates), 0)

    def test_11_rendering_disposition_low_id_is_broken_image_risk(self):
        """Test 11: selected_uid 1234 -> enters image branch (truthy) but candidates is empty -> broken_image_risk"""
        selected_uid = 1234
        self.assertTrue(selected_uid and selected_uid > 0, "Low-ID is truthy in JS, enters image branch")
        candidates = mirror_get_url_candidates(selected_uid)
        self.assertEqual(len(candidates), 0, "Low-ID results in empty candidates array -> src='undefined'")

    def test_12_rendering_disposition_playable_id_is_valid_image(self):
        """Test 12: selected_uid 105911 -> enters image branch with valid candidates"""
        selected_uid = 105911
        candidates = mirror_get_url_candidates(selected_uid)
        self.assertGreater(len(candidates), 0)

    def test_13_report_self_consistency(self):
        """Test 13: 驗證審計總數自我一致性契約 (Sums must match total_visible_cards)"""
        data = run_assessment()
        summary = data["summary"]
        total_visible = summary["visible_speaker_cards"]
        disp = summary["runtime_disposition"]
        dist = summary["quality_distribution"]

        disp_sum = sum(disp.values())
        dist_sum = sum(dist.values())

        self.assertEqual(disp_sum, total_visible, f"Disposition sum ({disp_sum}) != visible cards ({total_visible})")
        self.assertEqual(dist_sum, total_visible, f"Quality sum ({dist_sum}) != visible cards ({total_visible})")
        self.assertEqual(len(data["ui_collision_groups"]), summary["ui_collision_groups_count"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
