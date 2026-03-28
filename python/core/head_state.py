"""
EyeScroll 头部姿态状态机

5-state progressive control: IDLE -> DWELLING_DOWN/UP -> CONTINUOUS_DOWN/UP
Short dwell triggers single scroll on return to neutral.
Long dwell (>continuous_threshold_ms) switches to continuous scrolling.
"""
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

        Sign convention: positive offset = tilting down, negative = tilting up.
        down_threshold is positive, up_threshold is negative.
        Deadzone is the neutral band around zero: |offset_y| < deadzone → IDLE.

        Returns: 'scroll_down', 'scroll_up', 'continuous_down', 'continuous_up', or None.
        """
        now = time.monotonic()
        in_deadzone = abs(offset_y) < self._deadzone

        # DEBUG: print state transitions
        if self._state != STATE_IDLE or not in_deadzone:
            print(f"[HeadState] state={self._state} offset_y={offset_y:.4f} in_dz={in_deadzone} d_th={self._down_threshold} u_th={self._up_threshold}", flush=True)

        if self._state == STATE_IDLE:
            return self._handle_idle(offset_y, now)

        elif self._state == STATE_DWELLING_DOWN:
            if in_deadzone:
                self._state = STATE_IDLE
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
                    return "continuous_up"
                if elapsed_ms >= self._dwell_time_ms:
                    # Trigger scroll immediately on dwell met (with rate limit)
                    if (now - self._last_scroll_time) * 1000 >= self._scroll_interval_ms:
                        self._last_scroll_time = now
                        return "scroll_up"
            else:
                self._state = STATE_IDLE
            return None

        elif self._state == STATE_DWELLING_UP:
            if in_deadzone:
                self._state = STATE_IDLE
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
                    return "continuous_down"
                if elapsed_ms >= self._dwell_time_ms:
                    if (now - self._last_scroll_time) * 1000 >= self._scroll_interval_ms:
                        self._last_scroll_time = now
                        return "scroll_down"
            else:
                self._state = STATE_IDLE
            return None

        elif self._state == STATE_CONTINUOUS_DOWN:
            if in_deadzone or offset_y < self._down_threshold:
                self._state = STATE_IDLE
                return None
            if (now - self._last_scroll_time) * 1000 >= self._scroll_interval_ms:
                self._last_scroll_time = now
                return "scroll_up"
            return None

        elif self._state == STATE_CONTINUOUS_UP:
            if in_deadzone or offset_y > self._up_threshold:
                self._state = STATE_IDLE
                return None
            if (now - self._last_scroll_time) * 1000 >= self._scroll_interval_ms:
                self._last_scroll_time = now
                return "scroll_down"
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
