"""
EyeScroll HeadTracker 测试
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.head_tracker import HeadTracker
import numpy as np


def _make_landmarks(nose_y, chin_y, forehead_y):
    """Build a minimal fake landmark set with only the 3 points we need.
    MediaPipe landmarks are objects with .x, .y, .z attributes."""
    class LM:
        def __init__(self, x, y, z=0.0):
            self.x, self.y, self.z = x, y, z
    landmarks = [LM(0, 0)] * 478  # 478 total landmarks
    landmarks[1] = LM(0.5, nose_y)      # nose tip
    landmarks[10] = LM(0.5, forehead_y)  # forehead
    landmarks[152] = LM(0.5, chin_y)     # chin
    return landmarks


def test_weighted_head_y_calculation():
    """nose*0.5 + chin*0.3 + forehead*0.2"""
    tracker = HeadTracker()
    landmarks = _make_landmarks(nose_y=0.6, chin_y=0.8, forehead_y=0.4)
    result = tracker._compute_head_y(landmarks)
    # 0.6*0.5 + 0.8*0.3 + 0.4*0.2 = 0.30 + 0.24 + 0.08 = 0.62
    assert abs(result - 0.62) < 1e-6


def test_returns_none_when_no_face():
    tracker = HeadTracker()
    result = tracker.process(np.zeros((480, 640, 3), dtype=np.uint8))
    assert result is None


def test_returns_offset_after_calibration():
    """After calibration, process() returns (0.0, smooth_offset_y)."""
    tracker = HeadTracker()
    tracker._neutral_y = 0.5
    tracker._smooth_offset = 0.0
    tracker._calibrated = True
    # We can't easily mock MediaPipe here, so test _compute_offset directly
    offset = tracker._compute_offset(0.55)
    assert abs(offset - 0.05) < 1e-6  # 0.55 - 0.5 = 0.05


def test_ema_smoothing():
    """EMA with alpha=0.15: new values gradually pull the average."""
    tracker = HeadTracker()
    tracker._neutral_y = 0.5
    tracker._calibrated = True
    tracker._ema_alpha = 0.15
    tracker._smooth_offset = 0.0
    # Process several identical offsets
    for _ in range(50):
        tracker._smooth_offset = tracker._apply_ema(tracker._smooth_offset, 0.1)
    # After many iterations, smooth should approach 0.1
    assert abs(tracker._smooth_offset - 0.1) < 0.01


def test_spike_rejection():
    """Offset > 3x threshold should be discarded."""
    tracker = HeadTracker()
    tracker._down_threshold = 0.03
    tracker._up_threshold = -0.03
    assert tracker._is_spike(0.15) is True   # 0.15 > 3*0.03
    assert tracker._is_spike(-0.15) is True  # abs(-0.15) > 3*0.03
    assert tracker._is_spike(0.05) is False  # 0.05 < 3*0.03


def test_is_calibrated_false_by_default():
    tracker = HeadTracker()
    assert tracker.is_calibrated() is False


def test_neutral_y_none_before_calibration():
    tracker = HeadTracker()
    assert tracker.get_neutral_y() is None
