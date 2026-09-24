#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for Direct So-net Master DB Pipeline Integration (Phase F2A.4)

驗證範圍：
1. pipeline passes exact remote_tv to updater
2. direct official acquisition success -> UPDATED_SUCCESSFULLY
3. no request to WTHEE_DB_URL during DB update
4. unknown family -> NEEDS_NEW_SCHEMA_MAPPING -> no fallback to wthee
5. acquisition failure -> production DB byte-identical
6. normalization failure -> production DB byte-identical
7. dry-run -> no Master DB bundle download, no DB replace, no version-state write
8. version-state promotion only after full pipeline validation success
9. final validation failure -> no version-state promotion
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
from pipeline.sonet_master_db import MasterDbFetchResult
from pipeline.sonet_normalized_db import NormalizedDbResult
import pipeline.fetch as fetch_module
import pipeline.update as update_module


class TestDirectSonetDbPipelineIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.mock_db = self.test_dir / "redive_tw.db"

        # 建立初始生產 DB，記錄 byte-identical 對照 SHA256
        self.initial_bytes = b"ORIGINAL_PRODUCTION_DB_SENTINEL_DATA_XYZ_9876543210"
        with open(self.mock_db, "wb") as f:
            f.write(self.initial_bytes)
        self.initial_sha256 = hashlib.sha256(self.initial_bytes).hexdigest()

        self.report_path = self.test_dir / "db_update_report.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _assert_db_unchanged(self):
        """驗證目標 DB 維持 100% byte-identical。"""
        self.assertTrue(self.mock_db.exists(), "目標資料庫檔案應當存在")
        with open(self.mock_db, "rb") as f:
            actual = f.read()
        self.assertEqual(hashlib.sha256(actual).hexdigest(), self.initial_sha256, "資料庫被篡改，未維持 byte-identical！")

    # 1. pipeline passes exact remote_tv to updater
    @patch("pipeline.update.evaluate_freshness")
    @patch("pipeline.fetch.probe_truth_version")
    @patch("pipeline.fetch.update_db")
    def test_01_pipeline_passes_exact_remote_tv_to_updater(self, mock_update_db, mock_probe, mock_eval):
        mock_probe.return_value = MagicMock(confirmed_remote=True, version="00610008", source="remote_wthee_api")
        mock_eval.return_value = FreshnessResult(
            status=FreshnessStatus.UPDATE_AVAILABLE,
            remote_version="00610008",
            local_version="00610007",
            confirmed=True,
            update_required=True,
            degraded=False,
            message="新版本可用"
        )
        mock_update_db.return_value = {"status": "ok"}

        sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=False)

        mock_update_db.assert_called_once()
        kwargs = mock_update_db.call_args.kwargs
        self.assertEqual(kwargs.get("truth_version"), "00610008", "Pipeline 必須傳遞精確 remote_tv 至 updater")
        self.assertEqual(freshness.status, FreshnessStatus.UPDATED_SUCCESSFULLY)

    # 2. direct official acquisition success -> UPDATED_SUCCESSFULLY
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    @patch("pipeline.fetch._validate_normalized_db_pre_promotion")
    def test_02_direct_official_acquisition_success_and_provenance(self, mock_val, mock_norm, mock_fetch):
        # 模擬 fetcher 成功
        def side_effect_fetch(truth_version, destination):
            with open(destination, "wb") as f:
                f.write(b"RAW_SQLITE_MOCK_DATA")
            return MasterDbFetchResult(
                success=True,
                truth_version=truth_version,
                written_path=destination,
                manifest_url="https://img-pc.so-net.tw/dl/Resources/00610008/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest",
                manifest_sha256="manifest_sha_123",
                bundle_name="a/masterdata_master.unity3d",
                bundle_md5="bundle_md5_123",
                pool_hash="pool_hash_abc",
                bundle_size=46022656,
                bundle_url="https://img-pc.so-net.tw/dl/pool/AssetBundles/ea/ea31a8de308910be",
                db_sha256="raw_sha_456"
            )
        mock_fetch.side_effect = side_effect_fetch

        # 模擬 normalizer 成功
        def side_effect_norm(raw_db_path, truth_version, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"NORMALIZED_SQLITE_NEW_PRODUCTION_BYTES")
            return NormalizedDbResult(
                success=True,
                truth_version=truth_version,
                client_family="0061",
                mapping_file=Path("pipeline/manifests/sonet_db_schema_map_0061.json"),
                mapping_schema_version="1.0.0",
                output_path=output_path,
                table_stats={"story_detail": 100, "unit_data": 50},
                provenance={"mapped_column_count": 99}
            )
        mock_norm.side_effect = side_effect_norm
        mock_val.return_value = True

        res = fetch_module.update_db(
            truth_version="00610008",
            output=str(self.report_path),
            db_path=self.mock_db
        )

        self.assertEqual(res.get("status"), "ok", f"error was: {res.get('error')}")
        self.assertEqual(res["truth_version"], "00610008")
        self.assertEqual(res["source"], "sonet_official_cdn")
        self.assertEqual(res["client_family"], "0061")

        # Manifest assertions
        self.assertEqual(res["manifest"]["name"], "masterdata2_assetmanifest")
        self.assertEqual(res["manifest"]["url"], "https://img-pc.so-net.tw/dl/Resources/00610008/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest")
        self.assertEqual(res["manifest"]["sha256"], "manifest_sha_123")

        # Bundle assertions
        self.assertEqual(res["bundle"]["bundle_name"], "a/masterdata_master.unity3d")
        self.assertEqual(res["bundle"]["bundle_md5"], "bundle_md5_123")
        self.assertEqual(res["bundle"]["pool_hash"], "pool_hash_abc")
        self.assertEqual(res["bundle"]["bundle_size"], 46022656)
        self.assertEqual(res["bundle"]["bundle_url"], "https://img-pc.so-net.tw/dl/pool/AssetBundles/ea/ea31a8de308910be")

        # Raw DB assertions
        self.assertEqual(res["raw_db"]["sha256"], "raw_sha_456")
        self.assertGreater(res["raw_db"]["size"], 0)

        # Normalized DB assertions
        self.assertTrue(res["normalized_db"]["sha256"])
        self.assertGreater(res["normalized_db"]["size"], 0)
        self.assertEqual(res["normalized_db"]["table_count"], 2)
        self.assertEqual(res["normalized_db"]["mapped_column_count"], 99)

        # Mapping assertions
        self.assertEqual(res["mapping"]["client_family"], "0061")
        self.assertIn("sonet_db_schema_map_0061.json", res["mapping"]["contract_file"])
        self.assertNotEqual(res["mapping"]["schema_version"], "0061", "schema_version must not be 0061")
        self.assertEqual(res["mapping"]["schema_version"], "1.0.0")

        # 驗證目標檔案已成功被原子替換
        with open(self.mock_db, "rb") as f:
            final_bytes = f.read()
        self.assertEqual(final_bytes, b"NORMALIZED_SQLITE_NEW_PRODUCTION_BYTES")

        # 驗證報告已寫入磁碟
        self.assertTrue(self.report_path.exists())

    # 3. no request to WTHEE_DB_URL during DB update
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    @patch("pipeline.fetch._validate_normalized_db_pre_promotion")
    @patch("urllib.request.urlopen")
    def test_03_no_request_to_wthee_db_url(self, mock_urlopen, mock_val, mock_norm, mock_fetch):
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610008",
            written_path=Path(self.temp_dir.name) / "raw.db",
            bundle_md5="md5",
            pool_hash="hash",
            db_sha256="sha"
        )
        mock_norm.return_value = NormalizedDbResult(
            success=True,
            truth_version="00610008",
            client_family="0061",
            output_path=Path(self.temp_dir.name) / "norm.db",
            table_stats={}
        )
        mock_val.return_value = True

        # 調用 update_db，確認 urlopen 絕無被呼叫過指向 wthee redive_tw.db 的請求
        fetch_module.update_db(
            truth_version="00610008",
            output=None,
            db_path=self.mock_db
        )
        for call_args in mock_urlopen.call_args_list:
            req = call_args[0][0]
            url = req.full_url if hasattr(req, "full_url") else str(req)
            self.assertNotIn("wthee.xyz/db/redive_tw.db", url, "生產 DB 更新路徑中嚴禁請求 wthee DB URL")

    # 4. unknown family -> NEEDS_NEW_SCHEMA_MAPPING -> no fallback
    def test_04_unknown_family_fails_closed_needs_new_schema_mapping(self):
        res = fetch_module.update_db(
            truth_version="00620001",  # 未知家族
            output=str(self.report_path),
            db_path=self.mock_db
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("NEEDS_NEW_SCHEMA_MAPPING", res["error"])
        self._assert_db_unchanged()

    # 5. acquisition failure -> production DB unchanged
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    def test_05_acquisition_failure_preserves_production_db(self, mock_fetch):
        mock_fetch.return_value = MasterDbFetchResult(
            success=False,
            truth_version="00610008",
            written_path=None,
            error="Manifest 404 Not Found"
        )

        res = fetch_module.update_db(
            truth_version="00610008",
            output=str(self.report_path),
            db_path=self.mock_db
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("So-net 原始 Master DB 獲取失敗", res["error"])
        self._assert_db_unchanged()

    # 6. normalization failure -> production DB unchanged
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    def test_06_normalization_failure_preserves_production_db(self, mock_norm, mock_fetch):
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610008",
            written_path=Path(self.temp_dir.name) / "raw.db",
            bundle_md5="md5",
            pool_hash="hash",
            db_sha256="sha"
        )
        mock_norm.return_value = NormalizedDbResult(
            success=False,
            truth_version="00610008",
            client_family="0061",
            error="缺失實體表"
        )

        res = fetch_module.update_db(
            truth_version="00610008",
            output=str(self.report_path),
            db_path=self.mock_db
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("正規化資料庫生成失敗", res["error"])
        self._assert_db_unchanged()

    # 7. dry-run -> no Master DB bundle download, no DB replace, no version-state write
    @patch("pipeline.fetch.probe_truth_version")
    @patch("pipeline.update.evaluate_freshness")
    @patch("pipeline.fetch.update_db")
    @patch("pipeline.update.save_truth_version_state")
    def test_07_dry_run_contract_no_download_no_replace_no_state_write(
        self, mock_save_state, mock_update_db, mock_eval, mock_probe
    ):
        mock_probe.return_value = MagicMock(confirmed_remote=True, version="00610008", source="remote_wthee_api")
        mock_eval.return_value = FreshnessResult(
            status=FreshnessStatus.UPDATE_AVAILABLE,
            remote_version="00610008",
            local_version="00610007",
            confirmed=True,
            update_required=True,
            degraded=False,
            message="新版本可用"
        )

        sync_ok, freshness, _ = update_module.check_and_sync_upstream(dry_run=True)

        self.assertTrue(sync_ok)
        mock_update_db.assert_not_called()
        mock_save_state.assert_not_called()
        self._assert_db_unchanged()

    # 8. version-state promotion only after full pipeline validation success
    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.analyze_asset_completeness")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.save_truth_version_state")
    def test_08_version_state_promoted_only_after_full_validation_success(
        self, mock_save_state, mock_val, mock_bundle, mock_asset, mock_sync
    ):
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.UPDATED_SUCCESSFULLY,
                remote_version="00610008",
                local_version="00610007",
                confirmed=True,
                update_required=False,
                degraded=False,
                message="成功"
            ),
            MagicMock(analysis_status="VALID", metrics={}, overlaps={}, policy_status={}, source_status={}, missing_required_count=0)
        )
        mock_asset.return_value = MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0))
        mock_bundle.return_value = True
        mock_val.return_value = True
        mock_save_state.return_value = True

        exit_code = update_module.run_pipeline_update(dry_run=False, auto_deploy=False)
        self.assertEqual(exit_code, 0)
        mock_save_state.assert_called_once_with("00610008")

    # 9. final validation failure -> no version-state promotion
    @patch("pipeline.update.check_and_sync_upstream")
    @patch("pipeline.update.analyze_asset_completeness")
    @patch("pipeline.update.bundle_story_map")
    @patch("pipeline.update.validate_story_map")
    @patch("pipeline.update.save_truth_version_state")
    def test_09_final_validation_failure_prevents_version_state_promotion(
        self, mock_save_state, mock_val, mock_bundle, mock_asset, mock_sync
    ):
        mock_sync.return_value = (
            True,
            FreshnessResult(
                status=FreshnessStatus.UPDATED_SUCCESSFULLY,
                remote_version="00610008",
                local_version="00610007",
                confirmed=True,
                update_required=False,
                degraded=False,
                message="成功"
            ),
            MagicMock(analysis_status="VALID", metrics={}, overlaps={}, policy_status={}, source_status={}, missing_required_count=0)
        )
        mock_asset.return_value = MagicMock(success=True, movie_coverage=MagicMock(new_references_count=0))
        mock_bundle.return_value = True
        # 模擬最終全量驗證門禁失敗
        mock_val.return_value = False

        exit_code = update_module.run_pipeline_update(dry_run=False, auto_deploy=False)
        self.assertEqual(exit_code, 1)
        mock_save_state.assert_not_called()

    # 10. regression: metadata/hash failure BEFORE promotion preserves production DB
    @patch("pipeline.fetch.fetch_master_db_from_sonet")
    @patch("pipeline.fetch.generate_normalized_db")
    @patch("pipeline.fetch._validate_normalized_db_pre_promotion")
    @patch("pipeline.fetch.hashlib.sha256")
    def test_10_metadata_hash_failure_before_promotion_preserves_production_db(
        self, mock_sha, mock_val, mock_norm, mock_fetch
    ):
        mock_fetch.return_value = MasterDbFetchResult(
            success=True,
            truth_version="00610008",
            written_path=Path("mock.db"),
            manifest_url="http://test/manifest",
            manifest_sha256="sha1",
            bundle_name="bundle.unity3d",
            bundle_md5="md5",
            pool_hash="hash",
            bundle_size=1000,
            db_sha256="dbsha"
        )
        def side_effect_norm(raw_db_path, truth_version, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"STAGING_BYTES_NOT_YET_PROMOTED")
            return NormalizedDbResult(
                success=True,
                truth_version=truth_version,
                client_family="0061",
                output_path=output_path,
                table_stats={"story_detail": 10}
            )
        mock_norm.side_effect = side_effect_norm
        mock_val.return_value = True

        # 模擬在替換前計算 SHA256 拋出 IOError
        mock_sha.side_effect = IOError("Simulated disk error during hash calculation")

        res = fetch_module.update_db(
            truth_version="00610008",
            output=str(self.report_path),
            db_path=self.mock_db
        )

        self.assertEqual(res.get("status"), "error")
        self.assertIn("Simulated disk error", res.get("error", ""))

        # 驗證原正式 DB 仍保持完全一致的 byte-identical 舊狀態
        with open(self.mock_db, "rb") as f:
            final_bytes = f.read()
        self.assertEqual(final_bytes, self.initial_bytes, "若在 promotion 前失敗，原 DB 必須 byte-identical")


if __name__ == "__main__":
    unittest.main()
