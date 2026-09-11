# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Official Story Metadata Pipeline Tests (M2 / M2.1 / M2.2)
涵蓋 25 項針對性整合、生命週期與 Provenance 加固門禁測試 (全數 Hermetic 零外網洩漏)：
1. one TruthVersion snapshot -> exactly one load_story_manifest_bundle_refs call
2. multi-story fetch reuses shared bundle_refs dictionary
3. StoryBundleRef strict validation (rejects invalid truth_version, empty hash, empty/whitespace bundle_name)
4. fetch_story_json_by_id extract_metadata rejects empty/whitespace bundle_name without guess fallback
5. sync_story_batch_with_metadata directly derives snapshot version from bundle_refs without probe
6. sync_story_batch_with_metadata rejects conflicting explicit truth_version with bundle_refs
7. sync_story_batch_with_metadata rejects mixed truth_versions in bundle_refs
8. batch_update_manifest_entries rejects entry provenance truth_version mismatching batch version
9. sync_story_batch_with_metadata batch commit all-success atomic write
10. sync_story_batch_with_metadata mid-batch failure rollback (first OK, second fail -> zero manifest write)
11. Full rebuild replacement semantics clears stale IDs from manifest
12. Incremental sync merge semantics preserves existing untouched episodes
13. Canonical story universe builder pure contract & alternate dashboard_dir isolation
14. Canonical universe DEGRADED and INVALID status propagation
15. rebuild_official_metadata orchestrator helper integration
16. rebuild_official_metadata sample_limit <= 0 rejection (ValueError)
17. rebuild_official_metadata sample redirect to scratch directory (no main manifest pollution)
18. metadata-only extraction path (write_story_json=False byte-for-byte zero story modification)
19. deterministic multi-entry manifest generation (byte-identical regardless of insertion order)
20. bundle copies source manifest to dist/data/official_story_metadata.json
21. metadata_version equals source manifest SHA256[:12]
22. source/dist manifest SHA-256 parity gate & db_info metadata_version validation
23. dist db_info metadata_version mismatch hard rejection
24. fake synopsis / anti-hallucination regression guard
25. strict validation rejects unexpected ID, missing ID, and universe corruption; dev validation warns
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
import hashlib
import sqlite3
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
    compute_target_fingerprint,
    save_bootstrap_checkpoint,
    load_and_validate_bootstrap_checkpoint,
    CHECKPOINT_STATE_FILENAME,
    CHECKPOINT_DATA_FILENAME,
)
from pipeline.coverage import (
    build_canonical_story_universe,
    get_canonical_expected_story_ids,
    analyze_coverage,
    CanonicalStoryUniverse,
    CoverageAnalysisStatus,
)
from pipeline.validate import (
    validate_official_story_metadata,
    validate_story_map,
    ValidationResult,
)
from tools.pcrd_fetch import (
    StoryBundleRef,
    StoryFetchResult,
    fetch_story_json_by_id,
    sync_story_batch_with_metadata,
    load_story_manifest_bundle_refs,
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
    # 3. StoryBundleRef strict validation
    # ----------------------------------------------------------------------
    def test_03_story_bundle_ref_strict_validation(self):
        """3. 驗證 StoryBundleRef 欄位格式嚴格防護 (8碼版號、非空 Hash、非空/非純空白 bundle_name)"""
        # 合法建構
        valid_ref = StoryBundleRef(100101, "00600025", "hash_1", "storydata_100101.unity3d")
        self.assertEqual(valid_ref.story_id, 100101)

        # 非 8 碼 TruthVersion
        with self.assertRaises(ValueError):
            StoryBundleRef(100101, "600025", "hash_1", "storydata_100101.unity3d")
        with self.assertRaises(ValueError):
            StoryBundleRef(100101, "abcdefgh", "hash_1", "storydata_100101.unity3d")

        # 空 hash
        with self.assertRaises(ValueError):
            StoryBundleRef(100101, "00600025", "", "storydata_100101.unity3d")
        with self.assertRaises(ValueError):
            StoryBundleRef(100101, "00600025", "   ", "storydata_100101.unity3d")

        # 空或純空白 bundle_name
        with self.assertRaises(ValueError):
            StoryBundleRef(100101, "00600025", "hash_1", "")
        with self.assertRaises(ValueError):
            StoryBundleRef(100101, "00600025", "hash_1", "   \t\n")

    # ----------------------------------------------------------------------
    # 4. fetch_story_json_by_id rejects empty bundle_name without guess
    # ----------------------------------------------------------------------
    def test_04_fetch_story_rejects_empty_bundle_name_without_guess(self):
        """4. 驗證 extract_metadata=True 時若 bundle_name 為空或純空白，堅決報錯，嚴禁猜測 fallback"""
        with patch("urllib.request.urlopen", return_value=MockResponse(b"bundle_bytes")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=[(0, ["標題"])]):
            dummy_invalid_ref = MagicMock()
            dummy_invalid_ref.story_id = 100101
            dummy_invalid_ref.cdn_bundle_hash = "h1"
            dummy_invalid_ref.bundle_name = "   "
            dummy_invalid_ref.truth_version = "00600025"

            res = fetch_story_json_by_id(100101, bundle_ref=dummy_invalid_ref, extract_metadata=True, write_story_json=False)
            self.assertEqual(res.status, "PARSE_ERROR")
            self.assertIn("空白猜測", res.error_message)

    # ----------------------------------------------------------------------
    # 5. sync_story_batch derives version from bundle_refs without probe
    # ----------------------------------------------------------------------
    def test_05_sync_batch_derives_version_from_refs_without_probe(self):
        """5. 驗證傳入 bundle_refs 時，sync_story_batch_with_metadata 直接使用其版號，絕不呼叫 _get_sonet_ver"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}
        mock_cmds = [(0, ["第一話"]), (1, ["大綱"]), (6, ["佩可", "台詞"])]

        with patch("tools.pcrd_fetch._get_sonet_ver") as mock_probe, \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bytes")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, succ, fail = sync_story_batch_with_metadata(
                [100101],
                manifest_path=target_file,
                bundle_refs=shared_refs,
                write_story_json=False
            )
            self.assertTrue(ok)
            mock_probe.assert_not_called()

    # ----------------------------------------------------------------------
    # 6. sync_story_batch rejects conflicting explicit truth_version
    # ----------------------------------------------------------------------
    def test_06_sync_batch_rejects_conflicting_explicit_version(self):
        """6. 驗證傳入之 truth_version 與 bundle_refs 內部版號衝突時，拋出 ValueError"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}

        with self.assertRaises(ValueError):
            sync_story_batch_with_metadata(
                [100101],
                truth_version="00500030",  # 與 ref1 00600025 衝突
                manifest_path=target_file,
                bundle_refs=shared_refs,
                write_story_json=False
            )

    # ----------------------------------------------------------------------
    # 7. sync_story_batch rejects mixed truth_versions in bundle_refs
    # ----------------------------------------------------------------------
    def test_07_sync_batch_rejects_mixed_truth_versions_in_refs(self):
        """7. 驗證 bundle_refs 中若混雜多種 TruthVersion，違反單一快照合約，拋出 ValueError"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        ref2 = StoryBundleRef(100102, "00500030", "h2", "storydata_100102.unity3d")
        mixed_refs = {100101: ref1, 100102: ref2}

        with self.assertRaises(ValueError):
            sync_story_batch_with_metadata(
                [100101, 100102],
                manifest_path=target_file,
                bundle_refs=mixed_refs,
                write_story_json=False
            )

    # ----------------------------------------------------------------------
    # 8. batch_update_manifest_entries rejects provenance version mismatch
    # ----------------------------------------------------------------------
    def test_08_batch_update_rejects_provenance_version_mismatch(self):
        """8. 驗證 batch_update_manifest_entries 檢查 incoming entry provenance 與 batch version 一致性"""
        manifest_file = self.tmp_path / "official_story_metadata.json"
        entry_tv25 = self._create_mock_entry(100101, tv="00600025")

        with self.assertRaises(ValueError):
            batch_update_manifest_entries(
                {100101: entry_tv25},
                truth_version="00500030",  # Batch version 與 entry provenance 不符
                filepath=manifest_file
            )

    # ----------------------------------------------------------------------
    # 9. sync_story_batch_with_metadata all success
    # ----------------------------------------------------------------------
    def test_09_sync_story_batch_all_success(self):
        """9. 驗證 sync_story_batch_with_metadata 在多話全數成功時執行單次快照並一次原子寫入"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        ref2 = StoryBundleRef(100102, "00600025", "h2", "storydata_100102.unity3d")
        shared_refs = {100101: ref1, 100102: ref2}
        mock_cmds = [(0, ["話數標題"]), (1, ["官方大綱文字"]), (6, ["佩可", "台詞"])]

        with patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, succ_ids, fail_ids = sync_story_batch_with_metadata(
                [100101, 100102],
                manifest_path=target_file,
                bundle_refs=shared_refs,
                write_story_json=False
            )

            self.assertTrue(ok)
            self.assertEqual(len(succ_ids), 2)
            self.assertEqual(len(fail_ids), 0)
            self.assertIsNotNone(meta_ver)
            self.assertTrue(target_file.exists())

            data = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertEqual(data["episode_count"], 2)
            self.assertIn("100101", data["episodes"])
            self.assertIn("100102", data["episodes"])

    # ----------------------------------------------------------------------
    # 10. sync_story_batch mid-batch failure rollback (first OK, second fail)
    # ----------------------------------------------------------------------
    def test_10_sync_story_batch_mid_batch_failure_rollback(self):
        """10. 驗證真實 mid-batch 失敗 (第1話成功、第2話失敗) 時原子回滾，Manifest 零寫入"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        ref2 = StoryBundleRef(100102, "00600025", "h2", "storydata_100102.unity3d")
        shared_refs = {100101: ref1, 100102: ref2}

        def mock_fetch(sid, **kwargs):
            if sid == 100101:
                return StoryFetchResult(
                    story_id=100101, status="OK", dialogue_count=5, hash="h1",
                    metadata=self._create_mock_entry(100101)
                )
            else:
                return StoryFetchResult(
                    story_id=100102, status="NETWORK_ERROR", error_message="Connection timed out"
                )

        with patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=mock_fetch):
            ok, meta_ver, succ_ids, fail_ids = sync_story_batch_with_metadata(
                [100101, 100102],
                manifest_path=target_file,
                bundle_refs=shared_refs,
                write_story_json=False
            )

            self.assertFalse(ok)
            self.assertEqual(succ_ids, [100101])
            self.assertEqual(fail_ids, [100102])
            self.assertIsNone(meta_ver)
            self.assertFalse(target_file.exists(), "mid-batch 失敗時 Manifest 絕不可被寫入！")

    # ----------------------------------------------------------------------
    # 11. Full rebuild replacement semantics clears stale IDs
    # ----------------------------------------------------------------------
    def test_11_full_rebuild_replacement_clears_stale_ids(self):
        """11. 驗證 Full Rebuild (replace_existing=True) 採完全替換語意，清除歷史過期 stale ID"""
        target_file = self.tmp_path / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101), 999999: self._create_mock_entry(999999)},
            truth_version="00600025",
            filepath=target_file
        )
        data_before = json.loads(target_file.read_text(encoding="utf-8"))
        self.assertIn("999999", data_before["episodes"])

        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        ref2 = StoryBundleRef(100102, "00600025", "h2", "storydata_100102.unity3d")
        shared_refs = {100101: ref1, 100102: ref2}
        mock_cmds = [(0, ["標題"]), (1, ["大綱"]), (6, ["佩可", "台詞"])]

        with patch("pipeline.fetch.get_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, count, fail_ids = rebuild_official_metadata(
                truth_version="00600025",
                target_story_ids=[100101, 100102],
                output_path=target_file,
                write_story_json=False
            )
            self.assertTrue(ok)
            self.assertEqual(count, 2)

            data_after = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertNotIn("999999", data_after["episodes"], "Full Rebuild 必須清除已不在 target 的 stale ID！")
            self.assertEqual(data_after["episode_count"], 2)

    # ----------------------------------------------------------------------
    # 12. Incremental sync merge semantics preserves untouched episodes
    # ----------------------------------------------------------------------
    def test_12_incremental_sync_merge_preserves_untouched_episodes(self):
        """12. 驗證 Incremental Sync (replace_existing=False) 保持 Merge 語意，保留其他未修改話數"""
        target_file = self.tmp_path / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},
            truth_version="00600025",
            filepath=target_file
        )

        ref2 = StoryBundleRef(100102, "00600025", "h2", "storydata_100102.unity3d")
        shared_refs = {100102: ref2}
        mock_cmds = [(0, ["話數2"]), (1, ["大綱2"]), (6, ["佩可", "台詞2"])]

        with patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, succ, fail = sync_story_batch_with_metadata(
                [100102],
                manifest_path=target_file,
                bundle_refs=shared_refs,
                replace_existing=False,
                write_story_json=False
            )
            self.assertTrue(ok)
            data = json.loads(target_file.read_text(encoding="utf-8"))
            self.assertEqual(data["episode_count"], 2)
            self.assertIn("100101", data["episodes"])
            self.assertIn("100102", data["episodes"])

    # ----------------------------------------------------------------------
    # 13. Canonical Universe Builder pure contract & alternate DB isolation
    # ----------------------------------------------------------------------
    def test_13_canonical_universe_builder_isolation(self):
        """13. 驗證 build_canonical_story_universe 嚴格使用傳入之 dashboard_dir 本地 DB，零全域污染"""
        alt_board = self.tmp_path / "alt_dashboard"
        alt_data = alt_board / "data"
        alt_data.mkdir(parents=True)

        alt_db = alt_board / "redive_tw.db"
        conn = sqlite3.connect(str(alt_db))
        cur = conn.cursor()
        cur.execute("CREATE TABLE story_detail (story_id INTEGER PRIMARY KEY, title TEXT)")
        cur.execute("CREATE TABLE chara_story_status (story_id INTEGER PRIMARY KEY)")
        cur.execute("INSERT INTO story_detail VALUES (2001001, '第1章')")
        cur.execute("INSERT INTO story_detail VALUES (2001002, '第2章')")
        cur.execute("INSERT INTO chara_story_status VALUES (1001001)")
        conn.commit()
        conn.close()

        (alt_data / "tracked_characters.json").write_text(json.dumps({"characters": [{"unit_id": 100101}]}), encoding="utf-8")
        (alt_data / "branch_stories.json").write_text(json.dumps({"stories": [{"story_id": 2001099}]}), encoding="utf-8")
        (alt_data / "extra_events.json").write_text(json.dumps({"stories": [{"story_id": 5001001}]}), encoding="utf-8")

        univ = build_canonical_story_universe(alt_board)
        self.assertEqual(univ.analysis_status, CoverageAnalysisStatus.VALID)
        self.assertIn(2001001, univ.expected_ids)
        self.assertIn(2001002, univ.expected_ids)
        self.assertIn(2001099, univ.expected_ids)
        self.assertIn(5001001, univ.expected_ids)
        self.assertIn(1001001, univ.expected_ids)

    # ----------------------------------------------------------------------
    # 14. Canonical universe DEGRADED / INVALID status propagation
    # ----------------------------------------------------------------------
    def test_14_canonical_universe_degraded_and_invalid_status(self):
        """14. 驗證資料庫缺失時為 INVALID，配置檔案缺失時為 DEGRADED"""
        empty_board = self.tmp_path / "empty_board"
        empty_board.mkdir(parents=True)

        univ_invalid = build_canonical_story_universe(empty_board)
        self.assertEqual(univ_invalid.analysis_status, CoverageAnalysisStatus.INVALID)
        self.assertTrue(any("redive_tw.db" in err for err in univ_invalid.analysis_errors))

        db_path = empty_board / "redive_tw.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE story_detail (story_id INTEGER)")
        conn.close()

        univ_degraded = build_canonical_story_universe(empty_board)
        self.assertEqual(univ_degraded.analysis_status, CoverageAnalysisStatus.DEGRADED)

    # ----------------------------------------------------------------------
    # 15. rebuild_official_metadata orchestrator helper
    # ----------------------------------------------------------------------
    def test_15_rebuild_official_metadata_orchestrator(self):
        """15. 驗證 rebuild_official_metadata 獨立 orchestrator helper 正確產出 Manifest"""
        target_file = self.tmp_path / "official_story_metadata.json"
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}
        mock_cmds = [(0, ["話數標題"]), (1, ["官方大綱文字"]), (6, ["佩可", "台詞"])]

        with patch("pipeline.fetch.get_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            ok, meta_ver, count, fail_ids = rebuild_official_metadata(
                truth_version="00600025",
                target_story_ids=[100101],
                output_path=target_file,
                write_story_json=False
            )

            self.assertTrue(ok)
            self.assertEqual(count, 1)
            self.assertEqual(len(fail_ids), 0)
            self.assertIsNotNone(meta_ver)
            self.assertTrue(target_file.exists())

    # ----------------------------------------------------------------------
    # 16. rebuild_official_metadata sample_limit <= 0 rejection
    # ----------------------------------------------------------------------
    def test_16_rebuild_sample_limit_invalid_rejected(self):
        """16. 驗證 sample_limit <= 0 時拋出 ValueError"""
        with self.assertRaises(ValueError):
            rebuild_official_metadata(sample_limit=0)
        with self.assertRaises(ValueError):
            rebuild_official_metadata(sample_limit=-5)

    # ----------------------------------------------------------------------
    # 17. sample redirect to scratch directory
    # ----------------------------------------------------------------------
    def test_17_sample_redirect_to_scratch(self):
        """17. 驗證 sample_limit 模式未指定 output 時自動重定向至 scratch/ 防止污染 production"""
        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}
        mock_cmds = [(0, ["標題"]), (1, ["大綱"]), (6, ["佩可", "台詞"])]

        with patch("pipeline.fetch.get_truth_version", return_value="00600025"), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=shared_refs), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            scratch_target = self.tmp_path / "scratch" / "sample_official_metadata.json"
            scratch_target.parent.mkdir(parents=True, exist_ok=True)

            with patch("pipeline.metadata_manifest.PROJECT_ROOT", self.tmp_path):
                ok, meta_ver, count, fail_ids = rebuild_official_metadata(
                    truth_version="00600025",
                    target_story_ids=[100101],
                    sample_limit=1,
                    write_story_json=False
                )
                self.assertTrue(ok)
                self.assertTrue(scratch_target.exists(), "Sample 模式應自動轉向 scratch/ 目錄")

    # ----------------------------------------------------------------------
    # 18. metadata-only path (write_story_json=False)
    # ----------------------------------------------------------------------
    def test_18_metadata_only_zero_story_modification(self):
        """18. 驗證 write_story_json=False 時對話 JSON 零寫入、零修改"""
        story_file = self.tmp_path / "story" / "100101.json"
        story_file.parent.mkdir(parents=True, exist_ok=True)
        original_bytes = b'[{"name":"original","words":"old"}]'
        story_file.write_bytes(original_bytes)

        ref1 = StoryBundleRef(100101, "00600025", "h1", "storydata_100101.unity3d")
        shared_refs = {100101: ref1}
        mock_cmds = [(0, ["新標題"]), (1, ["新大綱"]), (6, ["佩可", "新台詞"])]

        with patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):

            res = fetch_story_json_by_id(100101, bundle_ref=ref1, extract_metadata=True, write_story_json=False)
            self.assertEqual(res.status, "OK")
            self.assertIsNone(res.written_path)
            self.assertEqual(story_file.read_bytes(), original_bytes, "write_story_json=False 絕不可觸碰對白 JSON")

    # ----------------------------------------------------------------------
    # 19. deterministic manifest generation
    # ----------------------------------------------------------------------
    def test_19_deterministic_manifest_order_independence(self):
        """19. 驗證無論話數寫入順序為何，序列化輸出之 Manifest 二進位與 metadata_version 完全一致"""
        manifest_a = create_empty_manifest(truth_version="00600025")
        manifest_b = create_empty_manifest(truth_version="00600025")

        manifest_a["episodes"]["100101"] = self._create_mock_entry(100101)
        manifest_a["episodes"]["100102"] = self._create_mock_entry(100102)
        manifest_a["episode_count"] = 2

        manifest_b["episodes"]["100102"] = self._create_mock_entry(100102)
        manifest_b["episodes"]["100101"] = self._create_mock_entry(100101)
        manifest_b["episode_count"] = 2

        str_a = serialize_canonical_manifest(manifest_a)
        str_b = serialize_canonical_manifest(manifest_b)
        self.assertEqual(str_a, str_b)
        self.assertEqual(compute_manifest_version(str_a.encode("utf-8")), compute_manifest_version(str_b.encode("utf-8")))

    # ----------------------------------------------------------------------
    # 20. bundle copies source manifest to dist
    # ----------------------------------------------------------------------
    def test_20_bundle_copies_manifest_to_dist(self):
        """20. 驗證 bundler 成功將 source official_story_metadata.json 複製至 dist/data/"""
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
        self.assertEqual(dist_manifest.read_bytes(), manifest_file.read_bytes())

    # ----------------------------------------------------------------------
    # 21. metadata_version equals source sha256[:12]
    # ----------------------------------------------------------------------
    def test_21_metadata_version_sha256_parity(self):
        """21. 驗證 metadata_version 嚴格等於 source official_story_metadata.json 之 SHA256[:12]"""
        manifest_file = self.tmp_path / "official_story_metadata.json"
        m_ver = batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},
            truth_version="00600025",
            filepath=manifest_file
        )
        content = manifest_file.read_bytes()
        expected_ver = hashlib.sha256(content).hexdigest()[:12]
        self.assertEqual(m_ver, expected_ver)

    # ----------------------------------------------------------------------
    # 22. source/dist manifest SHA-256 parity gate
    # ----------------------------------------------------------------------
    def test_22_source_dist_parity_gate(self):
        """22. 驗證 validate_official_story_metadata 嚴格執行 Source/Dist SHA-256 對齊門禁"""
        mock_board = self.tmp_path / "dashboard"
        mock_dist = self.tmp_path / "dist"
        (mock_board / "data").mkdir(parents=True)
        (mock_dist / "data").mkdir(parents=True)

        manifest_file = mock_board / "data" / "official_story_metadata.json"
        m_ver = batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        dist_manifest = mock_dist / "data" / "official_story_metadata.json"
        dist_manifest.write_bytes(manifest_file.read_bytes())

        (mock_dist / "data" / "db_info.json").write_text(
            json.dumps({"db_version": "hash_123456", "tw_size": 100, "jp_size": 0, "metadata_version": m_ver}),
            encoding="utf-8"
        )

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, dist_dir=mock_dist, check_dist=True, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertTrue(ok)
        self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 23. dist db_info metadata_version mismatch hard rejection
    # ----------------------------------------------------------------------
    def test_23_dist_db_info_metadata_version_mismatch_rejected(self):
        """23. 驗證 dist db_info.json 的 metadata_version 失配時，Validator 堅決報錯 (Hard Gate)"""
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
    # 24. fake synopsis / anti-hallucination regression guard
    # ----------------------------------------------------------------------
    def test_24_fake_synopsis_regression_rejected(self):
        """24. 驗證 Anti-Hallucination Gate 攔截已知之偽造大綱 (美食殿堂的羈絆 / 進一步的昇華)"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        fake_entry = self._create_mock_entry(100101, synopsis="本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。")
        batch_update_manifest_entries({100101: fake_entry}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("包含已確認之假大綱/幻覺文字" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 25. strict validation rejects unexpected ID, missing ID, and universe error
    # ----------------------------------------------------------------------
    def test_25_strict_validation_unexpected_and_missing_id_gate(self):
        """25. 驗證 Strict 門禁嚴格拒絕 unexpected_ids、missing_ids 與 Universe DEGRADED"""
        mock_board = self.tmp_path / "dashboard"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        # 1. 含有 unexpected ID (預期 {100101}，實際含有 999999)
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101), 999999: self._create_mock_entry(999999)},
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            # Strict 模式：拒絕 unexpected ID
            res_strict = ValidationResult()
            ok_strict = validate_official_story_metadata(mock_board, check_dist=False, res=res_strict, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok_strict)
            self.assertTrue(any("非 Eligible 話數元數據" in err or "非 Canonical 話數元數據" in err for err in res_strict.errors))

            # Dev 模式：發出 Warning
            res_dev = ValidationResult()
            ok_dev = validate_official_story_metadata(mock_board, check_dist=False, res=res_dev, allow_bootstrap_incomplete=True, verbose=False)
            self.assertTrue(ok_dev)
            self.assertTrue(any("非 Eligible 話數元數據" in w or "非 Canonical 話數元數據" in w for w in res_dev.warnings))

        # 2. Universe 非 VALID 時 strict 模式拒絕
        mock_univ_degraded = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "MISSING"},
            analysis_status=CoverageAnalysisStatus.DEGRADED,
            analysis_errors=["tracked_characters missing"]
        )
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ_degraded):
            res_strict2 = ValidationResult()
            ok_strict2 = validate_official_story_metadata(mock_board, check_dist=False, res=res_strict2, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok_strict2)
            self.assertTrue(any("來源健康狀態異常" in err for err in res_strict2.errors))

    # ----------------------------------------------------------------------
    # 26. Destructive-Rebuild Safety: DEGRADED Universe Rejection
    # ----------------------------------------------------------------------
    @patch("pipeline.coverage.build_canonical_story_universe")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    @patch("tools.pcrd_fetch._http_get")
    def test_26_rebuild_degraded_universe_rejected_and_safe(self, mock_http, mock_load_refs, mock_build_univ):
        """26. 驗證 Universe DEGRADED 時 full rebuild 立即安全拒絕，零網路請求，manifest bytes 不變"""
        manifest_file = self.tmp_path / "official_story_metadata.json"
        initial_entry = self._create_mock_entry(100101)
        batch_update_manifest_entries({100101: initial_entry}, truth_version="00600025", filepath=manifest_file)
        initial_bytes = manifest_file.read_bytes()

        mock_build_univ.return_value = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "ERROR (Corrupted)"},
            analysis_status=CoverageAnalysisStatus.DEGRADED,
            analysis_errors=["tracked_characters DB error"]
        )

        ok, m_ver, count, failed = rebuild_official_metadata(output_path=manifest_file, truth_version="00600025")

        self.assertFalse(ok)
        self.assertIsNone(m_ver)
        self.assertEqual(count, 0)
        self.assertEqual(manifest_file.read_bytes(), initial_bytes)
        mock_load_refs.assert_not_called()
        mock_http.assert_not_called()

    # ----------------------------------------------------------------------
    # 27. Destructive-Rebuild Safety: INVALID Universe Rejection
    # ----------------------------------------------------------------------
    @patch("pipeline.coverage.build_canonical_story_universe")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    @patch("tools.pcrd_fetch._http_get")
    def test_27_rebuild_invalid_universe_rejected_and_safe(self, mock_http, mock_load_refs, mock_build_univ):
        """27. 驗證 Universe INVALID 時 full rebuild 立即安全拒絕，零網路請求，manifest bytes 不變"""
        manifest_file = self.tmp_path / "official_story_metadata.json"
        initial_entry = self._create_mock_entry(100101)
        batch_update_manifest_entries({100101: initial_entry}, truth_version="00600025", filepath=manifest_file)
        initial_bytes = manifest_file.read_bytes()

        mock_build_univ.return_value = CanonicalStoryUniverse(
            required_ids=set(),
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids=set(),
            source_status={"database": "MISSING", "tracked_characters": "OK"},
            analysis_status=CoverageAnalysisStatus.INVALID,
            analysis_errors=["database missing"]
        )

        ok, m_ver, count, failed = rebuild_official_metadata(output_path=manifest_file, truth_version="00600025")

        self.assertFalse(ok)
        self.assertIsNone(m_ver)
        self.assertEqual(count, 0)
        self.assertEqual(manifest_file.read_bytes(), initial_bytes)
        mock_load_refs.assert_not_called()
        mock_http.assert_not_called()

    # ----------------------------------------------------------------------
    # 28. Destructive-Rebuild Safety: Empty Canonical Universe Rejection
    # ----------------------------------------------------------------------
    @patch("pipeline.coverage.build_canonical_story_universe")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    @patch("tools.pcrd_fetch._http_get")
    def test_28_rebuild_empty_canonical_universe_rejected(self, mock_http, mock_load_refs, mock_build_univ):
        """28. 驗證 Universe 雖為 VALID 但 eligible/local_present 為空時，禁止 replacement 覆寫現有 manifest"""
        mock_dash = self.tmp_path / "dashboard_28"
        mock_dash.mkdir(parents=True, exist_ok=True)
        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        initial_entry = self._create_mock_entry(100101)
        batch_update_manifest_entries({100101: initial_entry}, truth_version="00600025", filepath=manifest_file)
        initial_bytes = manifest_file.read_bytes()

        mock_build_univ.return_value = CanonicalStoryUniverse(
            required_ids=set(),
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids=set(),
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )

        ok, m_ver, count, failed = rebuild_official_metadata(
            output_path=manifest_file,
            truth_version="00600025",
            dashboard_dir=mock_dash
        )

        self.assertFalse(ok)
        self.assertIsNone(m_ver)
        self.assertEqual(count, 0)
        self.assertEqual(manifest_file.read_bytes(), initial_bytes)
        mock_load_refs.assert_not_called()
        mock_http.assert_not_called()

    # ----------------------------------------------------------------------
    # 29. Canonical Source Health: Tracked Character DB Query with 0 Rows
    # ----------------------------------------------------------------------
    def test_29_tracked_char_db_query_zero_rows_fallback_healthy(self):
        """29. 驗證 tracked_characters 查詢 DB 成功但為 0 rows 時，依 policy 正常 fallback 4 話且來源保持健康 (VALID)"""
        mock_dash = self.tmp_path / "dashboard_29"
        mock_data = mock_dash / "data"
        mock_data.mkdir(parents=True)
        db_path = mock_dash / "redive_tw.db"

        # 建立合法 SQLite 資料庫
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("CREATE TABLE story_detail (story_id INTEGER PRIMARY KEY)")
        cur.execute("INSERT INTO story_detail VALUES (200101)")
        cur.execute("CREATE TABLE chara_story_status (story_id INTEGER PRIMARY KEY)")
        # 不插入任何 chara_story_status 資料 (0 rows)
        conn.commit()
        conn.close()

        # 建立 tracked_characters.json, branch_stories.json, extra_events.json
        with open(mock_data / "tracked_characters.json", "w", encoding="utf-8") as f:
            json.dump({"characters": [{"unit_id": 100101}]}, f)
        with open(mock_data / "branch_stories.json", "w", encoding="utf-8") as f:
            json.dump({"stories": []}, f)
        with open(mock_data / "extra_events.json", "w", encoding="utf-8") as f:
            json.dump({"stories": []}, f)

        # 直接測試 helper
        from pipeline.coverage import _get_story_ids_from_db_isolated
        ids = _get_story_ids_from_db_isolated(db_path, 100101)
        self.assertEqual(ids, [1001001, 1001002, 1001003, 1001004])

        # 測試 universe
        univ = build_canonical_story_universe(mock_dash)
        self.assertEqual(univ.source_status["database"], "OK")
        self.assertEqual(univ.source_status["tracked_characters"], "OK")
        self.assertEqual(univ.analysis_status, CoverageAnalysisStatus.VALID)
        self.assertTrue({1001001, 1001002, 1001003, 1001004}.issubset(univ.expected_ids))

    # ----------------------------------------------------------------------
    # 30. Canonical Source Health: Tracked Character DB SQL Error -> Unhealthy Universe
    # ----------------------------------------------------------------------
    def test_30_tracked_char_db_sql_error_causes_unhealthy_universe(self):
        """30. 驗證 tracked_characters 查詢 DB 遇到 SQL/table 錯誤時，不得吞掉例外並偽裝健康，必須標記 DEGRADED"""
        mock_dash = self.tmp_path / "dashboard_30"
        mock_data = mock_dash / "data"
        mock_data.mkdir(parents=True)
        db_path = mock_dash / "redive_tw.db"

        # 建立 SQLite 資料庫，但缺少 chara_story_status 表格 (觸發 SQL Error)
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("CREATE TABLE story_detail (story_id INTEGER PRIMARY KEY)")
        cur.execute("INSERT INTO story_detail VALUES (200101)")
        conn.commit()
        conn.close()

        with open(mock_data / "tracked_characters.json", "w", encoding="utf-8") as f:
            json.dump({"characters": [{"unit_id": 100101}]}, f)
        with open(mock_data / "branch_stories.json", "w", encoding="utf-8") as f:
            json.dump({"stories": []}, f)
        with open(mock_data / "extra_events.json", "w", encoding="utf-8") as f:
            json.dump({"stories": []}, f)

        univ = build_canonical_story_universe(mock_dash)
        self.assertEqual(univ.source_status["database"], "OK")
        self.assertTrue(univ.source_status["tracked_characters"].startswith("ERROR"))
        self.assertEqual(univ.analysis_status, CoverageAnalysisStatus.DEGRADED)
        self.assertTrue(len(univ.analysis_errors) > 0)



    # ----------------------------------------------------------------------
    # 31. Local numeric story outside canonical expected -> STILL Metadata Eligible
    # ----------------------------------------------------------------------
    def test_31_local_numeric_story_outside_canonical_is_eligible(self):
        """31. 驗證本地 numeric story 不在 canonical.expected_ids (如 5001) 時，仍必須歸入 eligible_ids"""
        mock_dash = self.tmp_path / "dashboard_31"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "5001.json").write_text("[]", encoding="utf-8")  # 非 canonical 話數

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},  # canonical 僅有 100101
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        from pipeline.coverage import build_metadata_eligible_story_universe
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            m_univ = build_metadata_eligible_story_universe(mock_dash)
            self.assertEqual(m_univ.eligible_ids, {100101, 5001})
            self.assertEqual(m_univ.local_present_ids, {100101, 5001})
            self.assertEqual(m_univ.eligible_ids, m_univ.local_present_ids)

    # ----------------------------------------------------------------------
    # 32. Canonical {1}, Local {1, 5001}, Manifest {1} -> Strict FAIL missing 5001
    # ----------------------------------------------------------------------
    def test_32_canonical_1_local_1_5001_manifest_1_strict_fail_missing_5001(self):
        """32. 驗證 Canonical {1}、Local {1, 5001} 但 Manifest 僅有 {1} 時，Strict 驗證回報缺失 5001"""
        mock_dash = self.tmp_path / "dashboard_32"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "5001.json").write_text("[]", encoding="utf-8")

        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_dash, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok)
            self.assertTrue(any("缺失 1 話" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 33. Canonical {1}, Local {1, 5001}, Manifest {1, 5001} -> Strict PASS
    # ----------------------------------------------------------------------
    def test_33_canonical_1_local_1_5001_manifest_1_5001_strict_pass(self):
        """33. 驗證 Manifest 同步包含 {1, 5001} 時，Strict 驗證 PASS"""
        mock_dash = self.tmp_path / "dashboard_33"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "5001.json").write_text("[]", encoding="utf-8")

        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101), 5001: self._create_mock_entry(5001)},
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_dash, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertTrue(ok)
            self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 34. Optional DB row without local JSON -> NOT eligible, allows complete
    # ----------------------------------------------------------------------
    def test_34_optional_db_row_not_local_not_required_in_metadata(self):
        """34. 驗證 Optional 話數若本地無 story JSON，不進入 eligible_ids，且不阻止 strict complete"""
        mock_dash = self.tmp_path / "dashboard_34"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        # 200101 為 optional，本地無對應 json

        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids={200101},
            unknown_ids=set(),
            expected_ids={100101, 200101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_dash, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertTrue(ok)
            self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 35. Optional DB row adds local JSON -> Strict FAIL until Manifest updated
    # ----------------------------------------------------------------------
    def test_35_optional_db_row_adds_local_json_strict_fails_until_metadata_added(self):
        """35. 驗證當 Optional 話數新增本地 JSON 後，若 Manifest 未同步則 Strict FAIL，同步後 PASS"""
        mock_dash = self.tmp_path / "dashboard_35"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "200101.json").write_text("[]", encoding="utf-8")  # 新增 200101

        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},  # 尚未包含 200101
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids={200101},
            unknown_ids=set(),
            expected_ids={100101, 200101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_dash, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok)
            self.assertTrue(any("缺失 1 話" in err for err in res.errors))

            # 補齊 200101 元數據
            batch_update_manifest_entries(
                {100101: self._create_mock_entry(100101), 200101: self._create_mock_entry(200101)},
                truth_version="00600025",
                filepath=manifest_file
            )
            res2 = ValidationResult()
            ok2 = validate_official_story_metadata(mock_dash, check_dist=False, res=res2, allow_bootstrap_incomplete=False, verbose=False)
            self.assertTrue(ok2)
            self.assertEqual(len(res2.errors), 0)

    # ----------------------------------------------------------------------
    # 36. Required NOT Local -> Strict FAIL
    # ----------------------------------------------------------------------
    def test_36_required_not_local_causes_strict_fail(self):
        """36. 驗證 Required 話數若本地缺少 story JSON，Strict 門禁堅決拒絕 (Hard FAIL)"""
        mock_dash = self.tmp_path / "dashboard_36"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        # 100101 為 required，但本地目錄為空

        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_dash, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertFalse(ok)
            self.assertTrue(any("核心必備劇本缺少本地 JSON" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 37. Non-numeric JSON (speaker_appearance.json) -> NEVER Eligible
    # ----------------------------------------------------------------------
    def test_37_nonnumeric_speaker_appearance_never_eligible(self):
        """37. 驗證非純數字檔名 (例如 speaker_appearance.json) 絕不納入 eligible_ids"""
        mock_dash = self.tmp_path / "dashboard_37"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "speaker_appearance.json").write_text("{}", encoding="utf-8")
        (mock_dash / "story" / "readme.json").write_text("{}", encoding="utf-8")

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        from pipeline.coverage import build_metadata_eligible_story_universe
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            m_univ = build_metadata_eligible_story_universe(mock_dash)
            self.assertEqual(m_univ.eligible_ids, {100101})
            self.assertNotIn("speaker_appearance", m_univ.eligible_ids)
            self.assertNotIn("readme", m_univ.eligible_ids)

    # ----------------------------------------------------------------------
    # 38. Local Numeric Story Without Bundle Ref -> Bootstrap Preflight FAIL
    # ----------------------------------------------------------------------
    @patch("pipeline.coverage.build_canonical_story_universe")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_38_eligible_story_without_bundle_ref_fails_bootstrap_preflight(self, mock_load_refs, mock_build_univ):
        """38. 驗證當 Local Numeric 話數缺少 CDN bundle_ref 時，rebuild preflight 堅決報錯 (FAIL)"""
        mock_dash = self.tmp_path / "dashboard_38"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")

        mock_build_univ.return_value = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        # mock bundle_refs 為空字典 (缺少 100101)
        mock_load_refs.return_value = {}

        ok, m_ver, count, failed = rebuild_official_metadata(
            truth_version="00600025",
            output_path=mock_dash / "data" / "official_story_metadata.json",
            dashboard_dir=mock_dash
        )
        self.assertFalse(ok)
        self.assertIn(100101, failed)

    # ----------------------------------------------------------------------
    # 39. All Local Numeric Stories Have Bundle Refs -> Bootstrap Succeeds
    # ----------------------------------------------------------------------
    @patch("pipeline.coverage.build_canonical_story_universe")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_39_all_local_numeric_have_bundle_ref_allows_bootstrap(self, mock_load_refs, mock_build_univ):
        """39. 驗證所有 Local Numeric 話數均具備 bundle_ref 時，bootstrap 成功執行"""
        mock_dash = self.tmp_path / "dashboard_39"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "5001.json").write_text("[]", encoding="utf-8")

        mock_build_univ.return_value = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        mock_load_refs.return_value = {
            100101: StoryBundleRef(100101, "00600025", "hash1", "storydata_100101.unity3d"),
            5001: StoryBundleRef(5001, "00600025", "hash2", "storydata_5001.unity3d"),
        }
        mock_cmds = [(0, ["話數標題"]), (1, ["官方大綱文字"]), (6, ["佩可", "台詞"])]
        with patch("pipeline.fetch.get_truth_version", return_value="00600025"), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=mock_dash / "data" / "official_story_metadata.json",
                dashboard_dir=mock_dash
            )
            self.assertTrue(ok)
            self.assertEqual(count, 2)
            self.assertEqual(failed, [])

    # ----------------------------------------------------------------------
    # 40. Optional Non-Local Without Bundle Ref -> Bootstrap Preflight Does NOT Fail
    # ----------------------------------------------------------------------
    @patch("pipeline.coverage.build_canonical_story_universe")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_40_optional_non_local_without_bundle_ref_succeeds_bootstrap_preflight(self, mock_load_refs, mock_build_univ):
        """40. 驗證 Optional 且非本地之話數 (如 DB 預載) 即使缺少 bundle_ref，亦不阻止 eligible bootstrap 執行"""
        mock_dash = self.tmp_path / "dashboard_40"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        # 100102 為 optional 且本地無 json

        mock_build_univ.return_value = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids={100102},
            unknown_ids=set(),
            expected_ids={100101, 100102},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        # CDN 僅有 100101 之 bundle_ref (無 100102)
        mock_load_refs.return_value = {
            100101: StoryBundleRef(
                story_id=100101,
                truth_version="00600025",
                cdn_bundle_hash="hash100101",
                bundle_name="storydata_100101.unity3d"
            )
        }
        mock_cmds = [(0, ["話數標題"]), (1, ["官方大綱文字"]), (6, ["佩可", "台詞"])]
        with patch("pipeline.fetch.get_truth_version", return_value="00600025"), \
             patch("urllib.request.urlopen", return_value=MockResponse(b"mock_bundle")), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=mock_dash / "data" / "official_story_metadata.json",
                dashboard_dir=mock_dash
            )
            self.assertTrue(ok)
            self.assertEqual(count, 1)
            self.assertEqual(failed, [])

    # ----------------------------------------------------------------------
    # 41. Validator Zero Live Network Dependency
    # ----------------------------------------------------------------------
    def test_41_validator_zero_live_network_dependency(self):
        """41. 驗證 Validator 在完全阻斷網路的情況下，仍能 100% 離線完成驗證"""
        mock_dash = self.tmp_path / "dashboard_41"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")

        manifest_file = mock_dash / "data" / "official_story_metadata.json"
        batch_update_manifest_entries(
            {100101: self._create_mock_entry(100101)},
            truth_version="00600025",
            filepath=manifest_file
        )

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )

        def forbidden_network(*args, **kwargs):
            raise RuntimeError("Live Network Access is Strictly Forbidden in Validator!")

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("urllib.request.urlopen", side_effect=forbidden_network), \
             patch("tools.pcrd_fetch._http_get", side_effect=forbidden_network):
            res = ValidationResult()
            ok = validate_official_story_metadata(mock_dash, check_dist=False, res=res, allow_bootstrap_incomplete=False, verbose=False)
            self.assertTrue(ok)
            self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 42. ADR D2.2 Local Parity Contract Regression Guard
    # ----------------------------------------------------------------------
    def test_42_adr_d22_local_parity_contract_assertion(self):
        """42. ADR D2.2 回歸防護測試：official_story_metadata 與 numeric dashboard/story/*.json 嚴格為 1:1 對等合約"""
        mock_dash = self.tmp_path / "dashboard_42"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        for sid in [100101, 100102, 200101, 5001]:
            (mock_dash / "story" / f"{sid}.json").write_text("[]", encoding="utf-8")

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids={100102, 200101},
            unknown_ids=set(),
            expected_ids={100101, 100102, 200101},  # 注意：5001 不在 canonical expected 內
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        from pipeline.coverage import build_metadata_eligible_story_universe
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ):
            m_univ = build_metadata_eligible_story_universe(mock_dash)
            # 斷言：eligible_ids 必須完全等於 local_present_ids
            self.assertEqual(m_univ.eligible_ids, {100101, 100102, 200101, 5001})
            self.assertEqual(m_univ.eligible_ids, m_univ.local_present_ids)
            # 斷言：不得為 canonical.expected_ids (其缺少 5001)
            self.assertNotEqual(m_univ.eligible_ids, mock_univ.expected_ids)



    # ----------------------------------------------------------------------
    # 43. Checkpoint Network Error Saves Progress Manifest Absent
    # ----------------------------------------------------------------------
    def test_43_checkpoint_network_error_saves_progress_manifest_absent(self):
        """43. 模擬第 1 話成功、第 2 話 NETWORK_ERROR，驗證快照保存 1 話、狀態為 IN_PROGRESS、生產清單零寫入"""
        mock_dash = self.tmp_path / "dashboard_43"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "100102.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_43"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101, 100102},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101, 100102},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {
            100101: StoryBundleRef(100101, "00600025", "hash100101", "storydata_100101.unity3d"),
            100102: StoryBundleRef(100102, "00600025", "hash100102", "storydata_100102.unity3d"),
        }

        def mock_fetch(sid, bundle_ref=None, extract_metadata=True, write_story_json=False, timeout=30):
            if sid == 100101:
                return StoryFetchResult(story_id=sid, status="OK", metadata=self._create_mock_entry(100101))
            else:
                return StoryFetchResult(story_id=sid, status="NETWORK_ERROR", error_message="Simulated Network Timeout")

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=mock_fetch):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                story_retry_attempts=1,
            )
            self.assertFalse(ok)
            self.assertEqual(count, 1)
            self.assertEqual(failed, [100102])
            self.assertFalse(prod_manifest.exists(), "生產清單不得在失敗時建立")

            state_file = chk_dir / CHECKPOINT_STATE_FILENAME
            data_file = chk_dir / CHECKPOINT_DATA_FILENAME
            self.assertTrue(state_file.exists())
            self.assertTrue(data_file.exists())

            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "IN_PROGRESS")
            self.assertEqual(state["completed_count"], 1)
            self.assertEqual(state["target_count"], 2)

            chk_data = json.loads(data_file.read_text(encoding="utf-8"))
            self.assertEqual(chk_data["episode_count"], 1)
            self.assertIn("100101", chk_data["episodes"])
            self.assertNotIn("100102", chk_data["episodes"])

    # ----------------------------------------------------------------------
    # 44. Resume Skips Completed Fetches Pending Only
    # ----------------------------------------------------------------------
    def test_44_resume_skips_completed_fetches_pending_only(self):
        """44. 驗證從中斷快照續跑時，已完成話數絕不重複發起網路請求，僅抓取待處理話數"""
        mock_dash = self.tmp_path / "dashboard_44"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "100102.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_44"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        # 預先在 checkpoint 中存入 100101
        target_ids = [100101, 100102]
        existing_meta = {100101: self._create_mock_entry(100101)}
        save_bootstrap_checkpoint(chk_dir, target_ids, "00600025", existing_meta, status="IN_PROGRESS")

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101, 100102},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101, 100102},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {
            100101: StoryBundleRef(100101, "00600025", "hash100101", "storydata_100101.unity3d"),
            100102: StoryBundleRef(100102, "00600025", "hash100102", "storydata_100102.unity3d"),
        }

        fetched_sids = []
        def mock_fetch(sid, bundle_ref=None, extract_metadata=True, write_story_json=False, timeout=30):
            fetched_sids.append(sid)
            return StoryFetchResult(story_id=sid, status="OK", metadata=self._create_mock_entry(sid))

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=mock_fetch):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                resume=True,
            )
            self.assertTrue(ok)
            self.assertEqual(count, 2)
            self.assertEqual(failed, [])
            # 關鍵斷言：100101 絕不可被重複 fetch，僅 fetch 100102
            self.assertEqual(fetched_sids, [100102])

    # ----------------------------------------------------------------------
    # 45. Resume Completes Final Production Manifest Exact
    # ----------------------------------------------------------------------
    def test_45_resume_completes_final_production_manifest_exact(self):
        """45. 驗證續跑全數成功後，生產清單完整建立且包含全量話數，checkpoint 狀態更新為 COMPLETE"""
        mock_dash = self.tmp_path / "dashboard_45"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "100102.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_45"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        target_ids = [100101, 100102]
        existing_meta = {100101: self._create_mock_entry(100101)}
        save_bootstrap_checkpoint(chk_dir, target_ids, "00600025", existing_meta, status="IN_PROGRESS")

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101, 100102},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101, 100102},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {
            100101: StoryBundleRef(100101, "00600025", "hash100101", "storydata_100101.unity3d"),
            100102: StoryBundleRef(100102, "00600025", "hash100102", "storydata_100102.unity3d"),
        }

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", return_value=StoryFetchResult(story_id=100102, status="OK", metadata=self._create_mock_entry(100102))):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                resume=True,
            )
            self.assertTrue(ok)
            self.assertTrue(prod_manifest.exists())
            prod_data = json.loads(prod_manifest.read_text(encoding="utf-8"))
            self.assertEqual(prod_data["episode_count"], 2)
            self.assertIn("100101", prod_data["episodes"])
            self.assertIn("100102", prod_data["episodes"])

            state_file = chk_dir / CHECKPOINT_STATE_FILENAME
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "COMPLETE")
            self.assertEqual(state["completed_count"], 2)

    # ----------------------------------------------------------------------
    # 46. Checkpoint TruthVersion Mismatch Fails Before Story Fetch
    # ----------------------------------------------------------------------
    def test_46_checkpoint_truth_version_mismatch_fails_before_story_fetch(self):
        """46. 驗證快照 TruthVersion 與當前不符時，resume 堅決拒絕且零話數抓取 (Zero Story Fetch)"""
        mock_dash = self.tmp_path / "dashboard_46"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_46"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        target_ids = [100101]
        save_bootstrap_checkpoint(chk_dir, target_ids, "00600024", {100101: self._create_mock_entry(100101, tv="00600024")})

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id") as mock_fetch:
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                resume=True,
            )
            self.assertFalse(ok)
            mock_fetch.assert_not_called()

    # ----------------------------------------------------------------------
    # 47. Checkpoint Target Fingerprint Mismatch Fails Loudly
    # ----------------------------------------------------------------------
    def test_47_checkpoint_target_fingerprint_mismatch_fails_loudly(self):
        """47. 驗證快照話數指紋與當前目標不符時，resume 堅決拒絕且零話數抓取 (Zero Story Fetch)"""
        mock_dash = self.tmp_path / "dashboard_47"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        (mock_dash / "story" / "100102.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_47"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        save_bootstrap_checkpoint(chk_dir, [100101], "00600025", {100101: self._create_mock_entry(100101)})

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101, 100102},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101, 100102},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {
            100101: StoryBundleRef(100101, "00600025", "h1", "b1"),
            100102: StoryBundleRef(100102, "00600025", "h2", "b2"),
        }

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id") as mock_fetch:
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                resume=True,
            )
            self.assertFalse(ok)
            mock_fetch.assert_not_called()

    # ----------------------------------------------------------------------
    # 48. Checkpoint Unexpected Story ID Fails Loudly
    # ----------------------------------------------------------------------
    def test_48_checkpoint_unexpected_story_id_fails_loudly(self):
        """48. 驗證快照資料包含目標範圍外的多餘話數時，load_and_validate 堅決報錯"""
        chk_dir = self.tmp_path / "scratch_48"
        target_ids = [100101]
        episodes = {
            100101: self._create_mock_entry(100101),
            999999: self._create_mock_entry(999999),
        }
        save_bootstrap_checkpoint(chk_dir, target_ids, "00600025", episodes)
        with self.assertRaises(ValueError):
            load_and_validate_bootstrap_checkpoint(chk_dir, target_ids, "00600025")

    # ----------------------------------------------------------------------
    # 49. Checkpoint Provenance TV Mismatch Fails Loudly
    # ----------------------------------------------------------------------
    def test_49_checkpoint_provenance_tv_mismatch_fails_loudly(self):
        """49. 驗證快照內個別話數之 provenance.truth_version 與版本不符時，堅決報錯"""
        chk_dir = self.tmp_path / "scratch_49"
        target_ids = [100101]
        bad_entry = self._create_mock_entry(100101, tv="00600024")
        episodes = {100101: bad_entry}
        save_bootstrap_checkpoint(chk_dir, target_ids, "00600025", episodes)
        with self.assertRaises(ValueError):
            load_and_validate_bootstrap_checkpoint(chk_dir, target_ids, "00600025")

    # ----------------------------------------------------------------------
    # 50. Malformed Checkpoint Fails Loudly
    # ----------------------------------------------------------------------
    def test_50_malformed_checkpoint_fails_loudly(self):
        """50. 驗證快照檔案損毀 (非 JSON 格式) 時，resume 堅決失敗且零話數抓取 (Zero Story Fetch)"""
        mock_dash = self.tmp_path / "dashboard_50"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_50"
        chk_dir.mkdir(parents=True)
        (chk_dir / CHECKPOINT_STATE_FILENAME).write_text("corrupted_json{{{", encoding="utf-8")
        (chk_dir / CHECKPOINT_DATA_FILENAME).write_text("corrupted_json{{{", encoding="utf-8")

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id") as mock_fetch:
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                resume=True,
            )
            self.assertFalse(ok)
            mock_fetch.assert_not_called()

    # ----------------------------------------------------------------------
    # 51. Network Error Story Level Retries Eventual Success
    # ----------------------------------------------------------------------
    def test_51_network_error_story_level_retries_eventual_success(self):
        """51. 驗證單話遭遇 NETWORK_ERROR 時依設定進行退避重試，若最終成功則繼續推進"""
        mock_dash = self.tmp_path / "dashboard_51"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_51"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        attempts = 0
        def mock_fetch(sid, bundle_ref=None, extract_metadata=True, write_story_json=False, timeout=30):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return StoryFetchResult(story_id=sid, status="NETWORK_ERROR", error_message="Flaky CDN Timeout")
            return StoryFetchResult(story_id=sid, status="OK", metadata=self._create_mock_entry(100101))

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=mock_fetch):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                story_retry_attempts=3,
                story_retry_backoff=[0.001, 0.001, 0.001],
            )
            self.assertTrue(ok)
            self.assertEqual(attempts, 3)
            self.assertEqual(count, 1)
            self.assertEqual(failed, [])
            self.assertTrue(prod_manifest.exists())

    # ----------------------------------------------------------------------
    # 52. Parse Error No Story Level Retry
    # ----------------------------------------------------------------------
    def test_52_parse_error_no_story_level_retry(self):
        """52. 驗證單話遭遇 PARSE_ERROR (非網路錯誤) 時絕不進行無效重試，立即中斷並保存快照"""
        mock_dash = self.tmp_path / "dashboard_52"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_52"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        attempts = 0
        def mock_fetch(sid, bundle_ref=None, extract_metadata=True, write_story_json=False, timeout=30):
            nonlocal attempts
            attempts += 1
            return StoryFetchResult(story_id=sid, status="PARSE_ERROR", error_message="Corrupted Bundle Data")

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=mock_fetch):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                story_retry_attempts=3,
                story_retry_backoff=[0.001, 0.001, 0.001],
            )
            self.assertFalse(ok)
            self.assertEqual(attempts, 1, "PARSE_ERROR 絕不可發起重試")
            self.assertEqual(failed, [100101])
            self.assertFalse(prod_manifest.exists())

    # ----------------------------------------------------------------------
    # 53. Completed Story Never Refetched On Resume
    # ----------------------------------------------------------------------
    def test_53_completed_story_never_refetched_on_resume(self):
        """53. 驗證在 3 話任務中快照已完成 2 話時，resume 僅發起第 3 話之請求"""
        mock_dash = self.tmp_path / "dashboard_53"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        for sid in [100101, 100102, 100103]:
            (mock_dash / "story" / f"{sid}.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_53"

        target_ids = [100101, 100102, 100103]
        existing_meta = {
            100101: self._create_mock_entry(100101),
            100102: self._create_mock_entry(100102),
        }
        save_bootstrap_checkpoint(chk_dir, target_ids, "00600025", existing_meta, status="IN_PROGRESS")

        mock_univ = CanonicalStoryUniverse(
            required_ids=set(target_ids),
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids=set(target_ids),
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {sid: StoryBundleRef(sid, "00600025", f"h_{sid}", f"b_{sid}") for sid in target_ids}

        fetched_sids = []
        def mock_fetch(sid, bundle_ref=None, extract_metadata=True, write_story_json=False, timeout=30):
            fetched_sids.append(sid)
            return StoryFetchResult(story_id=sid, status="OK", metadata=self._create_mock_entry(sid))

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=mock_fetch):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=mock_dash / "data" / "official_story_metadata.json",
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                resume=True,
            )
            self.assertTrue(ok)
            self.assertEqual(fetched_sids, [100103])

    # ----------------------------------------------------------------------
    # 54. Production Manifest Never Partial
    # ----------------------------------------------------------------------
    def test_54_production_manifest_never_partial(self):
        """54. 驗證任何階段性中斷時，生產清單 official_story_metadata.json 絕不寫入半成品"""
        mock_dash = self.tmp_path / "dashboard_54"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        for sid in [100101, 100102]:
            (mock_dash / "story" / f"{sid}.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_54"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101, 100102},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101, 100102},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {
            100101: StoryBundleRef(100101, "00600025", "h1", "b1"),
            100102: StoryBundleRef(100102, "00600025", "h2", "b2"),
        }

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", side_effect=[
                 StoryFetchResult(story_id=100101, status="OK", metadata=self._create_mock_entry(100101)),
                 StoryFetchResult(story_id=100102, status="NETWORK_ERROR", error_message="Dropped"),
             ]):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                story_retry_attempts=1,
            )
            self.assertFalse(ok)
            self.assertFalse(prod_manifest.exists())

    # ----------------------------------------------------------------------
    # 55. Final Production Write Is Atomic
    # ----------------------------------------------------------------------
    def test_55_final_production_write_is_atomic(self):
        """55. 驗證全數完成時，生產清單是透過原子寫入機制替換落盤"""
        mock_dash = self.tmp_path / "dashboard_55"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_55"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        from pipeline.metadata_manifest import save_canonical_manifest
        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", return_value=StoryFetchResult(story_id=100101, status="OK", metadata=self._create_mock_entry(100101))), \
             patch("pipeline.metadata_manifest.save_canonical_manifest", wraps=save_canonical_manifest) as mock_save:
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
            )
            self.assertTrue(ok)
            # 檢查 save_canonical_manifest 有被呼叫，且傳入的 filepath 為 prod_manifest
            calls = [call[1].get("filepath") or (call[0][1] if len(call[0]) > 1 else None) for call in mock_save.call_args_list]
            self.assertIn(prod_manifest, calls)

    # ----------------------------------------------------------------------
    # 56. Write Story JSON Remains False Zero Write
    # ----------------------------------------------------------------------
    def test_56_write_story_json_remains_false_zero_write(self):
        """56. 驗證執行過程中 write_story_json=False，本地 story/*.json 內容與雜湊完全零變動"""
        mock_dash = self.tmp_path / "dashboard_56"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        story_file = mock_dash / "story" / "100101.json"
        story_content = '[{"id": 1, "speaker": "佩可", "text": "原文不變"}]'
        story_file.write_text(story_content, encoding="utf-8")
        orig_hash = hashlib.sha256(story_file.read_bytes()).hexdigest()

        chk_dir = self.tmp_path / "scratch_56"
        prod_manifest = mock_dash / "data" / "official_story_metadata.json"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", return_value=StoryFetchResult(story_id=100101, status="OK", metadata=self._create_mock_entry(100101))):
            ok, m_ver, count, failed = rebuild_official_metadata(
                truth_version="00600025",
                output_path=prod_manifest,
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
                write_story_json=False,
            )
            self.assertTrue(ok)
            new_hash = hashlib.sha256(story_file.read_bytes()).hexdigest()
            self.assertEqual(orig_hash, new_hash, "本地 story JSON 檔案在 metadata 回補中嚴禁被修改")

    # ----------------------------------------------------------------------
    # 57. Checkpoint And State Files Isolated In Scratch
    # ----------------------------------------------------------------------
    def test_57_checkpoint_and_state_files_isolated_in_scratch(self):
        """57. 驗證快照檔案與狀態檔案完全隔離於 scratch 目錄，dashboard/ 及其子目錄絕無污染"""
        mock_dash = self.tmp_path / "dashboard_57"
        (mock_dash / "data").mkdir(parents=True)
        (mock_dash / "story").mkdir(parents=True)
        (mock_dash / "story" / "100101.json").write_text("[]", encoding="utf-8")
        chk_dir = self.tmp_path / "scratch_57"

        mock_univ = CanonicalStoryUniverse(
            required_ids={100101},
            optional_ids=set(),
            unknown_ids=set(),
            expected_ids={100101},
            source_status={"database": "OK", "tracked_characters": "OK", "branch_stories": "OK", "extra_events": "OK"},
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[]
        )
        bundle_refs = {100101: StoryBundleRef(100101, "00600025", "h", "b")}

        with patch("pipeline.coverage.build_canonical_story_universe", return_value=mock_univ), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=bundle_refs), \
             patch("tools.pcrd_fetch.fetch_story_json_by_id", return_value=StoryFetchResult(story_id=100101, status="OK", metadata=self._create_mock_entry(100101))):
            rebuild_official_metadata(
                truth_version="00600025",
                output_path=mock_dash / "data" / "official_story_metadata.json",
                dashboard_dir=mock_dash,
                checkpoint_dir=chk_dir,
            )
            # 遍歷 mock_dash
            for p in mock_dash.rglob("*"):
                self.assertNotIn("checkpoint", p.name.lower())
                self.assertNotIn("bootstrap_state", p.name.lower())


    # ----------------------------------------------------------------------
    # 58. Legitimate Official Counterexample Contains Banned Phrase Passes
    # ----------------------------------------------------------------------
    def test_58_legitimate_official_counterexample_contains_banned_phrase_passes(self):
        """58. 驗證真實官方大綱 (如 4003016) 內文包含『美食殿堂的羈絆』時，不得誤判為假大綱，必須 PASS"""
        mock_board = self.tmp_path / "dashboard_58"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        official_text = (
            "美食殿堂一行人總算打倒了強敵。雪菲說默契十足的聯手攻擊成為決定勝負的關鍵時，"
            "讓她感受到了美食殿堂的羈絆。聽到這句話後，貪吃佩可等人懷著溫暖的心情踏上了歸途。"
        )
        # 故意使用非 4003016 的隨機話數 (如 100101)，證明完全不依賴任何 Story ID 白名單
        legit_entry = self._create_mock_entry(100101, synopsis=official_text)
        batch_update_manifest_entries({100101: legit_entry}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertTrue(ok)
        self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 59. Legitimate Different Text Contains Second Phrase Passes
    # ----------------------------------------------------------------------
    def test_59_legitimate_different_text_contains_second_phrase_passes(self):
        """59. 驗證合法不同文字包含『進一步的昇華』時，不得誤判，必須 PASS"""
        mock_board = self.tmp_path / "dashboard_59"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        legit_text = "經過長期的特訓，眾人的技巧得到了進一步的昇華，迎戰強敵。"
        legit_entry = self._create_mock_entry(100101, synopsis=legit_text)
        batch_update_manifest_entries({100101: legit_entry}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertTrue(ok)
        self.assertEqual(len(res.errors), 0)

    # ----------------------------------------------------------------------
    # 60. Exact Fake Fallback Rejected
    # ----------------------------------------------------------------------
    def test_60_exact_fake_fallback_rejected(self):
        """60. 驗證精準符合歷史假大綱全句時，精準攔截並報錯 (FAIL)"""
        mock_board = self.tmp_path / "dashboard_60"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        fake_text = "本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。"
        fake_entry = self._create_mock_entry(100101, synopsis=fake_text)
        batch_update_manifest_entries({100101: fake_entry}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("包含已確認之假大綱/幻覺文字" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 61. Fake Fallback With Whitespace Rejected
    # ----------------------------------------------------------------------
    def test_61_fake_fallback_with_whitespace_rejected(self):
        """61. 驗證假大綱前後夾帶空白字元或換行時，仍經正規化精準攔截 (FAIL)"""
        mock_board = self.tmp_path / "dashboard_61"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        padded_fake = "   \n  本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。  \t \n "
        fake_entry = self._create_mock_entry(100101, synopsis=padded_fake)
        batch_update_manifest_entries({100101: fake_entry}, truth_version="00600025", filepath=manifest_file)

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("包含已確認之假大綱/幻覺文字" in err for err in res.errors))

    # ----------------------------------------------------------------------
    # 62. map.js Contains Exact Fake Fallback Rejected
    # ----------------------------------------------------------------------
    def test_62_map_js_contains_exact_fake_fallback_rejected(self):
        """62. 驗證當 map.js 重新被植入完整歷史假大綱時，Runtime Regression Guard 報錯攔截 (FAIL)"""
        mock_board = self.tmp_path / "dashboard_62"
        (mock_board / "data").mkdir(parents=True)
        manifest_file = mock_board / "data" / "official_story_metadata.json"

        # Manifest 本身正常
        batch_update_manifest_entries({100101: self._create_mock_entry(100101)}, truth_version="00600025", filepath=manifest_file)

        # map.js 中植入完整歷史假大綱
        (mock_board / "map.js").write_text(
            "const fallback = '本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。';",
            encoding="utf-8"
        )

        res = ValidationResult()
        ok = validate_official_story_metadata(mock_board, check_dist=False, res=res, allow_bootstrap_incomplete=True, verbose=False)
        self.assertFalse(ok)
        self.assertTrue(any("map.js 包含已確認之假大綱完整文字" in err for err in res.errors))

if __name__ == "__main__":
    unittest.main()
