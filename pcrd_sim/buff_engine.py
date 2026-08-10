"""
PCRD 戰鬥模擬器 - 動態 Buff 疊層引擎 (Buff Stacking Engine)
"""

from typing import List, Dict, Any

class ActiveBuff:
    def __init__(self, buff_id: str, stat_type: str, value: float, duration_frames: int, source_name: str = ""):
        self.buff_id = buff_id
        self.stat_type = stat_type  # 'atk', 'pdef', 'mdef', 'tp_boost', 'crit'
        self.value = value
        self.duration_frames = duration_frames
        self.remaining_frames = duration_frames
        self.source_name = source_name

    def is_expired(self) -> bool:
        return self.remaining_frames <= 0

    def tick(self):
        if self.remaining_frames > 0:
            self.remaining_frames -= 1


class BuffTracker:
    def __init__(self):
        self.active_buffs: List[ActiveBuff] = []

    def add_buff(self, stat_type: str, value: float, duration_seconds: float = 12.0, source_name: str = ""):
        duration_frames = int(duration_seconds * 60)
        buff = ActiveBuff(
            buff_id=f"{stat_type}_{source_name}_{len(self.active_buffs)}",
            stat_type=stat_type,
            value=value,
            duration_frames=duration_frames,
            source_name=source_name
        )
        self.active_buffs.append(buff)

    def tick(self):
        for buff in list(self.active_buffs):
            buff.tick()
            if buff.is_expired():
                self.active_buffs.remove(buff)

    def get_total_buff_value(self, stat_type: str) -> float:
        """
        取得當前指定屬性的 Buff 總疊加值
        """
        return sum(b.value for b in self.active_buffs if b.stat_type == stat_type)

    def get_stack_count(self, stat_type: str = 'atk') -> int:
        """
        取得當前指定屬性的 Buff 疊加層數
        """
        return len([b for b in self.active_buffs if b.stat_type == stat_type])
