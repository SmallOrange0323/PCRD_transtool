"""
PCRD 戰鬥模擬器 - 公主騎士練度與屬性強化配置 (PK Enhancement Config)
"""

from typing import Dict, Any

class PKBoostConfig:
    """
    公主騎士系統練度設定：
    包含 5 大屬性等級、屬性技能、職階等級與大師技能加成
    """
    def __init__(
        self,
        element_levels: Dict[int, int] = None,   # 1:火, 2:水, 3:風, 4:光, 5:暗 (預設 Lv.40)
        element_dmg_bonus: float = 0.25,        # 同屬性傷害加成 (+25%)
        element_tp_boost: float = 5.0,           # 屬性 TP 上升加成 (+5)
        class_levels: Dict[str, int] = None,     # 職階等級 (預設 Lv.20)
        master_atk_bonus: float = 1000.0,        # 大師技能攻擊力加成
        master_hp_bonus: float = 5000.0,         # 大師技能 HP 加成
        master_tp_boost: float = 3.0             # 大師技能 TP 上升加成
    ):
        # 預設 5 屬性滿級 (Lv.40)
        self.element_levels = element_levels or {1: 40, 2: 40, 3: 40, 4: 40, 5: 40}
        self.element_dmg_bonus = element_dmg_bonus
        self.element_tp_boost = element_tp_boost
        
        self.class_levels = class_levels or {'tank': 20, 'physical_attacker': 20, 'magical_attacker': 20, 'support': 20}
        
        self.master_atk_bonus = master_atk_bonus
        self.master_hp_bonus = master_hp_bonus
        self.master_tp_boost = master_tp_boost

    def get_element_atk_multiplier(self, talent_id: int) -> float:
        """
        取得指定屬性角色的同屬性傷害加成倍率 (如 1.25 即 125% 傷害)
        """
        if not talent_id or talent_id <= 0:
            return 1.0
        return 1.0 + self.element_dmg_bonus

    def get_total_tp_boost(self, talent_id: int) -> float:
        """
        取得指定屬性角色的總 TP 上升附加值 (屬性技能 + 大師技能)
        """
        bonus = self.master_tp_boost
        if talent_id in self.element_levels:
            bonus += self.element_tp_boost
        return bonus

    def get_total_atk_bonus(self) -> float:
        """
        取得攻擊力附加值
        """
        return self.master_atk_bonus

    def get_total_hp_bonus(self) -> float:
        """
        取得 HP 附加值
        """
        return self.master_hp_bonus

# 預設滿練度設定檔 (Maxed PK Configuration)
MAXED_PK_CONFIG = PKBoostConfig(
    element_levels={1: 40, 2: 40, 3: 40, 4: 40, 5: 40},
    element_dmg_bonus=0.25,
    element_tp_boost=5.0,
    master_atk_bonus=1200.0,
    master_hp_bonus=6000.0,
    master_tp_boost=5.0
)

# 無練度設定檔 (Zero PK Configuration)
ZERO_PK_CONFIG = PKBoostConfig(
    element_levels={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
    element_dmg_bonus=0.0,
    element_tp_boost=0.0,
    master_atk_bonus=0.0,
    master_hp_bonus=0.0,
    master_tp_boost=0.0
)
