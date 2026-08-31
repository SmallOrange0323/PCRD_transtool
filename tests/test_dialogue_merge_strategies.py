#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Unit Tests for Dialogue Merge Strategies (Phase A2)
驗證 4 種合併策略 (LEGACY, STRICT, CONCRETE_GUARD, NO_MERGE) 的精確行為契約、
Policy Blocks 分類、以及 Canonical Stream Comparison 語意
"""

import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diagnostics.investigate_dialogue_merge_strategies import (
    normalize_stream_with_metrics,
    parse_concrete_unit_id,
    extract_canonical_item,
    is_canonical_stream_equal
)

class TestDialogueMergeStrategies(unittest.TestCase):

    def test_01_same_speaker_same_unit_compatible_voice(self):
        """Test 1: same name + same concrete unit_id + compatible voice -> Legacy/Strict/Guard 全部 merge"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911, "voice": "vo_1"},
            {"name": "可可蘿", "words": "今天也要加油喔。", "unit_id": 105911, "voice": "vo_1"}
        ]
        res_leg, m_leg, h_leg, b_leg = normalize_stream_with_metrics(raw, "LEGACY")
        res_str, m_str, h_str, b_str = normalize_stream_with_metrics(raw, "STRICT")
        res_grd, m_grd, h_grd, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 1)
        self.assertEqual(len(res_str), 1)
        self.assertEqual(len(res_grd), 1)
        self.assertEqual(h_grd, 0)
        self.assertEqual(len(b_grd), 0)

    def test_02_same_speaker_different_unit_id(self):
        """Test 2: same name + different concrete unit_id -> Legacy merge (Hazard), Strict NO, Guard NO"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
            {"name": "可可蘿", "words": "衣服換好了。", "unit_id": 105931}
        ]
        res_leg, m_leg, h_leg, b_leg = normalize_stream_with_metrics(raw, "LEGACY")
        res_str, m_str, h_str, b_str = normalize_stream_with_metrics(raw, "STRICT")
        res_grd, m_grd, h_grd, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 1)
        self.assertEqual(h_leg, 1, "Legacy 應產生 1 次 Hazard")
        self.assertEqual(len(b_leg), 0)

        self.assertEqual(len(res_str), 2, "Strict 應拒絕合併")
        self.assertEqual(h_str, 0)
        self.assertEqual(len(b_str), 1)

        self.assertEqual(len(res_grd), 2, "Guard 應拒絕合併並保護 unit_id")
        self.assertEqual(h_grd, 0)
        self.assertEqual(len(b_grd), 1)
        self.assertEqual(b_grd[0]["block_reason"], "confirmed_conflict_block")

    def test_03_previous_concrete_current_missing(self):
        """Test 3: same name + prev concrete + curr missing -> Legacy merge, Strict NO, Guard merge (Legacy)"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
            {"name": "可可蘿", "words": "今天天氣很好。"}  # no unit_id
        ]
        res_leg, _, _, b_leg = normalize_stream_with_metrics(raw, "LEGACY")
        res_str, _, _, b_str = normalize_stream_with_metrics(raw, "STRICT")
        res_grd, _, h_grd, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 1)
        self.assertEqual(len(res_str), 2, "Strict 會因 None != 105911 拒絕合併")
        self.assertEqual(len(b_str), 1)
        self.assertEqual(b_str[0]["block_reason"], "missing_id_block")

        self.assertEqual(len(res_grd), 1, "Guard 應維持 Legacy 合併決策")
        self.assertEqual(h_grd, 0)
        self.assertEqual(len(b_grd), 0)

    def test_04_previous_missing_current_concrete(self):
        """Test 4: prev missing + curr concrete -> Guard 維持 legacy merge decision"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。"},  # no unit_id
            {"name": "可可蘿", "words": "今天天氣很好。", "unit_id": 105911}
        ]
        res_leg, _, _, _ = normalize_stream_with_metrics(raw, "LEGACY")
        res_grd, _, h_grd, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 1)
        self.assertEqual(len(res_grd), 1, "Guard 應維持 Legacy 合併決策")
        self.assertEqual(h_grd, 0)
        self.assertEqual(len(b_grd), 0)

    def test_05_both_missing(self):
        """Test 5: both missing -> Guard = Legacy merge"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。"},
            {"name": "可可蘿", "words": "今天天氣很好。"}
        ]
        res_leg, _, _, _ = normalize_stream_with_metrics(raw, "LEGACY")
        res_grd, _, _, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 1)
        self.assertEqual(len(res_grd), 1)
        self.assertEqual(len(b_grd), 0)

    def test_06_different_voice_no_merge(self):
        """Test 6: different voice -> 語音不相容，所有策略皆不合併"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911, "voice": "vo_1"},
            {"name": "可可蘿", "words": "今天天氣很好。", "unit_id": 105911, "voice": "vo_2"}
        ]
        res_leg, _, _, _ = normalize_stream_with_metrics(raw, "LEGACY")
        res_grd, _, _, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 2)
        self.assertEqual(len(res_grd), 2)
        # 語音不同時 base_eligible 為 False，不計為 policy block
        self.assertEqual(len(b_grd), 0)

    def test_07_blank_row_filtering_and_subsequent_merge(self):
        """Test 7: blank row 被過濾後，後續有效台詞仍可正常合併"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
            {"name": "可可蘿", "words": "   \n\n  "},
            {"name": "可可蘿", "words": "今天天氣很好。", "unit_id": 105911}
        ]
        res_grd, _, _, _ = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")
        self.assertEqual(len(res_grd), 1)
        self.assertEqual(res_grd[0]["words"], "主人早安。\n今天天氣很好。")

    def test_08_special_item_breaks_merge(self):
        """Test 8: special item (still/bg/movie) 打斷台詞相鄰性，禁止合併"""
        raw = [
            {"name": "可可蘿", "words": "主人早安。", "unit_id": 105911},
            {"type": "background", "background": "10000"},
            {"name": "可可蘿", "words": "今天天氣很好。", "unit_id": 105911}
        ]
        res_grd, _, _, _ = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")
        self.assertEqual(len(res_grd), 3)

    def test_09_chain_merge_split_behavior(self):
        """Test 9: chain: 1001, 1002, 1002 -> Guard 應精確切成 2 筆 normalized rows"""
        raw = [
            {"name": "可可蘿", "words": "台詞 1", "unit_id": 105911},
            {"name": "可可蘿", "words": "台詞 2", "unit_id": 105931},
            {"name": "可可蘿", "words": "台詞 3", "unit_id": 105931}
        ]
        res_leg, _, h_leg, _ = normalize_stream_with_metrics(raw, "LEGACY")
        res_grd, _, h_grd, b_grd = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        self.assertEqual(len(res_leg), 1, "Legacy 會將 3 筆全部合為 1 筆")
        self.assertEqual(h_leg, 2, "Legacy 會產生 2 次 Hazard")

        self.assertEqual(len(res_grd), 2, "Guard 應產生 2 筆 (105911 獨立 1 筆, 105931 合併 1 筆)")
        self.assertEqual(res_grd[0]["unit_id"], 105911)
        self.assertEqual(res_grd[1]["unit_id"], 105931)
        self.assertEqual(res_grd[1]["words"], "台詞 2\n台詞 3")
        self.assertEqual(h_grd, 0)
        self.assertEqual(len(b_grd), 1)
        self.assertEqual(b_grd[0]["block_reason"], "confirmed_conflict_block")

    def test_10_same_speaker_same_unit_no_current_voice(self):
        """Test 10: same speaker + same unit + no-current-voice compatibility -> Guard 保留 legacy 繼承行為"""
        raw = [
            {"name": "可可蘿", "words": "台詞 1", "unit_id": 105911, "voice": "vo_1"},
            {"name": "可可蘿", "words": "台詞 2", "unit_id": 105911}  # no voice
        ]
        res_grd, _, _, _ = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")
        self.assertEqual(len(res_grd), 1)
        self.assertEqual(res_grd[0]["voice"], "vo_1")

    def test_11_chain_hazard_count_exceeds_row_delta(self):
        """Test 11: chain 1001 -> 1002 -> 1002 驗證 Hazard event 數 (2) > row delta (1)"""
        raw = [
            {"name": "可可蘿", "words": "A", "unit_id": 105911},
            {"name": "可可蘿", "words": "B", "unit_id": 105931},
            {"name": "可可蘿", "words": "C", "unit_id": 105931}
        ]
        res_leg, _, h_leg, _ = normalize_stream_with_metrics(raw, "LEGACY")
        res_grd, _, h_grd, _ = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")

        row_delta = len(res_grd) - len(res_leg)
        self.assertEqual(h_leg, 2)
        self.assertEqual(row_delta, 1)
        self.assertGreater(h_leg, row_delta, "Hazard event 數大於 output row delta，兩者不得直接相減")

    def test_12_guard_policy_block_classification(self):
        """Test 12: Guard policy block 分類為 confirmed_conflict_block"""
        raw = [
            {"name": "可可蘿", "words": "A", "unit_id": 105911},
            {"name": "可可蘿", "words": "B", "unit_id": 105931}
        ]
        _, _, _, blocks = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["block_reason"], "confirmed_conflict_block")

    def test_13_guard_missing_id_no_policy_block(self):
        """Test 13: Guard 遇到 1001 -> missing 不得產生 policy block"""
        raw = [
            {"name": "可可蘿", "words": "A", "unit_id": 105911},
            {"name": "可可蘿", "words": "B"}
        ]
        _, _, _, blocks = normalize_stream_with_metrics(raw, "CONCRETE_GUARD")
        self.assertEqual(len(blocks), 0)

    def test_14_strict_missing_id_block(self):
        """Test 14: Strict 遇到 1001 -> missing 應產生 missing_id_block"""
        raw = [
            {"name": "可可蘿", "words": "A", "unit_id": 105911},
            {"name": "可可蘿", "words": "B"}
        ]
        _, _, _, blocks = normalize_stream_with_metrics(raw, "STRICT")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["block_reason"], "missing_id_block")

    def test_15_canonical_stream_equality_ignores_analysis_fields(self):
        """Test 15: canonical stream equality 忽略 chain 與 orig_index 但比較 runtime 欄位"""
        item_a = [{"name": "可可蘿", "words": "早安", "unit_id": 105911, "orig_index": 1, "chain": [1]}]
        item_b = [{"name": "可可蘿", "words": "早安", "unit_id": 105911, "orig_index": 5, "chain": [5, 6]}]
        self.assertTrue(is_canonical_stream_equal(item_a, item_b))

    def test_16_canonical_stream_detects_content_difference_with_same_row_count(self):
        """Test 16: 行數相同但 unit_id 或 words 差異可被 is_canonical_stream_equal 檢出為 False"""
        item_a = [{"name": "可可蘿", "words": "早安", "unit_id": 105911}]
        item_b = [{"name": "可可蘿", "words": "早安", "unit_id": 105931}]
        self.assertFalse(is_canonical_stream_equal(item_a, item_b))

if __name__ == "__main__":
    unittest.main(verbosity=2)
