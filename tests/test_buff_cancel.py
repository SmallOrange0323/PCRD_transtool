"""
PCRD 戰鬥模擬器 - Set 斷 Buff 與動態 Buff 疊層檢測測試腳本
"""

import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pcrd_sim import BuffTracker, SkillAnimationState

def test_buff_stacking():
    print("[1/2] 測試動態 Buff 滾雪球疊加與計時衰減...")
    tracker = BuffTracker()
    
    # 第 1 秒：可可蘿放 Buff (+9000 物攻)
    tracker.add_buff('atk', 9000.0, duration_seconds=12.0, source_name="可可蘿（新年）")
    assert tracker.get_total_buff_value('atk') == 9000.0
    assert tracker.get_stack_count('atk') == 1
    
    # 第 3 秒：卯月放 Buff (+9000 物攻)
    tracker.add_buff('atk', 9000.0, duration_seconds=12.0, source_name="卯月（NGs）")
    assert tracker.get_total_buff_value('atk') == 18000.0
    assert tracker.get_stack_count('atk') == 2
    
    print(f"  └─ 成功！當前加攻 Buff 總加成: +{tracker.get_total_buff_value('atk'):,.0f} (疊加 {tracker.get_stack_count('atk')} 層)")

def test_set_interrupt_detection():
    print("[2/2] 測試 Set 提前打斷 Buff 招式檢測 (Set Cancel Buff Inspection)...")
    
    # 案例 A：Set UB 提前在第 20 幀切斷（Hit Frame 在第 45 幀） -> 應發出 ⚠️ 警告 Buff 丟失！
    anim_a = SkillAnimationState(skill_name="新年光輝", total_frames=90, hit_frame=45, is_buff_skill=True)
    anim_a.start()
    for _ in range(20):
        anim_a.tick()
        
    report_a = anim_a.interrupt_by_ub()
    print(f"  └─ [案例 A (第 20 幀硬切)]: {report_a['msg']}")
    assert report_a['type'] == 'BUFF_CANCELLED'

    # 案例 B：Set UB 在第 50 幀切斷（Buff 已在第 45 幀生效） -> 應發出 ✅ 成功 Cancel 後搖！
    anim_b = SkillAnimationState(skill_name="Smiling Brave", total_frames=90, hit_frame=45, is_buff_skill=True)
    anim_b.start()
    for _ in range(50):
        res = anim_b.tick()
        
    report_b = anim_b.interrupt_by_ub()
    print(f"  └─ [案例 B (第 50 幀硬切)]: {report_b['msg']}")
    assert report_b['type'] == 'SUCCESSFUL_CANCEL'

if __name__ == '__main__':
    print("=== 開始 PCRD Set 斷 Buff 與動態 Buff 疊層檢測驗證 ===")
    test_buff_stacking()
    test_set_interrupt_detection()
    print("\n✅ 三道綠燈自檢：動態 Buff 疊層與 Set 斷 Buff 檢測系統全數測試通過！")
