"""
PCRD 戰鬥模擬器 - 招式動畫與 Hit Frame 判定器 (Set 防打斷檢測器)
"""

from typing import Dict, Any, Optional

class SkillAnimationState:
    def __init__(self, skill_name: str, total_frames: int = 90, hit_frame: int = 45, is_buff_skill: bool = True):
        self.skill_name = skill_name
        self.total_frames = total_frames
        self.hit_frame = hit_frame
        self.is_buff_skill = is_buff_skill
        
        self.current_frame = 0
        self.is_active = False
        self.has_hit_applied = False

    def start(self):
        self.current_frame = 0
        self.is_active = True
        self.has_hit_applied = False

    def tick(self) -> Optional[str]:
        """
        每影格推進
        Returns:
            'APPLY_HIT' (當前影格抵達生效點)
            'FINISHED' (招式動畫播放結束)
        """
        if not self.is_active:
            return None

        self.current_frame += 1

        if self.current_frame == self.hit_frame:
            self.has_hit_applied = True
            return 'APPLY_HIT'

        if self.current_frame >= self.total_frames:
            self.is_active = False
            return 'FINISHED'

        return None

    def interrupt_by_ub(self) -> Dict[str, Any]:
        """
        當 Set 觸發 UB 硬切目前招式時呼叫
        Returns 診斷報告：是否打斷了 Buff，或成功 Cancel 後搖
        """
        if not self.is_active:
            return {'type': 'NORMAL_UB', 'msg': '正常狀態放 UB'}

        was_cancelled_before_hit = not self.has_hit_applied and self.is_buff_skill
        self.is_active = False

        if was_cancelled_before_hit:
            return {
                'type': 'BUFF_CANCELLED',
                'skill_name': self.skill_name,
                'frame': self.current_frame,
                'hit_frame': self.hit_frame,
                'msg': f"⚠️ 警告：Set 提前打斷了技能【{self.skill_name}】(第 {self.current_frame}/{self.hit_frame} 幀)！該層 Buff 丟失！"
            }
        else:
            return {
                'type': 'SUCCESSFUL_CANCEL',
                'skill_name': self.skill_name,
                'frame': self.current_frame,
                'msg': f"✅ 成功：技能【{self.skill_name}】Buff 已生效，完美 Cancel 後搖！"
            }
