"""
Windows 滚动适配器
使用 ctypes 调用 Windows API 发送滚动事件
"""
import time
import ctypes
from ctypes import windll, POINTER, Structure, c_long, c_ulong, byref


class MSLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("pt", c_ulong * 2),
        ("mouseData", c_ulong),
        ("flags", c_ulong),
        ("time", c_long),
    ]


# Windows constants
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120


class WinScrollController:
    """Windows 滚动控制器"""

    def __init__(
        self,
        scroll_distance: int = 30,
        scroll_interval_ms: int = 200,
        up_scroll_distance: int = 30,
        up_scroll_interval_ms: int = 200,
    ):
        self._down_distance = scroll_distance
        self._down_interval_ms = scroll_interval_ms
        self._last_down_scroll_time: float = 0

        self._up_distance = up_scroll_distance  # 正值向上滚动
        self._up_interval_ms = up_scroll_interval_ms
        self._last_up_scroll_time: float = 0

    def scroll_down(self) -> bool:
        """执行一次向下滚动"""
        current_time = time.monotonic() * 1000

        if current_time - self._last_down_scroll_time < self._down_interval_ms:
            return False

        self._last_down_scroll_time = current_time

        try:
            # 向下滚动：正值的 wheel delta
            windll.user32.mouse_event(
                MOUSEEVENTF_WHEEL,
                0,
                0,
                self._down_distance * WHEEL_DELTA // 30,  # 归一化到 WHEEL_DELTA
                0
            )
            return True
        except Exception as e:
            print(f"滚动错误: {e}")
            return False

    def scroll_up(self) -> bool:
        """执行一次向上滚动（回翻）"""
        current_time = time.monotonic() * 1000

        if current_time - self._last_up_scroll_time < self._up_interval_ms:
            return False

        self._last_up_scroll_time = current_time

        try:
            # 向上滚动：负值的 wheel delta
            windll.user32.mouse_event(
                MOUSEEVENTF_WHEEL,
                0,
                0,
                -self._up_distance * WHEEL_DELTA // 30,  # 归一化到 WHEEL_DELTA
                0
            )
            return True
        except Exception as e:
            print(f"滚动错误: {e}")
            return False

    def stop(self):
        """停止滚动"""
        pass

    def stop_down(self):
        """停止向下滚动"""
        self._last_down_scroll_time = 0

    def stop_up(self):
        """停止向上滚动"""
        self._last_up_scroll_time = 0
