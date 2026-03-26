"""
跨平台滚动适配器
"""
import sys

if sys.platform == "darwin":
    from .mac_scroll import MacScrollController as ScrollControllerImpl
elif sys.platform == "win32":
    from .win_scroll import WinScrollController as ScrollControllerImpl
else:
    raise NotImplementedError(f"Unsupported platform: {sys.platform}")
