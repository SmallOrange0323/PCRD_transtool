# -*- coding: utf-8 -*-
"""
tests/test_version_provenance_hardening.py
=========================================
驗證第三方版號 (如 wthee API 之 00600025) 僅為 informational reference，
絕不覆蓋、降級或滲透至權威 So-net 官方元數據 (TruthVersion: 00610014) 之寫入與下載路徑。
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipeline.metadata_manifest import (
    batch_update_manifest_entries,
    create_empty_manifest,
    load_metadata_manifest,
)
from tools.pcrd_fetch import (
    _get_sonet_ver,
    sync_story_batch_with_metadata,
    fetch_story_json_by_id,
    StoryFetchResult,
    StoryBundleRef,
    TruthVersionProbeResult,
)
import tools.pcrd_fetch as pcrd_fetch_module


class TestVersionProvenanceHardening(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_manifest_path = Path(self.temp_dir.name) / "official_story_metadata.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _sample_episode_entry(self, truth_version="00610014"):
        return {
            "chapter_title": "測試章節",
            "official_synopsis": "測試概要",
            "subtitle": "測試副標",
            "provenance": {
                "truth_version": str(truth_version),
                "cdn_bundle_hash": "a" * 32,
                "bundle_name": "manifest/soundstory_00000000.unity3d",
                "bundle_sha256": "f" * 64,
                "cmd1_present": True,
                "cmd1_nonempty": True,
                "cmd32_present": True,
                "cmd32_nonempty": True,
            },
        }

    def test_case_a_official_confirmed_with_older_third_party(self):
        """Case A: 官方確認版號 00610014，第三方較舊 00600025，寫入結果必須為 00610014，第三方不覆蓋"""
        with patch.object(pcrd_fetch_module, "_get_sonet_ver", return_value="00600025"):
            batch_update_manifest_entries(
                {},
                truth_version="00610014",
                filepath=self.test_manifest_path,
                replace_existing=True,
            )
            ep = self._sample_episode_entry("00610014")
            batch_update_manifest_entries(
                {100101: ep},
                truth_version="00610014",
                filepath=self.test_manifest_path,
            )

        loaded = load_metadata_manifest(self.test_manifest_path)
        self.assertEqual(loaded["truth_version"], "00610014")
        self.assertEqual(loaded["episodes"]["100101"]["provenance"]["truth_version"], "00610014")

    def test_case_b_official_confirmed_with_newer_third_party(self):
        """Case B: 官方確認版號 00610014，第三方較新 00620001，權威寫入版號仍為 00610014"""
        with patch.object(pcrd_fetch_module, "_get_sonet_ver", return_value="00620001"):
            batch_update_manifest_entries(
                {},
                truth_version="00610014",
                filepath=self.test_manifest_path,
                replace_existing=True,
            )
            ep = self._sample_episode_entry("00610014")
            batch_update_manifest_entries(
                {100102: ep},
                truth_version="00610014",
                filepath=self.test_manifest_path,
            )

        loaded = load_metadata_manifest(self.test_manifest_path)
        self.assertEqual(loaded["truth_version"], "00610014")
        self.assertEqual(loaded["episodes"]["100102"]["provenance"]["truth_version"], "00610014")

    @patch("tools.pcrd_fetch.fetch_story_json_by_id")
    @patch("tools.pcrd_fetch.load_story_manifest_snapshot")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_case_c_sync_story_batch_authoritative_write_path(
        self, mock_load_refs, mock_load_snapshot, mock_fetch_single
    ):
        """Case C: 透過 sync_story_batch_with_metadata 走真實 write-path，寫入 provenance 必為 00610014"""
        mock_ref = StoryBundleRef(
            story_id=100103,
            bundle_name="manifest/soundstory_100103.unity3d",
            cdn_bundle_hash="b" * 32,
            truth_version="00610014",
        )
        mock_load_refs.return_value = {100103: mock_ref}
        mock_load_snapshot.return_value = ({100103: "hash"}, {})

        mock_fetch_single.return_value = StoryFetchResult(
            story_id=100103,
            status="OK",
            metadata=self._sample_episode_entry("00610014"),
        )

        batch_update_manifest_entries(
            {},
            truth_version="00610014",
            filepath=self.test_manifest_path,
            replace_existing=True,
        )

        ok, m_ver, success_ids, failed_ids = sync_story_batch_with_metadata(
            [100103],
            truth_version="00610014",
            bundle_refs={100103: mock_ref},
            manifest_path=self.test_manifest_path,
            write_story_json=False,
        )

        self.assertTrue(ok)
        self.assertEqual(success_ids, [100103])
        self.assertEqual(failed_ids, [])

        loaded = load_metadata_manifest(self.test_manifest_path)
        self.assertEqual(loaded["episodes"]["100103"]["provenance"]["truth_version"], "00610014")

    def test_case_d_fail_closed_when_missing_authoritative_version(self):
        """Case D: 缺少 authoritative version 時，所有元數據寫入/萃取路徑 fail-closed 拒絕，不 fallback 到 00600025"""
        ep = self._sample_episode_entry("00610014")
        # 1. batch_update_manifest_entries 未提供 truth_version -> ValueError
        with self.assertRaises(ValueError) as cm:
            batch_update_manifest_entries(
                {100104: ep},
                truth_version=None,
                filepath=self.test_manifest_path,
            )
        self.assertIn("ContractError", str(cm.exception))

        # 2. sync_story_batch_with_metadata 未提供 truth_version 與 bundle_refs -> ValueError
        with self.assertRaises(ValueError) as cm_sync:
            sync_story_batch_with_metadata(
                [100104],
                truth_version=None,
                bundle_refs=None,
                manifest_path=self.test_manifest_path,
            )
        self.assertIn("ContractError", str(cm_sync.exception))

        # 3. fetch_story_json_by_id 提取元數據缺少有效 8 碼 TruthVersion -> fail closed NETWORK_ERROR
        with patch.object(pcrd_fetch_module, "_get_sonet_ver", return_value=None):
            result = fetch_story_json_by_id(
                100104,
                extract_metadata=True,
                truth_version=None,
                bundle_ref=None,
                bundle_refs=None,
            )
            self.assertEqual(result.status, "NETWORK_ERROR")
            self.assertIn("ContractError", result.error_message)

    def test_case_e_preserve_historical_episodes_provenance(self):
        """Case E: 既有 metadata fixture 包含 00600025 的歷史話數，寫入新話數 (00610014) 時，歷史話數 provenance 嚴格保持不變"""
        hist_ep = self._sample_episode_entry("00600025")
        manifest = create_empty_manifest("00600025")
        manifest["episodes"]["100001"] = hist_ep
        manifest["episode_count"] = 1
        with open(self.test_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        new_ep = self._sample_episode_entry("00610014")
        batch_update_manifest_entries(
            {100002: new_ep},
            truth_version="00610014",
            filepath=self.test_manifest_path,
        )

        loaded = load_metadata_manifest(self.test_manifest_path)
        self.assertEqual(loaded["truth_version"], "00610014")
        self.assertEqual(loaded["episode_count"], 2)
        self.assertEqual(loaded["episodes"]["100001"]["provenance"]["truth_version"], "00600025")
        self.assertEqual(loaded["episodes"]["100002"]["provenance"]["truth_version"], "00610014")

    def test_case_f_get_sonet_ver_fails_closed_when_official_unavailable(self):
        """Case F: confirmed official unavailable 且 third-party wthee 回傳 00600025 時，_get_sonet_ver 必須 Fail Closed 回傳 None，絕不回傳 00600025"""
        fake_db_path = str(Path(self.temp_dir.name) / "nonexistent" / "redive_tw.db")
        mock_wthee_probe = TruthVersionProbeResult("00600025", "remote_wthee_api", True)

        with patch.object(pcrd_fetch_module, "DB_PATH", fake_db_path), \
             patch.object(pcrd_fetch_module, "probe_truth_version", return_value=mock_wthee_probe):
            resolved = _get_sonet_ver()
            self.assertIsNone(resolved, "官方版本不可用時，_get_sonet_ver 必須 Fail Closed 回傳 None，嚴禁使用 wthee 00600025")

    def test_case_g_fetch_story_locked_when_official_unavailable(self):
        """Case G: explicit truth_version=None, confirmed official=unavailable, third-party=00600025 時，fetch_story_json_by_id 必報錯且絕不用 00600025 形成下載 URL"""
        fake_db_path = str(Path(self.temp_dir.name) / "nonexistent" / "redive_tw.db")
        mock_wthee_probe = TruthVersionProbeResult("00600025", "remote_wthee_api", True)

        with patch.object(pcrd_fetch_module, "DB_PATH", fake_db_path), \
             patch.object(pcrd_fetch_module, "probe_truth_version", return_value=mock_wthee_probe), \
             patch("urllib.request.urlopen") as mock_urlopen:

            result = fetch_story_json_by_id(
                100105,
                extract_metadata=True,
                truth_version=None,
                bundle_ref=None,
                bundle_refs=None,
            )

            self.assertEqual(result.status, "NETWORK_ERROR")
            self.assertIn("ContractError", result.error_message)

            # 斷言：絕不可向網路發起任何包含 00600025 的請求
            mock_urlopen.assert_not_called()

    def test_case_h_batch_update_rejects_implicit_manifest_version_inheritance(self):
        """Case H: 現有 Manifest 頂層已存在 00610014，但 caller 呼叫 batch_update_manifest_entries 寫入非空 entries 時未提供 truth_version，必須 Fail Closed 拒絕"""
        batch_update_manifest_entries(
            {},
            truth_version="00610014",
            filepath=self.test_manifest_path,
            replace_existing=True,
        )

        ep = self._sample_episode_entry("00610014")
        with self.assertRaises(ValueError) as cm:
            batch_update_manifest_entries(
                {100106: ep},
                truth_version=None,  # 故意未提供，測試是否嚴格禁止隱式繼承
                filepath=self.test_manifest_path,
            )
        self.assertIn("ContractError", str(cm.exception))
        self.assertIn("必須顯式提供", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
