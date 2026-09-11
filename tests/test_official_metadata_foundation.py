# -*- coding: utf-8 -*-
"""
tests/test_official_metadata_foundation.py
==========================================
針對 M1 階段建立之元數據萃取、確定性序列化與契約向後相容性之單元測試。
不依賴線上 CDN，全數使用 Mock / Fixtures。
"""

import io
import json
import hashlib
import unittest
from unittest.mock import patch, MagicMock, mock_open

from tools.pcrd_fetch import _parse_bundle_dialogues, fetch_story_json_by_id, StoryFetchResult
from pipeline.metadata_manifest import (
    OfficialStoryMetadataManifest,
    OfficialEpisodeMetadata,
    EpisodeProvenance,
    SCHEMA_VERSION,
    serialize_canonical_manifest,
    compute_manifest_version,
    validate_manifest_dict_contract,
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


class TestOfficialMetadataFoundation(unittest.TestCase):

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
        ep1 = OfficialEpisodeMetadata(
            story_id=200102,
            chapter_title="第2話",
            official_synopsis=None,
            subtitle="序章",
            provenance=EpisodeProvenance("10080000", "h2", "a/storydata_200102.unity3d", "s2", False, False, True, True)
        )
        ep2 = OfficialEpisodeMetadata(
            story_id=100101,
            chapter_title="第1話",
            official_synopsis="大綱1",
            subtitle=None,
            provenance=EpisodeProvenance("10080000", "h1", "a/storydata_100101.unity3d", "s1", True, True, False, False)
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

        # 兩者 insertion order 不同，但輸出 byte 序列必須 100% 一模一樣
        bytes_a = manifest_a.to_canonical_json().encode("utf-8")
        bytes_b = manifest_b.to_canonical_json().encode("utf-8")
        self.assertEqual(bytes_a, bytes_b)
        self.assertEqual(compute_manifest_version(bytes_a), compute_manifest_version(bytes_b))

        # 頂層 key 必須嚴格不含 metadata_version 與 generated_at，且順序可預測
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
                    provenance=EpisodeProvenance("10080000", "h", "b", "s", False, False, False, False)
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

            # 序列化為 JSON 後確認是頂層陣列
            serialized = json.dumps(dialogues, ensure_ascii=False)
            loaded = json.loads(serialized)
            self.assertIsInstance(loaded, list)
            self.assertEqual(loaded[0]["name"], "貪吃佩可")
            self.assertEqual(loaded[0]["words"], "好餓喔")

    def test_single_fetch_no_duplicate_network_call(self):
        """11. 單次下載原則：同一次 fetch 流程內同時產生 dialogues 與 metadata，無二次請求"""
        mock_manifest_map = {100101: "hash_manifest_100101"}
        mock_bundle_bytes = b"mock_unity3d_binary_stream"
        mock_cmds = [(0, ["標題0"]), (1, ["大綱1"]), (32, ["副標32"]), (6, ["コッコロ", "主人"])]

        download_call_count = 0

        class MockResponse:
            def __init__(self, data):
                self.data = data
            def read(self):
                return self.data
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        def fake_urlopen(req, timeout=15):
            nonlocal download_call_count
            download_call_count += 1
            return MockResponse(mock_bundle_bytes)

        with patch("tools.pcrd_fetch.load_story_manifest_hash_map", return_value=mock_manifest_map), \
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
            # 必須僅下載 1 次
            self.assertEqual(download_call_count, 1)
            # 對白筆數
            self.assertEqual(result.dialogue_count, 1)
            # 元數據必須同時提取
            self.assertIsNotNone(result.metadata)
            meta = result.metadata
            self.assertEqual(meta["chapter_title"], "標題0")
            self.assertEqual(meta["official_synopsis"], "大綱1")
            self.assertEqual(meta["subtitle"], "副標32")
            self.assertEqual(meta["provenance"]["cdn_bundle_hash"], "hash_manifest_100101")
            self.assertEqual(
                meta["provenance"]["bundle_sha256"],
                hashlib.sha256(mock_bundle_bytes).hexdigest()
            )

    def test_schema_and_required_fields_validation(self):
        """12. 驗證 schema 結構與 required fields，包含 episodes 內每個欄位結構"""
        ep = OfficialEpisodeMetadata(
            story_id=100201,
            chapter_title="第2章",
            official_synopsis="簡介文字",
            subtitle="副標文字",
            provenance=EpisodeProvenance(
                truth_version="10080000",
                cdn_bundle_hash="bundle_hash_val",
                bundle_name="a/storydata_100201.unity3d",
                bundle_sha256="sha256_val",
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

        # 頂層必填欄位
        self.assertEqual(manifest_dict["schema_version"], SCHEMA_VERSION)
        self.assertEqual(manifest_dict["truth_version"], "10080000")
        self.assertEqual(manifest_dict["episode_count"], 1)
        self.assertIn("100201", manifest_dict["episodes"])

        # 單話必填欄位
        ep_dict = manifest_dict["episodes"]["100201"]
        self.assertEqual(ep_dict["chapter_title"], "第2章")
        self.assertEqual(ep_dict["official_synopsis"], "簡介文字")
        self.assertEqual(ep_dict["subtitle"], "副標文字")

        # provenance
        prov = ep_dict["provenance"]
        self.assertEqual(prov["truth_version"], "10080000")
        self.assertEqual(prov["bundle_name"], "a/storydata_100201.unity3d")
        self.assertEqual(prov["cdn_bundle_hash"], "bundle_hash_val")
        self.assertEqual(prov["bundle_sha256"], "sha256_val")
        self.assertEqual(prov["cmd1_present"], True)
        self.assertEqual(prov["cmd1_nonempty"], True)
        self.assertEqual(prov["cmd32_present"], True)
        self.assertEqual(prov["cmd32_nonempty"], True)


if __name__ == "__main__":
    unittest.main()
