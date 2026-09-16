import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from tools.pcrd_fetch import _parse_bundle_dialogues

class TestStoryUnitIdExtraction(unittest.TestCase):
    """
    針對 PCRD Story command stream 的 unit_id 解析進行 Targeted 回歸測試。
    覆蓋：
    Case 1: 普通角色登場後發言得到正確 unit_id，連續發言延續相同 unit_id
    Case 2: 多人同場時，不因其他人的表情指令而誤配 speaker 的 unit_id
    Case 3: 造型切換（變身）後，後續對話切換為新造型 unit_id
    Case 4: 旁白 (0) 或多人合言 ('139611:139511')，安全 fallback（省略 unit_id）
    """
    
    def simulate_parse(self, commands):
        # 模擬 _parse_bundle_dialogues 中的指令流處理邏輯
        dialogues = []
        scene_actor_state = {}
        block_cmd4_units = []
        block_cmd3_units = []
        last_speaker = None
        last_speaker_unit = None
        current_voice = None
        
        for idx, args in commands:
            if idx == 68 and len(args) >= 2:
                u_str = str(args[0]).strip()
                pos_str = str(args[1]).strip()
                if u_str.isdigit() and len(u_str) == 6 and int(u_str) >= 100000:
                    scene_actor_state[pos_str] = int(u_str)
            elif idx == 4 and args:
                target_str = str(args[0]).strip()
                if target_str.isdigit() and len(target_str) == 6 and int(target_str) >= 100000:
                    block_cmd4_units.append(int(target_str))
                elif target_str == "0" or ":" in target_str:
                    block_cmd4_units.append(None)
            elif idx == 3 and args:
                u_str = str(args[0]).strip()
                if u_str.isdigit() and len(u_str) == 6 and int(u_str) >= 100000:
                    block_cmd3_units.append(int(u_str))
            elif idx == 12 and args:
                current_voice = args[0]
            elif idx == 6 and len(args) >= 2:
                speaker = args[0]
                words = args[1]
                
                resolved_unit = None
                valid_cmd4 = [u for u in block_cmd4_units if u is not None]
                unique_cmd4 = set(valid_cmd4)
                unique_cmd3 = set(block_cmd3_units)
                
                # 規則 1: 本區塊有且僅有一種有效的單一焦點 cmd 4
                if len(unique_cmd4) == 1 and (None not in block_cmd4_units):
                    resolved_unit = list(unique_cmd4)[0]
                # 規則 2: 本區塊無 cmd 4，但有且僅有一種表情 cmd 3
                elif len(block_cmd4_units) == 0 and len(unique_cmd3) == 1:
                    resolved_unit = list(unique_cmd3)[0]
                # 規則 3: 本區塊無任何立繪指令，且與上一句為同一位發言者
                elif len(block_cmd4_units) == 0 and len(block_cmd3_units) == 0:
                    if speaker == last_speaker and last_speaker_unit:
                        resolved_unit = last_speaker_unit

                entry = {"name": speaker, "words": words, "voice": current_voice}
                if resolved_unit is not None and isinstance(resolved_unit, int) and resolved_unit >= 100000:
                    entry["unit_id"] = resolved_unit

                dialogues.append(entry)
                current_voice = None
                
                last_speaker = speaker
                last_speaker_unit = resolved_unit
                block_cmd4_units = []
                block_cmd3_units = []
                
        return dialogues

    def test_case1_normal_single_actor(self):
        """Case 1: 普通角色登場後發言，獲得正確 unit_id，連續發言延續相同 unit_id"""
        cmds = [
            (4, ['107011']),
            (3, ['107011', '1']),
            (12, ['vo_01']),
            (6, ['似似花', '初次見面。']),
            (6, ['似似花', '我是似似花。']),
        ]
        res = self.simulate_parse(cmds)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].get("unit_id"), 107011)
        self.assertEqual(res[1].get("unit_id"), 107011)

    def test_case2_multi_actor_no_misassignment(self):
        """Case 2: 多人同場，另一角色做表情動作，不應錯配 speaker"""
        cmds = [
            # 角色 A (139611 可璃亞) 焦點
            (4, ['139611']),
            (3, ['139611', '2']),
            # 角色 B (139511 莉莉) 同時做表情
            (3, ['139511', '6']),
            (12, ['vo_koria_01']),
            (6, ['可璃亞', '這、這是……！？']),
        ]
        res = self.simulate_parse(cmds)
        self.assertEqual(len(res), 1)
        # 焦點為 139611，不應被 139511 覆蓋
        self.assertEqual(res[0].get("unit_id"), 139611)

    def test_case3_transformation_switch(self):
        """Case 3: 造型切換 (變身) 後，後續發言自動切換為新造型 ID"""
        cmds = [
            # 變身前苦戰 (125813 莉莉負傷)
            (4, ['125813']),
            (3, ['125813', '4']),
            (6, ['莉莉', '我們不能放棄……！']),
            # 變身演出後 (139511 莉莉女武神)
            (4, ['139511']),
            (3, ['139511', '6']),
            (6, ['莉莉', '這是……新的力量？']),
        ]
        res = self.simulate_parse(cmds)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].get("unit_id"), 125813)
        self.assertEqual(res[1].get("unit_id"), 139511)

    def test_case4_safe_fallback(self):
        """Case 4: 旁白 (0) 或多人合言 ('139611:139511')，安全 fallback (省略 unit_id)"""
        cmds = [
            (4, ['0']),
            (6, ['旁白', '戰鬥結束了。']),
            (4, ['139611:139511:139711']),
            (6, ['３人', '我們成功了！']),
        ]
        res = self.simulate_parse(cmds)
        self.assertEqual(len(res), 2)
        self.assertNotIn("unit_id", res[0])
        self.assertNotIn("unit_id", res[1])

if __name__ == '__main__':
    unittest.main()
