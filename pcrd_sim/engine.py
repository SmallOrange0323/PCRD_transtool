"""
PCRD 戰鬥模擬器 - 60 FPS 離散時間戰鬥引擎 (Tick Engine)
"""

from typing import List, Dict, Any, Optional
from .formulas import calculate_damage, calculate_effective_def, calculate_action_tp, calculate_damage_tp, calculate_ub_cost
from .data_loader import DataLoader
from .pk_config import PKBoostConfig, MAXED_PK_CONFIG

TOTAL_FRAMES = 5400  # 90 秒 * 60 FPS

class CombatEntity:
    def __init__(self, entity_id: int, name: str, is_boss: bool = False, talent_id: int = 0, max_hp: int = 100000, atk: int = 10000, pdef: int = 200, mdef: int = 200, tp_boost: float = 0.0, tp_retain: float = 0.0, element_mult: float = 1.0):
        self.entity_id = entity_id
        self.name = name
        self.is_boss = is_boss
        self.talent_id = talent_id
        
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.current_tp = 0
        
        self.atk = atk
        self.base_pdef = pdef
        self.base_mdef = mdef
        self.tp_boost = tp_boost
        self.tp_retain = tp_retain
        self.element_mult = element_mult
        
        # Debuffs
        self.pdef_debuffs: List[Dict[str, Any]] = []
        self.mdef_debuffs: List[Dict[str, Any]] = []
        
        # Status
        self.stun_frames_left = 0
        self.is_set_enabled = False
        
        # Action Loop
        self.skills: Dict[str, Any] = {}
        self.patterns: List[Dict[str, Any]] = []
        self.pattern_index = 0
        self.current_action_name = "Idle"
        self.action_cooldown_frames = 0
        
        # Statistics
        self.total_damage_dealt = 0
        self.ub_count = 0

    @property
    def current_pdef(self) -> float:
        debuff_val = sum(d['value'] for d in self.pdef_debuffs)
        return calculate_effective_def(self.base_pdef, [debuff_val])

    @property
    def current_mdef(self) -> float:
        debuff_val = sum(d['value'] for d in self.mdef_debuffs)
        return calculate_effective_def(self.base_mdef, [debuff_val])

    def add_tp(self, amount: int):
        self.current_tp = min(1000, max(0, self.current_tp + amount))

    def consume_ub_tp(self):
        cost = calculate_ub_cost(self.tp_retain)
        self.current_tp = max(0, self.current_tp - cost)
        self.ub_count += 1

    def tick_status(self):
        if self.stun_frames_left > 0:
            self.stun_frames_left -= 1

        for d in list(self.pdef_debuffs):
            d['duration_frames'] -= 1
            if d['duration_frames'] <= 0:
                self.pdef_debuffs.remove(d)

        for d in list(self.mdef_debuffs):
            d['duration_frames'] -= 1
            if d['duration_frames'] <= 0:
                self.mdef_debuffs.remove(d)


class BattleEngine:
    def __init__(self, boss_enemy_id: int, team_unit_ids: List[int], pk_config: Optional[PKBoostConfig] = None):
        self.loader = DataLoader()
        self.pk_config = pk_config or MAXED_PK_CONFIG
        
        # Load Boss
        boss_data = self.loader.load_boss_data(boss_enemy_id)
        info = boss_data['info']
        self.boss = CombatEntity(
            entity_id=boss_enemy_id,
            name=info.get('name', 'Boss'),
            is_boss=True,
            talent_id=0,
            max_hp=info.get('hp', 100000000),
            atk=info.get('atk', 15000),
            pdef=info.get('def', 1000),
            mdef=info.get('magic_def', 1000)
        )
        self.boss.skills = boss_data['skills']
        self.boss.patterns = boss_data['patterns']

        # Load Team
        self.team: List[CombatEntity] = []
        for uid in team_unit_ids:
            udata = self.loader.load_unit_data(uid)
            uinfo = udata['info']
            stats = udata['stats']  # 含 Rank 裝備與 Rank Bonus 最終面板
            talent_id = uinfo.get('talent_id', 0)
            
            # 套用 Rank 面板 + PKBoostConfig 公主騎士練度加成
            base_hp = stats.get('hp', 30000) + self.pk_config.get_total_hp_bonus()
            base_atk = stats.get('atk', 8000) + self.pk_config.get_total_atk_bonus()
            base_tp_boost = stats.get('energy_recovery_rate', 30.0) + self.pk_config.get_total_tp_boost(talent_id)
            base_tp_retain = stats.get('energy_reduce_rate', 0.0)
            elem_mult = self.pk_config.get_element_atk_multiplier(talent_id)
            
            member = CombatEntity(
                entity_id=uid,
                name=uinfo.get('unit_name', f'Unit_{uid}'),
                is_boss=False,
                talent_id=talent_id,
                max_hp=int(base_hp),
                atk=int(base_atk),
                pdef=stats.get('def', 300),
                mdef=stats.get('magic_def', 300),
                tp_boost=base_tp_boost,
                tp_retain=base_tp_retain,
                element_mult=elem_mult
            )
            member.skills = udata['skills']
            member.patterns = udata['patterns']
            self.team.append(member)

        self.current_frame = 0
        self.logs: List[str] = []

    def log(self, message: str):
        seconds_left = max(0, 90 - (self.current_frame // 60))
        frames_part = self.current_frame % 60
        time_str = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}.{frames_part:02d}"
        self.logs.append(f"[{time_str}] {message}")

    def run_simulation(self, set_configs: Optional[Dict[int, bool]] = None) -> Dict[str, Any]:
        if set_configs:
            for member in self.team:
                if member.entity_id in set_configs:
                    member.is_set_enabled = set_configs[member.entity_id]

        self.log("戰鬥開始！")

        for frame in range(TOTAL_FRAMES):
            self.current_frame = frame
            
            # 1. Status Update
            self.boss.tick_status()
            for member in self.team:
                member.tick_status()

            # 2. Check Set / UB Triggers for Team
            for member in self.team:
                if member.is_set_enabled and member.current_tp >= 1000 and member.stun_frames_left <= 0:
                    self.execute_ub(member, self.boss)

            # 3. Member Actions Logic
            for member in self.team:
                if member.stun_frames_left > 0:
                    continue
                if member.action_cooldown_frames > 0:
                    member.action_cooldown_frames -= 1
                else:
                    self.execute_normal_action(member, self.boss)
                    member.action_cooldown_frames = 120

            # 4. Boss Action Logic
            if self.boss.stun_frames_left <= 0:
                if self.boss.action_cooldown_frames > 0:
                    self.boss.action_cooldown_frames -= 1
                else:
                    self.execute_boss_action(self.boss, self.team)
                    self.boss.action_cooldown_frames = 100

        total_dmg = sum(m.total_damage_dealt for m in self.team)
        self.log(f"戰鬥結束！總傷害: {total_dmg:,}")
        
        return {
            'total_damage': total_dmg,
            'member_reports': [
                {
                    'unit_id': m.entity_id,
                    'name': m.name,
                    'talent_id': m.talent_id,
                    'damage': m.total_damage_dealt,
                    'ub_count': m.ub_count
                } for m in self.team
            ],
            'logs': self.logs
        }

    def execute_ub(self, attacker: CombatEntity, defender: CombatEntity):
        attacker.consume_ub_tp()
        dmg = calculate_damage(attacker.atk * 3.5, defender.current_pdef, is_crit=True, element_mult=attacker.element_mult)
        defender.current_hp = max(0, defender.current_hp - dmg)
        attacker.total_damage_dealt += dmg
        
        tp_gained = calculate_damage_tp(dmg, defender.max_hp, defender.tp_boost)
        defender.add_tp(tp_gained)
        
        self.log(f"⚔️ {attacker.name} 發動 【UB】！造成 {dmg:,} 傷害 (攻擊力: {attacker.atk:,}, 屬性倍率: x{attacker.element_mult:.2f})")

    def execute_normal_action(self, attacker: CombatEntity, defender: CombatEntity):
        dmg = calculate_damage(attacker.atk * 1.0, defender.current_pdef, element_mult=attacker.element_mult)
        defender.current_hp = max(0, defender.current_hp - dmg)
        attacker.total_damage_dealt += dmg
        
        tp_gained = calculate_action_tp(90, attacker.tp_boost)
        attacker.add_tp(tp_gained)
        
        boss_tp_gained = calculate_damage_tp(dmg, defender.max_hp, defender.tp_boost)
        defender.add_tp(boss_tp_gained)

    def execute_boss_action(self, boss: CombatEntity, team: List[CombatEntity]):
        if not team:
            return
        target = team[0]
        dmg = calculate_damage(boss.atk * 0.8, target.current_pdef)
        target.current_hp = max(0, target.current_hp - dmg)
        
        tp_gained = calculate_damage_tp(dmg, target.max_hp, target.tp_boost)
        target.add_tp(tp_gained)
