"""
EyeScroll 状态机测试
"""
import pytest
import time
from core.gaze_state import GazeStateMachine


class TestGazeStateMachine:
    """GazeStateMachine 状态转换测试"""

    def test_initial_state_is_idle(self):
        """初始状态应为 IDLE"""
        state_machine = GazeStateMachine()
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_gaze_in_reading_zone_stays_idle(self):
        """视线在阅读区保持 IDLE"""
        state_machine = GazeStateMachine(dwell_time_ms=500)
        # y = 0.5 在阅读区 (上方 75%)
        state_machine.update_gaze((0.5, 0.5))
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_gaze_enters_scroll_zone_triggers_dwelling(self):
        """视线进入滚动区开始计时"""
        state_machine = GazeStateMachine(dwell_time_ms=500, scroll_zone_ratio=0.25)
        # scroll_threshold_y = 0.75, y = 0.8 进入滚动区
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING

    def test_gaze_leaves_scroll_zone_returns_idle(self):
        """视线离开滚动区回到 IDLE"""
        state_machine = GazeStateMachine(dwell_time_ms=500)
        # 进入滚动区
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING
        # 离开滚动区
        state_machine.update_gaze((0.5, 0.5))
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_dwelling_timeout_transitions_to_scrolling(self):
        """停留超时后切换到 SCROLLING"""
        state_machine = GazeStateMachine(dwell_time_ms=100, scroll_zone_ratio=0.25)
        # 进入滚动区
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING
        # 等待超时
        time.sleep(0.15)
        state_machine.update_gaze((0.5, 0.8))  # 同一位置再次调用触发检查
        assert state_machine.get_state() == GazeStateMachine.STATE_SCROLLING

    def test_scrolling_gaze_leaves_returns_idle(self):
        """滚动时视线离开回到 IDLE"""
        state_machine = GazeStateMachine(dwell_time_ms=50, scroll_zone_ratio=0.25)
        # 快速触发滚动
        state_machine.update_gaze((0.5, 0.8))
        time.sleep(0.1)
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_SCROLLING
        # 视线离开
        state_machine.update_gaze((0.5, 0.5))
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_no_face_detected_returns_idle(self):
        """未检测到人脸回到 IDLE"""
        state_machine = GazeStateMachine()
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING
        state_machine.no_face_detected()
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_reset_clears_state(self):
        """reset() 重置状态"""
        state_machine = GazeStateMachine()
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING
        state_machine.reset()
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE
        assert state_machine.get_gaze_point() is None

    def test_duplicate_gaze_point_still_checks_timeout(self):
        """相同视线位置仍会检查超时"""
        state_machine = GazeStateMachine(dwell_time_ms=50, scroll_zone_ratio=0.25)
        # 进入滚动区开始计时
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING
        # 等待超时
        time.sleep(0.06)
        # 相同位置再次调用应触发滚动
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_SCROLLING

    def test_get_gaze_point_returns_last_valid(self):
        """get_gaze_point 返回最后有效的视线位置"""
        state_machine = GazeStateMachine()
        state_machine.update_gaze((0.3, 0.6))
        assert state_machine.get_gaze_point() == (0.3, 0.6)
        state_machine.update_gaze((0.4, 0.7))
        assert state_machine.get_gaze_point() == (0.4, 0.7)
