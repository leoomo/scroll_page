"""
HeadScroll 校准窗口
使用 AppKit 创建浮动窗口引导校准流程
"""
import json
import subprocess
import sys
import threading
import time

# AppKit 校准窗口脚本
_CALIBRATION_SCRIPT = '''
import sys
from AppKit import (
    NSApplication, NSWindow, NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered, NSColor, NSScreen, NSTextField,
    NSFloatingWindowLevel, NSFont, NSButton, NSProgressIndicator,
    NSMakeRect, NSDate, NSRunLoop, NSDefaultRunLoopMode, NSSound
)
from Foundation import NSSize

app = NSApplication.sharedApplication()
app.activateIgnoringOtherApps_(True)
screen = NSScreen.mainScreen()
frame = screen.frame()

# Window size
w, h = 340, 300
x = (frame.size.width - w) / 2
y = (frame.size.height - h) / 2

# Colors
BG_COLOR = NSColor.colorWithRed_green_blue_alpha_(0.12, 0.12, 0.12, 0.96)
TEXT_COLOR = NSColor.whiteColor()
SUCCESS_COLOR = NSColor.colorWithRed_green_blue_alpha_(0.20, 0.84, 0.29, 1.0)
ERROR_COLOR = NSColor.colorWithRed_green_blue_alpha_(1.0, 0.27, 0.23, 1.0)
WARNING_COLOR = NSColor.colorWithRed_green_blue_alpha_(1.0, 0.84, 0.04, 1.0)
GRAY_COLOR = NSColor.colorWithRed_green_blue_alpha_(0.56, 0.56, 0.58, 1.0)

# Create window
win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    NSMakeRect(x, y, w, h),
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    False,
)
win.setLevel_(NSFloatingWindowLevel)
win.setBackgroundColor_(BG_COLOR)
win.setOpaque_(False)
win.setHasShadow_(True)
win.setAlphaValue_(0.0)

# Content view
content = win.contentView()

# Helper function for fonts
def bold_font(size):
    return NSFont.boldSystemFontOfSize_(size)

def regular_font(size):
    return NSFont.systemFontOfSize_(size)

# Title label
title_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, h - 50, w - 40, 30))
title_label.setEditable_(False)
title_label.setSelectable_(False)
title_label.setBezeled_(False)
title_label.setDrawsBackground_(False)
title_label.setTextColor_(TEXT_COLOR)
title_label.setFont_(regular_font(16))
title_label.setStringValue_("HeadScroll 校准")
title_label.setAlignment_(1)
content.addSubview_(title_label)

# Countdown label (large centered number)
countdown_label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, h//2 - 60, w, 100))
countdown_label.setEditable_(False)
countdown_label.setSelectable_(False)
countdown_label.setBezeled_(False)
countdown_label.setDrawsBackground_(False)
countdown_label.setTextColor_(TEXT_COLOR)
countdown_label.setFont_(bold_font(96))
countdown_label.setAlignment_(1)
countdown_label.setStringValue_("")
countdown_label.setAlphaValue_(0.0)
content.addSubview_(countdown_label)

# Instruction label
instruction_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, h//2 - 100, w - 40, 30))
instruction_label.setEditable_(False)
instruction_label.setSelectable_(False)
instruction_label.setBezeled_(False)
instruction_label.setDrawsBackground_(False)
instruction_label.setTextColor_(TEXT_COLOR)
instruction_label.setFont_(regular_font(14))
instruction_label.setAlignment_(1)
instruction_label.setStringValue_("请注视屏幕中心")
content.addSubview_(instruction_label)

# Face status label
face_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, h//2 - 140, w - 40, 25))
face_label.setEditable_(False)
face_label.setSelectable_(False)
face_label.setBezeled_(False)
face_label.setDrawsBackground_(False)
face_label.setTextColor_(GRAY_COLOR)
face_label.setFont_(regular_font(13))
face_label.setAlignment_(1)
face_label.setStringValue_("面部: 等待中...")
content.addSubview_(face_label)

# Sample counter
sample_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, h//2 - 170, w - 40, 22))
sample_label.setEditable_(False)
sample_label.setSelectable_(False)
sample_label.setBezeled_(False)
sample_label.setDrawsBackground_(False)
sample_label.setTextColor_(GRAY_COLOR)
sample_label.setFont_(regular_font(12))
sample_label.setAlignment_(1)
sample_label.setStringValue_("采样: 0")
content.addSubview_(sample_label)

# Quality label (shown after completion)
quality_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, h//2 - 200, w - 40, 22))
quality_label.setEditable_(False)
quality_label.setSelectable_(False)
quality_label.setBezeled_(False)
quality_label.setDrawsBackground_(False)
quality_label.setTextColor_(SUCCESS_COLOR)
quality_label.setFont_(regular_font(13))
quality_label.setAlignment_(1)
quality_label.setStringValue_("")
quality_label.setHidden_(True)
content.addSubview_(quality_label)

# Result icon label
result_icon = NSTextField.alloc().initWithFrame_(NSMakeRect(0, h//2 - 30, w, 60))
result_icon.setEditable_(False)
result_icon.setSelectable_(False)
result_icon.setBezeled_(False)
result_icon.setDrawsBackground_(False)
result_icon.setFont_(bold_font(48))
result_icon.setAlignment_(1)
result_icon.setStringValue_("")
result_icon.setHidden_(True)
content.addSubview_(result_icon)

# Progress bar
progress_bar = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(40, 50, w - 80, 6))
progress_bar.setStyle_(1)  # 1 = bar style
progress_bar.setIndeterminate_(False)
progress_bar.setMinValue_(0)
progress_bar.setMaxValue_(100)
progress_bar.setDoubleValue_(0)
content.addSubview_(progress_bar)

# Buttons
cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(w//2 - 70, 15, 60, 30))
cancel_btn.setTitle_("取消")
cancel_btn.setFont_(regular_font(13))
cancel_btn.setBezelStyle_(6)
cancel_btn.setTarget_(app)
cancel_btn.setAction_("terminate:")
content.addSubview_(cancel_btn)

retry_btn = NSButton.alloc().initWithFrame_(NSMakeRect(w//2 - 50, 15, 100, 30))
retry_btn.setTitle_("重试")
retry_btn.setFont_(regular_font(13))
retry_btn.setBezelStyle_(6)
retry_btn.setTarget_(app)
retry_btn.setAction_("terminate:")
retry_btn.setHidden_(True)
content.addSubview_(retry_btn)

done_btn = NSButton.alloc().initWithFrame_(NSMakeRect(w//2 + 20, 15, 60, 30))
done_btn.setTitle_("完成")
done_btn.setFont_(regular_font(13))
done_btn.setBezelStyle_(6)
done_btn.setTarget_(app)
done_btn.setAction_("terminate:")
done_btn.setHidden_(True)
content.addSubview_(done_btn)

# Audio
def play_sound(name):
    try:
        NSSound.soundNamed_(name).play()
    except:
        pass

def beep():
    try:
        NSSound.beep()
    except:
        pass

# Animation helpers
def fade_in(target, duration=0.2):
    steps = 10
    for i in range(steps):
        target.setAlphaValue_((i + 1) / steps)
        until = NSDate.dateWithTimeIntervalSinceNow_(duration / steps)
        NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

def fade_out(target, duration=0.2):
    steps = 10
    for i in range(steps):
        target.setAlphaValue_(1.0 - (i + 1) / steps)
        until = NSDate.dateWithTimeIntervalSinceNow_(duration / steps)
        NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

def animate_countdown(num):
    for i in range(8):
        alpha = 1.0 - (i / 7.0)
        countdown_label.setAlphaValue_(alpha)
        until = NSDate.dateWithTimeIntervalSinceNow_(0.1)
        NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

# Fade in window
win.makeKeyAndOrderFront_(app)
fade_in(win, 0.3)

# Play start sound
play_sound("Glass")

# Animation complete - now read commands from stdin
import json
import sys

countdown_value = 3

while True:
    line = sys.stdin.readline()
    if not line:
        break

    try:
        cmd = json.loads(line.strip())
        action = cmd.get('action')
        data = cmd.get('data', {})

        if action == 'update':
            face_detected = data.get('face_detected', False)
            samples = data.get('samples', 0)
            elapsed = data.get('elapsed', 0)
            duration = data.get('duration', 3)

            if face_detected:
                face_label.setTextColor_(SUCCESS_COLOR)
                face_label.setStringValue_("面部: 已检测 ✓")
            else:
                face_label.setTextColor_(ERROR_COLOR)
                face_label.setStringValue_("面部: 未检测 ✗")

            sample_label.setStringValue_(f"采样: {samples}/~{int(duration * 30)}")

            progress = min(100, (elapsed / duration) * 100)
            progress_bar.setDoubleValue_(progress)

        elif action == 'countdown':
            val = data.get('value', 0)
            if val > 0:
                countdown_label.setStringValue_(str(val))
                countdown_label.setAlphaValue_(1.0)
                countdown_label.setFont_(bold_font(96))
                beep()
                animate_countdown(val)
            else:
                fade_out(countdown_label)

        elif action == 'start_collection':
            countdown_label.setStringValue_("")
            instruction_label.setStringValue_("保持姿势...")

        elif action == 'complete':
            success = data.get('success', False)
            sample_count = data.get('sample_count', 0)
            stddev = data.get('stddev', 0)

            fade_out(progress_bar)

            if success:
                if stddev < 0.005:
                    quality = "优秀"
                    quality_color = SUCCESS_COLOR
                elif stddev < 0.010:
                    quality = "良好"
                    quality_color = SUCCESS_COLOR
                elif stddev < 0.020:
                    quality = "一般"
                    quality_color = WARNING_COLOR
                else:
                    quality = "不稳定"
                    quality_color = ERROR_COLOR

                result_icon.setStringValue_("OK")
                result_icon.setTextColor_(SUCCESS_COLOR)
                result_icon.setHidden_(False)
                fade_in(result_icon, 0.3)

                quality_label.setStringValue_(f"精度: ±{stddev:.4f} ({quality})")
                quality_label.setTextColor_(quality_color)
                quality_label.setHidden_(False)
                fade_in(quality_label, 0.2)

                instruction_label.setStringValue_(f"校准成功 ({sample_count} 样本)")
                play_sound("Glass")

                done_btn.setHidden_(False)
                fade_in(done_btn, 0.2)
            else:
                result_icon.setStringValue_("X")
                result_icon.setTextColor_(ERROR_COLOR)
                result_icon.setHidden_(False)
                fade_in(result_icon, 0.3)

                error = data.get('error', '未知错误')
                instruction_label.setStringValue_(f"校准失败: {error}")
                play_sound("Basso")

                retry_btn.setHidden_(False)
                fade_in(retry_btn, 0.2)

        elif action == 'close':
            break

    except json.JSONDecodeError:
        pass
    except Exception as e:
        pass

# Fade out and close
fade_out(win, 0.2)
win.close()
'''


class CalibrationWindow:
    """浮动校准窗口"""

    def __init__(self, head_tracker, duration: float = 3.0):
        self.head_tracker = head_tracker
        self.duration = duration
        self._process = None
        self._running = False
        self._result_callback = None

    def show(self, on_result=None):
        """显示校准窗口并开始校准"""
        self._result_callback = on_result
        self._running = True

        # 启动 UI 进程
        self._process = subprocess.Popen(
            [sys.executable, '-c', _CALIBRATION_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

        # 启动校准
        self.head_tracker.start_calibration(self.duration)

        # 启动更新线程
        self._update_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._update_thread.start()

    def _poll_loop(self):
        """轮询校准进度并更新 UI"""
        countdown_value = 4

        while self._running:
            # 检查子进程是否还活着
            if self._process and self._process.poll() is not None:
                # 子进程已退出（用户关闭了窗口）
                self._running = False
                # 即使校准未完成，也停止它
                if self.head_tracker._calibrating:
                    result = self.head_tracker.stop_calibration()
                else:
                    result = {"success": False, "error": "用户取消"}
                if self._result_callback:
                    threading.Thread(target=self._result_callback, args=[result], daemon=True).start()
                break

            progress = self.head_tracker.get_calibration_progress()

            # 检查校准时间是否到期
            if self.head_tracker.is_calibration_done():
                result = self.head_tracker.stop_calibration()
                self._send({'action': 'complete', 'data': result})
                self._running = False
                if self._result_callback:
                    # 在 daemon 线程直接调用回调（非阻塞操作）
                    threading.Thread(target=self._result_callback, args=[result], daemon=True).start()
                break

            if not progress['calibrating'] and progress['samples'] > 0:
                # 校准完成（已调用 stop）
                result = self.head_tracker.stop_calibration()
                self._send({'action': 'complete', 'data': result})
                self._running = False
                if self._result_callback:
                    threading.Thread(target=self._result_callback, args=[result], daemon=True).start()
                break

            # 发送更新
            if not self._send({
                'action': 'update',
                'data': {
                    'face_detected': progress.get('face_detected', False),
                    'samples': progress.get('samples', 0),
                    'elapsed': progress.get('elapsed', 0),
                    'duration': self.duration,
                }
            }):
                self._running = False
                break

            # 倒计时逻辑
            elapsed = progress.get('elapsed', 0)
            new_countdown = int(self.duration - elapsed)

            if new_countdown != countdown_value and 1 <= new_countdown <= 3:
                countdown_value = new_countdown
                if not self._send({'action': 'countdown', 'data': {'value': countdown_value}}):
                    self._running = False
                    break
                if countdown_value == 3:
                    if not self._send({'action': 'start_collection', 'data': {}}):
                        self._running = False
                        break

            time.sleep(0.05)  # 20Hz 更新率

    def _send(self, msg):
        """发送消息到 UI 进程"""
        if self._process and self._process.stdin:
            try:
                line = json.dumps(msg) + '\n'
                self._process.stdin.write(line.encode())
                self._process.stdin.flush()
                return True
            except Exception:
                return False
        return False

    def close(self):
        """关闭窗口"""
        self._running = False
        try:
            self._send({'action': 'close', 'data': {}})
        except Exception:
            pass
        if self._process:
            self._process.terminate()
            self._process = None