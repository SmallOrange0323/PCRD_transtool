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
    is_target_identity_equal,
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
        def extract_side_effect(eid, bname, phash, force):
            (self.mock_out / f"{eid}.webp").write_bytes(b"webp_data")
            return (eid, True, None)
        mock_extract.side_effect = extract_side_effect

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

    # 10. SAME event_id + SAME pool_hash/md5/size + existing WebP -> cache reuse allowed
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_10_same_identity_allows_cache_reuse(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600025"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,md5_same,hash_same,sub,12000,\n"
        # 舊合約記錄完全相同 identity
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "hash_same", "bundle_md5": "md5_same", "bundle_size": 12000}
        }, contract_path=self.mock_contract)
        # 本地已存在輸出 WebP
        (self.mock_out / "5001.webp").write_bytes(b"existing_webp")
        mock_extract.return_value = ("5001", True, "cached")

        res = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        mock_extract.assert_called_once_with("5001", mock_extract.call_args[0][1], self.mock_out, False)
        self.assertEqual(res["cached"], 1)
        self.assertEqual(res["downloaded"], 0)

    # 11. SAME event_id + CHANGED pool_hash + existing WebP -> MUST call downloader / re-extract
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_11_changed_pool_hash_forces_download(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,md5_same,hash_NEW,sub,12000,\n"
        # 舊合約是 hash_OLD
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "hash_OLD", "bundle_md5": "md5_same", "bundle_size": 12000}
        }, contract_path=self.mock_contract)
        (self.mock_out / "5001.webp").write_bytes(b"stale_webp")
        mock_extract.return_value = ("5001", True, None)

        run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        # 斷言傳入的 force 參數必須為 True
        self.assertTrue(mock_extract.call_args[0][3], "pool_hash 變更時必須強制重新下載 (force=True)")

    # 12. SAME event_id + CHANGED bundle_md5 -> MUST refresh
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_12_changed_bundle_md5_forces_download(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,md5_NEW,hash_same,sub,12000,\n"
        # 舊合約是 md5_OLD
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "hash_same", "bundle_md5": "md5_OLD", "bundle_size": 12000}
        }, contract_path=self.mock_contract)
        (self.mock_out / "5001.webp").write_bytes(b"stale_webp")
        mock_extract.return_value = ("5001", True, None)

        run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertTrue(mock_extract.call_args[0][3], "bundle_md5 變更時必須強制重新下載 (force=True)")

    # 13. SAME event_id + CHANGED bundle_size -> MUST refresh
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_13_changed_bundle_size_forces_download(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,md5_same,hash_same,sub,99999,\n"
        # 舊合約 size 是 12000
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "hash_same", "bundle_md5": "md5_same", "bundle_size": 12000}
        }, contract_path=self.mock_contract)
        (self.mock_out / "5001.webp").write_bytes(b"stale_webp")
        mock_extract.return_value = ("5001", True, None)

        run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertTrue(mock_extract.call_args[0][3], "bundle_size 變更時必須強制重新下載 (force=True)")

    # 14. NEW event_id -> MUST download
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_14_new_event_id_forces_download(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5009.unity3d,md5_9,hash_9,sub,15000,\n"
        # 舊合約完全無 5009
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "h1"}
        }, contract_path=self.mock_contract)
        (self.mock_out / "5009.webp").write_bytes(b"dummy_webp")
        mock_extract.return_value = ("5009", True, None)

        run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertTrue(mock_extract.call_args[0][3], "全新事件即便本地存在檔案也必須強制下載 (force=True)")

    # 15. Provenance regression: Old-version WebP cannot masquerade as new-version source
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_15_provenance_regression_old_version_webp_cannot_masquerade(self, mock_extract, mock_dl_manifest, mock_get_tv):
        # 舊版合約
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "OLD_HASH", "bundle_md5": "OLD_MD5", "bundle_size": 1000}
        }, contract_path=self.mock_contract)
        # 本地已有 5001.webp
        (self.mock_out / "5001.webp").write_bytes(b"old_v25_webp")

        # 線上探測到新版 00600026 且 5001 的 pool_hash 變為 NEW_HASH
        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,NEW_MD5,NEW_HASH,sub,2000,\n"
        mock_extract.return_value = ("5001", True, None)

        res = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        # 驗證: 5001.webp 絕不能被視為 cached！
        self.assertEqual(res["cached"], 0, "素材 identity 變更時絕不得被計為 cached")
        self.assertEqual(res["downloaded"], 1, "素材 identity 變更時必須被計為 downloaded")
        self.assertTrue(mock_extract.call_args[0][3], "必須以 force=True 重新下載與提取")

    # 16. Failed refresh does NOT promote new contract
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_16_failed_refresh_does_not_promote_new_contract(self, mock_extract, mock_dl_manifest, mock_get_tv):
        old_targets = {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "OLD_HASH", "bundle_md5": "OLD_MD5", "bundle_size": 1000}
        }
        write_contract_manifest("00600025", old_targets, contract_path=self.mock_contract)
        (self.mock_out / "5001.webp").write_bytes(b"old_v25_webp")

        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,NEW_MD5,NEW_HASH,sub,2000,\n"
        mock_extract.return_value = ("5001", False, "Download error 500")

        res = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertFalse(res["success"], "下載失敗時 overall success 必須為 False")
        self.assertEqual(len(res["failed"]), 1)

        # 關鍵驗證：契約文件未被修改，仍然維持舊版 00600025 與 OLD_HASH
        with open(self.mock_contract, "r", encoding="utf-8") as f:
            saved_contract = json.load(f)
        self.assertEqual(saved_contract["truth_version"], "00600025", "下載失敗時不得晉升合約 TruthVersion")
        self.assertEqual(saved_contract["targets"]["5001"]["pool_hash"], "OLD_HASH", "下載失敗時不得更新 targets 標識")

    # 17. Retry after failed refresh still forces changed asset download
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_17_retry_after_failed_refresh_still_forces_changed_asset_download(self, mock_extract, mock_dl_manifest, mock_get_tv):
        # 初始狀態：合約為 v25，本地有舊的 5001.webp
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "OLD_HASH", "bundle_md5": "OLD_MD5", "bundle_size": 1000}
        }, contract_path=self.mock_contract)
        (self.mock_out / "5001.webp").write_bytes(b"old_v25_webp")

        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,NEW_MD5,NEW_HASH,sub,2000,\n"

        # 第 1 次執行：失敗
        mock_extract.return_value = ("5001", False, "Network Timeout")
        res1 = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )
        self.assertFalse(res1["success"])

        # 第 2 次執行 (重試)：因為合約保持在 v25，重試時依然比對到 OLD_HASH != NEW_HASH，必須再次強制下載！
        def extract_side_effect(eid, bname, phash, force):
            (self.mock_out / f"{eid}.webp").write_bytes(b"new_v26_webp")
            return (eid, True, None)
        mock_extract.side_effect = extract_side_effect

        res2 = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertTrue(mock_extract.call_args[0][3], "重試時必須依然維持 force=True 強制重新下載")
        self.assertEqual(res2["cached"], 0, "舊 WebP 絕不可在重試時被誤判為 cached")
        self.assertEqual(res2["downloaded"], 1)
        self.assertTrue(res2["success"])

        # 成功後合約終於晉升
        with open(self.mock_contract, "r", encoding="utf-8") as f:
            saved_contract = json.load(f)
        self.assertEqual(saved_contract["truth_version"], "00600026")
        self.assertEqual(saved_contract["targets"]["5001"]["pool_hash"], "NEW_HASH")

    # 18. Successful refresh promotes new contract
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_18_successful_refresh_promotes_new_contract(self, mock_extract, mock_dl_manifest, mock_get_tv):
        write_contract_manifest("00600025", {
            "5001": {"bundle_name": "a/icon_thumb_event_story_top_5001.unity3d", "pool_hash": "OLD_HASH", "bundle_md5": "OLD_MD5", "bundle_size": 1000}
        }, contract_path=self.mock_contract)

        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,NEW_MD5,NEW_HASH,sub,2000,\n"

        def extract_side_effect(eid, bname, phash, force):
            (self.mock_out / f"{eid}.webp").write_bytes(b"new_webp")
            return (eid, True, None)
        mock_extract.side_effect = extract_side_effect

        res = run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertTrue(res["success"])
        with open(self.mock_contract, "r", encoding="utf-8") as f:
            saved_contract = json.load(f)
        self.assertEqual(saved_contract["truth_version"], "00600026")
        self.assertEqual(saved_contract["targets"]["5001"]["pool_hash"], "NEW_HASH")

    # 19. Incomplete old/new identity does NOT allow cache reuse
    def test_19_incomplete_identity_does_not_allow_cache_reuse(self):
        # 完整基準
        base = {"pool_hash": "h1", "bundle_md5": "m1", "bundle_size": 100}
        self.assertTrue(is_target_identity_equal(base, base))

        # 缺少任一欄位即保守回傳 False
        self.assertFalse(is_target_identity_equal(None, base))
        self.assertFalse(is_target_identity_equal(base, None))
        self.assertFalse(is_target_identity_equal({}, base))
        self.assertFalse(is_target_identity_equal({"pool_hash": "h1"}, base))
        self.assertFalse(is_target_identity_equal({"pool_hash": "h1", "bundle_md5": "m1"}, base))
        self.assertFalse(is_target_identity_equal(base, {"pool_hash": "h1", "bundle_md5": "m1"}))
        self.assertFalse(is_target_identity_equal({"pool_hash": "h1", "bundle_size": 100}, base))

    # 20. Report file contains final verify_result and success
    @patch("tools.fetch_event_top_thumbnails.get_current_truth_version")
    @patch("tools.fetch_event_top_thumbnails.download_cdn_manifest")
    @patch("tools.fetch_event_top_thumbnails.download_and_extract_event_top")
    def test_20_report_file_contains_final_verify_result_and_success(self, mock_extract, mock_dl_manifest, mock_get_tv):
        mock_get_tv.return_value = "00600026"
        mock_dl_manifest.return_value = "a/icon_thumb_event_story_top_5001.unity3d,m1,h1,sub,100,\n"

        def extract_side_effect(eid, bname, phash, force):
            (self.mock_out / f"{eid}.webp").write_bytes(b"webp_content")
            return (eid, True, None)
        mock_extract.side_effect = extract_side_effect

        run_pipeline(
            from_contract=False,
            contract_path=self.mock_contract,
            output_dir=self.mock_out,
            report_path=self.mock_report
        )

        self.assertTrue(self.mock_report.exists(), "執行報告檔案必須存在")
        with open(self.mock_report, "r", encoding="utf-8") as f:
            report_json = json.load(f)

        self.assertIn("verify_result", report_json, "報告必須包含 verify_result")
        self.assertEqual(report_json["verify_result"]["status"], "PASS")
        self.assertIn("success", report_json, "報告必須包含 success")
        self.assertTrue(report_json["success"])
        # 確認純相對路徑，無絕對路徑洩漏
        self.assertEqual(report_json["output_dir"], "dashboard/icon/event_top")
        self.assertFalse(":" in report_json["output_dir"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

