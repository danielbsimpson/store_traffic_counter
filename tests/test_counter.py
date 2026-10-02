"""Unit tests for the tripwire counter."""

from __future__ import annotations

import pytest

from counter import TripwireCounter
from tracker import TrackedObject


def _obj(track_id: int, cy: int, cx: int = 100, frame_number: int = 1) -> TrackedObject:
    """Build a tracked object whose foot point (bottom-center) is (cx, cy)."""
    return TrackedObject(
        id=track_id,
        box=(cx - 10, cy - 20, cx + 10, cy),
        centroid=(cx, cy - 10),
        confidence=0.9,
        frame_number=frame_number,
    )


def test_default_line_at_half_height() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480)
    assert counter.line == ((0, 240), (640, 240))


def test_invalid_fraction_raises_value_error() -> None:
    with pytest.raises(ValueError):
        TripwireCounter(frame_width=640, frame_height=480, start=(0.0, 1.5))


def test_no_event_on_first_sighting() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480)
    events = counter.update([_obj(0, cy=100)], frame_number=1)
    assert events == []


def test_tripwire_entry_detection() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480, debounce_frames=1)
    counter.update([_obj(0, cy=100)], frame_number=1)  # above the line
    events = counter.update([_obj(0, cy=300)], frame_number=2)  # now below
    assert len(events) == 1
    assert events[0].direction == "in"
    assert events[0].person_id == 0
    assert events[0].cumulative_in == 1
    assert counter.total_in == 1
    assert counter.total_out == 0


def test_tripwire_exit_detection() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480, debounce_frames=1)
    counter.update([_obj(0, cy=300)], frame_number=1)  # below the line
    events = counter.update([_obj(0, cy=100)], frame_number=2)  # now above
    assert len(events) == 1
    assert events[0].direction == "out"
    assert events[0].cumulative_out == 1
    assert counter.total_in == 0
    assert counter.total_out == 1


def test_hysteresis_prevents_double_count() -> None:
    counter = TripwireCounter(
        frame_width=640, frame_height=480, hysteresis=10, debounce_frames=1
    )
    counter.update([_obj(0, cy=200)], frame_number=1)  # clearly above
    # Jitter inside the hysteresis band (line_y=240 +/- 10) should not register.
    for cy in (235, 242, 238, 246):
        events = counter.update([_obj(0, cy=cy)], frame_number=2)
        assert events == []
    # A clear crossing past the band triggers exactly one event.
    events = counter.update([_obj(0, cy=260)], frame_number=3)
    assert len(events) == 1
    assert events[0].direction == "in"
    assert counter.total_in == 1


def test_cumulative_counts_across_multiple_people() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480, debounce_frames=1)
    counter.update([_obj(0, cy=100), _obj(1, cy=300)], frame_number=1)
    events = counter.update([_obj(0, cy=300), _obj(1, cy=100)], frame_number=2)
    directions = {e.person_id: e.direction for e in events}
    assert directions == {0: "in", 1: "out"}
    assert counter.counts == (1, 1)


def test_no_crossing_when_staying_on_same_side() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480)
    counter.update([_obj(0, cy=100)], frame_number=1)
    events = counter.update([_obj(0, cy=120)], frame_number=2)
    assert events == []
    assert counter.counts == (0, 0)


def test_angled_line_crossing_detection() -> None:
    # Line slopes from top-left (0, 100) to bottom-right (640, 300), mimicking
    # a storefront viewed at a perspective angle rather than a flat horizontal line.
    counter = TripwireCounter(
        frame_width=640, frame_height=480, start=(0.0, 100 / 480), end=(1.0, 300 / 480),
        debounce_frames=1,
    )
    assert counter.line == ((0, 100), (640, 300))
    # At x=320 the line sits at y=200; start clearly above it.
    counter.update([_obj(0, cx=320, cy=100)], frame_number=1)
    events = counter.update([_obj(0, cx=320, cy=300)], frame_number=2)
    assert len(events) == 1
    assert events[0].direction == "in"
    assert counter.total_in == 1


def test_debounce_requires_consecutive_frames() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480, debounce_frames=3)
    counter.update([_obj(0, cy=100)], frame_number=1)  # above the line
    # Two frames on the new side aren't enough to commit the crossing.
    assert counter.update([_obj(0, cy=300)], frame_number=2) == []
    assert counter.update([_obj(0, cy=300)], frame_number=3) == []
    # The third consecutive frame confirms it.
    events = counter.update([_obj(0, cy=300)], frame_number=4)
    assert len(events) == 1
    assert events[0].direction == "in"
    assert counter.counts == (1, 0)


def test_debounce_cancels_on_return_to_original_side() -> None:
    counter = TripwireCounter(frame_width=640, frame_height=480, debounce_frames=3)
    counter.update([_obj(0, cy=100)], frame_number=1)  # above
    counter.update([_obj(0, cy=300)], frame_number=2)  # dips below (held=1)
    counter.update([_obj(0, cy=100)], frame_number=3)  # bounces back; cancels candidate
    # One frame below again is not enough; the bounce never counted.
    assert counter.update([_obj(0, cy=300)], frame_number=4) == []
    assert counter.counts == (0, 0)
