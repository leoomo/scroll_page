# Head Pose Scrolling Design

## Context

EyeScroll 原先使用 MediaPipe iris landmarks 进行眼球追踪来实现免手滚动。实际测试发现：普通摄像头的像素级眼球追踪精度低、抖动大、环境光线敏感，用户体验不理想。

本设计将核心交互信号从"眼球追踪"切换为"头部姿态控制"，利用面部关键点的 2D 位移来检测头部俯仰方向，实现稳定可靠的免手滚动。

## Core Signal: Multi-Keypoint Weighted Head Pose

### Key Points

| Key Point | Landmark Index | Weight | Rationale |
|-----------|---------------|--------|-----------|
| Nose tip | 1 | 0.5 | Most direct indicator of head pitch |
| Chin | 152 | 0.3 | Large displacement when tilting down |
| Forehead | 10 | 0.2 | More responsive than nose when tilting up |

### Calculation

```
head_y = 0.5 * nose_y + 0.3 * chin_y + 0.2 * forehead_y
```

MediaPipe normalized coordinates: 0.0 = top, 1.0 = bottom. Tilting down increases `head_y`, tilting up decreases it.

### Smoothing

EMA (Exponential Moving Average) to filter jitter:

```
smooth_offset = 0.15 * raw_offset + 0.85 * smooth_offset
```

α = 0.15 balances responsiveness and smoothness.

### Noise Rejection

Single-frame spike detection: if `|raw_offset| > 3 * threshold`, discard the frame.

## Neutral Point Calibration

### Flow

1. User clicks "Calibrate" button
2. A visual anchor point (dot + crosshair) appears at screen center
3. User naturally aligns gaze and head to the anchor
4. System auto-starts 3-second sample collection
5. Countdown displayed on the anchor
6. Collection ends: anchor disappears, status flashes green
7. Neutral value saved to `~/.eye_scroll/config.json`

### Algorithm

- Collect `head_y` samples for 3 seconds
- Compute median as `neutral_y`
- Compute standard deviation; if > threshold, prompt recalibration
- `offset = head_y - neutral_y` (positive = tilting down, negative = tilting up)

### Persistence

Saved in `~/.eye_scroll/config.json` alongside other settings. Auto-loaded on startup.

## State Machine

### States

```
IDLE ↔ DWELLING_DOWN ↔ CONTINUOUS_DOWN
IDLE ↔ DWELLING_UP   ↔ CONTINUOUS_UP
```

5 states total:

| State | Meaning | Enter Condition | Exit Condition |
|-------|---------|-----------------|----------------|
| IDLE | Natural reading, no scroll | Returns to neutral zone / single scroll completed | offset exceeds down/up threshold |
| DWELLING_DOWN | Head tilted down, awaiting confirmation | offset > down_threshold, duration < 2s | Returns to neutral → IDLE; duration >= 2s → CONTINUOUS_DOWN |
| DWELLING_UP | Head tilted up, awaiting confirmation | offset < up_threshold, duration < 2s | Returns to neutral → IDLE; duration >= 2s → CONTINUOUS_UP |
| CONTINUOUS_DOWN | Continuous down scrolling (throttle mode) | DWELLING_DOWN held >= 2s | offset returns to neutral zone → IDLE |
| CONTINUOUS_UP | Continuous up scrolling (throttle mode) | DWELLING_UP held >= 2s | offset returns to neutral zone → IDLE |

### Progressive Control

- **Single scroll** (DWELLING reaches dwell_time_ms=300ms then returns to neutral before continuous_threshold_ms=2000ms): triggers one `scroll_distance` pixel scroll on return to neutral
- **Continuous scroll** (DWELLING >= 2s): switches to `SCROLL_INTERVAL_MS` interval scrolling
- **Return to neutral**: `|smooth_offset| < deadzone`

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| down_threshold | 0.03 | Offset threshold to trigger down scroll |
| up_threshold | -0.03 | Offset threshold to trigger up scroll |
| deadzone | 0.01 | Neutral zone for return detection |
| dwell_time_ms | 300 | Min dwell time for single scroll trigger |
| continuous_threshold_ms | 2000 | Dwell time to switch to continuous mode |
| scroll_distance | 80 | Pixels per single scroll |
| scroll_interval_ms | 100 | Interval for continuous scrolling |
| ema_alpha | 0.15 | EMA smoothing factor |

## Architecture

### File Changes

| File | Action | Description |
|------|--------|-------------|
| `core/eye_tracker.py` | Delete | Replaced by head_tracker.py |
| `core/gaze_state.py` | Delete | Replaced by head_state.py |
| `core/head_tracker.py` | New | Multi-keypoint weighted head pose + EMA smoothing + neutral calibration |
| `core/head_state.py` | New | 5-state machine (IDLE/DWELLING_DOWN/DWELLING_UP/CONTINUOUS_DOWN/CONTINUOUS_UP) |
| `main.py` | Refactor | Update tracking loop to use new modules; fix calibration API |
| `src/web/index.html` | Rewrite | Minimal single-column layout |
| `src/web/main.js` | Rewrite | Anchor-guided calibration + offset visualizer |
| `src/web/style.css` | Rewrite | New minimal design system |
| `src-tauri/src/lib.rs` | Update | Add calibration Tauri commands |

### head_tracker.py Interface

```python
class HeadTracker:
    def process(frame) -> tuple[float, float]:
        """Returns (smooth_offset_x, smooth_offset_y).
        offset_y > 0 = tilting down, < 0 = tilting up."""

    def start_calibration() -> None:
        """Start 3-second neutral point collection."""

    def stop_calibration() -> float:
        """Stop collection, return neutral_y value."""

    def is_calibrated() -> bool

    def get_neutral_y() -> float | None
```

### head_state.py Interface

```python
class HeadStateMachine:
    def update(offset_y: float) -> str | None:
        """Returns 'scroll_down', 'scroll_up', 'continuous_down', 'continuous_up', or None."""

    def get_state() -> str:
        """Returns current state name."""

    def reset() -> None:
        """Force back to IDLE."""
```

### API Changes

| Endpoint | Change |
|----------|--------|
| `GET /api/state` | Returns head offset + current state (replaces gaze point) |
| `POST /api/calibrate/neutral` | New: start neutral calibration |
| `POST /api/calibrate/neutral/stop` | New: stop calibration |
| `POST /api/calibrate/top` | Removed |
| `POST /api/calibrate/bottom` | Removed |

### Unchanged Files

- `core/camera.py` — OpenCV wrapper, no changes needed
- `core/scroll_controller.py` — Adapter pattern, no changes needed
- `adapters/mac_scroll.py`, `adapters/win_scroll.py` — Platform scroll controllers
- `config.py` — Configuration management
- `utils/permissions.py` — macOS permission checks

## UI Design

### Layout (Single Column, Minimal)

1. **Top status bar** (one line): connection indicator + state text (IDLE/Scrolling)
2. **Center**: vertical offset indicator bar (shows head tilt direction and magnitude)
3. **Bottom control bar** (one line): Calibrate button + Enable/Disable toggle + Settings gear

### Settings Panel (expandable)

Hidden by default. Click gear icon to expand over center area:
- Scroll distance slider
- Sensitivity slider
- Reset calibration button

### Calibration Overlay

- Semi-transparent overlay covers entire UI
- Center anchor point (dot + crosshair)
- "Align your gaze here" text + 3-second countdown
- Auto-starts collection when overlay appears
- Disappears on completion with green flash confirmation

## Edge Cases

| Scenario | Handling |
|----------|----------|
| No calibration on startup | Show calibration prompt, disable tracking toggle |
| No face detected | State = IDLE, UI shows "No face detected" |
| Sudden lighting change (landmark jump) | EMA smoothing + spike rejection (discard if offset > 3x threshold) |
| User stationary for 30s+ | Auto-pause tracking, UI shows "Paused" prompt |
| Poor calibration quality (high stddev) | Prompt recalibration |

## First Launch Flow

1. Check camera permission → guide to System Settings if denied
2. Check accessibility permission → guide to System Settings if denied
3. Check saved calibration → if none, auto-enter calibration flow
4. Calibration complete → start tracking
