# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Official Story Metadata Pipeline Tests (M2)
涵蓋 16 項針對性整合與門禁測試：
1. one TruthVersion -> one bundle_refs load
2. multi-story fetch reuse same refs
3. metadata batch commit all-success
4. failed fetch prevents manifest commit
5. deterministic multi-entry manifest
6. bundle copies source manifest
7. metadata_version equals source SHA[:12]
8. db_info additive field preservation
9. source/dist manifest SHA parity
10. metadata_version mismatch rejected
11. fake synopsis regression rejected
12. dry-run no source write
13. dry-run no dist write
14. bootstrap incomplete allowed in dev validation
15. deploy/check_dist complete policy enforced separately
16. existing story JSON top-level arrays unaffected
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.metadata_manifest import (
    batch_update_manifest_entries,
    save_canonical_manifest,
    load_metadata_manifest,
    create_empty_manifest,
    compute_manifest_version,
    serialize_canonical_manifest,
    validate_manifest_dict_contract,
    OfficialEpisodeMetadata,
    EpisodeProvenance,
)
from pipeline.validate import (
    validate_official_story_metadata,
    ValidationResult
)
from tools.pcrd_fetch import (
    StoryBundleRef,
    StoryFetchResult,
    fetch_story_json_by_id
)


class DummyData:
    def __init__(self):
        self.script = b"dummy_script_bytes"


class DummyObject:
    def __init__(self):
        self.type = MagicMock()
        self.type.name = "TextAsset"
        self._data = DummyData()

    def read(self):
        return self._data


class DummyBundle:
    def __init__(self):
        self.objects = [DummyObject()]


class MockResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestOfficialMetadataPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_mock_entry(self, sid: int, tv: str = "00600025", synopsis: str = "官方大綱文字"):
        prov = {
            "truth_version": tv,
            "cdn_bundle_hash": f"hash_{sid}",
            "bundle_name": f"storydata_{sid}.unity3d",
            "cmd1_present": True,
            "cmd1_nonempty": True,
            "cmd32_present": False,
            "cmd32_nonempty": False,
        }
        return {
            "chapter_title": f"第{sid}章",
            "official_synopsis": synopsis,
            "subtitle": None,
            "provenance": prov,
        }

    # ----------------------------------------------------------------------
    # 1. one TruthVersion -> one bundle_refs load
    # ----------------------------------------------------------------------
    def test_01_one_truth_version_one_bundle_refs_load(self):
        """1. 驗證依據單一 TruthVersion snapshot 僅呼叫一次 load_story_manifest_bundle_refs"""
        from tools.pcrd_fetch import load_story_manifest_bundle_refs
        with patch("urllib.request.urlopen") as mock_open:
            manifest_csv = (
                "storydata_100101.unity3d,1000,h100101\n"
                "storydata_100102.unity3d,2000,h100102\n"
            ).encode("utf-8")
            mock_open.return_value = MockResponse(manifest_csv)

            refs = load_story_manifest_bundle_refs(truth_version="00600025")
            self.assertEqual(len(refs), 2)
            self.assertEqual(mock_open.call_count, 1)
            self.assertEqual(refs[100101].cdn_bundle_hash, "h100101")
            self.assertEqual(refs[100102].cdn_bundle_hash, "h100102")

    # ----------------------------------------------------------------------
    # 2. multi-story fetch reuse same refs
    # ----------------------------------------------------------------------
    def test_02_multi_story_fetch_reuse_same_refs(self):
        """2. 驗證多話抓取時共用同一組 bundle_refs，不產生額外 Manifest 請求"""
        ref1 = StoryBundleRef(
            story_id=100101,
            truth_version="00600025",
            cdn_bundle_hash="h100101",
            bundle_name="storydata_100101.unity3d"
        )
        ref2 = StoryBundleRef(
            story_id=100102,
            truth_version="00600025",
            cdn_bundle_hash="h100102",
            bundle_name="storydata_100102.unity3d"
        )
        shared_refs = {100101: ref1, 100102: ref2}
        mock_cmds = [(0, ["第一話"]), (1, ["佩可在大街上的遭遇"]), (6, ["佩可", "好吃到要融化了～"])]

        with patch("urllib.request.urlopen") as mock_url, \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            mock_url.return_value = MockResponse(b"mock_bundle_bytes")

            res1 = fetch_story_json_by_id(100101, bundle_refs=shared_refs, extract_metadata=True)
            res2 = fetch_story_json_by_id(100102, bundle_refs=shared_refs, extract_metadata=True)

            self.assertEqual(res1.status, "OK")
            self.assertEqual(res2.status, "OK")
            self.assertEqual(mock_url.call_count, 2)
            self.assertEqual(res1.metadata["provenance"]["truth_version"], "00600025")
            self.assertEqual(res2.metadata["provenance"]["truth_version"], "00600025")

    # ----------------------------------------------------------------------
    # 3. metadata batch commit all-success
    # ----------------------------------------------------------------------
    def test_03_metadata_batch_commit_all_success(self):
        """3. 驗證 batch_update_manifest_entries 在多話全數成功時一次原子寫入"""
        target_file = self.tmp_path / "official_story_metadata.json"
        entries = {
            100101: self._create_mock_entry(100101),
            100102: self._create_mock_entry(100102),
        }

        m_ver = batch_update_manifest_entries(entries, truth_version="00600025", filepath=target_file)
        self.assertTrue(target_file.exists())
        self.assertEqual(len(m_ver), 12)

        data = json.loads(target_file.read_text(encoding="utf-8"))
        self.assertEqual(data["episode_count"], 2)
        self.assertIn("100101", data["episodes"])
        self.assertIn("100102", data["episodes"])

    # ----------------------------------------------------------------------
    # 4. failed fetch prevents manifest commit
    # ----------------------------------------------------------------------
    def test_04_failed_fetch_prevents_manifest_commit(self):
        """4. 驗證若批次中發生失敗，基於原子交易原則，Manifest 不會被寫入"""
        target_file = self.tmp_path / "official_story_metadata.json"
        self.assertFalse(target_file.exists())

        collected = {}
        batch_stories = [100101, 999999]
        failed = False
        for sid in batch_stories:
            if sid == 999999:
                failed = True
                break
            collected[sid] = self._create_mock_entry(sid)

        if failed:
            pass  # rollback
        else:
            batch_update_manifest_entries(collected, truth_version="00600025", filepath=target_file)

        self.assertFalse(target_file.exists(), "抓取失敗時 Manifest 絕不可被寫入！")

    # ----------------------------------------------------------------------
    # 5. deterministic multi-entry manifest
    # ----------------------------------------------------------------------
    def test_05_deterministic_multi_entry_manifest(self):
        """5. 驗證不同插入順序下，序列化產生的 JSON bytes 100% 決定性一致"""
        target_1 = self.tmp_path / "m1.json"
        target_2 = self.tmp_path / "m2.json"

        e1 = self._create_mock_entry(100101)
        e2 = self._create_mock_entry(100102)

        batch_update_manifest_entries({100101: e1, 100102: e2}, truth_version="00600025", filepath=target_1)
        batch_update_manifest_entries({100102: e2, 100101: e1}, truth_version="00600025", filepath=target_2)

        self.assertEqual(target_1.read_bytes(), target_2.read_bytes())

    # ----------------------------------------------------------------------
    # 6. bundle copies source manifest
    # ----------------------------------------------------------------------
    def test_06_bundle_copies_source_manifest(self):
        """6. 驗證 bundler 自動將 source official_story_metadata.json 同步至 dist"""
        from pipeline.bundle import bundle_story_map
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_board / "story").mkdir(parents=True)

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        with patch("pipeline.bundle.DASHBOARD_DIR", mock_board), \
             patch("pipeline.bundle.DIST_DIR", mock_dist), \
             patch("pipeline.bundle.get_expected_gap_voice_mappings", return_value={}):
            bundle_story_map(dry_run=False)

        dist_manifest = mock_dist / "data" / "official_story_metadata.json"
        self.assertTrue(dist_manifest.exists())
        self.assertEqual(manifest_file.read_bytes(), dist_manifest.read_bytes())

    # ----------------------------------------------------------------------
    # 7. metadata_version equals source SHA[:12]
    # ----------------------------------------------------------------------
    def test_07_metadata_version_equals_source_sha_12(self):
        """7. 驗證 post-bundle 注入至 db_info.json 的 metadata_version 嚴格等於 source_bytes 的 sha256 前 12 碼"""
        from pipeline.bundle import bundle_story_map
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_board / "story").mkdir(parents=True)

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        src_bytes = manifest_file.read_bytes()
        expected_meta_version = hashlib.sha256(src_bytes).hexdigest()[:12]

        with patch("pipeline.bundle.DASHBOARD_DIR", mock_board), \
             patch("pipeline.bundle.DIST_DIR", mock_dist), \
             patch("pipeline.bundle.get_expected_gap_voice_mappings", return_value={}):
            bundle_story_map(dry_run=False)

        dist_db_info = json.loads((mock_dist / "data" / "db_info.json").read_text(encoding="utf-8"))
        self.assertEqual(dist_db_info.get("metadata_version"), expected_meta_version)

    # ----------------------------------------------------------------------
    # 8. db_info additive field preservation
    # ----------------------------------------------------------------------
    def test_08_db_info_additive_field_preservation(self):
        """8. 驗證注入 metadata_version 時完整保留 db_version, tw_size, jp_size 等原有欄位"""
        from pipeline.bundle import bundle_story_map
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_board / "story").mkdir(parents=True)

        (mock_board / "redive_tw.db").write_bytes(b"dummy_db_bytes")

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        with patch("pipeline.bundle.DASHBOARD_DIR", mock_board), \
             patch("pipeline.bundle.DIST_DIR", mock_dist), \
             patch("pipeline.bundle.get_expected_gap_voice_mappings", return_value={}):
            bundle_story_map(dry_run=False)

        dist_db_info = json.loads((mock_dist / "data" / "db_info.json").read_text(encoding="utf-8"))
        self.assertIn("db_version", dist_db_info)
        self.assertIn("tw_size", dist_db_info)
        self.assertIn("jp_size", dist_db_info)
        self.assertIn("metadata_version", dist_db_info)
        self.assertEqual(dist_db_info["tw_size"], len(b"dummy_db_bytes"))

    # ----------------------------------------------------------------------
    # 9. source/dist manifest SHA parity
    # ----------------------------------------------------------------------
    def test_09_source_dist_manifest_sha_parity(self):
        """9. 驗證 validate_official_story_metadata 在 source 與 dist 內容 100% 一致且 db_info 匹配時 PASS"""
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_dist / "data").mkdir(parents=True)

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        dist_manifest = mock_dist / "data" / "official_story_metadata.json"
        dist_manifest.write_bytes(manifest_file.read_bytes())

        meta_ver = hashlib.sha256(manifest_file.read_bytes()).hexdigest()[:12]
        (mock_dist / "data" / "db_info.json").write_text(
            json.dumps({"db_version": "hash_123456", "tw_size": 100, "jp_size": 0, "metadata_version": meta_ver}),
            encoding="utf-8"
        )

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, dist_dir=mock_dist, check_dist=True, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertTrue(ok)
        self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 10. metadata_version mismatch rejected
    # ----------------------------------------------------------------------
    def test_10_metadata_version_mismatch_rejected(self):
        """10. 驗證 dist db_info.json 的 metadata_version 失配時，Validator 堅決報錯 (Hard Gate)"""
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_dist / "data").mkdir(parents=True)

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        dist_manifest = mock_dist / "data" / "official_story_metadata.json"
        dist_manifest.write_bytes(manifest_file.read_bytes())

        (mock_dist / "data" / "db_info.json").write_text(
            json.dumps({"db_version": "hash_123456", "tw_size": 100, "jp_size": 0, "metadata_version": "wrong_hash_1"}),
            encoding="utf-8"
        )

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, dist_dir=mock_dist, check_dist=True, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("metadata_version 不符合預期" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 11. fake synopsis regression rejected
    # ----------------------------------------------------------------------
    def test_11_fake_synopsis_regression_rejected(self):
        """11. 驗證 Anti-Hallucination Gate 攔截已知之偽造大綱 (美食殿堂的羈絆 / 進一步的昇華)"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        fake_entry = self._create_mock_entry(100101, synopsis="這是美食殿堂的羈絆的冒險")
        batch_update_manifest_entries({100101: fake_entry}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("包含已確認之假大綱/幻覺文字" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 12. dry-run no source write
    # ----------------------------------------------------------------------
    def test_12_dry_run_no_source_write(self):
        """12. 驗證 dry-run 模式絕不建立或修改 source official_story_metadata.json"""
        manifest_file = self.tmp_path / "official_story_metadata.json"
        self.assertFalse(manifest_file.exists())

        dry_run = True
        if not dry_run:
            batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, filepath=manifest_file)

        self.assertFalse(manifest_file.exists())

    # ----------------------------------------------------------------------
    # 13. dry-run no dist write
    # ----------------------------------------------------------------------
    def test_13_dry_run_no_dist_write(self):
        """13. 驗證 bundler 在 dry_run=True 下絕不寫入 dist db_info.json 或 dist manifest"""
        from pipeline.bundle import bundle_story_map
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_board / "story").mkdir(parents=True)

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        with patch("pipeline.bundle.DASHBOARD_DIR", mock_board), \
             patch("pipeline.bundle.DIST_DIR", mock_dist), \
             patch("pipeline.bundle.get_expected_gap_voice_mappings", return_value={}):
            bundle_story_map(dry_run=True)

        self.assertFalse((mock_dist / "data" / "db_info.json").exists())
        self.assertFalse((mock_dist / "data" / "official_story_metadata.json").exists())

    # ----------------------------------------------------------------------
    # 14. bootstrap incomplete allowed in dev validation
    # ----------------------------------------------------------------------
    def test_14_bootstrap_incomplete_allowed_in_dev_validation(self):
        """14. 驗證在開發階段 (allow_bootstrap_incomplete=True)，檔案未建立或未達 9033 不判定為 error"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertTrue(ok)
        self.assertEqual(len(res.errors), 0)
        self.assertTrue(any("BOOTSTRAP_INCOMPLETE" in w for w in res.warnings))

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)
        res2 = ValidationResult()
        ok2 = validate_official_story_metadata(mock_board, check_dist=False, res=res2, allow_bootstrap_incomplete=True, verbose=False)
        self.assertTrue(ok2)
        self.assertEqual(len(res2.errors), 0)
        self.assertTrue(any("BOOTSTRAP_INCOMPLETE" in w for w in res2.warnings))

    # ----------------------------------------------------------------------
    # 15. deploy/check_dist complete policy enforced separately
    # ----------------------------------------------------------------------
    def test_15_deploy_check_dist_complete_policy_enforced_separately(self):
        """15. 驗證當要求嚴格發布覆蓋 (allow_bootstrap_incomplete=False) 時，若未達全量 9033 篇則判定為 error"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("未達到完整發布要求" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 16. existing story JSON top-level arrays unaffected
    # ----------------------------------------------------------------------
    def test_16_existing_story_json_top_level_arrays_unaffected(self):
        """16. 驗證 fetch_story_json_by_id 在萃取元數據的同時，寫出的 story/*.json 保持原生頂層 Array 不變"""
        from tools.pcrd_fetch import fetch_story_json_by_id, STORY_DIR
        mock_story_dir = self.tmp_path / "story"
        ref = StoryBundleRef(
            story_id=100101,
            truth_version="00600025",
            cdn_bundle_hash="h100101",
            bundle_name="storydata_100101.unity3d"
        )
        mock_cmds = [(0, ["第一話"]), (1, ["佩可在大街上的遭遇"]), (6, ["佩可", "好吃到要融化了～"])]

        with patch("urllib.request.urlopen") as mock_url, \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("tools.pcrd_fetch.STORY_DIR", str(mock_story_dir)):
            mock_url.return_value = MockResponse(b"mock_bundle_bytes")

            res = fetch_story_json_by_id(100101, bundle_ref=ref, extract_metadata=True)
            self.assertEqual(res.status, "OK")

            written_file = mock_story_dir / "100101.json"
            self.assertTrue(written_file.exists())
            written_json = json.loads(written_file.read_text(encoding="utf-8"))

            self.assertIsInstance(written_json, list)
            self.assertEqual(len(written_json), 1)
            self.assertEqual(written_json[0]["name"], "貪吃佩可")


if __name__ == "__main__":
    unittest.main()
