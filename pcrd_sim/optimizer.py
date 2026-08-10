"""
PCRD 戰鬥模擬器 - 半自動軸優化器 (Timeline Optimizer)
"""

from typing import List, Dict, Any
from .engine import BattleEngine

class TimelineOptimizer:
    def __init__(self, boss_enemy_id: int, team_unit_ids: List[int]):
        self.boss_id = boss_enemy_id
        self.team_ids = team_unit_ids

    def optimize(self, mode: str = 'relax') -> Dict[str, Any]:
        """
        對指定隊伍與 Boss 進行半自動軸優化
        - mode='relax': 尋找純 Set / 最低手動操作但高傷害的懶人軸
        - mode='max_damage': 尋找傷害最高的半自動刀
        """
        results = []
        
        # 1. 測試：全員未開 Set (純 Auto)
        eng1 = BattleEngine(self.boss_id, self.team_ids)
        res1 = eng1.run_simulation(set_configs={uid: False for uid in self.team_ids})
        results.append({
            'name': '純 Auto 模式',
            'ops_count': 0,
            'report': res1
        })
        
        # 2. 測試：全員開啟 Set (全 Set 模式)
        eng2 = BattleEngine(self.boss_id, self.team_ids)
        res2 = eng2.run_simulation(set_configs={uid: True for uid in self.team_ids})
        results.append({
            'name': '全 Set 模式',
            'ops_count': 1,
            'report': res2
        })

        # 3. 測試：僅主力輸出與破防角開啟 Set
        eng3 = BattleEngine(self.boss_id, self.team_ids)
        # 前兩位/主力開 Set
        half_set = {uid: (i < 3) for i, uid in enumerate(self.team_ids)}
        res3 = eng3.run_simulation(set_configs=half_set)
        results.append({
            'name': '關鍵角 Set 模式',
            'ops_count': 1,
            'report': res3
        })

        # 排序
        if mode == 'relax':
            # 優先考量操作少且傷害高的
            sorted_res = sorted(results, key=lambda x: (x['report']['total_damage'] - x['ops_count'] * 50000), reverse=True)
        else:
            sorted_res = sorted(results, key=lambda x: x['report']['total_damage'], reverse=True)

        best = sorted_res[0]
        return {
            'best_mode': best['name'],
            'best_damage': best['report']['total_damage'],
            'all_configurations': results,
            'best_logs': best['report']['logs'][:30]  # 取前 30 條 Log 範例
        }
