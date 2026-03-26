"""
EyeScroll 滚动控制模块
跨平台滚动控制器，使用适配器模式
"""
from .adapters import ScrollControllerImpl


class ScrollController:
    """滚动控制器 - 跨平台兼容"""

    def __init__(
        self,
        scroll_distance: int = 30,
        scroll_interval_ms: int = 200,
        up_scroll_distance: int = 30,
        up_scroll_interval_ms: int = 200,
    ):
        self._impl = ScrollControllerImpl(
            scroll_distance=scroll_distance,
            scroll_interval_ms=scroll_interval_ms,
            up_scroll_distance=up_scroll_distance,
            up_scroll_interval_ms=up_scroll_interval_ms,
        )

    def scroll_down(self) -> bool:
        return self._impl.scroll_down()

    def scroll_up(self) -> bool:
        return self._impl.scroll_up()

    def stop(self):
        return self._impl.stop()

    def stop_down(self):
        return self._impl.stop_down()

    def stop_up(self):
        return self._impl.stop_up()
