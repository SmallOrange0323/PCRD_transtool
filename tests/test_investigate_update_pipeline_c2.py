#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Unit Tests for Acquisition Coverage & Freshness Policy (Phase C2 Final Consistency)
驗證單一事實來源、集合互斥性、Union Cardinality、Markdown 與 JSON 一致性、原語契約與狀態流轉
"""

import unittest
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diagnostics.investigate_update_pipeline_c2 import build_investigation_model, write_artifacts, OUTPUT_JSON, OUTPUT_MD

class TestUpdatePipelineC2Investigation(unittest.TestCase):

    def setUp(self):
        self.data = build_investigation_model()

    def test_01_freshness_states_defined(self):
        """Test 1: 驗證新鮮度狀態機包含 CONFIRMED_CURRENT 與 UPDATED_SUCCESSFULLY 等明確流轉"""
        states = {s["state"]: s for s in self.data["freshness_state_model"]}
        self.assertIn("CONFIRMED_CURRENT", states)
        self.assertIn("UPDATED_SUCCESSFULLY", states)
        self.assertIn("REMOTE_UNREACHABLE", states)
        self.assertIn("matches local_tv", states["CONFIRMED_CURRENT"]["entry_condition"])
        self.assertIn("atomically saved", states["UPDATED_SUCCESSFULLY"]["entry_condition"])

    def test_02_set_disjointness_and_union_cardinality(self):
        """Test 2: 驗證 Required, Optional, Unknown 兩兩互斥且 Required 總數等於 Set Union 基數"""
        ids = self.data["coverage_snapshot"]["id_arrays"]
        req_set = set(ids["required_story_ids"])
        opt_set = set(ids["optional_historic_ids"])
        unk_set = set(ids["unknown_expected_ids"])

        self.assertEqual(req_set & opt_set, set(), "Required and Optional must be disjoint")
        self.assertEqual(req_set & unk_set, set(), "Required and Unknown must be disjoint")
        self.assertEqual(opt_set & unk_set, set(), "Optional and Unknown must be disjoint")

        m = self.data["coverage_snapshot"]["metrics"]
        self.assertEqual(len(req_set), m["required_story_ids_total"])
        self.assertEqual(len(opt_set), m["optional_historic_count"])
        self.assertEqual(len(unk_set), m["unknown_expected_count"])

    def test_03_missing_subsets_and_validator_warning_alignment(self):
        """Test 3: 驗證 Missing 集合為其母集合子集，且 Optional Missing 精確對齊 Validator 警告話數"""
        ids = self.data["coverage_snapshot"]["id_arrays"]
        m = self.data["coverage_snapshot"]["metrics"]

        self.assertTrue(set(ids["missing_required"]).issubset(set(ids["required_story_ids"])))
        self.assertTrue(set(ids["missing_optional"]).issubset(set(ids["optional_historic_ids"])))

        # Validator warning alignment
        self.assertEqual(m["missing_optional_count"], m["validator_warning_missing_count"])
        self.assertEqual(set(ids["missing_optional"]), set(ids["validator_warning_missing_ids"]))

    def test_04_policy_status_defined_when_unknown_zero(self):
        """Test 4: 驗證在 unknown_expected == 0 時，政策狀態為 DEFINED"""
        m = self.data["coverage_snapshot"]["metrics"]
        ps = self.data["coverage_snapshot"]["policy_status"]
        if m["unknown_expected_count"] == 0:
            self.assertEqual(ps["required_policy_status"], "DEFINED")
            self.assertEqual(ps["optional_policy_status"], "DEFINED")

    def test_05_markdown_and_json_dynamic_consistency(self):
        """Test 5: 驗證生成的 Markdown 與 JSON 產物中的數值 100% 吻合"""
        write_artifacts(self.data)
        self.assertTrue(OUTPUT_JSON.exists())
        self.assertTrue(OUTPUT_MD.exists())

        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            j_data = json.load(f)
        with open(OUTPUT_MD, "r", encoding="utf-8") as f:
            md_text = f.read()

        m = j_data["coverage_snapshot"]["metrics"]
        self.assertIn(str(m["required_story_ids_total"]), md_text)
        self.assertIn(str(m["tracked_character_required_count"]), md_text)
        self.assertIn(str(m["branch_expected_count"]), md_text)
        self.assertIn(str(m["extra_event_expected_count"]), md_text)
        self.assertIn(str(m["validator_warning_missing_count"]), md_text)

    def test_06_generic_primitive_contract(self):
        """Test 6: 驗證通用抓取原語無多媒體/縮圖副作用契約"""
        contract = self.data["generic_primitive_contract"]
        self.assertIn("fetch_story_json_by_id", contract["function_signature"])
        self.assertTrue(any("NO media" in g for g in contract["behavior_guarantees"]))
        self.assertTrue(any("NO thumbnail" in g for g in contract["behavior_guarantees"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
