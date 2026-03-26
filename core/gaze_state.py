"""
EyeScroll 状态机模块
管理 IDLE / DWELLING / SCROLLING 三种状态
"""
import time
from typing import Optional, Tuple


class GazeStateMachine:
    """视线状态机"""

    STATE_IDLE = "idle"
    STATE_DWELLING = "dwelling"
    STATE_SCROLLING = "scrolling"

    def __init__(
        self,
        dwell_time_ms: int = 500,
        scroll_zone_ratio: float = 0.25,
    ):
        self._dwell_time_ms = dwell_time_ms
        self._scroll_threshold_y = 1.0 - scroll_zone_ratio

        self._state = self.STATE_IDLE
        self._last_gaze_point: Optional[Tuple[float, float]] = None
        self._dwell_start_time: Optional[float] = None

    def update_gaze(self, gaze_point: Tuple[float, float]):
        """更新视线位置"""
        self._last_gaze_point = gaze_point
        gaze_x, gaze_y = gaze_point

        if self._state == self.STATE_SCROLLING:
            if gaze_y < self._scroll_threshold_y:
                self._transition_to(self.STATE_IDLE)
        elif self._state == self.STATE_DWELLING:
            if gaze_y < self._scroll_threshold_y:
                self._transition_to(self.STATE_IDLE)
            elif self._check_dwell_timeout():
                self._transition_to(self.STATE_SCROLLING)
        else:
            if gaze_y > self._scroll_threshold_y:
                self._start_dwell()

    def no_face_detected(self):
        """未检测到人脸，回到空闲状态"""
        self._transition_to(self.STATE_IDLE)

    def get_state(self) -> str:
        """获取当前状态"""
        return self._state

    def get_gaze_point(self) -> Optional[Tuple[float, float]]:
        """获取最后有效的视线位置"""
        return self._last_gaze_point

    def reset(self):
        """重置状态机"""
        self._state = self.STATE_IDLE
        self._last_gaze_point = None
        self._dwell_start_time = None

    def _transition_to(self, new_state: str):
        """状态转换"""
        if self._state != new_state:
            self._state = new_state
            if new_state != self.STATE_DWELLING:
                self._dwell_start_time = None

    def _start_dwell(self):
        """开始停留计时"""
        self._dwell_start_time = time.monotonic()
        self._transition_to(self.STATE_DWELLING)

    def _check_dwell_timeout(self) -> bool:
        """检查停留是否超时"""
        if self._dwell_start_time is None:
            return False
        elapsed_ms = (time.monotonic() - self._dwell_start_time) * 1000
        return elapsed_ms >= self._dwell_time_ms
