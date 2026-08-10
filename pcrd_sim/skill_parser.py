"""
PCRD 戰鬥模擬器 - 全 Action 解析器 (Skill Action Parser)
"""

from typing import Dict, Any, List

class ParsedAction:
    def __init__(self, action_id: int, action_type: int, val1: float, val2: float, val3: float, target_type: int = 0, target_area: int = 0):
        self.action_id = action_id
        self.action_type = action_type
        self.val1 = val1
        self.val2 = val2
        self.val3 = val3
        self.target_type = target_type
        self.target_area = target_area

    def get_calculated_value(self, skill_level: int = 300) -> float:
        """
        計算技能 Action 的真實數值
        Formula: Value = val2 + val3 * skill_level
        """
        return self.val2 + self.val3 * skill_level


class SkillParser:
    @staticmethod
    def parse_action_details(act_dict: Dict[str, Any], skill_level: int = 300) -> Dict[str, Any]:
        """
        解析單個 Action 的真實屬性：
        - Type 1 / 2: 物理/魔法傷害
        - Type 10: 攻防/暴擊/TP Buff
        - Type 4/6/8/9: 護盾/控場/治療
        - Type 26/28/35/38: 特殊領域與傷害加成
        """
        act_id = act_dict.get('action_id', 0)
        act_type = act_dict.get('action_type', 0)
        v1 = act_dict.get('action_value_1', 0.0)
        v2 = act_dict.get('action_value_2', 0.0)
        v3 = act_dict.get('action_value_3', 0.0)
        
        calc_val = v2 + v3 * skill_level
        duration = v3 if act_type == 10 and v3 > 0 else (v1 if v1 > 0 else 12.0)
        
        category = "UNKNOWN"
        if act_type in [1, 2]:
            category = "DAMAGE"
        elif act_type in [10, 26, 28, 35, 38]:
            category = "BUFF_DEBUFF"
        elif act_type in [8]:
            category = "CONTROL"
        elif act_type in [16]:
            category = "TP_REDUCE"

        return {
            'action_id': act_id,
            'action_type': act_type,
            'category': category,
            'value': calc_val,
            'duration_seconds': duration,
            'duration_frames': int(duration * 60),
            'target_area': act_dict.get('target_area', 0)
        }
