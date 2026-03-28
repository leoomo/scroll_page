"""
HeadScroll 校准窗口 - PySide6 实现（使用 multiprocessing 隔离 Qt）
"""
import sys
import time
import multiprocessing
import threading
from pathlib import Path
from typing import Callable, Optional


def _calibration_process_main(result_queue: multiprocessing.Queue, duration: float) -> None:
    """
    校准进程入口函数
    在独立进程中运行 Qt GUI，避免与 rumps 冲突
    """
    # 在这个进程中配置日志
    import logging
    log_file = Path.home() / ".eye_scroll" / "calibration_process.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file, mode='w')]
    )
    logger = logging.getLogger('CalibrationProcess')

    logger.info(f"Calibration process started, duration={duration}")

    try:
        from PySide6.QtCore import (
            QThread, Signal, Slot, Qt, QObject
        )
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import (
            QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
            QPushButton, QProgressBar, QGraphicsDropShadowEffect
        )

        class Worker(QObject):
            """工作线程 - 校准倒计时（纯计时，校准数据由主进程 head_tracker 采集）"""
            progress_updated = Signal(dict)
            countdown_tick = Signal(int)
            calibration_complete = Signal(dict)

            def __init__(self, duration: float) -> None:
                super().__init__()
                self.duration = duration
                self._running = True
                self._countdown_value = 4

            def start(self) -> None:
                """倒计时循环"""
                start_time = time.monotonic()

                while self._running:
                    elapsed = time.monotonic() - start_time

                    if elapsed >= self.duration:
                        self.calibration_complete.emit({"success": True})
                        break

                    self.progress_updated.emit({
                        'elapsed': elapsed,
                        'duration': self.duration,
                    })

                    new_countdown = int(self.duration - elapsed)
                    if new_countdown != self._countdown_value and 1 <= new_countdown <= 3:
                        self._countdown_value = new_countdown
                        self.countdown_tick.emit(new_countdown)

                    time.sleep(0.05)

            def stop(self) -> None:
                self._running = False

        class Dialog(QWidget):
            """校准对话框"""
            closed = Signal()

            def __init__(self, duration: float) -> None:
                super().__init__()
                self.duration = duration
                self.worker: Optional[Worker] = None
                self.worker_thread: Optional[QThread] = None
                self._result: Optional[dict] = None

                self._init_ui()
                self._setup_window()
                self._apply_styles()

            def _init_ui(self) -> None:
                layout = QVBoxLayout()
                layout.setSpacing(12)
                layout.setContentsMargins(24, 20, 24, 16)

                self.title_label = QLabel("HeadScroll")
                self.title_label.setAlignment(Qt.AlignCenter)
                self.title_label.setObjectName("title")
                layout.addWidget(self.title_label)

                self.status_label = QLabel("准备校准...")
                self.status_label.setAlignment(Qt.AlignCenter)
                self.status_label.setObjectName("status")
                layout.addWidget(self.status_label)

                self.countdown_label = QLabel("")
                self.countdown_label.setAlignment(Qt.AlignCenter)
                self.countdown_label.setObjectName("countdown")
                layout.addWidget(self.countdown_label)

                self.progress_bar = QProgressBar()
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)
                self.progress_bar.setTextVisible(False)
                self.progress_bar.setFixedHeight(6)
                layout.addWidget(self.progress_bar)

                self.face_status = QLabel("未检测到面部")
                self.face_status.setAlignment(Qt.AlignCenter)
                self.face_status.setObjectName("faceStatus")
                layout.addWidget(self.face_status)

                self.result_icon = QLabel("")
                self.result_icon.setAlignment(Qt.AlignCenter)
                self.result_icon.setObjectName("resultIcon")
                self.result_icon.hide()
                layout.addWidget(self.result_icon)

                button_layout = QHBoxLayout()

                self.cancel_btn = QPushButton("取消")
                self.cancel_btn.clicked.connect(self._on_cancel)
                button_layout.addWidget(self.cancel_btn)

                self.done_btn = QPushButton("完成")
                self.done_btn.clicked.connect(self._on_done)
                self.done_btn.hide()
                button_layout.addWidget(self.done_btn)

                self.retry_btn = QPushButton("重试")
                self.retry_btn.clicked.connect(self._on_retry)
                self.retry_btn.hide()
                button_layout.addWidget(self.retry_btn)

                layout.addLayout(button_layout)
                self.setLayout(layout)

            def _setup_window(self) -> None:
                self.setWindowFlags(
                    Qt.FramelessWindowHint |
                    Qt.WindowStaysOnTopHint |
                    Qt.Tool
                )
                self.setFixedSize(340, 280)

                # 居中
                screen = QApplication.primaryScreen()
                if screen:
                    center = screen.geometry().center()
                    self.move(center.x() - self.width() // 2,
                             center.y() - self.height() // 2)

                # 阴影
                shadow = QGraphicsDropShadowEffect(self)
                shadow.setBlurRadius(20)
                shadow.setColor(QColor(0, 0, 0, 80))
                shadow.setOffset(0, 4)
                self.setGraphicsEffect(shadow)

            def _apply_styles(self) -> None:
                self.setStyleSheet("""
                    QWidget { background-color: #1e1e1e; color: #ffffff; }
                    QLabel#title { font-size: 16px; font-weight: 600; }
                    QLabel#status { font-size: 13px; color: #a0a0a0; }
                    QLabel#countdown { font-size: 72px; font-weight: bold; color: #4fc3f7; min-height: 80px; }
                    QLabel#faceStatus { font-size: 12px; color: #888888; }
                    QLabel#resultIcon { font-size: 48px; font-weight: bold; min-height: 60px; }
                    QProgressBar { background-color: #333333; border-radius: 3px; }
                    QProgressBar::chunk { background-color: #4fc3f7; border-radius: 3px; }
                    QPushButton { background-color: #3d3d3d; color: #ffffff; border: none;
                                 border-radius: 6px; padding: 8px 16px; font-size: 13px; min-width: 80px; }
                    QPushButton:hover { background-color: #4d4d4d; }
                """)

            def start_calibration(self) -> None:
                """启动校准"""
                self.worker = Worker(self.duration)
                self.worker_thread = QThread()
                self.worker.moveToThread(self.worker_thread)

                self.worker.progress_updated.connect(self._on_progress)
                self.worker.countdown_tick.connect(self._on_countdown)
                self.worker.calibration_complete.connect(self._on_complete)

                self.worker_thread.started.connect(self.worker.start)
                self.worker_thread.start()

            def _on_progress(self, data: dict) -> None:
                elapsed = data.get('elapsed', 0)
                duration = data.get('duration', 3.0)
                progress = min(100, int((elapsed / duration) * 100))
                self.progress_bar.setValue(progress)
                self.face_status.setText("保持头部不动...")

            def _on_countdown(self, value: int) -> None:
                self.countdown_label.setText(str(value))
                self.status_label.setText("开始校准...")
                QApplication.beep()

            def _on_complete(self, result: dict) -> None:
                self._result = result

                self.progress_bar.hide()
                self.face_status.hide()
                self.countdown_label.hide()
                self.cancel_btn.hide()

                self.status_label.setText("校准完成")
                self.result_icon.setText("✓")
                self.result_icon.setStyleSheet("color: #4caf50;")
                self.result_icon.show()
                self.done_btn.show()

            def _on_cancel(self) -> None:
                self._cleanup()
                self._result = {"success": False, "error": "用户取消"}
                self.closed.emit()
                self.close()

            def _on_done(self) -> None:
                self.closed.emit()
                self.close()

            def _on_retry(self) -> None:
                self._cleanup()
                self.progress_bar.show()
                self.progress_bar.setValue(0)
                self.face_status.show()
                self.countdown_label.show()
                self.cancel_btn.show()
                self.result_icon.hide()
                self.retry_btn.hide()
                self.done_btn.hide()
                self.status_label.setText("准备校准...")
                self.countdown_label.setText("")
                self.start_calibration()

            def _cleanup(self) -> None:
                if self.worker:
                    self.worker.stop()
                if self.worker_thread:
                    self.worker_thread.quit()
                    self.worker_thread.wait(2000)

            def closeEvent(self, event) -> None:
                self._cleanup()
                self.closed.emit()
                event.accept()

            def get_result(self) -> Optional[dict]:
                return self._result

        # 创建 QApplication 并运行
        app = QApplication.instance() or QApplication(sys.argv[:1])

        dialog = Dialog(duration)

        def on_closed():
            result = dialog.get_result()
            result_queue.put(result or {"success": False, "error": "未完成"})
            app.quit()

        dialog.closed.connect(on_closed)
        dialog.show()
        dialog.start_calibration()

        logger.info("Starting QApplication.exec()")
        app.exec()
        logger.info("QApplication.exec() returned")

    except Exception as e:
        logger.exception("Error in calibration process")
        result_queue.put({"success": False, "error": str(e)})


class CalibrationManager:
    """
    校准管理器 - 使用 multiprocessing 隔离 Qt GUI
    """

    def __init__(self) -> None:
        self._process: Optional[multiprocessing.Process] = None
        self._result_queue: Optional[multiprocessing.Queue] = None
        self._callback: Optional[Callable[[dict], None]] = None
        self._monitor_thread: Optional[threading.Thread] = None

    def show(self, head_tracker, duration: float = 3.0,
             on_complete: Optional[Callable[[dict], None]] = None) -> None:
        """
        显示校准对话框

        Args:
            head_tracker: HeadTracker 实例（当前未使用，预留接口）
            duration: 校准持续时间
            on_complete: 完成回调
        """
        self._callback = on_complete

        # 创建队列用于进程间通信
        self._result_queue = multiprocessing.Queue()

        # 启动独立进程运行 Qt GUI
        self._process = multiprocessing.Process(
            target=_calibration_process_main,
            args=(self._result_queue, duration),
            daemon=False  # 非 daemon 进程，确保 GUI 正常显示
        )
        self._process.start()

        # 启动监控线程等待结果
        self._monitor_thread = threading.Thread(target=self._wait_for_result, daemon=True)
        self._monitor_thread.start()

    def _wait_for_result(self) -> None:
        """等待校准进程返回结果"""
        try:
            # 最多等待60秒
            result = self._result_queue.get(timeout=60)

            if self._callback:
                self._callback(result)

        except Exception as e:
            if self._callback:
                self._callback({"success": False, "error": str(e)})

        finally:
            # 清理进程
            if self._process and self._process.is_alive():
                self._process.join(timeout=2)
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=1)


def show_calibration_dialog(head_tracker, duration: float = 3.0,
                           on_complete: Optional[Callable[[dict], None]] = None):
    """
    显示校准对话框

    使用示例:
        show_calibration_dialog(
            head_tracker,
            duration=3.0,
            on_complete=lambda result: print(f"Result: {result}")
        )
    """
    manager = CalibrationManager()
    manager.show(head_tracker, duration, on_complete)
    return manager
