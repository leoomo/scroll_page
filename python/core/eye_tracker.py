"""
EyeScroll 眼球追踪模块
使用 MediaPipe Face Mesh 检测虹膜位置
"""
from pathlib import Path
import numpy as np
from typing import Optional, Tuple
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


LEFT_IRIS_INDEX = 468
RIGHT_IRIS_INDEX = 473

MODEL_DIR = Path(__file__).parent.parent / ".models"
MODEL_PATH = MODEL_DIR / "face_landmarker.task"


def _get_model_path() -> str:
    """获取模型文件路径"""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return str(MODEL_PATH)


class EyeTracker:
    """眼球追踪器"""

    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self._frame_timestamp = 0

        # 校准参数
        self._calibrated = False
        self._top_gaze_y = None   # 看屏幕顶部时的 y 值
        self._bottom_gaze_y = None # 看屏幕底部时的 y 值

        base_options = python.BaseOptions(
            model_asset_path=_get_model_path()
        )
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=confidence_threshold,
            min_face_presence_confidence=confidence_threshold,
            min_tracking_confidence=confidence_threshold,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)

    def calibrate_top(self, gaze_y: float):
        """校准顶部（看向摄像头）"""
        self._top_gaze_y = gaze_y
        print(f"[校准] 顶部 gaze_y = {gaze_y:.3f}")
        self._check_calibration()

    def calibrate_bottom(self, gaze_y: float):
        """校准底部（看向屏幕底部）"""
        self._bottom_gaze_y = gaze_y
        print(f"[校准] 底部 gaze_y = {gaze_y:.3f}")
        self._check_calibration()

    def _check_calibration(self):
        """检查校准是否完成"""
        if self._top_gaze_y is not None and self._bottom_gaze_y is not None:
            self._calibrated = True
            print(f"[校准] 完成! top={self._top_gaze_y:.3f}, bottom={self._bottom_gaze_y:.3f}")

    def is_calibrated(self) -> bool:
        return self._calibrated

    def reset_calibration(self):
        """重置校准"""
        self._calibrated = False
        self._top_gaze_y = None
        self._bottom_gaze_y = None
        print("[校准] 已重置")

    def process(self, frame: np.ndarray) -> Optional[Tuple[float, float]]:
        """处理一帧图像，检测视线位置"""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._detector.detect_for_video(mp_image, self._frame_timestamp)
        self._frame_timestamp += 33  # ~30fps

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return None

        face_landmarks = result.face_landmarks[0]
        left_iris = face_landmarks[LEFT_IRIS_INDEX]
        right_iris = face_landmarks[RIGHT_IRIS_INDEX]

        self._last_raw_x = (left_iris.x + right_iris.x) / 2
        self._last_raw_y = (left_iris.y + right_iris.y) / 2

        # 应用校准转换
        if self._calibrated and self._bottom_gaze_y != self._top_gaze_y:
            # 将 gaze_y 从 [top_gaze, bottom_gaze] 映射到 [0, 1]
            # gaze_y 越小 = 看屏幕上方
            screen_y = (self._last_raw_y - self._top_gaze_y) / (self._bottom_gaze_y - self._top_gaze_y)
            screen_y = max(0.0, min(1.0, screen_y))  # 限制在 [0, 1]
            return (float(self._last_raw_x), float(screen_y))

        return (float(self._last_raw_x), float(self._last_raw_y))

    def get_last_raw_y(self) -> Optional[float]:
        """获取上一次处理的原始 y 值（用于校准）"""
        return getattr(self, '_last_raw_y', None)

    def close(self):
        """关闭追踪器"""
        self._detector.close()
