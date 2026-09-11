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

        fake_entry = self._create_mock_entry(100101, synopsis="這是美食殿堂的羈絆的冒險")
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
            self.assertTrue(any("未知/非 Canonical 話數元數據" in err for err in res_strict.errors))

            # Dev 模式：發出 Warning
            res_dev = ValidationResult()
            ok_dev = validate_official_story_metadata(mock_board, check_dist=False, res=res_dev, allow_bootstrap_incomplete=True, verbose=False)
            self.assertTrue(ok_dev)
            self.assertTrue(any("非 Canonical 話數元數據" in w for w in res_dev.warnings))

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


if __name__ == "__main__":
    unittest.main()
