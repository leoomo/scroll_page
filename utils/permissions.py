"""
EyeScroll 权限检查模块
检查摄像头权限和辅助功能权限
"""
import subprocess


def check_camera_permission() -> bool:
    """检查摄像头权限"""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.release()
            return True
        return False
    except Exception:
        return False


def check_accessibility_permission() -> bool:
    """检查辅助功能权限"""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to return UI elements enabled'
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    except Exception:
        return False


def request_camera_permission():
    """请求摄像头权限 - 引导用户到系统设置"""
    subprocess.run(
        ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"],
        check=False,
    )


def request_accessibility_permission():
    """请求辅助功能权限 - 引导用户到系统设置"""
    subprocess.run(
        ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
        check=False,
    )


def check_all_permissions() -> dict:
    """检查所有必需权限"""
    return {
        "camera": check_camera_permission(),
        "accessibility": check_accessibility_permission(),
    }
