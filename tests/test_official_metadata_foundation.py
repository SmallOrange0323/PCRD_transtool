# -*- coding: utf-8 -*-
"""
tests/test_official_metadata_foundation.py
==========================================
針對 M1/M1.1 階段建立之元數據萃取、確定性序列化、來源溯源 (Provenance)
與嚴格契約向後相容性之單元測試。
不依賴線上 CDN，全數使用 Mock / Fixtures。
"""

import io
import json
import hashlib
import re
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from tools.pcrd_fetch import (
    _parse_bundle_dialogues,
    fetch_story_json_by_id,
    StoryFetchResult,
    StoryBundleRef,
    load_story_manifest_bundle_refs,
    load_story_manifest_hash_map,
)
from pipeline.metadata_manifest import (
    OfficialStoryMetadataManifest,
    OfficialEpisodeMetadata,
    EpisodeProvenance,
    SCHEMA_VERSION,
    serialize_canonical_manifest,
    compute_manifest_version,
    validate_manifest_dict_contract,
    create_empty_manifest,
    load_metadata_manifest,
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
    """Mock UnityPy Bundle 物件，提供 objects 迭代清單"""
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


class TestOfficialMetadataFoundation(unittest.TestCase):

    # ──────────────────────────────────────────────────────────
    # 既有 12 項基礎測試（含契約校準與型別強化）
    # ──────────────────────────────────────────────────────────

    def test_cmd0_chapter_title_extraction(self):
        """1. cmd 0 non-empty -> official_chapter_title 正確提取"""
        mock_cmds = [(0, ["王都的某一天"]), (6, ["佩可", "好餓喔"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            dialogues, meta = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertEqual(meta["chapter_title"], "王都的某一天")
            self.assertEqual(len(dialogues), 1)

    def test_cmd1_present_nonempty_synopsis(self):
        """2. cmd 1 present + nonempty -> official_synopsis 正確提取"""
        mock_cmds = [(0, ["王都"]), (1, ["在蘭德索爾發生的日常故事"]), (6, ["佩可", "好吃！"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            dialogues, meta = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertTrue(meta["cmd1_present"])
            self.assertTrue(meta["cmd1_nonempty"])
            self.assertEqual(meta["synopsis"], "在蘭德索爾發生的日常故事")

    def test_cmd1_present_empty_synopsis(self):
        """3. cmd 1 present + empty -> official_synopsis 為 null (None)"""
        mock_cmds = [(0, ["王都"]), (1, ["   "]), (6, ["佩可", "好吃！"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            dialogues, meta = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertTrue(meta["cmd1_present"])
            self.assertFalse(meta["cmd1_nonempty"])
            self.assertIsNone(meta["synopsis"])

    def test_cmd1_missing_synopsis(self):
        """4. cmd 1 missing -> official_synopsis 為 null (None)"""
        mock_cmds = [(0, ["王都"]), (6, ["佩可", "好吃！"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            dialogues, meta = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertFalse(meta["cmd1_present"])
            self.assertFalse(meta["cmd1_nonempty"])
            self.assertIsNone(meta["synopsis"])

    def test_cmd32_present_nonempty_subtitle(self):
        """5. cmd 32 present + nonempty -> subtitle 正確提取"""
        mock_cmds = [(0, ["第一章"]), (32, ["第1話 冒險的開始"]), (6, ["可可蘿", "主人"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            dialogues, meta = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertTrue(meta["cmd32_present"])
            self.assertTrue(meta["cmd32_nonempty"])
            self.assertEqual(meta["subtitle"], "第1話 冒險的開始")

    def test_cmd32_empty_or_missing_subtitle(self):
        """6. cmd 32 empty/missing -> subtitle 為 null (None)"""
        # Case A: empty
        mock_cmds_a = [(0, ["第一章"]), (32, [""]), (6, ["可可蘿", "主人"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds_a):
            _, meta_a = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertTrue(meta_a["cmd32_present"])
            self.assertFalse(meta_a["cmd32_nonempty"])
            self.assertIsNone(meta_a["subtitle"])

        # Case B: missing
        mock_cmds_b = [(0, ["第一章"]), (6, ["可可蘿", "主人"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds_b):
            _, meta_b = _parse_bundle_dialogues(b"mock_bytes", extract_metadata=True)
            self.assertFalse(meta_b["cmd32_present"])
            self.assertFalse(meta_b["cmd32_nonempty"])
            self.assertIsNone(meta_b["subtitle"])

    def test_hash_semantics_separation(self):
        """7. cdn_bundle_hash 語意與 bundle_sha256 各司其職"""
        raw_bytes = b"sample_bundle_bytes_for_testing"
        calculated_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        cdn_manifest_hash = "abcdef1234567890abcdef1234567890"

        ep = OfficialEpisodeMetadata(
            story_id=100101,
            chapter_title="測試章節",
            official_synopsis="測試大綱",
            subtitle="測試副標",
            provenance=EpisodeProvenance(
                truth_version="10000000",
                bundle_name="a/storydata_100101.unity3d",
                cdn_bundle_hash=cdn_manifest_hash,
                bundle_sha256=calculated_sha256,
                cmd1_present=True,
                cmd1_nonempty=True,
                cmd32_present=True,
                cmd32_nonempty=True
            )
        )
        data = ep.to_dict()
        self.assertEqual(data["provenance"]["cdn_bundle_hash"], cdn_manifest_hash)
        self.assertEqual(data["provenance"]["bundle_sha256"], calculated_sha256)
        self.assertNotEqual(data["provenance"]["cdn_bundle_hash"], data["provenance"]["bundle_sha256"])

    def test_deterministic_serialization(self):
        """8. 確定性序列化（相同輸入兩次執行 byte-for-byte 完全相同）"""
        dummy_sha_1 = "1" * 64
        dummy_sha_2 = "2" * 64
        ep1 = OfficialEpisodeMetadata(
            story_id=200102,
            chapter_title="第2話",
            official_synopsis=None,
            subtitle="序章",
            provenance=EpisodeProvenance("10080000", "h2", "a/storydata_200102.unity3d", dummy_sha_2, False, False, True, True)
        )
        ep2 = OfficialEpisodeMetadata(
            story_id=100101,
            chapter_title="第1話",
            official_synopsis="大綱1",
            subtitle=None,
            provenance=EpisodeProvenance("10080000", "h1", "a/storydata_100101.unity3d", dummy_sha_1, True, True, False, False)
        )

        manifest_a = OfficialStoryMetadataManifest(
            truth_version="10080000",
            episodes={
                200102: ep1,
                100101: ep2
            }
        )
        manifest_b = OfficialStoryMetadataManifest(
            truth_version="10080000",
            episodes={
                100101: ep2,
                200102: ep1
            }
        )

        bytes_a = manifest_a.to_canonical_json().encode("utf-8")
        bytes_b = manifest_b.to_canonical_json().encode("utf-8")
        self.assertEqual(bytes_a, bytes_b)
        self.assertEqual(compute_manifest_version(bytes_a), compute_manifest_version(bytes_b))

        parsed = json.loads(bytes_a)
        self.assertNotIn("metadata_version", parsed)
        self.assertNotIn("generated_at", parsed)
        self.assertEqual(list(parsed.keys()), ["schema_version", "truth_version", "episode_count", "episodes"])

    def test_episode_count_parity(self):
        """9. episode_count 與 len(episodes) parity 斷言"""
        manifest = OfficialStoryMetadataManifest(
            truth_version="10080000",
            episodes={
                100101: OfficialEpisodeMetadata(
                    story_id=100101,
                    chapter_title="1",
                    official_synopsis=None,
                    subtitle=None,
                    provenance=EpisodeProvenance("10080000", "h", "b", "0" * 64, False, False, False, False)
                )
            }
        )
        self.assertEqual(manifest.episode_count, 1)
        d = manifest.to_dict()
        self.assertEqual(d["episode_count"], len(d["episodes"]))

    def test_dialogue_json_top_level_array_backward_compatibility(self):
        """10. 對白檔案維持頂層 Array 結構（與舊契約相容）"""
        mock_cmds = [(0, ["標題"]), (1, ["大綱"]), (6, ["ペコリーヌ", "好餓喔"])]
        with patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds):
            dialogues = _parse_bundle_dialogues(b"mock_bytes")
            self.assertIsInstance(dialogues, list)
            self.assertIsInstance(dialogues[0], dict)
            self.assertIn("name", dialogues[0])
            self.assertIn("words", dialogues[0])

            serialized = json.dumps(dialogues, ensure_ascii=False)
            loaded = json.loads(serialized)
            self.assertIsInstance(loaded, list)
            self.assertEqual(loaded[0]["name"], "貪吃佩可")
            self.assertEqual(loaded[0]["words"], "好餓喔")

    def test_single_fetch_no_duplicate_network_call(self):
        """11. 單次下載原則：同一次 fetch 流程內同時產生 dialogues 與 metadata，無二次請求"""
        mock_bundle_bytes = b"mock_unity3d_binary_stream"
        mock_cmds = [(0, ["標題0"]), (1, ["大綱1"]), (32, ["副標32"]), (6, ["コッコロ", "主人"])]
        mock_bundle_refs = {
            100101: StoryBundleRef(
                story_id=100101,
                truth_version="10080000",
                cdn_bundle_hash="hash_manifest_100101",
                bundle_name="a/storydata_100101.unity3d"
            )
        }

        download_call_count = 0

        def fake_urlopen(req, timeout=15):
            nonlocal download_call_count
            download_call_count += 1
            return MockResponse(mock_bundle_bytes)

        with patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=mock_bundle_refs), \
             patch("tools.pcrd_fetch._get_sonet_ver", return_value="10080000"), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.replace"):

            result = fetch_story_json_by_id(100101, extract_metadata=True)

            self.assertIsInstance(result, StoryFetchResult)
            self.assertEqual(result.status, "OK")
            # 必須僅下載 1 次 AssetBundle
            self.assertEqual(download_call_count, 1)
            self.assertEqual(result.dialogue_count, 1)
            self.assertIsNotNone(result.metadata)
            meta = result.metadata
            self.assertEqual(meta["chapter_title"], "標題0")
            self.assertEqual(meta["official_synopsis"], "大綱1")
            self.assertEqual(meta["subtitle"], "副標32")
            self.assertEqual(meta["provenance"]["cdn_bundle_hash"], "hash_manifest_100101")
            self.assertEqual(meta["provenance"]["bundle_name"], "a/storydata_100101.unity3d")
            self.assertEqual(
                meta["provenance"]["bundle_sha256"],
                hashlib.sha256(mock_bundle_bytes).hexdigest()
            )

    def test_schema_and_required_fields_validation(self):
        """12. 驗證 schema 結構與 required fields，包含 episodes 內每個欄位結構"""
        valid_sha256 = "c" * 64
        ep = OfficialEpisodeMetadata(
            story_id=100201,
            chapter_title="第2章",
            official_synopsis="簡介文字",
            subtitle="副標文字",
            provenance=EpisodeProvenance(
                truth_version="10080000",
                cdn_bundle_hash="bundle_hash_val",
                bundle_name="a/storydata_100201.unity3d",
                bundle_sha256=valid_sha256,
                cmd1_present=True,
                cmd1_nonempty=True,
                cmd32_present=True,
                cmd32_nonempty=True
            )
        )
        manifest = OfficialStoryMetadataManifest(
            truth_version="10080000",
            episodes={100201: ep}
        )

        manifest_dict = manifest.to_dict()
        validate_manifest_dict_contract(manifest_dict)

        self.assertEqual(manifest_dict["schema_version"], SCHEMA_VERSION)
        self.assertEqual(manifest_dict["truth_version"], "10080000")
        self.assertEqual(manifest_dict["episode_count"], 1)
        self.assertIn("100201", manifest_dict["episodes"])

        ep_dict = manifest_dict["episodes"]["100201"]
        self.assertEqual(ep_dict["chapter_title"], "第2章")
        self.assertEqual(ep_dict["official_synopsis"], "簡介文字")
        self.assertEqual(ep_dict["subtitle"], "副標文字")

        prov = ep_dict["provenance"]
        self.assertEqual(prov["truth_version"], "10080000")
        self.assertEqual(prov["bundle_name"], "a/storydata_100201.unity3d")
        self.assertEqual(prov["cdn_bundle_hash"], "bundle_hash_val")
        self.assertEqual(prov["bundle_sha256"], valid_sha256)
        self.assertEqual(prov["cmd1_present"], True)
        self.assertEqual(prov["cmd1_nonempty"], True)
        self.assertEqual(prov["cmd32_present"], True)
        self.assertEqual(prov["cmd32_nonempty"], True)

    # ──────────────────────────────────────────────────────────
    # M1.1 核心強化測試：Provenance、Snapshot、Strict Contracts
    # ──────────────────────────────────────────────────────────

    def test_truth_version_snapshot_once_prevents_race(self):
        """13. TruthVersion 單次 Snapshot：流程中即便底層版本變動，也絕不發生版本分裂"""
        mock_bundle_bytes = b"mock_unity3d_binary_stream"
        mock_cmds = [(0, ["第1話"]), (1, ["摘要"]), (32, ["話名"]), (6, ["角色", "台詞"])]

        # 模擬 _get_sonet_ver 在流程中如果被第二次呼叫會回傳新版本
        version_sequence = iter(["10080000", "10080099"])
        def mock_ver():
            return next(version_sequence)

        mock_refs = {
            100101: StoryBundleRef(
                story_id=100101,
                truth_version="10080000",
                cdn_bundle_hash="hash_100101",
                bundle_name="manifest/storydata_100101.unity3d"
            )
        }

        with patch("tools.pcrd_fetch._get_sonet_ver", side_effect=mock_ver) as mock_ver_fn, \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=mock_refs) as mock_load_refs, \
             patch("urllib.request.urlopen", return_value=MockResponse(mock_bundle_bytes)), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.replace"):

            result = fetch_story_json_by_id(100101, extract_metadata=True)

            self.assertEqual(result.status, "OK")
            # 斷言：provenance.truth_version 嚴格等於最初 snapshot 的版本
            self.assertEqual(result.metadata["provenance"]["truth_version"], "10080000")
            # 斷言：load_story_manifest_bundle_refs 接收到的版本正是快照版本
            mock_load_refs.assert_called_once_with(truth_version="10080000")
            # 斷言：_get_sonet_ver 僅被呼叫 1 次（絕不在下載 bundle 後再次重新探測）
            self.assertEqual(mock_ver_fn.call_count, 1)

    def test_raw_manifest_hash_map_rejects_metadata_extraction(self):
        """14. 傳入裸 manifest_hash_map 且要求 extract_metadata=True 時 Fail Loudly 拋出 ValueError"""
        with self.assertRaises(ValueError) as ctx:
            fetch_story_json_by_id(100101, manifest_hash_map={100101: "hash"}, extract_metadata=True)
        self.assertIn("Cannot extract metadata with raw manifest_hash_map", str(ctx.exception))

    def test_raw_manifest_hash_map_allows_dialogue_only_fetch(self):
        """15. 傳入裸 manifest_hash_map 且 extract_metadata=False（預設）時向後相容正常運作"""
        mock_bundle_bytes = b"mock_bundle"
        mock_cmds = [(6, ["佩可", "好吃"])]
        with patch("urllib.request.urlopen", return_value=MockResponse(mock_bundle_bytes)), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.replace"):

            result = fetch_story_json_by_id(100101, manifest_hash_map={100101: "h100101"}, extract_metadata=False)
            self.assertEqual(result.status, "OK")
            self.assertEqual(result.dialogue_count, 1)
            self.assertIsNone(result.metadata)

    def test_bundle_name_comes_from_manifest_path(self):
        """16. bundle_name 嚴格源自 Manifest 原始 path，非模板推導"""
        mock_bundle_bytes = b"mock_data"
        mock_cmds = [(0, ["標題"]), (6, ["角色", "話語"])]
        custom_path = "some/nested/special_storydata_100101.unity3d"
        mock_refs = {
            100101: StoryBundleRef(
                story_id=100101,
                truth_version="10080000",
                cdn_bundle_hash="hash_custom",
                bundle_name=custom_path
            )
        }
        with patch("tools.pcrd_fetch.load_story_manifest_bundle_refs", return_value=mock_refs), \
             patch("tools.pcrd_fetch._get_sonet_ver", return_value="10080000"), \
             patch("urllib.request.urlopen", return_value=MockResponse(mock_bundle_bytes)), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.replace"):

            result = fetch_story_json_by_id(100101, extract_metadata=True)
            self.assertEqual(result.metadata["provenance"]["bundle_name"], custom_path)
            self.assertNotEqual(result.metadata["provenance"]["bundle_name"], "a/storydata_100101.unity3d")

    def test_bundle_ref_parameter_usage_and_mismatch_guard(self):
        """17. 傳入特定 bundle_ref 的正常解碼與 ID 不符保護"""
        ref = StoryBundleRef(
            story_id=100101,
            truth_version="10080000",
            cdn_bundle_hash="hash_ref",
            bundle_name="path/ref.unity3d"
        )
        # Case A: story_id 不符防禦
        with self.assertRaises(ValueError):
            fetch_story_json_by_id(999999, bundle_ref=ref, extract_metadata=True)

        # Case B: 正常解碼
        mock_bundle_bytes = b"bundle_content"
        mock_cmds = [(0, ["第一章"]), (6, ["佩可", "嗨"])]
        with patch("urllib.request.urlopen", return_value=MockResponse(mock_bundle_bytes)), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=mock_cmds), \
             patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.replace"):

            result = fetch_story_json_by_id(100101, bundle_ref=ref, extract_metadata=True)
            self.assertEqual(result.status, "OK")
            self.assertEqual(result.metadata["provenance"]["bundle_name"], "path/ref.unity3d")
            self.assertEqual(result.metadata["provenance"]["cdn_bundle_hash"], "hash_ref")

    def test_bundle_refs_dict_parameter_usage(self):
        """18. 傳入 bundle_refs 字典之提取與找不到話數之保護"""
        refs_dict = {
            100101: StoryBundleRef(100101, "10080000", "hash_100101", "path_100101")
        }
        # Case A: 找不到
        res_not_found = fetch_story_json_by_id(100102, bundle_refs=refs_dict, extract_metadata=True)
        self.assertEqual(res_not_found.status, "HASH_NOT_FOUND")

        # Case B: 找到
        mock_bundle_bytes = b"bytes"
        with patch("urllib.request.urlopen", return_value=MockResponse(mock_bundle_bytes)), \
             patch("UnityPy.load", return_value=DummyBundle()), \
             patch("tools.pcrd_fetch._deserialize_story_raw", return_value=[]), \
             patch("builtins.open", mock_open()), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.replace"):
            res_found = fetch_story_json_by_id(100101, bundle_refs=refs_dict, extract_metadata=True)
            self.assertEqual(res_found.status, "OK")
            self.assertEqual(res_found.metadata["provenance"]["cdn_bundle_hash"], "hash_100101")

    def test_create_empty_manifest_requires_truth_version(self):
        """19. create_empty_manifest 嚴格移除預設值，未傳入時拋出 TypeError"""
        with self.assertRaises(TypeError):
            create_empty_manifest()  # pylint: disable=no-value-for-parameter

    def test_create_empty_manifest_rejects_invalid_truth_version(self):
        """20. create_empty_manifest 傳入非 8 碼數字時拋出 ValueError"""
        invalid_versions = ["1008000", "100800001", "1008000a", "", "ABCDEFGH"]
        for bad_v in invalid_versions:
            with self.subTest(bad_v=bad_v):
                with self.assertRaises(ValueError):
                    create_empty_manifest(bad_v)

    def test_manifest_contract_rejects_invalid_top_level_truth_version(self):
        """21. Manifest 頂層 truth_version 必須嚴格為 8 碼數字"""
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000_dirty",
            "episode_count": 0,
            "episodes": {}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("truth_version 必須為 8 位數字字串", str(ctx.exception))

    def test_manifest_contract_rejects_invalid_provenance_truth_version(self):
        """22. episode provenance.truth_version 必須嚴格為 8 碼數字"""
        valid_ep = {
            "chapter_title": "標題",
            "official_synopsis": None,
            "subtitle": None,
            "provenance": {
                "truth_version": "1008",  # 不符 8 碼
                "cdn_bundle_hash": "hash_val",
                "bundle_name": "bundle_val",
                "cmd1_present": False,
                "cmd1_nonempty": False,
                "cmd32_present": False,
                "cmd32_nonempty": False
            }
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": valid_ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("provenance.truth_version 必須為 8 位數字字串", str(ctx.exception))

    def test_manifest_contract_rejects_extra_episode_keys(self):
        """23. episodes[sid] 拒絕未定義額外欄位 (additionalProperties: false)"""
        ep = {
            "chapter_title": "標題",
            "official_synopsis": None,
            "subtitle": None,
            "provenance": {
                "truth_version": "10080000",
                "cdn_bundle_hash": "h",
                "bundle_name": "b",
                "cmd1_present": False,
                "cmd1_nonempty": False,
                "cmd32_present": False,
                "cmd32_nonempty": False
            },
            "extra_field": "disallowed"
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("additionalProperties: false", str(ctx.exception))
        self.assertIn("extra_field", str(ctx.exception))

    def test_manifest_contract_rejects_extra_provenance_keys(self):
        """24. provenance 拒絕未定義額外欄位 (additionalProperties: false)"""
        ep = {
            "chapter_title": "標題",
            "official_synopsis": None,
            "subtitle": None,
            "provenance": {
                "truth_version": "10080000",
                "cdn_bundle_hash": "h",
                "bundle_name": "b",
                "cmd1_present": False,
                "cmd1_nonempty": False,
                "cmd32_present": False,
                "cmd32_nonempty": False,
                "unknown_prov_field": "disallowed"
            }
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("additionalProperties: false", str(ctx.exception))
        self.assertIn("unknown_prov_field", str(ctx.exception))

    def test_manifest_contract_rejects_invalid_bundle_sha256_format(self):
        """25. bundle_sha256 若存在，必須嚴格為 64 碼十六進位字串"""
        invalid_hashes = ["short_hash", "z" * 64, "1" * 63, "1" * 65]
        for bad_hash in invalid_hashes:
            ep = {
                "chapter_title": "標題",
                "official_synopsis": None,
                "subtitle": None,
                "provenance": {
                    "truth_version": "10080000",
                    "cdn_bundle_hash": "h",
                    "bundle_name": "b",
                    "bundle_sha256": bad_hash,
                    "cmd1_present": False,
                    "cmd1_nonempty": False,
                    "cmd32_present": False,
                    "cmd32_nonempty": False
                }
            }
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "truth_version": "10080000",
                "episode_count": 1,
                "episodes": {"100101": ep}
            }
            with self.subTest(bad_hash=bad_hash):
                with self.assertRaises(ValueError) as ctx:
                    validate_manifest_dict_contract(manifest)
                self.assertIn("64 位十六進位字串", str(ctx.exception))

    def test_manifest_contract_rejects_empty_cdn_bundle_hash_or_bundle_name(self):
        """26. cdn_bundle_hash 與 bundle_name 必須為非空字串"""
        for field in ["cdn_bundle_hash", "bundle_name"]:
            prov = {
                "truth_version": "10080000",
                "cdn_bundle_hash": "valid_hash",
                "bundle_name": "valid_name",
                "cmd1_present": False,
                "cmd1_nonempty": False,
                "cmd32_present": False,
                "cmd32_nonempty": False
            }
            prov[field] = "   "  # 空白字串
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "truth_version": "10080000",
                "episode_count": 1,
                "episodes": {
                    "100101": {
                        "chapter_title": None,
                        "official_synopsis": None,
                        "subtitle": None,
                        "provenance": prov
                    }
                }
            }
            with self.subTest(field=field):
                with self.assertRaises(ValueError) as ctx:
                    validate_manifest_dict_contract(manifest)
                self.assertIn(f"provenance.{field} 必須為非空字串", str(ctx.exception))

    def test_manifest_contract_rejects_cmd1_nonempty_without_present(self):
        """27. 標記蘊含關係：cmd1_nonempty=True 必須蘊含 cmd1_present=True"""
        ep = {
            "chapter_title": None,
            "official_synopsis": "有大綱",
            "subtitle": None,
            "provenance": {
                "truth_version": "10080000",
                "cdn_bundle_hash": "h",
                "bundle_name": "b",
                "cmd1_present": False,  # 矛盾
                "cmd1_nonempty": True,
                "cmd32_present": False,
                "cmd32_nonempty": False
            }
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("cmd1_nonempty 為 True 但 cmd1_present 為 False", str(ctx.exception))

    def test_manifest_contract_rejects_cmd32_nonempty_without_present(self):
        """28. 標記蘊含關係：cmd32_nonempty=True 必須蘊含 cmd32_present=True"""
        ep = {
            "chapter_title": None,
            "official_synopsis": None,
            "subtitle": "有副標",
            "provenance": {
                "truth_version": "10080000",
                "cdn_bundle_hash": "h",
                "bundle_name": "b",
                "cmd1_present": False,
                "cmd1_nonempty": False,
                "cmd32_present": False,  # 矛盾
                "cmd32_nonempty": True
            }
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("cmd32_nonempty 為 True 但 cmd32_present 為 False", str(ctx.exception))

    def test_manifest_contract_rejects_synopsis_when_cmd1_not_nonempty(self):
        """29. official_synopsis Null Contract：非 (cmd1_present && cmd1_nonempty) 必須嚴格為 null"""
        # Case: cmd1_present=True, cmd1_nonempty=False, 但 official_synopsis 不為 None
        ep = {
            "chapter_title": None,
            "official_synopsis": "殘留文本",
            "subtitle": None,
            "provenance": {
                "truth_version": "10080000",
                "cdn_bundle_hash": "h",
                "bundle_name": "b",
                "cmd1_present": True,
                "cmd1_nonempty": False,
                "cmd32_present": False,
                "cmd32_nonempty": False
            }
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("cmd1 非 nonempty，official_synopsis 必須嚴格為 null", str(ctx.exception))

    def test_manifest_contract_rejects_subtitle_when_cmd32_not_nonempty(self):
        """30. subtitle Null Contract：非 (cmd32_present && cmd32_nonempty) 必須嚴格為 null"""
        ep = {
            "chapter_title": None,
            "official_synopsis": None,
            "subtitle": "殘留副標",
            "provenance": {
                "truth_version": "10080000",
                "cdn_bundle_hash": "h",
                "bundle_name": "b",
                "cmd1_present": False,
                "cmd1_nonempty": False,
                "cmd32_present": False,
                "cmd32_nonempty": False
            }
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "truth_version": "10080000",
            "episode_count": 1,
            "episodes": {"100101": ep}
        }
        with self.assertRaises(ValueError) as ctx:
            validate_manifest_dict_contract(manifest)
        self.assertIn("cmd32 非 nonempty，subtitle 必須嚴格為 null", str(ctx.exception))

    def test_load_metadata_manifest_file_not_found_without_default(self):
        """31. load_metadata_manifest 在檔案不存在且未提供 default_truth_version 時拋出 FileNotFoundError"""
        fake_path = Path("non_existent_metadata_file_test.json")
        with self.assertRaises(FileNotFoundError):
            load_metadata_manifest(fake_path)

        # 若提供 default_truth_version 則能初始化空白骨架
        res = load_metadata_manifest(fake_path, default_truth_version="10080000")
        self.assertEqual(res["truth_version"], "10080000")
        self.assertEqual(res["episode_count"], 0)


if __name__ == "__main__":
    unittest.main()
