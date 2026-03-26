"""
EyeScroll 状态机
"""
from typing import Optional, Tuple


class GazeStateMachine:
    STATE_IDLE = "idle"
    STATE_SCROLLING_DOWN = "scrolling_down"
    STATE_SCROLLING_UP = "scrolling_up"

    def __init__(self):
        self._state = self.STATE_IDLE

    def update_gaze(self, gaze_point: Tuple[float, float]):
        pass

    def get_state(self) -> str:
        return self._state

    def get_gaze_point(self) -> Optional[Tuple[float, float]]:
        return None

    def no_face_detected(self):
        self._state = self.STATE_IDLE

    def reset(self):
        self._state = self.STATE_IDLE
