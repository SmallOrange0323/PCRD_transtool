#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_event_top_thumbnail_fetcher.py
So-net 官方活動頂層專屬縮圖下載與驗證工具針對性密閉單元測試 (Hermetic Unit Tests)
完全零網路、零實體 CDN 依賴，驗證雙模式、版本語意、完整性校驗與 Fail-Closed 門禁。
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.fetch_event_top_thumbnails import (
    download_cdn_manifest,
    parse_event_top_targets_from_manifest,
    write_contract_manifest,
    load_pinned_contract,
    download_and_extract_event_top,
    verify_local_assets,
    run_pipeline
)


class TestEventTopThumbnailFetcher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pcrd_event_top_test_")
        self.mock_root = Path(self.temp_dir)
        self.mock_contract = self.mock_root / "official_event_top_manifest.json"
        self.mock_out = self.mock_root / "icon" / "event_top"
        self.mock_report = self.mock_root / "event_top_thumb_report.json"
        self.mock_out.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. online current mode uses discovered TruthVersion
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_01_online_current_mode_uses_discovered_truth_version(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600099"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,md5_5001,hash_5001,sub,12000,\n"
        mock_extract.return_value = ("5001", True, None)

        res = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        mock_get_tv.assert_called_once()
        mock_dl_manifest.assert_called_once_with("00600099")
        self.assertEqual(res["truth_version"], "00600099")
        self.assertEqual(res["mode"], "online_update")
        self.assertTrue(self.mock_contract.exists())
        with open(self.mock_contract, "r", encoding="utf-8") as f:
            c_data = json.load(f)
        self.assertEqual(c_data["truth_version"], "00600099")

    # 2. report TruthVersion equals actual source version used
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_02_report_truth_version_equals_actual_source_version(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600077"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5002.unity3d,md5_5002,hash_5002,sub,13000,\n"
        mock_extract.return_value = ("5002", True, "cached")

        run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        with open(self.mock_report, "r", encoding="utf-8") as f:
            r_data = json.load(f)
        self.assertEqual(r_data["truth_version"], "00600077")
        self.assertEqual(r_data["output_dir"], "dashboard/icon/event_top")

    # 3. pinned contract mode uses contract TruthVersion
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_03_pinned_contract_mode_uses_contract_truth_version(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600099"  # 線上新版
        # 建立 pinned contract 為舊版 00500010
        write_contract_manifest("00500010", {
            "5003": {"bundle_name": "a/icon_thumb_event_story_top_5003.unity3d", "pool_hash": "h3", "bundle_size": 100}
        }, contract_path=self.mock_contract)
        mock_extract.return_value = ("5003", True, "cached")

        res = run_pipeline(
            from_contract=True,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        # 嚴格禁止調用線上探測與下載 manifest
        mock_get_tv.assert_not_called()
        mock_dl_manifest.assert_not_called()
        self.assertEqual(res["truth_version"], "00500010")
        self.assertEqual(res["mode"], "pinned_contract")
        with open(self.mock_report, "r", encoding="utf-8") as f:
            r_data = json.load(f)
        self.assertEqual(r_data["truth_version"], "00500010")

    # 4. stale arbitrary local icon2_assetmanifest is NOT silently treated as current
    @patch("urllib.request.urlopen")
    def test_04_stale_arbitrary_local_manifest_not_reused_silently(self, mock_urlopen):
        # 模擬 CDN 回應指定版本之 manifest
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"a/icon_thumb_event_story_top_5004.unity3d,md5_4,h4,sub,14000,\n"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        download_cdn_manifest("00600025")

        # 斷言請求 URL 包含確切指定的版本號
        called_req = mock_urlopen.call_args[0][0]
        self.assertIn("/Resources/00600025/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest", called_req.full_url)

    # 5. one failed asset causes command/fetch result to fail closed
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_05_one_failed_asset_causes_fail_closed(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600025"
        mock_dl_manifest.return_value = (
            "a/icon_thumb_event_story_top_5001.unity3d,md5_1,h1,sub,100,\n"
            "a/icon_thumb_event_story_top_5002.unity3d,md5_2,h2,sub,200,\n"
        )
        # 5001 成功，5002 失敗
        mock_extract.side_effect = [
            ("5001", True, None),
            ("5002", False, "HTTP 404 Not Found")
        ]

        res = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertFalse(res["success"], "任一素材失敗必須導致整體流程標記 Fail-Closed")
        self.assertEqual(len(res["failed"]), 1)
        self.assertEqual(res["failed"][0]["event_id"], "5002")

    # 6. missing asset -> verify FAIL
    def test_06_missing_asset_verify_fail(self):
        targets = {
            "5001": {"pool_hash": "h1"},
            "5002": {"pool_hash": "h2"}
        }
        # 本地僅有 5001.webp
        (self.mock_out / "5001.webp").write_bytes(b"webp1")

        res = verify_local_assets(targets, asset_dir=self.mock_out)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["matched_count"], 1)
        self.assertEqual(res["missing_count"], 1)
        self.assertIn("5002", res["missing_ids"])

    # 7. extra asset -> verify FAIL
    def test_07_extra_asset_verify_fail(self):
        targets = {
            "5001": {"pool_hash": "h1"}
        }
        # 本地有 5001.webp 與額外孤立的 9999.webp
        (self.mock_out / "5001.webp").write_bytes(b"webp1")
        (self.mock_out / "9999.webp").write_bytes(b"extra")

        res = verify_local_assets(targets, asset_dir=self.mock_out)
        self.assertEqual(res["status"], "FAIL", "存在多餘孤立檔案時必須 FAIL")
        self.assertEqual(res["extra_count"], 1)
        self.assertIn("9999", res["extra_ids"])

    # 8. bundle MD5 mismatch -> rejected
    @patch("urllib.request.urlopen")
    def test_08_bundle_md5_mismatch_rejected(self, mock_urlopen):
        raw_bytes = b"sample_bundle_bytes"
        wrong_md5 = "00000000000000000000000000000000"

        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_bytes
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        target_info = {
            "pool_hash": "198eabc0c906565e",
            "bundle_md5": wrong_md5,
            "bundle_size": len(raw_bytes)
        }

        eid, ok, err = download_and_extract_event_top("5001", target_info, self.mock_out, force=True)
        self.assertFalse(ok)
        self.assertIn("MD5 mismatch", str(err))

    # 9. bundle size mismatch -> rejected
    @patch("urllib.request.urlopen")
    def test_09_bundle_size_mismatch_rejected(self, mock_urlopen):
        raw_bytes = b"sample_bundle_bytes_50_chars_long_data_here_1234567890"

        mock_resp = MagicMock()
        mock_resp.read.return_value = raw_bytes
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        target_info = {
            "pool_hash": "198eabc0c906565e",
            "bundle_md5": hashlib.md5(raw_bytes).hexdigest(),
            "bundle_size": 999999  # 錯誤的預期大小
        }

        eid, ok, err = download_and_extract_event_top("5001", target_info, self.mock_out, force=True)
        self.assertFalse(ok)
        self.assertIn("Size mismatch", str(err))


if __name__ == "__main__":
    unittest.main(verbosity=2)
