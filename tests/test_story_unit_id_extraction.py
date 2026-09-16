import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from tools.pcrd_fetch import _resolve_dialogue_unit_id


class TestStoryUnitIdExtraction(unittest.TestCase):
    """
    針對 Production Helper `_resolve_dialogue_unit_id()` 進行 Targeted 回歸測試。
    直接測試真正的 production code，確保無 duplicate resolver 邏輯漂移。
    """

    def test_case1_unique_cmd4_focus(self):
        """Case 1: 區塊內有唯一合法單一焦點 cmd 4，正確取得該 unit_id"""
        res = _resolve_dialogue_unit_id(
            speaker="似似花",
            block_cmd4_units=[107011],
            block_cmd3_units=[107011],
            last_speaker=None,
            last_speaker_unit=None,
        )
        self.assertEqual(res, 107011)

    def test_case2_continuous_same_speaker_no_commands(self):
        """Case 2: 區塊內無任何 cmd 4 / cmd 3，且與上一句為同一發言者，延續上一句 unit_id"""
        res = _resolve_dialogue_unit_id(
            speaker="似似花",
            block_cmd4_units=[],
            block_cmd3_units=[],
            last_speaker="似似花",
            last_speaker_unit=107011,
        )
        self.assertEqual(res, 107011)

    def test_case3_different_speaker_no_commands(self):
        """Case 3: 區塊內無任何立繪指令，但 speaker 已切換，安全回退 None"""
        res = _resolve_dialogue_unit_id(
            speaker="佑樹",
            block_cmd4_units=[],
            block_cmd3_units=[],
            last_speaker="似似花",
            last_speaker_unit=107011,
        )
        self.assertIsNone(res)

    def test_case4_cmd4_focus_wins_over_other_actors_cmd3(self):
        """Case 4: 多人同場時，區塊內焦點為可璃亞 (139611)，但莉莉 (139511) 也有表情動作，必須正確給可璃亞"""
        res = _resolve_dialogue_unit_id(
            speaker="可璃亞",
            block_cmd4_units=[139611],
            block_cmd3_units=[139611, 139511],
            last_speaker="莉莉",
            last_speaker_unit=139511,
        )
        self.assertEqual(res, 139611)

    def test_case5_cmd3_only_must_not_attribute_speaker(self):
        """
        Case 5 (Review Blocker 專門驗證):
        無 cmd 4，只有單一 cmd 3 (例如莉莉 139511 表情)，但可璃亞說話。
        不能因為單一 cmd 3 就推定 speaker，必須安全回退 None。
        """
        res = _resolve_dialogue_unit_id(
            speaker="可璃亞",
            block_cmd4_units=[],
            block_cmd3_units=[139511],
            last_speaker="莉莉",
            last_speaker_unit=139511,
        )
        self.assertIsNone(res)

        # 即使該單一 cmd 3 剛好也是說話者名字，只要沒有 cmd 4 且換人了，也必須保守回退 None
        res2 = _resolve_dialogue_unit_id(
            speaker="普蕾西亞",
            block_cmd4_units=[],
            block_cmd3_units=[126113],
            last_speaker="莉莉",
            last_speaker_unit=125813,
        )
        self.assertIsNone(res2)

    def test_case6_transformation_switch(self):
        """Case 6: 造型切換 (變身) 前後透過 cmd 4 正確切換舊造型與新造型"""
        # 變身前
        res_before = _resolve_dialogue_unit_id(
            speaker="莉莉",
            block_cmd4_units=[125813],
            block_cmd3_units=[125813],
            last_speaker=None,
            last_speaker_unit=None,
        )
        self.assertEqual(res_before, 125813)

        # 變身後
        res_after = _resolve_dialogue_unit_id(
            speaker="莉莉",
            block_cmd4_units=[139511],
            block_cmd3_units=[139511],
            last_speaker="莉莉",
            last_speaker_unit=125813,
        )
        self.assertEqual(res_after, 139511)

    def test_case7_safe_fallback_for_narrator_and_multi_focus(self):
        """Case 7: 解除焦點 (0) 或多人同時高亮 (None in block)，安全回退 None"""
        # 旁白解除焦點 (cmd 4: ['0'] 會放入 None)
        res_narrator = _resolve_dialogue_unit_id(
            speaker="旁白",
            block_cmd4_units=[None],
            block_cmd3_units=[],
            last_speaker="莉莉",
            last_speaker_unit=139511,
        )
        self.assertIsNone(res_narrator)

        # 多人同時高亮 (cmd 4: ['139611:139511'] 會放入 None)
        res_multi = _resolve_dialogue_unit_id(
            speaker="３人",
            block_cmd4_units=[None],
            block_cmd3_units=[],
            last_speaker="莉莉",
            last_speaker_unit=139511,
        )
        self.assertIsNone(res_multi)


if __name__ == '__main__':
    unittest.main()
