# Head Pose Scrolling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace iris-based eye tracking with multi-keypoint weighted head pose control for stable, hands-free scrolling.

**Architecture:** MediaPipe Face Mesh extracts 3 facial landmark Y-coordinates (nose, chin, forehead), weighted combination produces a `head_y` signal. EMA smoothing filters jitter. A 5-state machine implements progressive control: short dwell triggers single scroll, long dwell (>2s) switches to continuous scrolling. Neutral-point calibration (3s median) makes the system user-adaptive.

**Tech Stack:** Python 3.13, MediaPipe Face Landmarker, OpenCV, asyncio HTTP server, vanilla JS frontend, Tauri 2 (Rust shell)

**Spec:** `docs/superpowers/specs/2026-03-26-head-pose-scrolling-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `python/core/head_tracker.py` | Create | Multi-keypoint weighted head pose extraction, EMA smoothing, neutral calibration |
| `python/core/head_state.py` | Create | 5-state machine with progressive control (single → continuous) |
| `python/core/eye_tracker.py` | Delete | Replaced by head_tracker.py |
| `python/core/gaze_state.py` | Delete | Replaced by head_state.py |
| `python/main.py` | Modify | Tracking loop uses HeadTracker + HeadStateMachine; new calibration API |
| `python/config.py` | Modify | Add head pose config keys (thresholds, ema_alpha) |
| `python/tests/test_head_tracker.py` | Create | Tests for HeadTracker signal extraction, smoothing, calibration |
| `python/tests/test_head_state.py` | Create | Tests for HeadStateMachine state transitions |
| `python/tests/test_gaze_state.py` | Delete | Replaced by test_head_state.py |
| `src/web/index.html` | Modify | Minimal single-column layout with offset indicator |
| `src/web/main.js` | Modify | New calibration flow, offset visualization, updated API |
| `src/web/style.css` | Modify | Minimal design updates for new layout |
| `src-tauri/src/lib.rs` | Modify | Updated types and calibration commands |

---

### Task 1: HeadTracker — Signal Extraction

**Files:**
- Create: `python/core/head_tracker.py`
- Test: `python/tests/test_head_tracker.py`

- [ ] **Step 1: Write tests for head pose signal extraction**

```python
# python/tests/test_head_tracker.py
import sys
sys.path.insert(0, sys.path[0] + "/..")
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/test_head_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.head_tracker'`

- [ ] **Step 3: Implement HeadTracker signal extraction**

```python
# python/core/head_tracker.py
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
            model_path = str(Path(__file__).parent.parent / ".models" / "face_landmarker.task")

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/test_head_tracker.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/core/head_tracker.py python/tests/test_head_tracker.py
git commit -m "feat(core): add HeadTracker with multi-keypoint weighted pose extraction"
```

---

### Task 2: HeadStateMachine — Progressive Control

**Files:**
- Create: `python/core/head_state.py`
- Test: `python/tests/test_head_state.py`

- [ ] **Step 1: Write tests for the state machine**

```python
# python/tests/test_head_state.py
import sys
sys.path.insert(0, sys.path[0] + "/..")
from core.head_state import (
    HeadStateMachine,
    STATE_IDLE,
    STATE_DWELLING_DOWN,
    STATE_DWELLING_UP,
    STATE_CONTINUOUS_DOWN,
    STATE_CONTINUOUS_UP,
)
import time


def test_initial_state_is_idle():
    sm = HeadStateMachine()
    assert sm.get_state() == STATE_IDLE


def test_no_action_when_idle_and_small_offset():
    sm = HeadStateMachine(dwell_time_ms=300)
    result = sm.update(0.01)  # below threshold of 0.03
    assert result is None
    assert sm.get_state() == STATE_IDLE


def test_enter_dwell_down_on_large_offset():
    sm = HeadStateMachine(dwell_time_ms=300)
    sm.update(0.05)  # above down_threshold
    assert sm.get_state() == STATE_DWELLING_DOWN
    assert sm.update(0.05) is None  # no action yet


def test_single_scroll_down_on_return_to_neutral():
    """Dwell past dwell_time_ms then return to neutral → single scroll."""
    sm = HeadStateMachine(dwell_time_ms=100, down_threshold=0.03, deadzone=0.01)
    sm.update(0.05)  # enter DWELLING_DOWN
    time.sleep(0.15)  # exceed dwell_time_ms
    result = sm.update(0.005)  # return to neutral (within deadzone)
    assert result == "scroll_down"
    assert sm.get_state() == STATE_IDLE


def test_no_scroll_if_dwell_too_short():
    """Return to neutral before dwell_time_ms → no scroll."""
    sm = HeadStateMachine(dwell_time_ms=300, down_threshold=0.03, deadzone=0.01)
    sm.update(0.05)  # enter DWELLING_DOWN
    time.sleep(0.05)  # NOT enough dwell time
    result = sm.update(0.005)  # return to neutral
    assert result is None
    assert sm.get_state() == STATE_IDLE


def test_continuous_scroll_down_after_long_dwell():
    """Dwell past continuous_threshold_ms → auto switch to continuous."""
    sm = HeadStateMachine(
        dwell_time_ms=100,
        continuous_threshold_ms=200,
        down_threshold=0.03,
        scroll_interval_ms=50,
    )
    sm.update(0.05)  # enter DWELLING_DOWN
    time.sleep(0.25)  # exceed continuous threshold
    result = sm.update(0.05)
    assert result == "continuous_down"
    assert sm.get_state() == STATE_CONTINUOUS_DOWN


def test_continuous_down_keeps_scrolling():
    """Once in CONTINUOUS_DOWN, each update returns scroll action at interval."""
    sm = HeadStateMachine(
        dwell_time_ms=100,
        continuous_threshold_ms=200,
        down_threshold=0.03,
        scroll_interval_ms=50,
    )
    sm.update(0.05)
    time.sleep(0.25)
    sm.update(0.05)  # transition to continuous
    time.sleep(0.06)  # wait for scroll interval
    result = sm.update(0.05)
    assert result == "scroll_down"  # continuous mode emits discrete scrolls


def test_continuous_down_stops_on_neutral():
    """Return to neutral while in CONTINUOUS_DOWN → back to IDLE."""
    sm = HeadStateMachine(
        dwell_time_ms=100,
        continuous_threshold_ms=200,
        down_threshold=0.03,
        deadzone=0.01,
    )
    sm.update(0.05)
    time.sleep(0.25)
    sm.update(0.05)  # enter continuous
    result = sm.update(0.005)  # return to neutral
    assert result is None
    assert sm.get_state() == STATE_IDLE


def test_enter_dwell_up_on_negative_offset():
    sm = HeadStateMachine(dwell_time_ms=300, up_threshold=-0.03)
    sm.update(-0.05)
    assert sm.get_state() == STATE_DWELLING_UP


def test_single_scroll_up_on_return_to_neutral():
    sm = HeadStateMachine(dwell_time_ms=100, up_threshold=-0.03, deadzone=0.01)
    sm.update(-0.05)
    time.sleep(0.15)
    result = sm.update(0.005)
    assert result == "scroll_up"
    assert sm.get_state() == STATE_IDLE


def test_continuous_scroll_up():
    sm = HeadStateMachine(
        dwell_time_ms=100,
        continuous_threshold_ms=200,
        up_threshold=-0.03,
        scroll_interval_ms=50,
    )
    sm.update(-0.05)
    time.sleep(0.25)
    result = sm.update(-0.05)
    assert result == "continuous_up"
    assert sm.get_state() == STATE_CONTINUOUS_UP


def test_direction_switch_resets_state():
    """Switching from DWELLING_DOWN to up offset → reset to DWELLING_UP."""
    sm = HeadStateMachine(
        dwell_time_ms=300,
        down_threshold=0.03,
        up_threshold=-0.03,
    )
    sm.update(0.05)  # DWELLING_DOWN
    sm.update(-0.05)  # switch direction
    assert sm.get_state() == STATE_DWELLING_UP


def test_no_face_detected_resets_to_idle():
    sm = HeadStateMachine(dwell_time_ms=100, down_threshold=0.03)
    sm.update(0.05)
    assert sm.get_state() == STATE_DWELLING_DOWN
    sm.no_face_detected()
    assert sm.get_state() == STATE_IDLE


def test_reset():
    sm = HeadStateMachine(dwell_time_ms=100, down_threshold=0.03)
    sm.update(0.05)
    sm.reset()
    assert sm.get_state() == STATE_IDLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/test_head_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.head_state'`

- [ ] **Step 3: Implement HeadStateMachine**

```python
# python/core/head_state.py
import time

# State constants
STATE_IDLE = "idle"
STATE_DWELLING_DOWN = "dwelling_down"
STATE_DWELLING_UP = "dwelling_up"
STATE_CONTINUOUS_DOWN = "continuous_down"
STATE_CONTINUOUS_UP = "continuous_up"


class HeadStateMachine:
    def __init__(
        self,
        down_threshold: float = 0.03,
        up_threshold: float = -0.03,
        deadzone: float = 0.01,
        dwell_time_ms: int = 300,
        continuous_threshold_ms: int = 2000,
        scroll_interval_ms: int = 100,
    ):
        self._down_threshold = down_threshold
        self._up_threshold = up_threshold
        self._deadzone = deadzone
        self._dwell_time_ms = dwell_time_ms
        self._continuous_threshold_ms = continuous_threshold_ms
        self._scroll_interval_ms = scroll_interval_ms

        self._state = STATE_IDLE
        self._dwell_start: float = 0.0
        self._last_scroll_time: float = 0.0

    def update(self, offset_y: float) -> str | None:
        """Update with current head offset. Returns action or None.

        Returns: 'scroll_down', 'scroll_up', 'continuous_down', 'continuous_up', or None.
        """
        now = time.monotonic()
        in_deadzone = abs(offset_y) < self._deadzone

        if self._state == STATE_IDLE:
            return self._handle_idle(offset_y, now)

        elif self._state == STATE_DWELLING_DOWN:
            if in_deadzone:
                # Check if dwell was long enough for a single scroll
                elapsed_ms = (now - self._dwell_start) * 1000
                self._state = STATE_IDLE
                if elapsed_ms >= self._dwell_time_ms:
                    return "scroll_down"
                return None
            elif offset_y < self._up_threshold:
                # Direction switch
                self._dwell_start = now
                self._state = STATE_DWELLING_UP
                return None
            elif offset_y >= self._down_threshold:
                elapsed_ms = (now - self._dwell_start) * 1000
                if elapsed_ms >= self._continuous_threshold_ms:
                    self._state = STATE_CONTINUOUS_DOWN
                    self._last_scroll_time = now
                    return "continuous_down"
            else:
                # Between up_threshold and down_threshold but not in deadzone
                self._state = STATE_IDLE
            return None

        elif self._state == STATE_DWELLING_UP:
            if in_deadzone:
                elapsed_ms = (now - self._dwell_start) * 1000
                self._state = STATE_IDLE
                if elapsed_ms >= self._dwell_time_ms:
                    return "scroll_up"
                return None
            elif offset_y > self._down_threshold:
                # Direction switch
                self._dwell_start = now
                self._state = STATE_DWELLING_DOWN
                return None
            elif offset_y <= self._up_threshold:
                elapsed_ms = (now - self._dwell_start) * 1000
                if elapsed_ms >= self._continuous_threshold_ms:
                    self._state = STATE_CONTINUOUS_UP
                    self._last_scroll_time = now
                    return "continuous_up"
            else:
                self._state = STATE_IDLE
            return None

        elif self._state == STATE_CONTINUOUS_DOWN:
            if in_deadzone or offset_y < self._down_threshold:
                self._state = STATE_IDLE
                return None
            if (now - self._last_scroll_time) * 1000 >= self._scroll_interval_ms:
                self._last_scroll_time = now
                return "scroll_down"
            return None

        elif self._state == STATE_CONTINUOUS_UP:
            if in_deadzone or offset_y > self._up_threshold:
                self._state = STATE_IDLE
                return None
            if (now - self._last_scroll_time) * 1000 >= self._scroll_interval_ms:
                self._last_scroll_time = now
                return "scroll_up"
            return None

        return None

    def _handle_idle(self, offset_y: float, now: float) -> None:
        if offset_y >= self._down_threshold:
            self._state = STATE_DWELLING_DOWN
            self._dwell_start = now
        elif offset_y <= self._up_threshold:
            self._state = STATE_DWELLING_UP
            self._dwell_start = now

    def get_state(self) -> str:
        return self._state

    def no_face_detected(self) -> None:
        self._state = STATE_IDLE

    def reset(self) -> None:
        self._state = STATE_IDLE
        self._dwell_start = 0.0
        self._last_scroll_time = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/test_head_state.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/core/head_state.py python/tests/test_head_state.py
git commit -m "feat(core): add HeadStateMachine with progressive dwell-to-continuous control"
```

---

### Task 3: Config Updates

**Files:**
- Modify: `python/config.py`

- [ ] **Step 1: Read current config.py to understand existing keys**

Read `python/config.py` and note the existing `DEFAULT_CONFIG` keys and the `get()`/`set()` interface.

- [ ] **Step 2: Add head pose config keys to DEFAULT_CONFIG**

Add these keys to `DEFAULT_CONFIG` in `python/config.py`:

```python
"head_down_threshold": 0.03,
"head_up_threshold": -0.03,
"head_deadzone": 0.01,
"head_ema_alpha": 0.15,
"head_dwell_time_ms": 300,
"head_continuous_threshold_ms": 2000,
```

Keep all existing keys unchanged. The scroll controller keys (`scroll_distance`, `scroll_interval_ms`, etc.) remain as-is.

- [ ] **Step 3: Run existing config tests**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/test_config.py -v`
Expected: All existing tests PASS (new keys have defaults so no breakage)

- [ ] **Step 4: Commit**

```bash
git add python/config.py
git commit -m "feat(config): add head pose threshold and timing parameters"
```

---

### Task 4: Delete Old Modules and Tests

**Files:**
- Delete: `python/core/eye_tracker.py`
- Delete: `python/core/gaze_state.py`
- Delete: `python/tests/test_gaze_state.py`

- [ ] **Step 1: Delete old files**

```bash
rm python/core/eye_tracker.py python/core/gaze_state.py python/tests/test_gaze_state.py
```

- [ ] **Step 2: Commit**

```bash
git add -A python/core/eye_tracker.py python/core/gaze_state.py python/tests/test_gaze_state.py
git commit -m "refactor(core): remove old eye_tracker and gaze_state modules"
```

---

### Task 5: Refactor main.py Tracking Loop and API

**Files:**
- Modify: `python/main.py:55-182` (AppState + tracking_loop)
- Modify: `python/main.py:235-319` (calibration API)
- Modify: `python/main.py:442-559` (HTTP routes)

This is the largest change. The key modifications:

- [ ] **Step 1: Update imports and AppState**

Replace `EyeTracker`/`GazeStateMachine` imports with `HeadTracker`/`HeadStateMachine`. Update `AppState` fields:
- `eye_tracker` → `head_tracker`
- `gaze_state` → `head_state`
- `gaze_point` → `head_offset` (float | None)
- Remove `raw_gaze_y`

- [ ] **Step 2: Update initialize()**

Create `HeadTracker` and `HeadStateMachine` using config values. Load saved neutral_y from config if present:

```python
state.head_tracker = HeadTracker(
    ema_alpha=config.get("head_ema_alpha"),
    down_threshold=config.get("head_down_threshold"),
    up_threshold=config.get("head_up_threshold"),
)
state.head_state = HeadStateMachine(
    down_threshold=config.get("head_down_threshold"),
    up_threshold=config.get("head_up_threshold"),
    deadzone=config.get("head_deadzone"),
    dwell_time_ms=config.get("head_dwell_time_ms"),
    continuous_threshold_ms=config.get("head_continuous_threshold_ms"),
    scroll_interval_ms=config.get("scroll_interval_ms"),
)
```

If config has saved `neutral_y`, set it on the tracker and mark as calibrated.

- [ ] **Step 3: Rewrite tracking_loop()**

```python
def tracking_loop():
    while state.running:
        if not state.enabled:
            time.sleep(0.033)
            continue

        frame = state.camera.read()
        if frame is None:
            continue

        result = state.head_tracker.process(frame)
        if result is None:
            state.head_state.no_face_detected()
            state.head_offset = None
            continue

        _, offset_y = result
        state.head_offset = offset_y

        # Check if calibration collection period is done
        if state.head_tracker.is_calibration_done():
            cal_result = state.head_tracker.stop_calibration()
            # Store result for API to retrieve
            state._last_calibration_result = cal_result

        action = state.head_state.update(offset_y)

        if action == "scroll_down":
            state.scroll_controller.scroll_down()
        elif action == "scroll_up":
            state.scroll_controller.scroll_up()
        elif action in ("continuous_down", "continuous_up"):
            # State transition only, scrolling happens on subsequent updates
            pass

        time.sleep(0.005)  # ~30fps with processing overhead
```

- [ ] **Step 4: Replace calibration API**

Remove `/api/calibrate/top`, `/api/calibrate/bottom`, `/api/calibrate/start`, `/api/calibrate/stop`.
Add new endpoints:

- `POST /api/calibrate/neutral` — calls `head_tracker.start_calibration(3.0)`, returns `{"status": "collecting", "duration": 3.0}`
- `POST /api/calibrate/neutral/stop` — calls `head_tracker.stop_calibration()`, returns the result dict
- `GET /api/calibrate/result` — returns `state._last_calibration_result` if available
- `POST /api/calibration/save` — saves `neutral_y` to config
- `POST /api/calibration/load` — loads `neutral_y` from config into tracker
- `POST /api/calibration/reset` — calls `head_tracker.reset_calibration()`

- [ ] **Step 5: Update GET /api/state response**

Return:
```json
{
    "state": "idle|dwelling_down|dwelling_up|continuous_down|continuous_up",
    "head_offset": 0.05,
    "calibrated": true,
    "neutral_y": 0.52,
    "enabled": true,
    "face_detected": true
}
```

- [ ] **Step 6: Remove old endpoints**

Remove `GET /api/gaze` (no longer needed — offset is in `/api/state`).

- [ ] **Step 7: Update save_calibration / load_calibration**

Save/load only `neutral_y` to/from config (no more `_center_y`, `calibrate_center()`, etc.).

- [ ] **Step 8: Run all Python tests**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add python/main.py
git commit -m "refactor(main): integrate HeadTracker and HeadStateMachine, update API"
```

---

### Task 6: Web UI — Minimal Layout

**Files:**
- Modify: `src/web/index.html`
- Modify: `src/web/style.css`
- Modify: `src/web/main.js`

- [ ] **Step 1: Rewrite index.html with minimal single-column layout**

Replace the two-column layout with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EyeScroll</title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body>
    <div id="app">
        <!-- Top status bar -->
        <header id="status-bar">
            <div class="status-indicator" id="connection-dot"></div>
            <span id="state-text">IDLE</span>
        </header>

        <!-- Center: offset visualizer -->
        <main id="visualizer">
            <div id="offset-bar">
                <div id="offset-marker"></div>
                <div id="deadzone"></div>
            </div>
            <div id="offset-labels">
                <span class="label-up">UP</span>
                <span class="label-neutral">—</span>
                <span class="label-down">DOWN</span>
            </div>
        </main>

        <!-- Bottom control bar -->
        <footer id="control-bar">
            <button id="btn-calibrate">Calibrate</button>
            <label class="toggle">
                <input type="checkbox" id="toggle-enabled" checked>
                <span class="toggle-slider"></span>
            </label>
            <button id="btn-settings" class="icon-btn">⚙</button>
        </footer>

        <!-- Settings panel (hidden by default) -->
        <div id="settings-panel" class="hidden">
            <div class="setting-group">
                <label>Scroll Distance</label>
                <input type="range" id="scroll-distance" min="20" max="200" value="80">
                <span id="scroll-distance-val">80</span>
            </div>
            <div class="setting-group">
                <label>Sensitivity</label>
                <input type="range" id="sensitivity" min="1" max="10" value="5">
                <span id="sensitivity-val">5</span>
            </div>
            <button id="btn-reset-calibration" class="danger-btn">Reset Calibration</button>
        </div>

        <!-- Calibration overlay -->
        <div id="calibration-overlay" class="hidden">
            <div class="calibration-content">
                <div id="calibration-anchor">
                    <div class="crosshair-h"></div>
                    <div class="crosshair-v"></div>
                    <div class="anchor-dot"></div>
                </div>
                <p id="calibration-text">Align your gaze here</p>
                <p id="calibration-countdown" class="hidden">3</p>
                <p id="calibration-result" class="hidden"></p>
            </div>
        </div>
    </div>
    <script src="main.js"></script>
</body>
</html>
```

- [ ] **Step 2: Rewrite style.css for minimal design**

Keep the existing CSS custom properties system but simplify. Key additions:
- `#status-bar`: flex row, centered, full-width
- `#visualizer`: centered, contains the offset bar (vertical track with a sliding marker)
- `#offset-bar`: tall narrow track (4px wide, 200px tall), with `#offset-marker` (a dot that slides up/down)
- `#deadzone`: a highlighted zone in the center of the bar
- `#control-bar`: flex row at bottom, gap between buttons
- `#calibration-overlay`: full-screen semi-transparent backdrop, centered anchor with crosshair
- `.toggle`: CSS-only toggle switch
- `#settings-panel`: slide-up panel, hidden by default
- `.hidden { display: none !important; }`
- `.danger-btn`: red variant for destructive actions
- Status colors: green = connected/active, gray = idle, red = error

- [ ] **Step 3: Rewrite main.js**

Core logic:
- `fetchState()`: polls `GET /api/state` at ~30fps via `requestAnimationFrame`. Updates:
  - `#state-text` with state name
  - `#connection-dot` color (green if face_detected, gray if not)
  - `#offset-marker` position (map offset_y to pixel position within the bar)
- Calibration flow:
  1. Click "Calibrate" → show `#calibration-overlay`, POST `/api/calibrate/neutral`
  2. Start 3s countdown (update `#calibration-countdown`)
  3. After 3s, POST `/api/calibrate/neutral/stop`
  4. Show result (success/fail) in `#calibration-result`
  5. If success, POST `/api/calibration/save`, hide overlay after 1s
  6. If fail, show "Try again" button
- Settings:
  - Toggle `#toggle-enabled` → POST `/api/enable` or `/api/disable`
  - Scroll distance slider → PUT `/api/config` with `scroll_distance`
  - Sensitivity slider → maps 1-10 to threshold values, PUT `/api/config`
  - Reset calibration → POST `/api/calibration/reset`
  - Gear button toggles `#settings-panel` visibility

- [ ] **Step 4: Build frontend**

Run: `cd /Users/zen/projects/scroll_page/src/web && npm run build`

- [ ] **Step 5: Commit**

```bash
git add src/web/index.html src/web/main.js src/web/style.css src/dist/
git commit -m "feat(ui): minimal single-column layout with anchor-guided calibration"
```

---

### Task 7: Tauri Shell Updates

**Files:**
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Update Rust types and commands**

Replace `GazeData` with `HeadStateData`:

```rust
#[derive(serde::Serialize)]
struct HeadStateData {
    state: String,
    head_offset: Option<f64>,
    calibrated: bool,
    neutral_y: Option<f64>,
    enabled: bool,
    face_detected: bool,
}
```

Update `get_state()` to return `HeadStateData`.

Remove `calibrate_top()` and `calibrate_bottom()` commands.

Add new commands:
- `calibrate_neutral()` → POST `/api/calibrate/neutral`
- `calibrate_neutral_stop()` → POST `/api/calibrate/neutral/stop`
- `save_calibration()` → POST `/api/calibration/save`
- `reset_calibration()` → POST `/api/calibration/reset`

Update `generate_handler![]` with new command names.

- [ ] **Step 2: Commit**

```bash
git add src-tauri/src/lib.rs
git commit -m "feat(tauri): update commands for head pose calibration API"
```

---

### Task 8: Integration Test & Fix

**Files:**
- May modify: `python/main.py`, `src/web/main.js`

- [ ] **Step 1: Run the full application**

```bash
cd /Users/zen/projects/scroll_page && python python/main.py
```

Then open `http://localhost:5173` in a browser (or launch via Tauri).

- [ ] **Step 2: Verify the following flows work end-to-end:**

1. App starts, UI shows "Not calibrated" state
2. Click "Calibrate" → anchor overlay appears → countdown runs → calibration completes
3. After calibration, offset bar moves when tilting head
4. Tilting down past threshold → state shows "DWELLING" → return to neutral → single scroll fires
5. Tilting down for >2s → state shows "CONTINUOUS" → continuous scrolling
6. Return to neutral → scrolling stops
7. Same for tilting up
8. Settings panel opens/closes, sliders update config
9. Toggle enable/disable works
10. Reset calibration works

- [ ] **Step 3: Fix any issues found during integration testing**

- [ ] **Step 4: Run all tests**

Run: `cd /Users/zen/projects/scroll_page/python && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes"
```

---

## Verification

1. **Unit tests**: `cd python && python -m pytest tests/ -v` — all pass
2. **Manual test**: Start app, calibrate, verify head-pose-driven scrolling works
3. **Edge cases**: Cover face with hand (no face → IDLE), sudden movement (spike rejection), 30s idle (auto-pause if implemented)
