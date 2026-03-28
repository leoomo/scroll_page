"""
HeadScroll - 本地菜单栏客户端
纯本地应用，无网络开销，追求最低延迟
"""
import atexit
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import rumps

# 使用 PyObjC 来正确退出应用
try:
    from AppKit import NSApplication
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False
    print("[Warning] AppKit not available, exit may not work properly")

sys.path.insert(0, str(Path(__file__).parent))

from core.camera import Camera
from core.head_tracker import HeadTracker
from core.head_state import HeadStateMachine
from core.scroll_controller import ScrollController
from config import config
from adapters.mac_flash import show_flash
from adapters.calibration_pyside6 import show_calibration_dialog

APP_NAME = "HeadScroll"
CALIBRATION_FILE = Path.home() / ".eye_scroll" / "calibration.json"

# ==================== Global State ====================

class AppState:
    def __init__(self):
        self.camera = None
        self.head_tracker = None
        self.head_state = None
        self.scroll_controller = None
        self.running = False
        self.enabled = True
        self.head_offset = None
        self.face_detected = False
        self.last_action = None
        self._calibrating = False
        self._camera_lock = threading.Lock()  # 保护摄像头访问

state = AppState()

# ==================== Calibration ====================

def save_calibration():
    if state.head_tracker and state.head_tracker.is_calibrated():
        data = {"neutral_y": state.head_tracker.get_neutral_y()}
        CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(data, f, indent=2)

def load_calibration():
    if not state.head_tracker:
        return
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            data = json.load(f)
        neutral_y = data.get("neutral_y")
        if neutral_y is not None:
            state.head_tracker._neutral_y = neutral_y
            state.head_tracker._calibrated = True
            state.head_tracker._smooth_offset = 0.0
    except Exception:
        pass

# ==================== Tracking Loop (高性能主循环) ====================

def tracking_loop():
    """主追踪循环 - 纯本地，无锁竞争"""
    camera_open = False
    last_action = None
    last_flash_time = 0.0

    while state.running:
        # 暂停时释放摄像头节省资源
        if not state.enabled and not state._calibrating:
            if camera_open:
                with state._camera_lock:
                    if state.camera:
                        state.camera.release()
                        state.camera = None
                camera_open = False
            time.sleep(0.1)
            continue

        # 按需打开摄像头
        if not camera_open:
            try:
                with state._camera_lock:
                    if not state.running:
                        break
                    # 如果 main() 已经创建了 camera，直接使用
                    if state.camera is None:
                        state.camera = Camera()
                camera_open = True
            except Exception:
                time.sleep(1)
                continue

        # 读取帧（加锁保护）
        with state._camera_lock:
            if not state.running or state.camera is None:
                break
            try:
                frame = state.camera.read()
            except Exception:
                frame = None

        if frame is None:
            continue

        # 处理帧
        try:
            result = state.head_tracker.process(frame)
        except Exception:
            result = None

        if result is None:
            if state.head_tracker and state.head_tracker._calibrating:
                state.face_detected = getattr(state.head_tracker, '_last_face_detected', False)
            else:
                state.head_state.no_face_detected()
                state.head_offset = None
                state.face_detected = False
                last_action = None
        else:
            _, offset_y = result
            state.head_offset = offset_y
            state.face_detected = True

            action = state.head_state.update(offset_y)
            state.last_action = action

            if action == "scroll_down":
                state.scroll_controller.scroll_down()
            elif action == "scroll_up":
                state.scroll_controller.scroll_up()

            # 方向箭头（限速2秒）
            if action and action != last_action:
                now = time.monotonic()
                if now - last_flash_time > 2.0:
                    last_flash_time = now
                    if "down" in action:
                        show_flash("↓")
                    elif "up" in action:
                        show_flash("↑")
                last_action = action
            elif not action:
                last_action = None

        # ~200Hz 循环，无睡眠最大性能
        time.sleep(0.005)

    # 循环退出时释放摄像头
    if camera_open:
        with state._camera_lock:
            if state.camera:
                try:
                    state.camera.release()
                except Exception:
                    pass
                state.camera = None

# ==================== Cleanup ====================

def cleanup():
    """清理资源并退出应用"""
    print("[HeadScroll] 退出...")
    state.running = False

    # 使用 AppKit 终止应用（在主线程中安全）
    if HAS_APPKIT:
        try:
            from AppKit import NSApplication
            app = NSApplication.sharedApplication()
            app.terminate_(None)
        except Exception as e:
            print(f"[HeadScroll] AppKit terminate error: {e}")

# ==================== Menu Bar App ====================

class HeadScrollApp(rumps.App):
    def __init__(self):
        super().__init__("👤", menu=[
            rumps.MenuItem("启用"),
            None,
            rumps.MenuItem("校准 (3秒)"),
            rumps.MenuItem("重置校准"),
            None,
            rumps.MenuItem("状态: -"),
            rumps.MenuItem("面部: -"),
            None,
            rumps.MenuItem("退出"),
        ])

        self.status_item = self.menu["状态: -"]
        self.face_item = self.menu["面部: -"]
        self.enable_item = self.menu["启用"]

        # 状态更新定时器 (2Hz 足够，但退出检查需要更快)
        self.updater = rumps.Timer(self._update, 0.1)
        self.updater.start()

    def _update(self, sender=None):
        # 检查是否需要退出（用于信号处理）
        if not state.running:
            print("[HeadScroll] 检测到退出信号，正在关闭...")
            if HAS_APPKIT:
                from AppKit import NSApplication
                app = NSApplication.sharedApplication()
                app.terminate_(None)
            else:
                sys.exit(0)
            return

        # 状态显示映射：技术术语 → 用户友好中文
        state_map = {
            "idle": "待机",
            "dwelling_down": "低头滚动",
            "dwelling_up": "抬头滚动",
            "continuous_down": "↓ 向下滚动",
            "continuous_up": "↑ 向上滚动",
        }
        # 滚动时的图标映射
        icon_map = {
            "continuous_down": "👤 ↓",
            "continuous_up": "👤 ↑",
            "dwelling_down": "👤 ↓",
            "dwelling_up": "👤 ↑",
        }
        raw_state = state.head_state.get_state() if state.head_state else "idle"
        display_state = state_map.get(raw_state, raw_state)

        # 防抖：只有状态稳定超过 0.3 秒才改变图标，避免闪烁
        now = time.monotonic()
        if not hasattr(self, '_last_icon_state') or self._last_icon_state != raw_state:
            self._last_icon_state = raw_state
            self._icon_change_time = now
        else:
            if now - self._icon_change_time > 0.3:
                # 禁用时显示暂停图标
                if not state.enabled:
                    new_icon = "⏸"
                else:
                    new_icon = icon_map.get(raw_state, "👤")
                if self.title != new_icon:
                    self.title = new_icon

        if state.head_state:
            display_state = "已禁用" if not state.enabled else display_state
            self.status_item.title = f"状态: {display_state}"
        else:
            self.status_item.title = "状态: N/A"
        self.face_item.title = "面部: 已检测" if state.face_detected else "面部: 未检测"
        self.enable_item.title = "禁用" if state.enabled else "启用"

    @rumps.clicked("启用")
    def toggle(self, sender):
        state.enabled = not state.enabled
        if not state.enabled:
            state.scroll_controller.stop()
            state.head_state.reset()
            show_flash("OFF")
        else:
            show_flash("ON")

    @rumps.clicked("校准 (3秒)")
    def calibrate(self, sender):
        if state.head_tracker:
            # 启动真实校准（head_tracker 在 tracking_loop 的 process() 中采集数据）
            state.head_tracker.start_calibration(3.0)
            state._calibrating = True
            print("[HeadScroll] 开始校准...", flush=True)

            # 显示视觉倒计时对话框（纯 UI，不采集数据）
            def on_dialog_complete(dialog_result):
                print(f"[HeadScroll] 校准对话框完成: {dialog_result}", flush=True)
                state._calibrating = False
                # 从 head_tracker 获取真实校准数据
                real_result = state.head_tracker.stop_calibration()
                if dialog_result.get("success") and real_result.get("success"):
                    save_calibration()
                    show_flash(f"校准完成 ({real_result.get('sample_count')} 样本)")
                else:
                    error = real_result.get('error', '样本不足')
                    show_flash(f"校准失败: {error}")

            show_calibration_dialog(
                head_tracker=state.head_tracker,
                duration=3.0,
                on_complete=on_dialog_complete
            )

    @rumps.clicked("重置校准")
    def reset(self, sender):
        if state.head_tracker:
            state.head_tracker.reset_calibration()
        if CALIBRATION_FILE.exists():
            CALIBRATION_FILE.unlink()
        show_flash("已重置")

    @rumps.clicked("退出")
    def quit(self, sender):
        print("[HeadScroll] 退出菜单被点击")
        cleanup()
        print("[HeadScroll] cleanup 完成，准备退出")
        sys.exit(0)

# ==================== Main ====================

def main():
    # 初始化
    try:
        state.camera = Camera()
        state.head_tracker = HeadTracker(
            confidence_threshold=config.detection_confidence,
            ema_alpha=config.get("head_ema_alpha"),
            down_threshold=config.get("head_down_threshold"),
            up_threshold=config.get("head_up_threshold"),
        )
        state.head_state = HeadStateMachine(
            down_threshold=config.get("head_down_threshold"),
            up_threshold=config.get("head_up_threshold"),
            deadzone=config.get("head_deadzone"),
            dwell_time_ms=config.get("head_dwell_time_ms"),
            continuous_threshold_ms=config.get("head_continuous_threshold_ms"),
            scroll_interval_ms=config.scroll_interval_ms,
        )
        state.scroll_controller = ScrollController(
            scroll_distance=config.scroll_distance,
            scroll_interval_ms=config.scroll_interval_ms,
            up_scroll_distance=config.up_scroll_distance,
            up_scroll_interval_ms=config.up_scroll_interval_ms,
        )
        load_calibration()
        state.running = True
    except Exception as e:
        print(f"[HeadScroll] 初始化失败: {e}")
        sys.exit(1)

    # 信号处理
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup() or sys.exit(0))

    # 启动追踪线程
    t = threading.Thread(target=tracking_loop, daemon=True, name="tracking_thread")
    t.start()

    print(f"[HeadScroll] 已启动 (PID: {os.getpid()})")

    # 运行菜单栏 (阻塞)
    app = HeadScrollApp()
    app.run()

if __name__ == "__main__":
    main()