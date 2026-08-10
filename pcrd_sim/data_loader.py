"""
PCRD 戰鬥模擬器 - 資料庫資料載入模組 (Data Loader)
"""

import sqlite3
import os
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard', 'redive_tw.db')

class DataLoader:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_boss_data(self, enemy_id: int) -> Dict[str, Any]:
        """
        載入 Boss 完整面版與技能數據
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM enemy_parameter WHERE enemy_id = ?", (enemy_id,))
        boss_row = cur.fetchone()
        if not boss_row:
            conn.close()
            raise ValueError(f"Boss Enemy ID {enemy_id} not found in DB")
            
        boss_dict = dict(boss_row)
        unit_id = boss_dict['unit_id']
        
        cur.execute("SELECT * FROM unit_skill_data WHERE unit_id = ?", (unit_id,))
        skill_row = cur.fetchone()
        skills = {}
        if skill_row:
            skill_dict = dict(skill_row)
            for key in ['union_burst', 'main_skill_1', 'main_skill_2', 'main_skill_3']:
                sid = skill_dict.get(key, 0)
                if sid and sid > 0:
                    skills[key] = self.load_skill_data(sid)

        cur.execute("SELECT * FROM unit_attack_pattern WHERE unit_id = ?", (unit_id,))
        pattern_rows = cur.fetchall()
        patterns = [dict(r) for r in pattern_rows]

        conn.close()
        return {
            'info': boss_dict,
            'skills': skills,
            'patterns': patterns
        }

    def load_unit_data(self, unit_id: int, rarity: int = 5, promotion_level: Optional[int] = None) -> Dict[str, Any]:
        """
        載入角色基本資料、Rank 裝備加成、Promotion Bonus 與技能數據
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM unit_data WHERE unit_id = ?", (unit_id,))
        unit_row = cur.fetchone()
        if not unit_row:
            conn.close()
            raise ValueError(f"Unit ID {unit_id} not found in DB")
            
        unit_dict = dict(unit_row)
        
        # 查 unit_talent 取得屬性 ID (1:火, 2:水, 3:風, 4:光, 5:暗)
        cur.execute("SELECT talent_id FROM unit_talent WHERE unit_id = ?", (unit_id,))
        talent_row = cur.fetchone()
        talent_id = talent_row['talent_id'] if talent_row else 0
        unit_dict['talent_id'] = talent_id
        
        # 查最高或指定的 promotion_level (Rank 裝備加成)
        if promotion_level is None:
            cur.execute("SELECT * FROM unit_promotion_status WHERE unit_id = ? ORDER BY promotion_level DESC LIMIT 1", (unit_id,))
        else:
            cur.execute("SELECT * FROM unit_promotion_status WHERE unit_id = ? AND promotion_level = ?", (unit_id, promotion_level))
            
        promo_row = cur.fetchone()
        promo_dict = dict(promo_row) if promo_row else {}
        actual_rank = promo_dict.get('promotion_level', 40)
        
        # 查 promotion_bonus (最高 Rank Bonus 加成)
        cur.execute("SELECT * FROM promotion_bonus WHERE unit_id = ? AND promotion_level = ?", (unit_id, actual_rank))
        bonus_row = cur.fetchone()
        bonus_dict = dict(bonus_row) if bonus_row else {}

        # 基礎星級屬性 unit_rarity
        cur.execute("SELECT * FROM unit_rarity WHERE unit_id = ? AND rarity = ?", (unit_id, rarity))
        rarity_row = cur.fetchone()
        rarity_dict = dict(rarity_row) if rarity_row else {}
        
        # 整合 Rank 裝備與 Rank Bonus 加成屬性
        final_stats = {
            'hp': rarity_dict.get('hp', 0) + promo_dict.get('hp', 0) + bonus_dict.get('hp', 0),
            'atk': max(rarity_dict.get('atk', 0), rarity_dict.get('magic_str', 0)) + max(promo_dict.get('atk', 0), promo_dict.get('magic_str', 0)) + max(bonus_dict.get('atk', 0), bonus_dict.get('magic_str', 0)),
            'def': rarity_dict.get('def', 0) + promo_dict.get('def', 0) + bonus_dict.get('def', 0),
            'magic_def': rarity_dict.get('magic_def', 0) + promo_dict.get('magic_def', 0) + bonus_dict.get('magic_def', 0),
            'energy_recovery_rate': rarity_dict.get('energy_recovery_rate', 0) + promo_dict.get('energy_recovery_rate', 0) + bonus_dict.get('energy_recovery_rate', 0),
            'energy_reduce_rate': rarity_dict.get('energy_reduce_rate', 0) + promo_dict.get('energy_reduce_rate', 0) + bonus_dict.get('energy_reduce_rate', 0),
            'promotion_level': actual_rank
        }
        
        # unit_skill_data
        cur.execute("SELECT * FROM unit_skill_data WHERE unit_id = ?", (unit_id,))
        skill_row = cur.fetchone()
        skills = {}
        if skill_row:
            skill_dict = dict(skill_row)
            for key in ['union_burst', 'main_skill_1', 'main_skill_2', 'main_skill_3']:
                sid = skill_dict.get(key, 0)
                if sid and sid > 0:
                    skills[key] = self.load_skill_data(sid)

        # unit_attack_pattern
        cur.execute("SELECT * FROM unit_attack_pattern WHERE unit_id = ?", (unit_id,))
        pattern_rows = cur.fetchall()
        patterns = [dict(r) for r in pattern_rows]

        conn.close()
        return {
            'info': unit_dict,
            'stats': final_stats,
            'skills': skills,
            'patterns': patterns
        }

    def load_skill_data(self, skill_id: int) -> Dict[str, Any]:
        """
        載入技能詳情與包含的所有 skill_action
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM skill_data WHERE skill_id = ?", (skill_id,))
        skill_row = cur.fetchone()
        if not skill_row:
            conn.close()
            return {'skill_id': skill_id, 'name': 'Unknown', 'actions': []}
            
        skill_dict = dict(skill_row)
        actions = []
        for i in range(1, 8):
            act_key = f'action_{i}'
            act_id = skill_dict.get(act_key, 0)
            if act_id and act_id > 0:
                cur.execute("SELECT * FROM skill_action WHERE action_id = ?", (act_id,))
                act_row = cur.fetchone()
                if act_row:
                    actions.append(dict(act_row))

        conn.close()
        skill_dict['actions'] = actions
        return skill_dict
