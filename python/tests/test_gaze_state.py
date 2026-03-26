"""
EyeScroll 状态机测试
"""
import pytest
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
        state_machine = GazeStateMachine(dwell_time_ms=500, scroll_zone_ratio=0.25)
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
        state_machine = GazeStateMachine(scroll_zone_ratio=0.25)
        state_machine.update_gaze((0.5, 0.8))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING
        state_machine.no_face_detected()
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_reset_clears_state(self):
        """reset() 重置状态"""
        state_machine = GazeStateMachine(scroll_zone_ratio=0.25)
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

    # ===== 向上滚动功能测试 =====

    def test_up_scroll_disabled_by_default(self):
        """向上滚动默认关闭"""
        state_machine = GazeStateMachine(up_scroll_enabled=False)
        # 视线进入上方区域
        state_machine.update_gaze((0.5, 0.05))
        # 仍应保持 IDLE，不触发向上滚动
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_up_scroll_enabled_triggers_dwelling_up(self):
        """启用向上滚动后，视线进入上方区域触发 DWELLING_UP"""
        state_machine = GazeStateMachine(
            up_scroll_enabled=True,
            up_scroll_ratio=0.10,
            up_dwell_time_ms=800,
        )
        # y = 0.05 在上方区域 (0-10%)
        state_machine.update_gaze((0.5, 0.05))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING_UP

    def test_up_dwelling_timeout_transitions_to_scrolling_up(self):
        """向上滚动：停留超时后切换到 SCROLLING_UP"""
        state_machine = GazeStateMachine(
            up_scroll_enabled=True,
            up_scroll_ratio=0.10,
            up_dwell_time_ms=100,
        )
        # 进入上方区域
        state_machine.update_gaze((0.5, 0.05))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING_UP
        # 等待超时
        time.sleep(0.15)
        state_machine.update_gaze((0.5, 0.05))
        assert state_machine.get_state() == GazeStateMachine.STATE_SCROLLING_UP

    def test_up_scrolling_gaze_leaves_up_zone_returns_idle(self):
        """向上滚动时视线离开上方区域回到 IDLE"""
        state_machine = GazeStateMachine(
            up_scroll_enabled=True,
            up_scroll_ratio=0.10,
            up_dwell_time_ms=50,
        )
        # 快速触发向上滚动
        state_machine.update_gaze((0.5, 0.05))
        time.sleep(0.06)
        state_machine.update_gaze((0.5, 0.05))
        assert state_machine.get_state() == GazeStateMachine.STATE_SCROLLING_UP
        # 视线离开上方区域
        state_machine.update_gaze((0.5, 0.5))
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE

    def test_up_scroll_longer_dwell_time_than_down(self):
        """向上滚动需要更长的停留时间"""
        state_machine = GazeStateMachine(
            up_scroll_enabled=True,
            up_scroll_ratio=0.10,
            dwell_time_ms=100,  # 向下滚动 100ms
            up_dwell_time_ms=300,  # 向上滚动 300ms
        )
        # 向下滚动区域 y = 0.9 (> 0.8)
        state_machine.update_gaze((0.5, 0.9))
        time.sleep(0.15)
        state_machine.update_gaze((0.5, 0.9))
        # 向下滚动应该已经触发
        assert state_machine.get_state() == GazeStateMachine.STATE_SCROLLING_DOWN

    def test_down_and_up_scroll_zones_separate(self):
        """向下和向上滚动区域互不影响"""
        state_machine = GazeStateMachine(
            up_scroll_enabled=True,
            up_scroll_ratio=0.10,
            scroll_zone_ratio=0.20,  # 下方 20% (80-100%)
            dwell_time_ms=50,
            up_dwell_time_ms=50,
        )
        # 进入下方区域
        state_machine.update_gaze((0.5, 0.9))
        assert state_machine.get_state() == GazeStateMachine.STATE_DWELLING_DOWN
        # 视线移到上方区域
        state_machine.update_gaze((0.5, 0.05))
        # 应该回到 IDLE，因为下方滚动已停止
        assert state_machine.get_state() == GazeStateMachine.STATE_IDLE
