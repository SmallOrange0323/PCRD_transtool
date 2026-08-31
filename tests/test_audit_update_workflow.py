#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Unit Tests for Update Workflow Audit (Phase C1 Reproducibility Polish)
驗證權威命令地圖、發布同步邊界 (Sync Boundary)、上游同步標記 (performs_upstream_sync)、
雙倉庫架構與可重現性發布流程
"""

import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diagnostics.audit_update_workflow import audit_workflow

class TestUpdateWorkflowAudit(unittest.TestCase):

    def setUp(self):
        self.data = audit_workflow()

    def test_01_command_sync_classification(self):
        """Test 1: 驗證全流程更新與純發布命令之上游同步職責分離"""
        cmd_map = {c["role"]: c for c in self.data["command_map"]}
        self.assertTrue(cmd_map["CANONICAL_UPDATE_ORCHESTRATOR"]["performs_upstream_sync"])
        self.assertFalse(cmd_map["DEPLOY_ONLY_PRIMITIVE"]["performs_upstream_sync"])
        self.assertFalse(cmd_map["DETERMINISTIC_BUNDLER_ONLY"]["performs_upstream_sync"])

    def test_02_release_synchronization_boundary(self):
        """Test 2: 驗證發布同步邊界不變式 (來源提交後禁止二次上游同步)"""
        sync_bound = self.data["repo_architecture"]["synchronization_boundary"]
        self.assertTrue(sync_bound["source_sync_before_commit"])
        self.assertFalse(sync_bound["full_update_after_commit_allowed"])
        self.assertTrue(sync_bound["deploy_only_after_commit"])
        self.assertTrue(any("pipeline.bundle" in step for step in sync_bound["preferred_final_flow"]))
        self.assertTrue(any("pipeline.deploy" in step for step in sync_bound["preferred_final_flow"]))

    def test_03_tool_duty_classification(self):
        """Test 3: 驗證各工具職責分類精確性"""
        tool_map = {t["tool_name"]: t for t in self.data["tool_classification"]}
        self.assertEqual(tool_map["fetch-stories"]["classification"], "DOWNLOAD_JSON_CHARACTER_ONLY")
        self.assertEqual(tool_map["sync-episode"]["classification"], "DOWNLOAD_JSON_SINGLE_EPISODE")
        self.assertEqual(tool_map["scan-cdn"]["classification"], "DISCOVERY_ONLY")
        self.assertEqual(tool_map["fetch-story-voices"]["classification"], "DOWNLOAD_MEDIA_ONLY")
        self.assertEqual(tool_map["fetch-story-images"]["classification"], "DOWNLOAD_MEDIA_ONLY")

    def test_04_story_acquisition_matrix_has_verified_paths(self):
        """Test 4: 驗證各故事類別之抓取路徑不含虛構指令"""
        matrix = {row["story_type"]: row for row in self.data["story_type_matrix"]}
        self.assertIn("Character Story (個人劇情)", matrix)
        self.assertIn("fetch-stories --unit-id", matrix["Character Story (個人劇情)"]["verified_acquisition_path"])
        self.assertIn("sync-episode --story-id", matrix["Main Story (主線劇情)"]["verified_acquisition_path"])

    def test_05_validator_semantics_source_subset_of_dist(self):
        """Test 5: 驗證 validator dist 關係為單向子集包含 (Source <= Dist) 與 DB 查詢描述"""
        val = self.data["validator_coverage"]
        self.assertIn("SOURCE_SUBSET_OF_DIST", val["dist_relationship"])
        self.assertFalse(val["extra_dist_stories_rejected"])
        self.assertIn("queries unit_data count", val["db_query_semantics"])

    def test_06_idempotence_partially_verified(self):
        """Test 6: 驗證冪等性宣告為 PARTIALLY_VERIFIED"""
        self.assertIn("PARTIALLY_VERIFIED", self.data["idempotence_status"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
