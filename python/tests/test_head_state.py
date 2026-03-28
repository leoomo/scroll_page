"""
EyeScroll HeadStateMachine 测试

Sign convention: offset_y positive = tilting down, negative = tilting up.
down_threshold is positive, up_threshold is negative.
"""
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
    sm = HeadStateMachine(dwell_time_ms=300, down_threshold=0.03, up_threshold=-0.03, deadzone=0.01)
    result = sm.update(0.005)  # within deadzone
    assert result is None
    assert sm.get_state() == STATE_IDLE


def test_enter_dwell_down_on_positive_offset():
    """Positive offset (tilting down) past down_threshold → DWELLING_DOWN."""
    sm = HeadStateMachine(dwell_time_ms=300, down_threshold=0.03, up_threshold=-0.03)
    sm.update(0.05)  # past down_threshold (0.03)
    assert sm.get_state() == STATE_DWELLING_DOWN
    assert sm.update(0.05) is None  # no action yet


def test_enter_dwell_up_on_negative_offset():
    """Negative offset (tilting up) past up_threshold → DWELLING_UP."""
    sm = HeadStateMachine(dwell_time_ms=300, down_threshold=0.03, up_threshold=-0.03)
    sm.update(-0.05)  # past up_threshold (-0.03)
    assert sm.get_state() == STATE_DWELLING_UP


def test_single_scroll_down_on_dwell():
    """Dwell past dwell_time_ms in DWELLING_DOWN → scroll_down."""
    sm = HeadStateMachine(dwell_time_ms=100, down_threshold=0.03, deadzone=0.01)
    sm.update(0.05)  # enter DWELLING_DOWN
    time.sleep(0.15)  # exceed dwell_time_ms
    result = sm.update(0.05)  # still past threshold → trigger scroll
    assert result == "scroll_down"


def test_no_scroll_if_dwell_too_short():
    """Not enough dwell time → no scroll."""
    sm = HeadStateMachine(dwell_time_ms=300, down_threshold=0.03, deadzone=0.01)
    sm.update(0.05)  # enter DWELLING_DOWN
    time.sleep(0.05)  # NOT enough dwell time
    result = sm.update(0.05)
    assert result is None


def test_continuous_scroll_down_after_long_dwell():
    """Dwell past continuous_threshold_ms → auto switch to CONTINUOUS_DOWN."""
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
        up_threshold=-0.03,
        deadzone=0.01,
    )
    sm.update(0.05)
    time.sleep(0.25)
    sm.update(0.05)  # enter continuous
    result = sm.update(0.005)  # return to neutral
    assert result is None
    assert sm.get_state() == STATE_IDLE


def test_continuous_up_stops_on_neutral():
    """Return to neutral while in CONTINUOUS_UP → back to IDLE."""
    sm = HeadStateMachine(
        dwell_time_ms=100,
        continuous_threshold_ms=200,
        down_threshold=0.03,
        up_threshold=-0.03,
        deadzone=0.01,
    )
    sm.update(-0.05)
    time.sleep(0.25)
    sm.update(-0.05)  # enter continuous
    result = sm.update(0.005)  # return to neutral
    assert result is None
    assert sm.get_state() == STATE_IDLE


def test_single_scroll_up_on_dwell():
    """Dwell past dwell_time_ms in DWELLING_UP → scroll_up."""
    sm = HeadStateMachine(dwell_time_ms=100, up_threshold=-0.03, deadzone=0.01)
    sm.update(-0.05)
    time.sleep(0.15)
    result = sm.update(-0.05)
    assert result == "scroll_up"


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


def test_direction_switch_down_to_up():
    """Switching from DWELLING_DOWN to negative offset past up_threshold → DWELLING_UP."""
    sm = HeadStateMachine(
        dwell_time_ms=300,
        down_threshold=0.03,
        up_threshold=-0.03,
    )
    sm.update(0.05)  # DWELLING_DOWN
    sm.update(-0.05)  # switch direction — past up_threshold
    assert sm.get_state() == STATE_DWELLING_UP


def test_direction_switch_up_to_down():
    """Switching from DWELLING_UP to positive offset past down_threshold → DWELLING_DOWN."""
    sm = HeadStateMachine(
        dwell_time_ms=300,
        down_threshold=0.03,
        up_threshold=-0.03,
    )
    sm.update(-0.05)  # DWELLING_UP
    sm.update(0.05)  # switch direction — past down_threshold
    assert sm.get_state() == STATE_DWELLING_DOWN


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
