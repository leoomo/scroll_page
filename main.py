"""
EyeScroll - 眼球追踪滚动应用
macOS 菜单栏应用，通过摄像头追踪眼球实现免手滚动
"""
import rumps
import threading
import time
from typing import Optional, Tuple
from dataclasses import dataclass

from config import config
from core.camera import Camera
from core.eye_tracker import EyeTracker
from core.gaze_state import GazeStateMachine
from core.scroll_controller import ScrollController


@dataclass
class GazeData:
    """共享的视线数据"""
    state: str = GazeStateMachine.STATE_IDLE
    gaze_point: Optional[Tuple[float, float]] = None


class EyeScrollApp(rumps.App):
    """EyeScroll 应用主类"""

    STATE_TITLES = {
        GazeStateMachine.STATE_IDLE: "阅读中",
        GazeStateMachine.STATE_DWELLING_DOWN: "准备向下滚动...",
        GazeStateMachine.STATE_SCROLLING_DOWN: "向下滚动中",
        GazeStateMachine.STATE_DWELLING_UP: "准备向上回翻...",
        GazeStateMachine.STATE_SCROLLING_UP: "向上回翻中",
    }

    STATE_ICONS = {
        GazeStateMachine.STATE_IDLE: "👁",
        GazeStateMachine.STATE_DWELLING_DOWN: "👁⏳",
        GazeStateMachine.STATE_SCROLLING_DOWN: "👁⬇",
        GazeStateMachine.STATE_DWELLING_UP: "👁🔼",
        GazeStateMachine.STATE_SCROLLING_UP: "👁⬆",
    }

    def __init__(self):
        super().__init__("EyeScroll", "👁")

        self._enabled = True
        self._camera: Optional[Camera] = None
        self._eye_tracker: Optional[EyeTracker] = None
        self._gaze_state: Optional[GazeStateMachine] = None
        self._scroll_controller: Optional[ScrollController] = None
        self._tracking_thread: Optional[threading.Thread] = None
        self._running = False

        self._gaze_data = GazeData()
        self._data_lock = threading.Lock()

        self._last_ui_state: Optional[str] = None
        self._last_ui_gaze: Optional[Tuple[float, float]] = None

        self._setup_menu()

    def _setup_menu(self):
        """设置菜单"""
        self._toggle_item = rumps.MenuItem(
            "已启用",
            callback=self._on_toggle,
        )

        self._status_item = rumps.MenuItem("状态: 启动中...")
        self._status_item.enabled = False

        self._gaze_item = rumps.MenuItem("视线位置: -")
        self._gaze_item.enabled = False

        quit_item = rumps.MenuItem("退出", callback=self._on_quit)

        self.menu = [
            self._toggle_item,
            rumps.separator,
            self._status_item,
            self._gaze_item,
            rumps.separator,
            quit_item,
        ]

    def _on_toggle(self, sender):
        """切换启用/暂停"""
        self._enabled = not self._enabled
        sender.title = "已暂停" if not self._enabled else "已启用"

        if not self._enabled:
            self.title = "👁⊘"
            self._status_item.title = "状态: 已暂停"
            if self._scroll_controller:
                self._scroll_controller.stop()
            if self._gaze_state:
                self._gaze_state.reset()
        else:
            self.title = "👁"

    def _on_quit(self, sender):
        """退出应用"""
        self._running = False
        self.cleanup()
        rumps.quit_application()

    def _initialize_modules(self):
        """初始化所有模块"""
        try:
            self._camera = Camera()
            self._eye_tracker = EyeTracker(
                confidence_threshold=config.detection_confidence
            )
            self._gaze_state = GazeStateMachine(
                dwell_time_ms=config.dwell_time_ms,
                scroll_zone_ratio=config.scroll_zone_ratio,
                up_scroll_enabled=config.up_scroll_enabled,
                up_scroll_ratio=config.up_scroll_ratio,
                up_dwell_time_ms=config.up_dwell_time_ms,
            )
            self._scroll_controller = ScrollController(
                scroll_distance=config.scroll_distance,
                scroll_interval_ms=config.scroll_interval_ms,
                up_scroll_distance=config.up_scroll_distance,
                up_scroll_interval_ms=config.up_scroll_interval_ms,
            )
            return True
        except Exception as e:
            print(f"初始化失败: {e}")
            return False

    def _tracking_loop(self):
        """追踪主循环 - 在子线程运行"""
        while self._running:
            if not self._enabled:
                time.sleep(0.1)
                continue

            if self._camera is None:
                time.sleep(0.1)
                continue

            frame = self._camera.read()
            if frame is None:
                time.sleep(0.1)
                continue

            gaze_point = self._eye_tracker.process(frame)

            if gaze_point is None:
                self._gaze_state.no_face_detected()
            else:
                self._gaze_state.update_gaze(gaze_point)

            state = self._gaze_state.get_state()

            if state == GazeStateMachine.STATE_SCROLLING_DOWN:
                self._scroll_controller.scroll_down()
            elif state == GazeStateMachine.STATE_SCROLLING_UP:
                self._scroll_controller.scroll_up()
            else:
                self._scroll_controller.stop()

            with self._data_lock:
                self._gaze_data.state = state
                self._gaze_data.gaze_point = gaze_point

            time.sleep(1 / 30)

    def _update_ui_timer(self, sender):
        """定时器回调 - 在主线程更新 UI"""
        if not self._running:
            sender.stop()
            return

        if not self._enabled:
            return

        with self._data_lock:
            state = self._gaze_data.state
            gaze_point = self._gaze_data.gaze_point

        if state == self._last_ui_state and gaze_point == self._last_ui_gaze:
            return

        self.title = self.STATE_ICONS.get(state, "👁")
        self._status_item.title = f"状态: {self.STATE_TITLES.get(state, '未知')}"

        if gaze_point:
            x, y = gaze_point
            self._gaze_item.title = f"视线位置: ({x:.2f}, {y:.2f})"
        else:
            self._gaze_item.title = "视线位置: 未检测"

        self._last_ui_state = state
        self._last_ui_gaze = gaze_point

    def cleanup(self):
        """清理资源"""
        if self._scroll_controller:
            self._scroll_controller.stop()
        if self._camera:
            self._camera.release()

    def run(self):
        """运行应用"""
        if not self._initialize_modules():
            self.title = "👁❌"
            self._status_item.title = "状态: 初始化失败"
            return

        self._running = True
        self.title = "👁"
        self._status_item.title = "状态: 阅读中"

        self._tracking_thread = threading.Thread(
            target=self._tracking_loop,
            daemon=True,
        )
        self._tracking_thread.start()

        self._ui_timer = rumps.Timer(self._update_ui_timer, 0.1)
        self._ui_timer.start()

        super().run()


def main():
    app = EyeScrollApp()
    app.run()


if __name__ == "__main__":
    main()
