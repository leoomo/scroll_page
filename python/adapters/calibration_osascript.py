"""
HeadScroll 校准 - osascript 简单实现
使用 AppleScript 显示进度对话框，最可靠
"""
import subprocess
import threading
import time
from typing import Callable, Optional


def run_calibration(head_tracker, duration: float = 3.0,
                    on_complete: Optional[Callable[[dict], None]] = None) -> None:
    """
    运行校准流程，使用 AppleScript 显示进度

    Args:
        head_tracker: HeadTracker 实例
        duration: 校准持续时间（秒）
        on_complete: 完成回调
    """
    # 启动校准
    head_tracker.start_calibration(duration)

    # 显示开始提示
    _show_alert("HeadScroll 校准", "请将头部保持在中立位置\n校准将在 3 秒后开始...")

    # 等待倒计时
    for i in range(3, 0, -1):
        time.sleep(1)
        # 播放提示音
        subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"],
                      capture_output=True)

    # 显示进度条
    _show_progress_dialog(head_tracker, duration, on_complete)


def _show_alert(title: str, message: str) -> None:
    """显示警告对话框"""
    script = f'''
    display dialog "{message}" \
        with title "{title}" \
        buttons {{"开始"}} \
        default button "开始"
    '''
    subprocess.run(["osascript", "-e", script],
                  capture_output=True)


def _show_progress_dialog(head_tracker, duration: float,
                         on_complete: Optional[Callable[[dict], None]]) -> None:
    """显示进度对话框并轮询"""
    # 创建进度 AppleScript
    script = f'''
    set progress total steps to {int(duration * 10)}
    set progress completed steps to 0
    set progress description to "校准中..."
    set progress additional description to "请保持头部稳定"

    repeat with i from 1 to {int(duration * 10)}
        delay 0.1
        set progress completed steps to i
    end repeat

    display notification "HeadScroll 校准完成" with title "HeadScroll"
    '''

    # 在后台运行 AppleScript
    def run_script():
        result = subprocess.run(["osascript", "-e", script],
                              capture_output=True, text=True)

        # 停止校准并获取结果
        cal_result = head_tracker.stop_calibration()

        # 显示结果
        if cal_result.get("success"):
            msg = f"校准成功！\\n样本数: {cal_result.get('sample_count', 0)}"
            _show_result_dialog("HeadScroll 校准完成", msg, "确定")
        else:
            msg = f"校准失败: {cal_result.get('error', '未知错误')}"
            _show_result_dialog("HeadScroll 校准失败", msg, "重试")

        # 回调
        if on_complete:
            on_complete(cal_result)

    threading.Thread(target=run_script, daemon=True).start()


def _show_result_dialog(title: str, message: str, button: str) -> None:
    """显示结果对话框"""
    script = f'''
    display dialog "{message}" \
        with title "{title}" \
        buttons {{"{button}"}} \
        default button "{button}"
    '''
    subprocess.run(["osascript", "-e", script],
                  capture_output=True)


def show_calibration_dialog(head_tracker, duration: float = 3.0,
                           on_complete: Optional[Callable[[dict], None]] = None):
    """兼容原有接口"""
    run_calibration(head_tracker, duration, on_complete)
