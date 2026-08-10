"""
PCRD 戰鬥模擬器 - 官方標準計算公式庫
"""

import math

def calculate_damage(atk: float, def_val: float, is_crit: bool = False, crit_dmg_mult: float = 2.0, element_mult: float = 1.0) -> int:
    """
    計算物理/魔法傷害 (標準防禦扣抵公式，含屬性加成)
    Damage = (ATK * Element_Mult) / (1 + DEF / 100)
    """
    effective_def = max(0.0, def_val)
    raw_damage = (atk * max(0.0, element_mult)) / (1.0 + effective_def / 100.0)
    
    if is_crit:
        raw_damage *= crit_dmg_mult
        
    return max(1, int(math.floor(raw_damage)))

def calculate_effective_def(base_def: float, debuffs: list) -> float:
    """
    計算扣除破防後的有效防禦力
    """
    total_debuff = sum(debuffs)
    return max(0.0, base_def - total_debuff)

def calculate_action_tp(base_tp: float, tp_boost: float) -> int:
    """
    計算行動/技能獲得的 TP
    Gained TP = Base TP * (1 + TP_Boost / 100)
    """
    gained = base_tp * (1.0 + max(0.0, tp_boost) / 100.0)
    return int(math.floor(gained))

def calculate_damage_tp(damage_taken: float, max_hp: float, tp_boost: float) -> int:
    """
    計算受傷獲得的 TP
    Damage TP = (Damage_Taken / Max_HP) * 0.5 * 1000 * (1 + TP_Boost / 100)
    """
    if max_hp <= 0:
        return 0
    hp_ratio = damage_taken / max_hp
    raw_tp = hp_ratio * 0.5 * 1000.0
    gained = raw_tp * (1.0 + max(0.0, tp_boost) / 100.0)
    return int(math.floor(gained))

def calculate_ub_cost(tp_retain: float) -> int:
    """
    計算施放 UB 消耗的 TP (扣除 TP 消耗降低)
    Consumed TP = 1000 * (1 - TP_Retain / 100)
    """
    consumed = 1000.0 * (1.0 - min(100.0, max(0.0, tp_retain)) / 100.0)
    return int(math.floor(consumed))
