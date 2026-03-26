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

        gaze_x = (left_iris.x + right_iris.x) / 2
        gaze_y = (left_iris.y + right_iris.y) / 2

        return (float(gaze_x), float(gaze_y))

    def close(self):
        """关闭追踪器"""
        self._detector.close()
