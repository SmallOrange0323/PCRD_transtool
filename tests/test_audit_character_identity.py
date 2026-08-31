#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Unit Tests for Character Identity Audit Engine (Phase A1)
驗證 audit_character_identity.py 的 clean_name 邏輯、unit_id 解析、合併危害偵測與嚴謹碰撞分類
"""

import unittest
import tempfile
import json
from pathlib import Path
import sys

# 將專案根目錄與 tools 加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diagnostics.audit_character_identity import (
    clean_name,
    parse_concrete_unit_id,
    run_identity_audit
)

class TestCharacterIdentityAudit(unittest.TestCase):

    def test_01_same_raw_name_same_unit_id_not_multi_unit(self):
        """Test 1: 同一 raw name、相同 unit_id 不應被判定為 multi-unit risk"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
                {"name": "可可蘿", "words": "今天也要加油喔。", "unit_id": 105911}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["same_name_multiple_unit_ids"]), 0)

    def test_02_same_raw_name_different_unit_id_detected(self):
        """Test 2: 同一 raw name、不同 unit_id 應被精確檢出"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
                {"name": "佩可", "words": "哇～好棒！", "unit_id": 105811},
                {"name": "可可蘿", "words": "這是儀式服裝。", "unit_id": 105931}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["same_name_multiple_unit_ids"]), 1)
            entry = result["same_name_multiple_unit_ids"][0]
            self.assertEqual(entry["raw_name"], "可可蘿")
            self.assertEqual(entry["distinct_unit_id_count"], 2)

    def test_03_clean_name_classification_rules(self):
        """Test 3: 驗證 cleanName 嚴謹分級 (HIGH / MEDIUM / LOW / UNKNOWN)"""
        # Test A: Raw A {1001}, Raw B {2001} -> HIGH (Disjoint pair)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿（儀式服）", "words": "儀式開始。", "unit_id": 105931},
                {"name": "可可蘿（公主）", "words": "公主型態！", "unit_id": 105941}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["clean_name_collisions"]), 1)
            col = result["clean_name_collisions"][0]
            self.assertEqual(col["clean_key"], "可可蘿")
            self.assertEqual(col["risk_level"], "HIGH")
            self.assertEqual(len(col["disjoint_pairs"]), 1)

        # Test B: Raw A {1001, 1002}, Raw B {1002} -> MEDIUM (Overlap / Subset)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿（常規）", "words": "主人早安。", "unit_id": 105911},
                {"name": "可可蘿（常規）", "words": "主人再見。", "unit_id": 105912},
                {"name": "可可蘿", "words": "今天也要加油喔。", "unit_id": 105912}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            col = result["clean_name_collisions"][0]
            self.assertEqual(col["risk_level"], "MEDIUM")
            self.assertEqual(len(col["disjoint_pairs"]), 0)

        # Test C: Raw A {1001}, Raw B {1001} -> LOW (Identical sets)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿（常規）", "words": "主人早安。", "unit_id": 105911},
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            col = result["clean_name_collisions"][0]
            self.assertEqual(col["risk_level"], "LOW")

        # Test D: Raw A {1001}, Raw B missing-only -> MEDIUM
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿（常規）", "words": "主人早安。", "unit_id": 105911},
                {"name": "可可蘿", "words": "主人早安。"}  # no unit_id
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            col = result["clean_name_collisions"][0]
            self.assertEqual(col["risk_level"], "MEDIUM")

        # Test E: Raw A missing-only, Raw B missing-only -> UNKNOWN
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿（常規）", "words": "主人早安。"},
                {"name": "可可蘿", "words": "主人早安。"}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            col = result["clean_name_collisions"][0]
            self.assertEqual(col["risk_level"], "UNKNOWN")

    def test_04_normalizer_merge_hazard_detected(self):
        """Test 4: same name + different unit_id + voice-compatible 應偵測為 normalizer merge hazard"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911, "voice": "vo_1"},
                {"name": "可可蘿", "words": "衣服換好了。", "unit_id": 105931, "voice": "vo_1"}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["normalizer_merge_hazards"]), 1)
            hazard = result["normalizer_merge_hazards"][0]
            self.assertEqual(hazard["prev_unit_id"], 105911)
            self.assertEqual(hazard["curr_unit_id"], 105931)

    def test_05_normalizer_incompatible_voice_not_merge_hazard(self):
        """Test 5: same name + different unit_id + incompatible voice 不符合合併條件，不應構成 hazard"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911, "voice": "vo_1"},
                {"name": "可可蘿", "words": "衣服換好了。", "unit_id": 105931, "voice": "vo_2"}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["normalizer_merge_hazards"]), 0)

    def test_06_special_item_prevents_merge(self):
        """Test 6: special item (still/background) 夾在中間時不符合連線相鄰合併條件"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
                {"type": "background", "background": "10000"},
                {"name": "可可蘿", "words": "衣服換好了。", "unit_id": 105931}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["normalizer_merge_hazards"]), 0)

    def test_07_blank_dialogue_filtering(self):
        """Test 7: 純空白或純換行對白被過濾，不影響後續有效合併判斷"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            story_data = [
                {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
                {"name": "可可蘿", "words": "   \n\n  ", "unit_id": 105999},  # 純空白行，應被跳過
                {"name": "可可蘿", "words": "衣服換好了。", "unit_id": 105931}
            ]
            (tmp_path / "1000101.json").write_text(json.dumps(story_data), encoding="utf-8")
            result = run_identity_audit(tmp_path)
            self.assertEqual(len(result["normalizer_merge_hazards"]), 1)

    def test_08_missing_unit_id_no_false_concrete_identity(self):
        """Test 8: 缺失 / null / 0 / 非法 unit_id 不得被視為 concrete unit_id"""
        self.assertIsNone(parse_concrete_unit_id(None))
        self.assertIsNone(parse_concrete_unit_id(0))
        self.assertIsNone(parse_concrete_unit_id("0"))
        self.assertIsNone(parse_concrete_unit_id(""))
        self.assertIsNone(parse_concrete_unit_id("abc"))
        self.assertEqual(parse_concrete_unit_id(105911), 105911)
        self.assertEqual(parse_concrete_unit_id("105911"), 105911)

    def test_09_compound_speaker_name_and_parentheses(self):
        """Test 9: 驗證 clean_name 拆分合稱 (、＆&和與)、去除括號與結尾「的聲音」之行為"""
        self.assertEqual(clean_name("佩可＆凱留"), "佩可")
        self.assertEqual(clean_name("可可蘿、優衣"), "可可蘿")
        self.assertEqual(clean_name("優衣&怜"), "優衣")
        self.assertEqual(clean_name("佩可和優衣"), "佩可")
        self.assertEqual(clean_name("凱留與佩可"), "凱留")
        self.assertEqual(clean_name("可可蘿（公主）"), "可可蘿")
        self.assertEqual(clean_name("可可蘿(公主)"), "可可蘿")
        self.assertEqual(clean_name("霸瞳皇帝的聲音"), "霸瞳皇帝")
        self.assertEqual(clean_name("可可蘿（儀式服）的聲音"), "可可蘿")

if __name__ == "__main__":
    unittest.main(verbosity=2)
