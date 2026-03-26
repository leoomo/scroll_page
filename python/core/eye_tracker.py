"""
EyeScroll 头部姿态追踪
"""
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


NOSE_TIP = 1
LEFT_IRIS_INDEX = 468
RIGHT_IRIS_INDEX = 473

MODEL_DIR = Path(__file__).parent.parent / ".models"
MODEL_PATH = MODEL_DIR / "face_landmarker.task"


def _get_model_path() -> str:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return str(MODEL_PATH)


class EyeTracker:
    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self._frame_timestamp = 0

        base_options = python.BaseOptions(model_asset_path=_get_model_path())
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
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._detector.detect_for_video(mp_image, self._frame_timestamp)
        self._frame_timestamp += 33

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return None

        face_landmarks = result.face_landmarks[0]
        nose_y = face_landmarks[NOSE_TIP].y

        return (0.0, nose_y)

    def is_calibrated(self) -> bool:
        return True

    def reset_calibration(self):
        pass

    def get_last_offset_y(self) -> Optional[float]:
        return None

    def close(self):
        self._detector.close()
