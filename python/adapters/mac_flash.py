"""
macOS 全屏 Flash 通知
通过子进程创建透明置顶窗口，在任何应用上方显示消息
"""
import subprocess
import sys


_FLASH_SCRIPT = '''
import sys, time
from AppKit import NSApplication, NSWindow, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, NSColor, NSScreen, NSTextField, NSFloatingWindowLevel, NSFont
from Foundation import NSMakeRect, NSDate, NSRunLoop, NSDefaultRunLoopMode

app = NSApplication.sharedApplication()
screen = NSScreen.mainScreen()
frame = screen.frame()

text = sys.argv[1]
w = max(280, len(text) * 18 + 60)
h = 64
x = (frame.size.width - w) / 2
y = (frame.size.height - h) / 2

window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    NSMakeRect(x, y, w, h),
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    False,
)
window.setLevel_(NSFloatingWindowLevel)
window.setBackgroundColor_(NSColor.clearColor())
window.setOpaque_(False)
window.setHasShadow_(True)
window.setAlphaValue_(0.0)

label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
label.setEditable_(False)
label.setSelectable_(False)
label.setBezeled_(False)
label.setDrawsBackground_(False)
label.setAlignment_(1)
label.setStringValue_(text)
label.setTextColor_(NSColor.whiteColor())
label.setFont_(NSFont.systemFontOfSize_weight_(22, 0))

window.setContentView_(label)
window.orderFrontRegardless()

until = NSDate.dateWithTimeIntervalSinceNow_(0.05)
NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

for i in range(5):
    window.setAlphaValue_((i + 1) / 5 * 0.92)
    until = NSDate.dateWithTimeIntervalSinceNow_(0.04)
    NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

until = NSDate.dateWithTimeIntervalSinceNow_(0.6)
NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

for i in range(5):
    window.setAlphaValue_(0.92 * (5 - i) / 5)
    until = NSDate.dateWithTimeIntervalSinceNow_(0.05)
    NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, until)

window.close()
'''


def show_flash(text: str):
    """在屏幕正中显示 flash 消息（非阻塞）"""
    subprocess.Popen(
        [sys.executable, '-c', _FLASH_SCRIPT, text],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
