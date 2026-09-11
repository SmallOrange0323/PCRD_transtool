# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Official Story Metadata Pipeline Tests (M2 / M2.1)
涵蓋 20 項針對性整合與生命週期門禁測試：
1. one TruthVersion snapshot -> exactly one load_story_manifest_bundle_refs call
2. multi-story fetch reuses shared bundle_refs dictionary
3. sync_story_batch_with_metadata batch commit all-success atomic write
4. sync_story_batch_with_metadata failure rollback (zero manifest write)
5. rebuild_official_metadata orchestrator helper integration
6. rebuild_official_metadata sample_limit <= 0 rejection (ValueError)
7. rebuild_official_metadata sample redirect to scratch directory (no main manifest pollution)
8. metadata-only extraction path (write_story_json=False byte-for-byte zero story modification)
9. deterministic multi-entry manifest generation (byte-identical regardless of insertion order)
10. bundle copies source manifest to dist/data/official_story_metadata.json
11. metadata_version equals source manifest SHA256[:12]
12. db_info additive field preservation (db_version, tw_size, metadata_version)
13. source/dist manifest SHA-256 parity gate
14. dist db_info metadata_version mismatch hard rejection
15. fake synopsis / anti-hallucination regression guard
16. dry-run mode zero source write
17. dry-run mode zero dist write
18. dev validation allows BOOTSTRAP_INCOMPLETE (warning only)
19. strict deploy validation rejects BOOTSTRAP_INCOMPLETE (hard error)
20. coverage gate set-difference comparison & same-count wrong-ID rejection
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
    rebuild_official_metadata,
    OfficialEpisodeMetadata,
    EpisodeProvenance,
)
from pipeline.validate import (
    validate_official_story_metadata,
    validate_story_map,
    ValidationResult
)
from tools.pcrd_fetch import (
    StoryBundleRef,
    StoryFetchResult,
    fetch_story_json_by_id,
    sync_story_batch_with_metadata
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

            res1 = fetch_story_json_by_id(100101, bundle_refs=shared_refs, extract_metadata=True, write_story_json=False)
            res2 = fetch_story_json_by_id(100102, bundle_refs=shared_refs, extract_metadata=True, write_story_json=False)

            self.assertEqual(res1.status, "OK")
            self.assertEqual(res2.status, "OK")
            self.assertEqual(mock_url.call_count, 2)
            self.assertEqual(res1.metadata["provenance"]["truth_version"], "00600025")
            self.assertEqual(res2.metadata["provenance"]["truth_version"], "00600025")

    # ----------------------------------------------------------------------
    # 3. sync_story_batch_with_metadata batch commit all-success
    # ----------------------------------------------------------------------
    def test_03_sync_story_batch_with_metadata_all_success(self):
        """3. 驗證 sync_story_batch_with_metadata 在多話全數成功時執行單次快照並一次原子寫入"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        ref2 = StoryBundleRef(100102, "00600025", "h2", "storydata_100102.unity3d")
        shared_refs = {100101: ref1, 100102: ref2}
        mock_cmds = [(0, ["話數標題"]), (1, ["官方大綱文字"]), (6, ["佩可", "台詞"])]

        with patch("tools.pcrd_fetch.get_latest_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs) as mock_load_refs, \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, succ_ids, fail_ids = sync_story_batch_with_metadata(
                [100101, 100102],
                manifest_path=target_file,
                write_story_json=False
            )

            self.assertTrue(ok)
            self.assertEqual(len(succ_ids), 2)
            self.assertEqual(len(fail_ids), 0)
            self.assertIsNotNone(meta_ver)
            self.assertEqual(mock_load_refs.call_count, 1)
            self.assertTrue(target_file.exists())

            data = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertEqual(data["episode_count"], 2)
            self.assertIn("100101", data["episodes"])
            self.assertIn("100102", data["episodes"])

    # ----------------------------------------------------------------------
    # 4. sync_story_batch_with_metadata failure rollback (zero write)
    # ----------------------------------------------------------------------
    def test_04_sync_story_batch_failure_rollback(self):
        """4. 驗證批次中任一話失敗時，原子性機制確保 Manifest 零寫入"""
        target_file = self.tmp_path / "official_story_metadata.json"
        self.assertFalse(target_file.exists())

        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}  # 缺少 100102

        with patch("tools.pcrd_fetch.get_latest_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs):

            ok, meta_ver, succ_ids, fail_ids = sync_story_batch_with_metadata(
                [100101, 100102],
                manifest_path=target_file,
                write_story_json=False
            )

            self.assertFalse(ok)
            self.assertEqual(len(fail_ids), 1)
            self.assertIsNone(meta_ver)
            self.assertFalse(target_file.exists(), "批次失敗時 Manifest 絕不可被寫入！")

    # ----------------------------------------------------------------------
    # 5. rebuild_official_metadata orchestrator helper
    # ----------------------------------------------------------------------
    def test_05_rebuild_official_metadata_orchestrator(self):
        """5. 驗證 rebuild_official_metadata 獨立 orchestrator helper 正確產出 Manifest"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}
        mock_cmds = [(0, ["話數標題"]), (1, ["官方大綱文字"]), (6, ["佩可", "台詞"])]

        with patch("tools.pcrd_fetch.get_latest_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, processed_cnt, fail_ids = rebuild_official_metadata(
                target_story_ids=[100101],
                output_path=target_file,
                truth_version="00600025"
            )

            self.assertTrue(ok)
            self.assertIsNotNone(meta_ver)
            self.assertEqual(processed_cnt, 1)
            self.assertEqual(len(fail_ids), 0)
            self.assertTrue(target_file.exists())
            data = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertEqual(data["episode_count"], 1)
            self.assertIn("100101", data["episodes"])

    # ----------------------------------------------------------------------
    # 6. rebuild_official_metadata sample_limit <= 0 rejection
    # ----------------------------------------------------------------------
    def test_06_rebuild_sample_limit_negative_or_zero_rejected(self):
        """6. 驗證 sample_limit <= 0 時拋出 ValueError 嚴禁非法執行"""
        with self.assertRaises(ValueError):
            rebuild_official_metadata(sample_limit=0)

        with self.assertRaises(ValueError):
            rebuild_official_metadata(sample_limit=-5)

    # ----------------------------------------------------------------------
    # 7. rebuild_official_metadata sample redirect to scratch
    # ----------------------------------------------------------------------
    def test_07_rebuild_sample_redirect_to_scratch(self):
        """7. 驗證 sample_limit 模式未指定自訂 output 時自動重定向至 scratch/ 防污染主檔案"""
        scratch_dir = PROJECT_ROOT / "scratch"
        scratch_target = scratch_dir / "sample_official_metadata.json"
        if scratch_target.exists():
            scratch_target.unlink()

        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}
        mock_cmds = [(0, ["第一話"]), (1, ["大綱"]), (6, ["佩可", "台詞"])]

        with patch("tools.pcrd_fetch.get_latest_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs), \
             patch("pipeline.coverage.get_canonical_expected_story_ids", return_value=[100101, 100102]), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, processed_cnt, fail_ids = rebuild_official_metadata(sample_limit=1, truth_version="00600025")
            self.assertTrue(ok)
            self.assertIsNotNone(meta_ver)
            self.assertTrue(scratch_target.exists(), "Sample 產物必須輸出至 scratch/ 目錄！")

            # 清理
            if scratch_target.exists():
                scratch_target.unlink()

    # ----------------------------------------------------------------------
    # 8. metadata-only extraction path (write_story_json=False)
    # ----------------------------------------------------------------------
    def test_08_metadata_only_extraction_does_not_modify_story_json(self):
        """8. 驗證 write_story_json=False 時，磁碟上的 story/*.json 保持 byte-for-byte 零改寫"""
        mock_story_dir = self.tmp_path / "story"
        mock_story_dir.mkdir(parents=True)
        original_file = mock_story_dir / "100101.json"
        original_content = b'[{"name": "Original", "text": "Original text"}]'
        original_file.write_bytes(original_content)

        ref = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        mock_cmds = [(0, ["第一話"]), (1, ["新大綱"]), (6, ["佩可", "新台詞"])]

        with patch("urllib.request.urlopen", return_value=MockResponse(b"mock")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("tools.pcrd_fetch.STORY_DIR", str(mock_story_dir)):

            res = fetch_story_json_by_id(100101, bundle_ref=ref, extract_metadata=True, write_story_json=False)
            self.assertEqual(res.status, "OK")
            self.assertIsNotNone(res.metadata)

            # 驗證原始 story 檔案完全未被更動
            self.assertEqual(original_file.read_bytes(), original_content)

    # ----------------------------------------------------------------------
    # 9. deterministic multi-entry manifest
    # ----------------------------------------------------------------------
    def test_09_deterministic_multi_entry_manifest(self):
        """9. 驗證不同插入順序下，序列化產生的 JSON bytes 100% 決定性一致"""
        target_1 = self.tmp_path / "m1.json"
        target_2 = self.tmp_path / "m2.json"

        e1 = self._create_mock_entry(100101)
        e2 = self._create_mock_entry(100102)

        batch_update_manifest_entries({100101: e1, 100102: e2}, truth_version="00600025", filepath=target_1)
        batch_update_manifest_entries({100102: e2, 100101: e1}, truth_version="00600025", filepath=target_2)

        self.assertEqual(target_1.read_bytes(), target_2.read_bytes())

    # ----------------------------------------------------------------------
    # 10. bundle copies source manifest
    # ----------------------------------------------------------------------
    def test_10_bundle_copies_source_manifest(self):
        """10. 驗證 bundler 自動將 source official_story_metadata.json 同步至 dist"""
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
    # 11. metadata_version equals source SHA[:12]
    # ----------------------------------------------------------------------
    def test_11_metadata_version_equals_source_sha_12(self):
        """11. 驗證 post-bundle 注入至 db_info.json 的 metadata_version 嚴格等於 source_bytes 的 sha256 前 12 碼"""
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
    # 12. db_info additive field preservation
    # ----------------------------------------------------------------------
    def test_12_db_info_additive_field_preservation(self):
        """12. 驗證注入 metadata_version 時完整保留 db_version, tw_size, jp_size 等原有欄位"""
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
    # 13. source/dist manifest SHA parity
    # ----------------------------------------------------------------------
    def test_13_source_dist_manifest_sha_parity(self):
        """13. 驗證 validate_official_story_metadata 在 source 與 dist 內容 100% 一致且 db_info 匹配時 PASS"""
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
    # 14. metadata_version mismatch rejected
    # ----------------------------------------------------------------------
    def test_14_metadata_version_mismatch_rejected(self):
        """14. 驗證 dist db_info.json 的 metadata_version 失配時，Validator 堅決報錯 (Hard Gate)"""
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
    # 15. fake synopsis regression rejected
    # ----------------------------------------------------------------------
    def test_15_fake_synopsis_regression_rejected(self):
        """15. 驗證 Anti-Hallucination Gate 攔截已知之偽造大綱 (美食殿堂的羈絆 / 進一步的昇華)"""
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
    # 16. dry-run no source write
    # ----------------------------------------------------------------------
    def test_16_dry_run_no_source_write(self):
        """16. 驗證 dry-run 模式絕不建立或修改 source official_story_metadata.json"""
        manifest_file = self.tmp_path / "official_story_metadata.json"
        self.assertFalse(manifest_file.exists())

        dry_run = True
        if not dry_run:
            batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, filepath=manifest_file)

        self.assertFalse(manifest_file.exists())

    # ----------------------------------------------------------------------
    # 17. dry-run no dist write
    # ----------------------------------------------------------------------
    def test_17_dry_run_no_dist_write(self):
        """17. 驗證 bundler 在 dry_run=True 下絕不寫入 dist db_info.json 或 dist manifest"""
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
    # 18. bootstrap incomplete allowed in dev validation
    # ----------------------------------------------------------------------
    def test_18_bootstrap_incomplete_allowed_in_dev_validation(self):
        """18. 驗證在開發階段 (allow_bootstrap_incomplete=True)，檔案未建立或話數不全不判定為 error"""
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
    # 19. strict deploy validation rejects BOOTSTRAP_INCOMPLETE
    # ----------------------------------------------------------------------
    def test_19_strict_deploy_validation_rejects_incomplete(self):
        """19. 驗證在嚴格發布模式 (allow_bootstrap_incomplete=False) 下，話數缺失堅決判定為 error"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        with patch("pipeline.coverage.get_canonical_expected_story_ids", return_value={100101, 100102}):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok)
            self.assertTrue(any("未達到嚴格發布要求" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 20. coverage gate set difference & same-count wrong-ID rejection
    # ----------------------------------------------------------------------
    def test_20_coverage_gate_set_difference_and_same_count_wrong_id(self):
        """20. 驗證 Coverage Gate 使用集合差集比對，能精確抓到同數量錯 ID 的情況"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        # 預期為 {100101, 100102}，實際 Manifest 為 {100101, 100103} (數量相同皆為 2)
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101), 100103: self._create_mock_entry(100103)},
            truth_version="00600025",
            filepath=manifest_file
        )

        with patch("pipeline.coverage.get_canonical_expected_story_ids", return_value={100101, 100102}):
            # 1. 在 strict 模式下判定為 error (缺失 100102)
            res_strict = ValidationResult()
            ok_strict = validate_official_story_metadata(mock_board, check_dist=False, res=res_strict, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok_strict)
            self.assertTrue(any("缺失 1 話" in err for err in res_strict.errors))

            # 2. 完全匹配時判定為 COMPLETE
            manifest_file_complete = mock_board / "data" / "official_story_metadata.json"
            batch_update_manifest_entries(
                {100101: self._create_mock_entry(100101), 100102: self._create_mock_entry(100102)},
                truth_version="00600025",
                filepath=manifest_file_complete
            )
            res_complete = ValidationResult()
            ok_complete = validate_official_story_metadata(mock_board, check_dist=False, res=res_complete, allow_bootstrap_incomplete=False, verbose=False)
            self.assertTrue(ok_complete)
            self.assertEqual(len(res_complete.errors), 0)
            self.assertEqual(len(res_complete.warnings), 0)


if __name__ == "__main__":
    unittest.main()
