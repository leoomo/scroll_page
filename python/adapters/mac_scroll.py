"""
macOS 滚动适配器
使用 PyObjC 调用 macOS Accessibility API 发送滚动事件
"""
import logging
import time
from Quartz import (
    CGEventCreateScrollWheelEvent, CGEventPost, kCGHIDEventTap,
)

logger = logging.getLogger(__name__)


class MacScrollController:
    """macOS 滚动控制器"""

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

        self._up_distance = -up_scroll_distance
        self._up_interval_ms = up_scroll_interval_ms
        self._last_up_scroll_time: float = 0

    def _send_scroll(self, delta: int) -> bool:
        """发送滚轮事件到鼠标所在窗口（而非前台应用）。"""
        try:
            # 创建带 nil source 的事件（这样系统会根据鼠标位置路由到对应窗口）
            event = CGEventCreateScrollWheelEvent(
                None,           # nil source → 根据鼠标位置路由
                0,              # 0 = kCGScrollEventUnitPixel
                1,              # 1 个滚轮
                delta,
            )
            if event:
                CGEventPost(kCGHIDEventTap, event)
                logger.debug("CGEvent posted: delta=%d", delta)
            else:
                logger.warning("CGEvent creation FAILED: delta=%d", delta)
            return True
        except Exception as e:
            logger.error("Scroll event failed: %s", e)
            return False

    def scroll_down(self) -> bool:
        """执行一次向下滚动（内容向上走）"""
        current_time = time.monotonic() * 1000
        elapsed = current_time - self._last_down_scroll_time
        if elapsed < self._down_interval_ms:
            return False
        self._last_down_scroll_time = current_time
        return self._send_scroll(self._down_distance)

    def scroll_up(self) -> bool:
        """执行一次向上滚动（内容向下走）"""
        current_time = time.monotonic() * 1000
        if current_time - self._last_up_scroll_time < self._up_interval_ms:
            return False
        self._last_up_scroll_time = current_time
        return self._send_scroll(self._up_distance)

    def stop(self):
        pass

    def stop_down(self):
        self._last_down_scroll_time = 0

    def stop_up(self):
        self._last_up_scroll_time = 0
