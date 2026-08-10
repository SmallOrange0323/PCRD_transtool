"""
PCRD 戰鬥模擬器單元測試與模擬驗證腳本
"""

import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pcrd_sim import (
    calculate_damage, calculate_effective_def, calculate_action_tp, 
    DataLoader, BattleEngine, TimelineOptimizer,
    PKBoostConfig, MAXED_PK_CONFIG, ZERO_PK_CONFIG
)

def test_formulas():
    print("[1/5] 測試公式庫 (formulas)...")
    dmg = calculate_damage(atk=10000, def_val=100, element_mult=1.25)
    assert dmg == 6250, f"Expected 6250 damage, got {dmg}"
    
    eff_def = calculate_effective_def(200, [50, 30])
    assert eff_def == 120, f"Expected 120 effective def, got {eff_def}"
    
    tp = calculate_action_tp(90, 30.0)
    assert tp == 117, f"Expected 117 TP, got {tp}"
    print("  └─ 公式庫測試全數通過！")

def test_data_loader():
    print("[2/5] 測試資料載入器 (data_loader)...")
    loader = DataLoader()
    boss_data = loader.load_boss_data(401902403)
    assert boss_data['info']['name'] == '芒刺爬行者'
    print(f"  └─ 成功載入 Boss: {boss_data['info']['name']}")
    
    unit_data = loader.load_unit_data(106301)
    talent_id = unit_data['info']['talent_id']
    print(f"  └─ 成功載入角色: {unit_data['info']['unit_name']} (屬性 Talent ID: {talent_id})")

def test_pk_enhancement():
    print("[3/5] 測試公主騎士練度與屬性強化 (PK Boost)...")
    boss_id = 401902403
    team_ids = [106301, 103801, 100101, 100201, 100301]
    
    # 零練度模擬
    eng_zero = BattleEngine(boss_id, team_ids, pk_config=ZERO_PK_CONFIG)
    res_zero = eng_zero.run_simulation(set_configs={106301: True})
    
    # 滿練度模擬
    eng_max = BattleEngine(boss_id, team_ids, pk_config=MAXED_PK_CONFIG)
    res_max = eng_max.run_simulation(set_configs={106301: True})
    
    print(f"  └─ 無 PK 練度總傷害: {res_zero['total_damage']:,}")
    print(f"  └─ 滿 PK 練度總傷害: {res_max['total_damage']:,}")
    assert res_max['total_damage'] > res_zero['total_damage'], "Maxed PK should deal higher damage"

def test_engine_simulation():
    print("[4/5] 測試戰鬥模擬引擎 (engine 60 FPS 90秒)...")
    boss_id = 401902403
    team_ids = [106301, 103801, 100101, 100201, 100301]
    
    engine = BattleEngine(boss_id, team_ids)
    res = engine.run_simulation(set_configs={106301: True, 103801: True})
    
    print(f"  └─ 模擬成功！總傷害: {res['total_damage']:,}, 產生日誌條數: {len(res['logs'])}")
    assert res['total_damage'] > 0

def test_optimizer():
    print("[5/5] 測試半自動軸優化器 (optimizer)...")
    boss_id = 401902403
    team_ids = [106301, 103801, 100101, 100201, 100301]
    
    opt = TimelineOptimizer(boss_id, team_ids)
    opt_res = opt.optimize(mode='relax')
    print(f"  └─ 優化完成！最佳模式: {opt_res['best_mode']}, 傷害: {opt_res['best_damage']:,}")

if __name__ == '__main__':
    print("=== 開始 PCRD 戰鬥模擬器驗證 (含 PK 練度) ===")
    test_formulas()
    test_data_loader()
    test_pk_enhancement()
    test_engine_simulation()
    test_optimizer()
    print("\n✅ 三道綠燈自檢：戰鬥模擬器與公主騎士練度系統測試全數通過！")
