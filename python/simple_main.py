"""
EyeScroll - Simplified Menu Bar App
A simple macOS menu bar application for eye-tracking scroll control.
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

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core.camera import Camera
from core.head_tracker import HeadTracker
from core.head_state import HeadStateMachine
from core.scroll_controller import ScrollController
from config import config
from adapters.mac_flash import show_flash

# ==================== Constants ====================

APP_NAME = "EyeScroll"
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

state = AppState()

# ==================== Calibration ====================

def save_calibration():
    """Save calibration data to file."""
    if state.head_tracker and state.head_tracker.is_calibrated():
        data = {"neutral_y": state.head_tracker.get_neutral_y()}
        CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False

def load_calibration():
    """Load calibration data from file."""
    if CALIBRATION_FILE.exists() and state.head_tracker:
        try:
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            neutral_y = data.get("neutral_y")
            if neutral_y is not None:
                state.head_tracker._neutral_y = neutral_y
                state.head_tracker._calibrated = True
                state.head_tracker._smooth_offset = 0.0
                return True
        except Exception as e:
            print(f"[Calibration] Failed to load: {e}")
    return False

def reset_calibration():
    """Reset calibration."""
    if state.head_tracker:
        state.head_tracker.reset_calibration()
    if CALIBRATION_FILE.exists():
        CALIBRATION_FILE.unlink()

# ==================== Initialize ====================

def initialize():
    """Initialize all modules."""
    try:
        state.camera = Camera()
        state.head_tracker = HeadTracker(
            confidence_threshold=config.detection_confidence,
            ema_alpha=config.get("head_ema_alpha", 0.15),
            down_threshold=config.get("head_down_threshold", 0.025),
            up_threshold=config.get("head_up_threshold", -0.025),
        )
        state.head_state = HeadStateMachine(
            down_threshold=config.get("head_down_threshold", 0.025),
            up_threshold=config.get("head_up_threshold", -0.025),
            deadzone=config.get("head_deadzone", 0.015),
            dwell_time_ms=config.get("head_dwell_time_ms", 300),
            continuous_threshold_ms=config.get("head_continuous_threshold_ms", 2000),
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
        return True
    except Exception as e:
        print(f"初始化失败: {e}")
        return False

# ==================== Tracking Loop ====================

def tracking_loop():
    """Main tracking loop running in background thread."""
    camera_open = False
    last_action = None
    last_flash_time = 0.0

    while state.running:
        # Check if disabled (but not calibrating)
        if not state.enabled and not state._calibrating:
            if camera_open:
                state.camera.release()
                camera_open = False
            time.sleep(0.1)
            continue

        # Open camera if needed
        if not camera_open:
            try:
                state.camera = Camera()
                camera_open = True
            except Exception:
                time.sleep(1)
                continue

        # Read frame
        frame = state.camera.read()
        if frame is None:
            continue

        # Process frame
        result = state.head_tracker.process(frame)

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

            # Update state machine
            action = state.head_state.update(offset_y)
            state.last_action = action

            # Send scroll events
            if action == "scroll_down":
                state.scroll_controller.scroll_down()
            elif action == "scroll_up":
                state.scroll_controller.scroll_up()

            # Flash direction arrow (throttled)
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

        time.sleep(0.005)

# ==================== Cleanup ====================

def cleanup():
    """Cleanup all resources."""
    print("[Cleanup] Starting cleanup...")
    state.running = False

    if state.scroll_controller:
        try:
            state.scroll_controller.stop()
        except Exception:
            pass

    if state.camera:
        try:
            state.camera.release()
        except Exception:
            pass

    if state.head_tracker:
        try:
            state.head_tracker.close()
        except Exception:
            pass

    print("[Cleanup] Cleanup complete")

# ==================== Menu Bar App ====================

class EyeScrollApp(rumps.App):
    def __init__(self):
        # Build menu
        menu_items = [
            rumps.MenuItem("启用追踪", callback=self.toggle_enabled),
            None,  # separator
            rumps.MenuItem("校准", callback=self.calibrate),
            rumps.MenuItem("重置校准", callback=self.reset_calibration),
            None,
            rumps.MenuItem("状态: -"),
            rumps.MenuItem("面部: -"),
            None,
            rumps.MenuItem("退出", callback=self.quit_app),
        ]

        super().__init__(APP_NAME, menu=menu_items)

        # State display items
        self.status_item = self.menu["状态: -"]
        self.face_item = self.menu["面部: -"]
        self.enable_item = self.menu["启用追踪"]

        # Start update timer
        self.updater = rumps.Timer(self._update_state, 0.5)
        self.updater.start()

    def _update_state(self, sender=None):
        """Periodically update menu bar and state display."""
        if state.head_state:
            self.status_item.title = f"状态: {state.head_state.get_state().upper()}"
        else:
            self.status_item.title = "状态: N/A"

        if state.face_detected:
            self.face_item.title = "面部: 已检测 ✓"
        else:
            self.face_item.title = "面部: 未检测 ✗"

        self.enable_item.title = "禁用追踪" if state.enabled else "启用追踪"

    @rumps.clicked("启用追踪")
    def toggle_enabled(self, sender):
        """Toggle tracking enabled/disabled."""
        state.enabled = not state.enabled
        if not state.enabled:
            if state.scroll_controller:
                state.scroll_controller.stop()
            if state.head_state:
                state.head_state.reset()
            show_flash("OFF")
        else:
            show_flash("ON")

    @rumps.clicked("校准")
    def calibrate(self, sender):
        """Start calibration."""
        if state.head_tracker:
            state._calibrating = True
            state.head_tracker.start_calibration(3.0)
            show_flash("校准中...")

            # Wait for calibration to complete in background
            threading.Thread(target=self._wait_calibration, daemon=True).start()

    def _wait_calibration(self):
        """Wait for calibration to complete."""
        time.sleep(3.0)
        if state.head_tracker:
            result = state.head_tracker.stop_calibration()
            state._calibrating = False
            if result.get("success"):
                save_calibration()
                show_flash(f"校准完成 ({result.get('sample_count')} 样本)")
            else:
                show_flash(f"校准失败")

    @rumps.clicked("重置校准")
    def reset_calibration(self, sender):
        """Reset calibration."""
        reset_calibration()
        show_flash("校准已重置")

    @rumps.clicked("退出")
    def quit_app(self, sender):
        """Quit the application."""
        cleanup()
        rumps.quit()

# ==================== Main ====================

def main():
    """Main entry point."""
    print("EyeScroll 启动中...", flush=True)

    # Initialize
    if not initialize():
        print("初始化失败，退出。", flush=True)
        sys.exit(1)

    print("初始化完成!", flush=True)

    # Register cleanup
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup() or sys.exit(0))

    # Start tracking thread
    tracking_thread = threading.Thread(target=tracking_loop, daemon=True)
    tracking_thread.start()

    print("EyeScroll 已启动!", flush=True)
    print("按 Cmd+Q 或点击菜单栏图标退出。", flush=True)

    # Run menu bar app (this blocks)
    app = EyeScrollApp()
    app.run()

if __name__ == "__main__":
    main()