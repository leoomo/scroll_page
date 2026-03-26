"""
EyeScroll 头部姿态追踪

Uses MediaPipe Face Mesh to extract head pose from multiple keypoints
(nose tip, chin, forehead) with weighted combination, EMA smoothing,
and spike rejection for robust signal extraction.
"""
import time
import statistics
from pathlib import Path
from typing import Optional, Tuple

import mediapipe as mp
import numpy as np

# MediaPipe Face Mesh landmark indices
NOSE_TIP = 1
FOREHEAD = 10
CHIN = 152

# Weights for weighted head pose
WEIGHTS = {
    NOSE_TIP: 0.5,
    CHIN: 0.3,
    FOREHEAD: 0.2,
}

# Key indices list
KEY_INDICES = [NOSE_TIP, FOREHEAD, CHIN]

# Default model path
MODEL_PATH = Path(__file__).parent.parent / ".models" / "face_landmarker.task"


class HeadTracker:
    def __init__(
        self,
        model_path: str | None = None,
        confidence_threshold: float = 0.5,
        ema_alpha: float = 0.15,
        down_threshold: float = 0.03,
        up_threshold: float = -0.03,
    ):
        if model_path is None:
            model_path = str(MODEL_PATH)

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=confidence_threshold,
            min_face_presence_confidence=confidence_threshold,
            min_tracking_confidence=confidence_threshold,
        )
        self._detector = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self._frame_timestamp_ms = 0

        # Calibration state
        self._neutral_y: float | None = None
        self._calibrated = False

        # Smoothing
        self._ema_alpha = ema_alpha
        self._smooth_offset = 0.0

        # Thresholds (used for spike rejection)
        self._down_threshold = down_threshold
        self._up_threshold = up_threshold

        # Calibration sample collection
        self._calibrating = False
        self._calibration_samples: list[float] = []
        self._calibration_start_time: float = 0.0
        self._calibration_duration: float = 3.0

    def process(self, frame: np.ndarray) -> Tuple[float, float] | None:
        """Process a frame, return (smooth_offset_x, smooth_offset_y) or None if no face."""
        self._frame_timestamp_ms += 33

        rgb_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._detector.detect_for_video(rgb_frame, self._frame_timestamp_ms)

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return None

        landmarks = result.face_landmarks[0]
        head_y = self._compute_head_y(landmarks)

        # During calibration, collect samples instead of computing offset
        if self._calibrating:
            self._calibration_samples.append(head_y)
            return None

        if not self._calibrated:
            return None

        raw_offset = self._compute_offset(head_y)

        # Spike rejection
        if self._is_spike(raw_offset):
            return (0.0, self._smooth_offset)

        self._smooth_offset = self._apply_ema(self._smooth_offset, raw_offset)
        return (0.0, self._smooth_offset)

    def _compute_head_y(self, landmarks) -> float:
        """Compute weighted head Y from key landmarks."""
        head_y = 0.0
        for idx in KEY_INDICES:
            head_y += WEIGHTS[idx] * landmarks[idx].y
        return head_y

    def _compute_offset(self, head_y: float) -> float:
        """Compute offset from neutral point. Positive = tilting down, negative = tilting up."""
        return head_y - self._neutral_y

    def _apply_ema(self, old: float, new: float) -> float:
        """Apply exponential moving average smoothing."""
        return self._ema_alpha * new + (1 - self._ema_alpha) * old

    def _is_spike(self, offset: float) -> bool:
        """Reject single-frame spikes that exceed 3x the threshold."""
        max_threshold = max(abs(self._down_threshold), abs(self._up_threshold))
        return abs(offset) > 3 * max_threshold

    def start_calibration(self, duration_seconds: float = 3.0) -> None:
        """Start collecting samples for neutral point calibration."""
        self._calibrating = True
        self._calibration_samples = []
        self._calibration_start_time = time.monotonic()
        self._calibration_duration = duration_seconds

    def stop_calibration(self) -> dict:
        """Stop calibration, compute neutral point. Returns result dict."""
        self._calibrating = False
        if len(self._calibration_samples) < 10:
            return {"success": False, "error": "Too few samples"}

        neutral_y = statistics.median(self._calibration_samples)
        stddev = statistics.stdev(self._calibration_samples)

        self._neutral_y = neutral_y
        self._calibrated = True
        self._smooth_offset = 0.0

        return {
            "success": True,
            "neutral_y": neutral_y,
            "sample_count": len(self._calibration_samples),
            "stddev": stddev,
        }

    def is_calibration_done(self) -> bool:
        """Check if calibration collection period has elapsed."""
        if not self._calibrating:
            return False
        return (time.monotonic() - self._calibration_start_time) >= self._calibration_duration

    def is_calibrated(self) -> bool:
        return self._calibrated

    def get_neutral_y(self) -> float | None:
        return self._neutral_y

    def reset_calibration(self) -> None:
        self._neutral_y = None
        self._calibrated = False
        self._smooth_offset = 0.0

    def close(self) -> None:
        self._detector.close()
