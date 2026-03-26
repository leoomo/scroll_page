"""
EyeScroll 状态机模块
管理 IDLE / DWELLING_DOWN / SCROLLING_DOWN / DWELLING_UP / SCROLLING_UP 五种状态
"""
import time
from typing import Optional, Tuple


class GazeStateMachine:
    """视线状态机"""

    STATE_IDLE = "idle"
    STATE_DWELLING_DOWN = "dwelling_down"
    STATE_SCROLLING_DOWN = "scrolling_down"
    STATE_DWELLING_UP = "dwelling_up"
    STATE_SCROLLING_UP = "scrolling_up"

    # 向后兼容别名
    STATE_DWELLING = "dwelling_down"
    STATE_SCROLLING = "scrolling_down"

    def __init__(
        self,
        dwell_time_ms: int = 500,
        scroll_zone_ratio: float = 0.20,
        up_scroll_enabled: bool = False,
        up_scroll_ratio: float = 0.10,
        up_dwell_time_ms: int = 800,
    ):
        # 向下滚动参数
        self._dwell_time_ms = dwell_time_ms
        self._down_threshold_y = 1.0 - scroll_zone_ratio  # 默认 0.80

        # 向上滚动参数
        self._up_scroll_enabled = up_scroll_enabled
        self._up_threshold_y = up_scroll_ratio  # 默认 0.10
        self._up_dwell_time_ms = up_dwell_time_ms

        self._state = self.STATE_IDLE
        self._last_gaze_point: Optional[Tuple[float, float]] = None
        self._dwell_start_time: Optional[float] = None
        self._in_up_zone = False  # 标记当前是否在上方区域

    def update_gaze(self, gaze_point: Tuple[float, float]):
        """更新视线位置"""
        self._last_gaze_point = gaze_point
        gaze_x, gaze_y = gaze_point

        if self._state == self.STATE_SCROLLING_DOWN:
            if gaze_y < self._down_threshold_y:
                self._transition_to(self.STATE_IDLE)

        elif self._state == self.STATE_SCROLLING_UP:
            if gaze_y > self._up_threshold_y:
                self._transition_to(self.STATE_IDLE)

        elif self._state == self.STATE_DWELLING_DOWN:
            if gaze_y < self._down_threshold_y:
                self._transition_to(self.STATE_IDLE)
            elif self._check_dwell_timeout(self._dwell_time_ms):
                self._transition_to(self.STATE_SCROLLING_DOWN)

        elif self._state == self.STATE_DWELLING_UP:
            if gaze_y > self._up_threshold_y:
                self._transition_to(self.STATE_IDLE)
            elif self._check_dwell_timeout(self._up_dwell_time_ms):
                self._transition_to(self.STATE_SCROLLING_UP)

        else:  # IDLE
            if gaze_y > self._down_threshold_y:
                # 进入下方滚动区
                self._in_up_zone = False
                self._dwell_start_time = time.monotonic()
                self._transition_to(self.STATE_DWELLING_DOWN)
            elif gaze_y < self._up_threshold_y and self._up_scroll_enabled:
                # 进入上方滚动区
                self._in_up_zone = True
                self._dwell_start_time = time.monotonic()
                self._transition_to(self.STATE_DWELLING_UP)

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
            if new_state not in (self.STATE_DWELLING_DOWN, self.STATE_DWELLING_UP):
                self._dwell_start_time = None

    def _check_dwell_timeout(self, dwell_time_ms: int) -> bool:
        """检查停留是否超时"""
        if self._dwell_start_time is None:
            return False
        elapsed_ms = (time.monotonic() - self._dwell_start_time) * 1000
        return elapsed_ms >= dwell_time_ms
