# -*- coding: utf-8 -*-
"""
tests/test_story_short_id_parser.py — Manifest-Backed Short-ID Parser 單元測試

測試範疇 (100% Hermetic, isolated, no network, no external binary dependencies):
1. _extract_portrait_asset_keys_from_manifest 提取正規表達式能力 (Case K)
2. _normalize_story_unit_target 正規化規則 (Case A ~ Case I)
3. _resolve_dialogue_unit_id 與 Carry Barrier 阻斷邏輯 (Case J & cmd3/cmd4 交互)
4. load_story_manifest_snapshot 快取防線
"""

import unittest
from unittest.mock import patch
from tools.pcrd_fetch import (
    _extract_portrait_asset_keys_from_manifest,
    _normalize_story_unit_target,
    _resolve_dialogue_unit_id,
    load_story_manifest_snapshot,
    _STORY_MANIFEST_SNAPSHOT_CACHE,
)


class TestManifestExtraction(unittest.TestCase):
    def test_extract_portrait_asset_keys_from_manifest(self):
        """Case K: 測試從 storydata2_assetmanifest 文字/二進位中正確抽取 6 位數 asset_key"""
        manifest_sample = (
            "a/b/storydata_icon_unit_006112.unity3d,12345,hash1\n"
            "a/b/storydata_icon_unit_100011.unity3d,23456,hash2\n"
            "a/b/storydata_5218004.unity3d,34567,hash3\n"
            "a/b/storydata_icon_unit_006111.unity3d,45678,hash4\n"
            "a/b/icon_unit_999999.unity3d,56789,hash5\n"  # 前綴不符，不應提取
        )
        # 測試 bytes 輸入
        keys_bytes = _extract_portrait_asset_keys_from_manifest(manifest_sample.encode("utf-8"))
        self.assertEqual(keys_bytes, {"006112", "100011", "006111"})

        # 測試 str 輸入
        keys_str = _extract_portrait_asset_keys_from_manifest(manifest_sample)
        self.assertEqual(keys_str, {"006112", "100011", "006111"})


class TestNormalizeStoryUnitTarget(unittest.TestCase):
    def setUp(self):
        self.manifest_keys = {"006112", "100011", "100012"}

    def test_case_a_standard_six_digit(self):
        """Case A: 100011 (六位數標準角色) -> 100011 (即使不在 manifest 也維持向下相容)"""
        self.assertEqual(_normalize_story_unit_target("100011", self.manifest_keys), 100011)
        self.assertEqual(_normalize_story_unit_target(100011, self.manifest_keys), 100011)
        # 未在 manifest_keys 的六位數依然直接回傳（保持相容）
        self.assertEqual(_normalize_story_unit_target("199999", self.manifest_keys), 199999)

    def test_case_b_valid_short_id_in_manifest(self):
        """Case B: 6112 搭配包含 '006112' 的 manifest -> 6112 (int)"""
        self.assertEqual(_normalize_story_unit_target("6112", self.manifest_keys), 6112)
        self.assertEqual(_normalize_story_unit_target(6112, self.manifest_keys), 6112)

    def test_case_c_zero_padded_short_id_in_manifest(self):
        """Case C: '006112' 搭配包含 '006112' 的 manifest -> 6112 (int)"""
        self.assertEqual(_normalize_story_unit_target("006112", self.manifest_keys), 6112)

    def test_case_d_short_id_not_in_manifest(self):
        """Case D: 6111 搭配不包含 '006111' 的 manifest -> None"""
        self.assertIsNone(_normalize_story_unit_target("6111", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target(6111, self.manifest_keys))

    def test_case_e_legacy_short_id_not_in_manifest(self):
        """Case E: 1411 (legacy short ID 未在 manifest) -> None"""
        self.assertIsNone(_normalize_story_unit_target("1411", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target(1411, self.manifest_keys))

    def test_case_f_zero_focus_reset(self):
        """Case F: 0 / '0' (解除焦點) -> None"""
        self.assertIsNone(_normalize_story_unit_target(0, self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("0", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("000000", self.manifest_keys))

    def test_case_g_invalid_or_non_digit_strings(self):
        """Case G: None / 空字串 / 非數字 (如 'abc', '') -> None"""
        self.assertIsNone(_normalize_story_unit_target(None, self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("   ", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("abc", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("6112a", self.manifest_keys))

    def test_case_h_multi_speaker_colon(self):
        """Case H: 多人冒號字串 (如 '100011:100012') -> None"""
        self.assertIsNone(_normalize_story_unit_target("100011:100012", self.manifest_keys))
        self.assertIsNone(_normalize_story_unit_target("6112:6111", self.manifest_keys))

    def test_case_i_fail_safe_without_manifest_keys(self):
        """Case I: portrait_asset_keys=None 時輸入 6112 -> None (fail-safe)"""
        self.assertIsNone(_normalize_story_unit_target(6112, None))
        self.assertIsNone(_normalize_story_unit_target("6112", None))
        self.assertIsNone(_normalize_story_unit_target("006112", None))
        # 但六位數仍然可回傳
        self.assertEqual(_normalize_story_unit_target("100011", None), 100011)


class TestDialogueResolutionAndBarriers(unittest.TestCase):
    def test_case_j_cmd4_barrier_blocks_carry(self):
        """Case J: cmd 4 帶無效 short ID 或 '0' 時，作為 carry barrier，阻止上一句對白 carry"""
        last_speaker = "秘書"
        last_speaker_unit = 6112

        # 下一句依然是「秘書」，但在這之間出現了無效焦點切換（block_cmd4_units 包含 None）
        block_cmd4_with_barrier = [None]
        block_cmd3_empty = []

        resolved = _resolve_dialogue_unit_id(
            speaker="秘書",
            block_cmd4_units=block_cmd4_with_barrier,
            block_cmd3_units=block_cmd3_empty,
            last_speaker=last_speaker,
            last_speaker_unit=last_speaker_unit,
        )
        self.assertIsNone(resolved, "cmd 4 barrier 必須阻斷上一句 unit_id carry-forward")

    def test_cmd3_barrier_blocks_carry(self):
        """cmd 3 表情指令在區塊中出現時，阻止 Rule 2 carry-forward"""
        last_speaker = "秘書"
        last_speaker_unit = 6112

        # 區塊中沒有 cmd 4，但有 cmd 3（非空，即使值為 None 或表情 ID）
        resolved = _resolve_dialogue_unit_id(
            speaker="秘書",
            block_cmd4_units=[],
            block_cmd3_units=[None],
            last_speaker=last_speaker,
            last_speaker_unit=last_speaker_unit,
        )
        self.assertIsNone(resolved, "cmd 3 存在時必須阻斷 Rule 2 carry-forward")

    def test_valid_short_id_resolution_and_carry(self):
        """合法的 short-ID (6112) 在單一焦點 cmd 4 下正確解析，並在無阻斷時被同一 speaker carry"""
        # 第一句：cmd 4 指向 6112
        res1 = _resolve_dialogue_unit_id(
            speaker="秘書",
            block_cmd4_units=[6112],
            block_cmd3_units=[],
            last_speaker=None,
            last_speaker_unit=None,
        )
        self.assertEqual(res1, 6112)

        # 第二句：同一發言人，無 cmd 4 與 cmd 3 -> 成功 carry 6112
        res2 = _resolve_dialogue_unit_id(
            speaker="秘書",
            block_cmd4_units=[],
            block_cmd3_units=[],
            last_speaker="秘書",
            last_speaker_unit=res1,
        )
        self.assertEqual(res2, 6112)


class TestManifestSnapshotCache(unittest.TestCase):
    def tearDown(self):
        _STORY_MANIFEST_SNAPSHOT_CACHE.clear()

    @patch("tools.pcrd_fetch._http_get")
    def test_snapshot_cached_per_truth_version(self, mock_http_get):
        """測試同一 TruthVersion 只發送一次 HTTP 請求下載 manifest，第二次呼叫直接命中快取"""
        sample_manifest = (
            "a/b/storydata_icon_unit_006112.unity3d,12345,hash1\n"
            "a/b/storydata_5218004.unity3d,23456,hash2\n"
        ).encode("utf-8")
        mock_http_get.return_value = sample_manifest

        # 第一次載入
        refs1, keys1 = load_story_manifest_snapshot(truth_version="00600025")
        self.assertEqual(mock_http_get.call_count, 1)
        self.assertIn("006112", keys1)
        self.assertIn(5218004, refs1)

        # 第二次載入相同版本 -> 應命中快取，不呼叫 mock_http_get
        refs2, keys2 = load_story_manifest_snapshot(truth_version="00600025")
        self.assertEqual(mock_http_get.call_count, 1)
        self.assertIs(refs1, refs2)
        self.assertIs(keys1, keys2)


if __name__ == "__main__":
    unittest.main()
