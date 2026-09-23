#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Focused tests for Freshness Direction & Bounded Version Comparison.
驗證:
1. remote == local -> CONFIRMED_CURRENT
2. remote > local  -> UPDATE_AVAILABLE (update_required=True, confirmed=True)
3. remote < local  -> REMOTE_BEHIND_LOCAL (update_required=False, confirmed=False, degraded=True)
4. check_and_sync_upstream 在 remote < local 時不呼叫 update_db()
5. remote < local 時生產部署門禁預設阻擋，但 --allow-unconfirmed-freshness 可手動覆蓋
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.coverage import evaluate_freshness, FreshnessStatus, FreshnessResult, analyze_coverage
from pipeline.fetch import TruthVersionProbeResult
from pipeline.update import check_and_sync_upstream, run_pipeline_update


class TestFreshnessDirection(unittest.TestCase):

    def test_remote_equals_local_is_confirmed_current(self):
        """remote=00610002, local=00610002 -> CONFIRMED_CURRENT"""
        res = evaluate_freshness("00610002", "00610002", db_exists=True)
        self.assertEqual(res.status, FreshnessStatus.CONFIRMED_CURRENT)
        self.assertTrue(res.confirmed)
        self.assertFalse(res.update_required)
        self.assertFalse(res.degraded)
        self.assertEqual(res.remote_version, "00610002")
        self.assertEqual(res.local_version, "00610002")

    def test_remote_greater_than_local_is_update_available(self):
        """remote=00610003, local=00610002 -> UPDATE_AVAILABLE"""
        res = evaluate_freshness("00610003", "00610002", db_exists=True)
        self.assertEqual(res.status, FreshnessStatus.UPDATE_AVAILABLE)
        self.assertTrue(res.confirmed)
        self.assertTrue(res.update_required)
        self.assertFalse(res.degraded)
        self.assertEqual(res.remote_version, "00610003")
        self.assertEqual(res.local_version, "00610002")

    def test_remote_less_than_local_is_remote_behind_local(self):
        """remote=00600025, local=00610002 -> REMOTE_BEHIND_LOCAL"""
        res = evaluate_freshness("00600025", "00610002", db_exists=True)
        self.assertEqual(res.status, FreshnessStatus.REMOTE_BEHIND_LOCAL)
        self.assertFalse(res.confirmed)
        self.assertFalse(res.update_required)
        self.assertTrue(res.degraded)
        self.assertIn("remote version is older than local recorded version", res.message)
        self.assertEqual(res.remote_version, "00600025")
        self.assertEqual(res.local_version, "00610002")

    @patch("pipeline.fetch.probe_truth_version", return_value=TruthVersionProbeResult("00600025", "remote_wthee_api", True))
    @patch("pipeline.fetch.update_db")
    def test_check_and_sync_upstream_does_not_call_update_db_when_remote_behind_local(self, mock_update_db, mock_probe):
        """驗證 check_and_sync_upstream 在 remote < local (00600025 < 00610002) 時不呼叫 update_db()"""
        ok, freshness, cov = check_and_sync_upstream(dry_run=False)
        self.assertTrue(ok)
        self.assertEqual(freshness.status, FreshnessStatus.REMOTE_BEHIND_LOCAL)
        self.assertFalse(freshness.confirmed)
        self.assertFalse(freshness.update_required)
        self.assertTrue(freshness.degraded)
        # 嚴格驗證: 絕對不得調用 update_db()
        mock_update_db.assert_not_called()

    @patch("pipeline.fetch.probe_truth_version", return_value=TruthVersionProbeResult("00600025", "remote_wthee_api", True))
    @patch("pipeline.fetch.update_db")
    @patch("pipeline.update.bundle_story_map", return_value=True)
    @patch("pipeline.update.validate_story_map", return_value=True)
    @patch("pipeline.update.analyze_asset_completeness", return_value=MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0)))
    @patch("pipeline.update.run_deploy")
    def test_remote_behind_local_blocks_deploy_by_default(self, mock_deploy, mock_assets, mock_validate, mock_bundle, mock_update_db, mock_probe):
        """驗證 remote < local (REMOTE_BEHIND_LOCAL) 時，生產部署門禁預設阻擋"""
        code = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=False)
        self.assertEqual(code, 1)
        mock_deploy.assert_not_called()
        mock_update_db.assert_not_called()

    @patch("pipeline.fetch.probe_truth_version", return_value=TruthVersionProbeResult("00600025", "remote_wthee_api", True))
    @patch("pipeline.fetch.update_db")
    @patch("pipeline.update.bundle_story_map", return_value=True)
    @patch("pipeline.update.validate_story_map", return_value=True)
    @patch("pipeline.update.analyze_asset_completeness", return_value=MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0)))
    @patch("pipeline.update.run_deploy", return_value=True)
    def test_remote_behind_local_allows_deploy_with_override(self, mock_deploy, mock_assets, mock_validate, mock_bundle, mock_update_db, mock_probe):
        """驗證 remote < local (REMOTE_BEHIND_LOCAL) 時，帶入 --allow-unconfirmed-freshness 可手動覆蓋發布"""
        code = run_pipeline_update(dry_run=False, auto_deploy=True, allow_unconfirmed_freshness=True)
        self.assertEqual(code, 0)
        mock_deploy.assert_called_once()
        mock_update_db.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
