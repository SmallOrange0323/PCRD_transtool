#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for Content-Driven So-net CDN Update Policy (Phase F2C)

驗證範圍 (13 條核心場景):
1. wthee unavailable + official CDN unchanged -> update pipeline remains healthy (NO_CHANGE)
2. wthee unavailable + official CDN meaningful content change -> update can proceed (UPDATED_SUCCESSFULLY)
3. wthee reports older version than observed CDN -> wthee does not veto official content update
4. wthee reports newer/different value -> it remains informational and cannot force promotion
5. CDN candidate exists but normalization fails -> production DB unchanged
6. CDN candidate exists but runtime validation fails -> production DB unchanged
7. unknown client family -> NEEDS_NEW_SCHEMA_MAPPING hard stop
8. same TruthVersion + changed relevant content fingerprint -> update is not skipped solely because version number matches
9. different TruthVersion + identical relevant content -> pipeline may report no meaningful content change without unnecessary production replacement
10. successful validated CDN content change -> normalized DB is atomically promoted
11. deployment of already validated local state -> does not call remote_wthee_api
12. wthee outage -> does not block deploy
13. dry-run -> no DB replacement, no persistent state mutation
"""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from pipeline.coverage import FreshnessStatus, FreshnessResult
from pipeline.sonet_master_db import (
    CdnCandidateProbeResult,
    CdnDiscoveryResult,
    MasterDbFetchResult,
)
from pipeline.sonet_normalized_db import NormalizedDbResult
import pipeline.fetch as fetch_module
import pipeline.update as update_module


class TestContentDrivenUpdatePolicy(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.mock_db = self.test_dir / "redive_tw.db"

        # 建立初始生產 DB，記錄 byte-identical 對照 SHA256
        self.initial_bytes = b"ORIGINAL_PRODUCTION_DB_SENTINEL_F2C_CONTENT_DRIVEN"
        with open(self.mock_db, "wb") as f:
            f.write(self.initial_bytes)
        self.initial_sha256 = hashlib.sha256(self.initial_bytes).hexdigest()

        self.report_path = self.test_dir / "db_update_report.json"

        self.cov_patcher = patch("pipeline.update.analyze_coverage")
        self.mock_cov = self.cov_patcher.start()
        mock_coverage = MagicMock()
        mock_coverage.analysis_status = update_module.CoverageAnalysisStatus.VALID
        mock_coverage.analysis_errors = []
        mock_coverage.required_total_count = 100
        mock_coverage.missing_required_count = 0
        mock_coverage.optional_total_count = 50
        mock_coverage.missing_optional_count = 0
        mock_coverage.unknown_expected_count = 0
        mock_coverage.missing_unknown_count = 0
        mock_coverage.missing_required_ids = []
        mock_coverage.missing_optional_ids = []
        mock_coverage.missing_unknown_ids = []
        self.mock_cov.return_value = mock_coverage

    def tearDown(self):
        self.cov_patcher.stop()
        self.temp_dir.cleanup()

    def _assert_db_unchanged(self):
        """驗證目標 DB 維持 100% byte-identical。"""
        self.assertTrue(self.mock_db.exists(), "目標資料庫檔案應當存在")
        with open(self.mock_db, "rb") as f:
            actual = f.read()
        self.assertEqual(hashlib.sha256(actual).hexdigest(), self.initial_sha256, "資料庫被篡改，未維持 byte-identical！")

    # 1. wthee unavailable + official CDN unchanged -> update pipeline remains healthy (NO_CHANGE)
    @patch("pipeline.fetch.probe_third_party_reference")
    @patch("pipeline.fetch.discover_cdn_candidate_snapshots")
    def test_01_wthee_unavailable_and_cdn_unchanged_remains_healthy(self, mock_discover, mock_wthee):
        # 模擬 wthee 完全斷線/離線
        mock_wthee.return_value = {"source": "remote_wthee_api", "version": None, "confirmed": False, "error": "timeout"}
        
        # 模擬官方 CDN 探測成功，版本為 00610008，且指紋一致
        candidate = CdnCandidateProbeResult(
            version="00610008",
            exists=True,
            manifest_sha256="sha_abc",
            master_bundle_md5="md5_xyz",
            master_pool_hash="pool_123"
        )
        mock_discover.return_value = CdnDiscoveryResult(
            highest_observed_cdn_version="00610008",
            candidates={"00610008": candidate},
            scan_bounds={"base_version": "00610008"}
        )

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            # 建立本地 version_history.json 指紋相符
            ver_file = self.test_dir / "versions" / "version_history.json"
            ver_file.parent.mkdir(parents=True, exist_ok=True)
            with open(ver_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_applied_cdn_version": "00610008",
                    "last_applied_manifest_sha256": "sha_abc",
                    "last_applied_master_bundle_md5": "md5_xyz",
                }, f)

            sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

            self.assertTrue(sync_ok, "wthee 斷線不應阻斷健康檢查")
            self.assertEqual(freshness.status, FreshnessStatus.NO_CHANGE)
            self.assertFalse(freshness.update_required, "指紋一致不應要求更新")

    # 2. wthee unavailable + official CDN meaningful content change -> update can proceed (UPDATED_SUCCESSFULLY)
    @patch("pipeline.fetch.probe_third_party_reference")
    @patch("pipeline.fetch.discover_cdn_candidate_snapshots")
    @patch("pipeline.fetch.update_db")
    def test_02_wthee_unavailable_and_cdn_changed_proceeds(self, mock_update_db, mock_discover, mock_wthee):
        mock_wthee.return_value = {"source": "remote_wthee_api", "version": None, "confirmed": False, "error": "500 Server Error"}
        
        # 官方 CDN 探測到新版本 00610009
        candidate = CdnCandidateProbeResult(
            version="00610009",
            exists=True,
            manifest_sha256="sha_new",
            master_bundle_md5="md5_new",
            master_pool_hash="pool_new"
        )
        mock_discover.return_value = CdnDiscoveryResult(
            highest_observed_cdn_version="00610009",
            candidates={"00610009": candidate},
            scan_bounds={"base_version": "00610008"}
        )
        mock_update_db.return_value = {"status": "ok", "applied": True}

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            ver_file = self.test_dir / "versions" / "version_history.json"
            ver_file.parent.mkdir(parents=True, exist_ok=True)
            with open(ver_file, "w", encoding="utf-8") as f:
                json.dump({"last_applied_cdn_version": "00610008"}, f)

            sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

            self.assertTrue(sync_ok)
            mock_update_db.assert_called_once()
            self.assertEqual(mock_update_db.call_args.kwargs.get("truth_version"), "00610009")
            self.assertEqual(freshness.status, FreshnessStatus.UPDATED_SUCCESSFULLY)

    # 3. wthee reports older version than observed CDN -> wthee does not veto official content update
    @patch("pipeline.fetch.probe_third_party_reference")
    @patch("pipeline.fetch.discover_cdn_candidate_snapshots")
    @patch("pipeline.fetch.update_db")
    def test_03_wthee_older_does_not_veto_cdn_update(self, mock_update_db, mock_discover, mock_wthee):
        mock_wthee.return_value = {"source": "remote_wthee_api", "version": "00610007", "confirmed": True}
        candidate = CdnCandidateProbeResult(
            version="00610008",
            exists=True,
            manifest_sha256="sha_8",
            master_bundle_md5="md5_8",
            master_pool_hash="pool_8"
        )
        mock_discover.return_value = CdnDiscoveryResult(
            highest_observed_cdn_version="00610008",
            candidates={"00610008": candidate},
            scan_bounds={"base_version": "00610007"}
        )
        mock_update_db.return_value = {"status": "ok", "applied": True}

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            ver_file = self.test_dir / "versions" / "version_history.json"
            ver_file.parent.mkdir(parents=True, exist_ok=True)
            with open(ver_file, "w", encoding="utf-8") as f:
                json.dump({"last_applied_cdn_version": "00610007"}, f)

            sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

            self.assertTrue(sync_ok)
            self.assertEqual(mock_update_db.call_args.kwargs.get("truth_version"), "00610008")
            self.assertEqual(freshness.status, FreshnessStatus.UPDATED_SUCCESSFULLY)

    # 4. wthee reports newer/different value -> it remains informational and cannot force promotion
    @patch("pipeline.fetch.probe_third_party_reference")
    @patch("pipeline.fetch.discover_cdn_candidate_snapshots")
    @patch("pipeline.fetch.update_db")
    def test_04_wthee_newer_cannot_force_unsupported_cdn_version(self, mock_update_db, mock_discover, mock_wthee):
        mock_wthee.return_value = {"source": "remote_wthee_api", "version": "00610099", "confirmed": True}
        candidate = CdnCandidateProbeResult(
            version="00610008",
            exists=True,
            manifest_sha256="sha_8",
            master_bundle_md5="md5_8",
            master_pool_hash="pool_8"
        )
        mock_discover.return_value = CdnDiscoveryResult(
            highest_observed_cdn_version="00610008",
            candidates={"00610008": candidate, "00610099": CdnCandidateProbeResult(version="00610099", exists=False)},
            scan_bounds={"base_version": "00610008"}
        )

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            ver_file = self.test_dir / "versions" / "version_history.json"
            ver_file.parent.mkdir(parents=True, exist_ok=True)
            with open(ver_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_applied_cdn_version": "00610008",
                    "last_applied_manifest_sha256": "sha_8",
                    "last_applied_master_bundle_md5": "md5_8",
                }, f)

            sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

            self.assertTrue(sync_ok)
            mock_update_db.assert_not_called()
            self.assertEqual(freshness.status, FreshnessStatus.NO_CHANGE)

    # 5. CDN candidate exists but normalization fails -> production DB unchanged
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    def test_05_cdn_exists_normalization_fails_preserves_db(self, mock_norm, mock_fetch):
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610008",
            manifest_url="https://test",
            manifest_sha256="sha",
            bundle_name="a",
            bundle_md5="md5",
            pool_hash="pool"
        )
        mock_norm.return_value = NormalizedDbResult(success=False, truth_version="00610008", client_family="0061", error="Schema mapping mismatch")

        res = fetch_module.update_db(
            truth_version="00610008",
            db_path=self.mock_db,
            output=str(self.report_path)
        )

        self.assertEqual(res.get("status"), "error")
        self._assert_db_unchanged()

    # 6. CDN candidate exists but runtime validation fails -> production DB unchanged
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    @patch("pipeline.fetch._validate_normalized_db_pre_promotion")
    def test_06_cdn_exists_validation_fails_preserves_db(self, mock_val, mock_norm, mock_fetch):
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610008",
            manifest_url="https://test",
            manifest_sha256="sha",
            bundle_name="a",
            bundle_md5="md5",
            pool_hash="pool"
        )
        mock_norm.return_value = NormalizedDbResult(success=True, truth_version="00610008", client_family="0061")
        mock_val.side_effect = ValueError("Corrupt unit_data rows")

        res = fetch_module.update_db(
            truth_version="00610008",
            db_path=self.mock_db,
            output=str(self.report_path)
        )

        self.assertEqual(res.get("status"), "error")
        self.assertIn("Corrupt unit_data rows", res.get("error", ""))
        self._assert_db_unchanged()

    # 7. unknown client family -> NEEDS_NEW_SCHEMA_MAPPING hard stop
    def test_07_unknown_client_family_hard_stop(self):
        res = fetch_module.update_db(
            truth_version="00620001",
            db_path=self.mock_db,
            output=str(self.report_path)
        )
        self.assertEqual(res.get("status"), "error")
        self.assertIn("NEEDS_NEW_SCHEMA_MAPPING", res.get("error", ""))
        self._assert_db_unchanged()

    # 8. same TruthVersion + changed relevant content fingerprint -> update is not skipped solely because version number matches
    @patch("pipeline.fetch.probe_third_party_reference")
    @patch("pipeline.fetch.discover_cdn_candidate_snapshots")
    @patch("pipeline.fetch.update_db")
    def test_08_same_version_changed_fingerprint_triggers_update(self, mock_update_db, mock_discover, mock_wthee):
        mock_wthee.return_value = {"source": "remote_wthee_api", "version": "00610008", "confirmed": True}
        candidate = CdnCandidateProbeResult(
            version="00610008",
            exists=True,
            manifest_sha256="sha_CHANGED",
            master_bundle_md5="md5_CHANGED",
            master_pool_hash="pool_new"
        )
        mock_discover.return_value = CdnDiscoveryResult(
            highest_observed_cdn_version="00610008",
            candidates={"00610008": candidate},
            scan_bounds={"base_version": "00610008"}
        )
        mock_update_db.return_value = {"status": "ok", "applied": True}

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            ver_file = self.test_dir / "versions" / "version_history.json"
            ver_file.parent.mkdir(parents=True, exist_ok=True)
            with open(ver_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_applied_cdn_version": "00610008",
                    "last_applied_manifest_sha256": "sha_OLD",
                    "last_applied_master_bundle_md5": "md5_OLD",
                }, f)

            sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

            self.assertTrue(sync_ok)
            mock_update_db.assert_called_once()
            self.assertEqual(freshness.status, FreshnessStatus.UPDATED_SUCCESSFULLY)

    # 9. different TruthVersion + identical relevant content -> pipeline reports no meaningful content change without replacement
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    @patch("pipeline.fetch._validate_normalized_db_pre_promotion")
    def test_09_different_version_identical_content_skips_replacement(self, mock_val, mock_norm, mock_fetch):
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610009",
            manifest_url="https://test",
            manifest_sha256="sha",
            bundle_name="a",
            bundle_md5="md5",
            pool_hash="pool"
        )
        
        def side_effect_norm(raw_db_path, truth_version, output_path):
            with open(output_path, "wb") as f:
                f.write(self.initial_bytes)
            return NormalizedDbResult(success=True, truth_version="00610009", client_family="0061")
        mock_norm.side_effect = side_effect_norm

        res = fetch_module.update_db(
            truth_version="00610009",
            db_path=self.mock_db,
            skip_if_identical=True,
            output=str(self.report_path)
        )

        self.assertEqual(res.get("status"), "ok", f"error was: {res.get('error')}")
        self.assertFalse(res.get("applied"), "內容無實質變化時不應進行檔案替換")
        self.assertEqual(res.get("reason"), "content_identical")
        self._assert_db_unchanged()

    # 10. successful validated CDN content change -> normalized DB is atomically promoted
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    @patch("pipeline.fetch._validate_normalized_db_pre_promotion")
    def test_10_validated_cdn_change_promotes_db_atomically(self, mock_val, mock_norm, mock_fetch):
        new_content = b"PROMOTED_NEW_VALIDATED_NORMALIZED_DB_DATA_12345"
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610009",
            manifest_url="https://test",
            manifest_sha256="sha",
            bundle_name="a",
            bundle_md5="md5",
            pool_hash="pool"
        )
        def side_effect_norm(raw_db_path, truth_version, output_path):
            with open(output_path, "wb") as f:
                f.write(new_content)
            return NormalizedDbResult(success=True, truth_version="00610009", client_family="0061")
        mock_norm.side_effect = side_effect_norm

        res = fetch_module.update_db(
            truth_version="00610009",
            db_path=self.mock_db,
            skip_if_identical=True,
            output=str(self.report_path)
        )

        self.assertEqual(res.get("status"), "ok", f"error was: {res.get('error')}")
        self.assertTrue(res.get("applied"))
        with open(self.mock_db, "rb") as f:
            self.assertEqual(f.read(), new_content, "生產 DB 應原子替換為新產物")

    # 11. deployment of already validated local state -> does not call remote_wthee_api
    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.analyze_asset_completeness")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.run_deploy")
    @patch("pipeline.fetch.probe_third_party_reference")
    def test_11_deployment_does_not_call_wthee(self, mock_wthee, mock_deploy, mock_val, mock_bundle, mock_asset, mock_sync):
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.NO_CHANGE,
                remote_version="00610008",
                local_version="00610008",
                confirmed=True,
                update_required=False,
                degraded=False,
                message="本地內容最新"
            ),
            MagicMock(analysis_status="VALID", unknown_expected_count=0, missing_unknown_count=0, missing_required_count=0)
        )
        mock_asset.return_value = MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0))
        mock_bundle.return_value = True
        mock_val.return_value = True
        mock_deploy.return_value = True

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            code = update_module.run_pipeline_update(auto_deploy=True)

            self.assertEqual(code, 0)
            mock_deploy.assert_called_once()
            # 部署流程本身絕不調用 probe_third_party_reference
            mock_wthee.assert_not_called()

    # 12. wthee outage -> does not block deploy
    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.analyze_asset_completeness")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.run_deploy")
    def test_12_wthee_outage_does_not_block_deploy(self, mock_deploy, mock_val, mock_bundle, mock_asset, mock_sync):
        # 即使新鮮度處於 REMOTE_UNREACHABLE（網路或第三方離線），只要本地完整且驗證通過，發布不受阻
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.REMOTE_UNREACHABLE,
                remote_version=None,
                local_version="00610008",
                confirmed=False,
                update_required=False,
                degraded=True,
                message="離線模式"
            ),
            MagicMock(analysis_status="VALID", unknown_expected_count=0, missing_unknown_count=0, missing_required_count=0)
        )
        mock_asset.return_value = MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0))
        mock_bundle.return_value = True
        mock_val.return_value = True
        mock_deploy.return_value = True

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            code = update_module.run_pipeline_update(auto_deploy=True)

            self.assertEqual(code, 0, "第三方離線不應阻斷已驗證本地產物之發布")
            mock_deploy.assert_called_once()

    # 13. dry-run -> no DB replacement, no persistent state mutation
    @patch("pipeline.fetch.discover_cdn_candidate_snapshots")
    @patch("pipeline.fetch.probe_third_party_reference")
    @patch("pipeline.update.analyze_asset_completeness")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.fetch.update_db")
    @patch("pipeline.update.save_truth_version_state")
    def test_13_dry_run_zero_side_effect(self, mock_save_state, mock_update_db, mock_val, mock_bundle, mock_asset, mock_wthee, mock_discover):
        mock_wthee.return_value = {"source": "remote_wthee_api", "version": "00610009"}
        mock_discover.return_value = CdnDiscoveryResult(
            highest_observed_cdn_version="00610009",
            candidates={"00610009": CdnCandidateProbeResult(version="00610009", exists=True)},
            scan_bounds={"base_version": "00610008"}
        )
        mock_asset.return_value = MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0))
        mock_bundle.return_value = True
        mock_val.return_value = True

        with patch("pipeline.update.DASHBOARD_DIR", self.test_dir):
            code = update_module.run_pipeline_update(dry_run=True)

            self.assertEqual(code, 0)
            mock_update_db.assert_not_called()
            mock_save_state.assert_not_called()
            self._assert_db_unchanged()

    # 14. bundle catalog icon mappings safely handles string unit_ids from normalized db (Regression for Rule B)
    def test_14_bundle_catalog_icon_mappings_handles_string_unit_ids(self):
        from pipeline.bundle import get_character_catalog_icon_mappings
        
        icon_dir = self.test_dir / "icon" / "unit"
        icon_dir.mkdir(parents=True, exist_ok=True)
        (icon_dir / "100111.png").write_bytes(b"dummy")
        (icon_dir / "190101.png").write_bytes(b"dummy")

        with patch("pipeline.bundle.get_playable_character_unit_ids", return_value={"100101", "190101", 100201}):
            mappings = get_character_catalog_icon_mappings(self.test_dir)
            self.assertIn("100111.png", mappings)
            self.assertIn("190101.png", mappings)


if __name__ == "__main__":
    unittest.main()
