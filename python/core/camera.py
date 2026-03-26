"""
EyeScroll 摄像头模块
使用 OpenCV 捕获视频流
"""
import cv2
import numpy as np
from typing import Optional


class Camera:
    """摄像头捕获封装"""

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self._cap: Optional[cv2.VideoCapture] = None
        self._open()

    def _open(self):
        """打开摄像头"""
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError("无法打开摄像头，请检查是否被其他应用占用")

        # 设置分辨率
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        # 设置帧率
        self._cap.set(cv2.CAP_PROP_FPS, 30)

    def read(self) -> Optional[np.ndarray]:
        """
        读取一帧

        Returns:
            numpy.ndarray: RGB 格式的图像数组，失败返回 None
        """
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame = self._cap.read()
        if not ret:
            return None

        # 转换为 RGB 格式（OpenCV 默认 BGR）
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame_rgb

    def release(self):
        """释放摄像头资源"""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
