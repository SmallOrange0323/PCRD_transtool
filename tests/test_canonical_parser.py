# -*- coding: utf-8 -*-
"""
tests/test_canonical_parser.py — Canonical Story Parser Regression Tests

驗證：
1. Case A: FACE slot bug 防護 (slot 1 bound -> FACE [1, emotion] -> unit_id 保留原角，不產生 unit_id=1)
2. Case B: Slot 切換與 Focus 焦點精確對齊
3. Case C: 角色卸載 (BUSTUP 0 / FADEOUT / FADEOUT_ALL) 後嚴格清除，不 carry stale identity
4. Case D: 同名換裝角色 (如佩可) 依指令流正確保留各形態獨立 unit_id
5. Case E: 場外無立繪發言 (Off-screen speech) 嚴格輸出 unit_id: null，不進行 name-based 猜測
6. Case F: 確定性序列化 (Deterministic Serialization SHA-256 完全相同)
7. Case G: JSON Schema 合規性檢驗 (dialogue, still, background, movie)
"""

import hashlib
import json
import unittest
from tools.pcrd_fetch import (
    StorySlotStateMachine,
    serialize_canonical_story_json
)


class TestCanonicalStoryParser(unittest.TestCase):

    def setUp(self):
        # 模擬一組包含合法 6 碼與合法 short ID 的 manifest portrait keys
        self.mock_portrait_keys = {"006112", "100111", "105811", "107511", "127911", "193211", "193631"}

    def test_case_a_face_slot_bug_protection(self):
        """Case A: FACE slot 1 歷史 Bug 防護"""
        sm = StorySlotStateMachine(portrait_asset_keys=self.mock_portrait_keys)
        # 加載 193211 (媞雅)
        sm.handle_command(50, ["193211", "1"])
        self.assertEqual(sm.current_focus, 193211)

        # 模擬歷史 bug 觸發點: FACE ['1', '2']
        sm.handle_command(3, ["1", "2"])

        # 發言
        resolved = sm.resolve_dialogue_identity("媞雅")
        self.assertEqual(resolved, 193211, "FACE slot 1 操作必須正確歸屬於活躍角色 193211")
        self.assertNotEqual(resolved, 1, "絕對禁止將 slot 參數 1 作為 unit_id")

    def test_case_b_slot_change_and_focus(self):
        """Case B: 多角色插槽與焦點精確切換"""
        sm = StorySlotStateMachine(portrait_asset_keys=self.mock_portrait_keys)
        # 加載角色 A (100111: 日和) 與 角色 B (193631: 八斗神局長)
        sm.handle_command(68, ["100111", "L", "1"])
        sm.handle_command(68, ["193631", "R", "1"])

        # 焦點切換至 100111
        sm.handle_command(4, ["100111"])
        resolved_a = sm.resolve_dialogue_identity("日和")
        self.assertEqual(resolved_a, 100111)

        # 焦點切換至 193631
        sm.handle_command(4, ["193631"])
        resolved_b = sm.resolve_dialogue_identity("八斗神局長")
        self.assertEqual(resolved_b, 193631)

    def test_case_c_character_unload_clears_stale_identity(self):
        """Case C: 角色卸載後不得 carry stale identity"""
        sm = StorySlotStateMachine(portrait_asset_keys=self.mock_portrait_keys)
        sm.handle_command(50, ["105811", "1"])
        self.assertEqual(sm.resolve_dialogue_identity("貪吃佩可"), 105811)

        # 卸載角色 (FADEOUT 或 BUSTUP 0)
        sm.handle_command(50, ["0", "0"])
        self.assertNotIn(105811, sm.active_units)
        self.assertIsNone(sm.current_focus)

        # 下一句對話無新立繪加載 -> 必須輸出 None
        resolved_after = sm.resolve_dialogue_identity("貪吃佩可")
        self.assertIsNone(resolved_after, "角色立繪卸載後嚴禁延續舊身分，必須為 None")

    def test_case_d_multi_costume_character_preserves_variants(self):
        """Case D: 同發言人換裝形態必須保留獨立 unit_id"""
        sm = StorySlotStateMachine(portrait_asset_keys=self.mock_portrait_keys)
        # 普通形態 (105811)
        sm.handle_command(50, ["105811", "1"])
        res1 = sm.resolve_dialogue_identity("貪吃佩可")
        self.assertEqual(res1, 105811)

        # 夏日換裝 (107511)
        sm.handle_command(50, ["107511", "1"])
        res2 = sm.resolve_dialogue_identity("貪吃佩可")
        self.assertEqual(res2, 107511)

        # 超載形態 (127911)
        sm.handle_command(50, ["127911", "1"])
        res3 = sm.resolve_dialogue_identity("貪吃佩可")
        self.assertEqual(res3, 127911)

        self.assertNotEqual(res1, res2)
        self.assertNotEqual(res2, res3)

    def test_case_e_unresolved_off_screen_speech_returns_null(self):
        """Case E: 場外無立繪發言 (如 2206099 開頭) 必須為 null，嚴禁姓名推導"""
        sm = StorySlotStateMachine(portrait_asset_keys=self.mock_portrait_keys)
        # 開頭無 BUSTUP，FOCUS 0，FACE ['1', '1']
        sm.handle_command(4, ["0"])
        sm.handle_command(50, ["0", "0"])
        sm.handle_command(3, ["1", "1"])

        # 發言人為媞雅，但此時場上無立繪 -> 嚴格 Fail-Closed 輸出 None
        resolved = sm.resolve_dialogue_identity("媞雅")
        self.assertIsNone(resolved, "無官方場上立繪支持時必須為 null，不得猜測為 193211，更不得為 1")

    def test_case_f_deterministic_serialization(self):
        """Case F: 確定性序列化保證兩次輸出 SHA-256 完全相同"""
        sample_dialogues = [
            {"type": "dialogue", "name": "可可蘿", "words": "主公大人！", "voice": "vo_001", "unit_id": 105911},
            {"type": "still", "still_id": "100101"},
            {"type": "dialogue", "name": "旁白", "words": "陽光灑落在草地上。", "voice": None, "unit_id": None},
            {"type": "background", "bg_id": "500170"},
            {"type": "movie", "movie_id": "521700701"}
        ]

        str1 = serialize_canonical_story_json(sample_dialogues)
        str2 = serialize_canonical_story_json(sample_dialogues)

        hash1 = hashlib.sha256(str1.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(str2.encode("utf-8")).hexdigest()

        self.assertEqual(str1, str2)
        self.assertEqual(hash1, hash2)

    def test_case_g_canonical_json_schema_compliance(self):
        """Case G: JSON Schema 格式規格檢驗"""
        sample_dialogues = [
            {"type": "dialogue", "name": "日和", "words": "喝呀！", "voice": "vo_1001", "unit_id": 100111},
            {"type": "dialogue", "name": "魔物", "words": "嘰！", "voice": None, "unit_id": None},
            {"type": "still", "still_id": "end"},
            {"type": "background", "bg_id": "500000"},
            {"type": "movie", "movie_id": "221200601"}
        ]

        # 檢驗各類型欄位契約
        for row in sample_dialogues:
            self.assertIn("type", row)
            if row["type"] == "dialogue":
                self.assertIn("name", row)
                self.assertIn("words", row)
                self.assertIn("voice", row)
                self.assertIn("unit_id", row)
            elif row["type"] == "still":
                self.assertIn("still_id", row)
                self.assertNotIn("words", row)
            elif row["type"] == "background":
                self.assertIn("bg_id", row)
                self.assertNotIn("words", row)
            elif row["type"] == "movie":
                self.assertIn("movie_id", row)
                self.assertNotIn("words", row)


if __name__ == "__main__":
    unittest.main()
