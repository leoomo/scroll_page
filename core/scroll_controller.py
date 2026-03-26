"""
EyeScroll 滚动控制模块
使用 PyObjC 调用 macOS Accessibility API 发送滚动事件
"""
import time
from Quartz import CGEventCreateScrollWheelEvent, CGEventPost, kCGHIDEventTap


class ScrollController:
    """滚动控制器"""

    def __init__(
        self,
        scroll_distance: int = 30,
        scroll_interval_ms: int = 200,
    ):
        self.scroll_distance = -scroll_distance  # 负值向上滚动（眼睛往下看时内容应向上）
        self.scroll_interval_ms = scroll_interval_ms
        self._last_scroll_time: float = 0
        self._is_scrolling = False

    def scroll(self) -> bool:
        """执行一次滚动"""
        current_time = time.monotonic() * 1000

        if current_time - self._last_scroll_time < self.scroll_interval_ms:
            return False

        self._last_scroll_time = current_time
        self._is_scrolling = True

        try:
            scroll_event = CGEventCreateScrollWheelEvent(
                None,
                0,
                1,
                self.scroll_distance,
            )

            if scroll_event:
                CGEventPost(kCGHIDEventTap, scroll_event)

            return True
        except Exception as e:
            print(f"滚动错误: {e}")
            return False

    def stop(self):
        """停止滚动"""
        self._is_scrolling = False

    @property
    def is_scrolling(self) -> bool:
        """是否正在滚动"""
        return self._is_scrolling
