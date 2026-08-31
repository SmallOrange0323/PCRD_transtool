#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Unit Tests for Phase C2 Minimal Implementation (Amended)
驗證 Freshness Result / Gate、Generic Story JSON Primitive、Coverage Integrity / Source Health、
Unknown Coverage Gate、Mirror-Lag Defense (UPDATE_DOWNLOADED_UNCONFIRMED)、Dry-run Zero Write 與 Deploy Override 邊界
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.coverage import (
    evaluate_freshness,
    analyze_coverage,
    FreshnessStatus,
    FreshnessResult,
    CoverageResult,
    CoverageAnalysisStatus
)
from pipeline.fetch import fetch_story_json_by_id, StoryFetchResult, load_story_manifest_hash_map
from pipeline.update import run_pipeline_update, check_and_sync_upstream, save_truth_version_state

class TestUpdatePipelineC2Implementation(unittest.TestCase):

    def test_01_freshness_evaluation_matrix(self):
        """Test 1: 驗證新鮮度狀態機流轉邏輯"""
        # A. Remote == Local -> CONFIRMED_CURRENT
        r1 = evaluate_freshness("00600023", "00600023", True)
        self.assertEqual(r1.status, FreshnessStatus.CONFIRMED_CURRENT)
        self.assertTrue(r1.confirmed)
        self.assertFalse(r1.update_required)

        # B. Remote != Local -> UPDATE_AVAILABLE
        r2 = evaluate_freshness("00600024", "00600023", True)
        self.assertEqual(r2.status, FreshnessStatus.UPDATE_AVAILABLE)
        self.assertTrue(r2.confirmed)
        self.assertTrue(r2.update_required)

        # C. Remote None + Local DB Exists -> REMOTE_UNREACHABLE (Degraded)
        r3 = evaluate_freshness(None, "00600023", True)
        self.assertEqual(r3.status, FreshnessStatus.REMOTE_UNREACHABLE)
        self.assertFalse(r3.confirmed)
        self.assertTrue(r3.degraded)

        # D. Remote None + DB Missing -> LOCAL_STATE_MISSING
        r4 = evaluate_freshness(None, None, False)
        self.assertEqual(r4.status, FreshnessStatus.LOCAL_STATE_MISSING)
        self.assertFalse(r4.confirmed)
        self.assertTrue(r4.update_required)

    def test_02_coverage_analysis_contract_and_source_health(self):
        """Test 2: 驗證 CoverageResult 契約、分析完整度與來源健康狀態"""
        cov = analyze_coverage()
        self.assertIsInstance(cov, CoverageResult)
        self.assertEqual(cov.analysis_status, CoverageAnalysisStatus.VALID)
        self.assertEqual(cov.source_status["database"], "OK")
        self.assertEqual(cov.source_status["tracked_characters"], "OK")
        self.assertEqual(cov.source_status["branch_stories"], "OK")
        self.assertEqual(cov.source_status["extra_events"], "OK")
        self.assertGreater(cov.local_present_count, 0)
        self.assertGreater(cov.required_total_count, 0)
        self.assertGreater(cov.optional_total_count, 0)
        self.assertEqual(cov.missing_required_count, 0)
        self.assertEqual(cov.unknown_expected_count, 0)
        self.assertEqual(cov.policy_status["required_policy_status"], "DEFINED")
        self.assertEqual(cov.policy_status["optional_policy_status"], "DEFINED")

    @patch("urllib.request.urlopen")
    def test_03_load_story_manifest_hash_map(self, mock_urlopen):
        """Test 3: 驗證 Manifest 解析字典輸出"""
        mock_data = b"Resources/00600023/Jpn/AssetBundles/Android/manifest/storydata_2001001.unity3d,1234,aabbccdd11223344\n"
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_data
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        hash_map = load_story_manifest_hash_map("00600023")
        self.assertIn(2001001, hash_map)
        self.assertEqual(hash_map[2001001], "aabbccdd11223344")

    @patch("pcrd_fetch.load_story_manifest_hash_map")
    @patch("urllib.request.urlopen")
    @patch("pcrd_fetch._parse_bundle_dialogues")
    def test_04_fetch_story_json_by_id_success_and_atomic_write(self, mock_parse, mock_urlopen, mock_manifest):
        """Test 4: 驗證 fetch_story_json_by_id 成功抓取與原子寫入"""
        virtual_story_id = 99999991
        mock_manifest.return_value = {virtual_story_id: "1234567890abcdef"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"MOCK_BUNDLE_DATA"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        mock_parse.return_value = [{"speaker": "可可蘿", "text": "主人您好。"}]

        with tempfile.TemporaryDirectory() as tmp_dir:
            import pcrd_fetch
            orig_story_dir = pcrd_fetch.STORY_DIR
            pcrd_fetch.STORY_DIR = tmp_dir
            try:
                res = fetch_story_json_by_id(virtual_story_id, manifest_hash_map={virtual_story_id: "1234567890abcdef"})
                self.assertEqual(res.status, "OK")
                self.assertEqual(res.dialogue_count, 1)
                self.assertEqual(res.hash, "1234567890abcdef")
                self.assertTrue(os.path.exists(os.path.join(tmp_dir, f"{virtual_story_id}.json")))
                with open(os.path.join(tmp_dir, f"{virtual_story_id}.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data[0]["speaker"], "可可蘿")
            finally:
                pcrd_fetch.STORY_DIR = orig_story_dir

    def test_05_fetch_story_json_by_id_hash_not_found(self):
        """Test 5: 驗證 Hash 缺失時回傳 HASH_NOT_FOUND 且不 sys.exit"""
        res = fetch_story_json_by_id(99999999, manifest_hash_map={})
        self.assertEqual(res.status, "HASH_NOT_FOUND")
        self.assertIn("無法在 Manifest 中找到", res.error_message)

    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.run_deploy")
    def test_06_deploy_freshness_gate_blocks_unconfirmed(self, mock_deploy, mock_validate, mock_bundle, mock_sync):
        """Test 6: 驗證新鮮度未確認時 auto_deploy 預設阻斷 (BLOCK DEPLOY)"""
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.REMOTE_UNREACHABLE,
                remote_version=None,
                local_version="00600023",
                confirmed=False,
                update_required=False,
                degraded=True,
                message="Remote unreachable"
            ),
            analyze_coverage()
        )
        mock_bundle.return_value = True
        mock_validate.return_value = True

        # Default: auto_deploy without override -> return 1 and DO NOT call deploy
        code = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=False)
        self.assertEqual(code, 1)
        mock_deploy.assert_not_called()

        # With override: auto_deploy with allow_unconfirmed_freshness -> call deploy
        mock_deploy.return_value = True
        code_override = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=True)
        self.assertEqual(code_override, 0)
        mock_deploy.assert_called_once()

    def test_07_coverage_only_cli_zero_write(self):
        """Test 7: 驗證 --coverage 唯讀執行返回 0"""
        code = run_pipeline_update(check_coverage_only=True)
        self.assertEqual(code, 0)

    @patch("pipeline.coverage.DB_PATH", Path("non_existent_db_for_test.db"))
    def test_08_authoritative_db_failure_marks_invalid(self):
        """Test 8: 驗證資料庫不存在或損毀時標記 INVALID 且政策狀態為 UNRESOLVED"""
        cov = analyze_coverage()
        self.assertEqual(cov.analysis_status, CoverageAnalysisStatus.INVALID)
        self.assertIn("MISSING", cov.source_status["database"])
        self.assertEqual(cov.policy_status["required_policy_status"], "UNRESOLVED")

    @patch("pipeline.coverage.DATA_DIR", Path("non_existent_data_dir_for_test"))
    def test_09_authoritative_metadata_failure_marks_degraded(self):
        """Test 9: 驗證元數據缺失或解析異常時標記 DEGRADED 且政策狀態為 PARTIAL"""
        cov = analyze_coverage()
        self.assertEqual(cov.analysis_status, CoverageAnalysisStatus.DEGRADED)
        self.assertEqual(cov.policy_status["required_policy_status"], "PARTIAL")

    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.run_deploy")
    def test_10_unknown_coverage_blocks_deploy(self, mock_deploy, mock_validate, mock_bundle, mock_sync):
        """Test 10: 驗證存在未分類話數 (Unknown > 0) 時阻斷生產發布"""
        cov = analyze_coverage()
        cov.unknown_expected_count = 5  # mock unknown exists
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.CONFIRMED_CURRENT,
                remote_version="00600023",
                local_version="00600023",
                confirmed=True,
                update_required=False,
                degraded=False,
                message="Confirmed current"
            ),
            cov
        )
        mock_bundle.return_value = True
        mock_validate.return_value = True

        code = run_pipeline_update(dry_run=False, auto_deploy=True)
        self.assertEqual(code, 1)
        mock_deploy.assert_not_called()

    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.run_deploy")
    def test_11_degraded_coverage_blocks_deploy_even_with_freshness_override(self, mock_deploy, mock_validate, mock_bundle, mock_sync):
        """Test 11: 驗證覆蓋率分析降級 (DEGRADED) 時發布阻斷，且 --allow-unconfirmed-freshness 無法覆蓋"""
        cov = analyze_coverage()
        cov.analysis_status = CoverageAnalysisStatus.DEGRADED
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.CONFIRMED_CURRENT,
                remote_version="00600023",
                local_version="00600023",
                confirmed=True,
                update_required=False,
                degraded=False,
                message="Confirmed current"
            ),
            cov
        )
        mock_bundle.return_value = True
        mock_validate.return_value = True

        code = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=True)
        self.assertEqual(code, 1)
        mock_deploy.assert_not_called()

    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.run_deploy")
    def test_12_valid_deploy_path_calls_deploy(self, mock_deploy, mock_validate, mock_bundle, mock_sync):
        """Test 12: 驗證所有門禁均通過時，正常進入 deploy 呼叫"""
        cov = analyze_coverage()
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.CONFIRMED_CURRENT,
                remote_version="00600023",
                local_version="00600023",
                confirmed=True,
                update_required=False,
                degraded=False,
                message="Confirmed current"
            ),
            cov
        )
        mock_bundle.return_value = True
        mock_validate.return_value = True
        mock_deploy.return_value = True

        code = run_pipeline_update(dry_run=False, auto_deploy=True)
        self.assertEqual(code, 0)
        mock_deploy.assert_called_once()

    @patch("pipeline.fetch.get_truth_version", return_value="00600024")
    @patch("pipeline.fetch.update_db")
    def test_13_mirror_unproven_db_update_marks_unconfirmed_and_blocks_deploy(self, mock_update_db, mock_get_tv):
        """Test 13: 驗證鏡像 DB 更新後標記 UPDATE_DOWNLOADED_UNCONFIRMED 且阻斷自動發布"""
        mock_update_db.return_value = None
        ok, freshness, cov = check_and_sync_upstream(dry_run=False)
        self.assertTrue(ok)
        self.assertEqual(freshness.status, FreshnessStatus.UPDATE_DOWNLOADED_UNCONFIRMED)
        self.assertFalse(freshness.confirmed)
        self.assertTrue(freshness.degraded)

        # auto_deploy must be blocked by default
        with patch("pipeline.update.bundle_story_map", return_value=True), \
             patch("pipeline.update.validate_story_map", return_value=True), \
             patch("pipeline.update.run_deploy") as mock_deploy:
            code = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=False)
            self.assertEqual(code, 1)
            mock_deploy.assert_not_called()

    @patch("pipeline.fetch.get_truth_version", return_value="00600024")
    @patch("pipeline.fetch.update_db")
    def test_14_mirror_unproven_db_update_with_override_passes_freshness(self, mock_update_db, mock_get_tv):
        """Test 14: 驗證鏡像未證實更新在帶入 --allow-unconfirmed-freshness 時可通過發布 (在 coverage VALID 下)"""
        mock_update_db.return_value = None
        with patch("pipeline.update.bundle_story_map", return_value=True), \
             patch("pipeline.update.validate_story_map", return_value=True), \
             patch("pipeline.update.run_deploy", return_value=True) as mock_deploy:
            code = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=True)
            self.assertEqual(code, 0)
            mock_deploy.assert_called_once()

    def test_15_save_truth_version_state_empty_string_fails(self):
        """Test 15: 驗證 save_truth_version_state 空字串防禦"""
        saved = save_truth_version_state("")
        self.assertFalse(saved)

if __name__ == "__main__":
    unittest.main(verbosity=2)
