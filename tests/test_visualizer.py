"""Unit tests for the VideoVisualizer overlay renderer."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from config import (
    VIS_COLOR_DEFAULT,
    VIS_COLOR_IN,
    VIS_COLOR_NEAR_TRIPWIRE,
    VIS_COLOR_OUT,
    VIS_CROSSING_HIGHLIGHT_FRAMES,
)
from counter import CountEvent
from tracker import TrackedObject
from visualizer import VideoVisualizer


def _track(track_id: int = 0, box: tuple[int, int, int, int] = (100, 100, 200, 300)) -> TrackedObject:
    x1, y1, x2, y2 = box
    return TrackedObject(
        id=track_id,
        box=box,
        centroid=((x1 + x2) // 2, (y1 + y2) // 2),
        confidence=0.88,
        frame_number=1,
    )


def _crossing_event(person_id: int, direction: str) -> CountEvent:
    return CountEvent(
        timestamp=datetime.now(timezone.utc),
        frame_number=1,
        person_id=person_id,
        direction=direction,
        cumulative_in=1 if direction == "in" else 0,
        cumulative_out=1 if direction == "out" else 0,
    )


def test_annotate_returns_same_shape_copy() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer()
    out = vis.annotate(frame, [_track()])
    assert out.shape == frame.shape
    assert out is not frame  # must not mutate the input


def test_annotate_draws_box_pixels() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False)
    out = vis.annotate(frame, [_track()])
    # Input is all black; drawing a box must introduce non-zero pixels.
    assert out.sum() > 0


def test_annotate_empty_tracks_no_boxes() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False)
    out = vis.annotate(frame, [])
    assert out.sum() == 0


def test_color_for_id_is_deterministic_and_distinct() -> None:
    assert VideoVisualizer.color_for_id(0) == VideoVisualizer.color_for_id(0)
    assert VideoVisualizer.color_for_id(0) != VideoVisualizer.color_for_id(1)
    color = VideoVisualizer.color_for_id(5)
    assert len(color) == 3
    assert all(0 <= c <= 255 for c in color)


def test_hud_renders_when_stats_provided() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer()
    out = vis.annotate(
        frame, [], frame_number=42, fps=12.5, active_tracks=3, total_tracks=10
    )
    assert out.sum() > 0  # HUD text drawn even with no tracks


def test_tripwire_drawn_when_configured() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    without = VideoVisualizer(show_hud=False, tripwire=None).annotate(frame, [])
    with_line = VideoVisualizer(
        show_hud=False, tripwire=((0, 240), (640, 240))
    ).annotate(frame, [])
    assert without.sum() == 0
    assert with_line.sum() > 0


def test_counts_overlay_drawn_when_provided() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer()
    out = vis.annotate(frame, [], counts=(7, 5))
    assert out.sum() > 0


def test_default_box_color_is_grey() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False)
    out = vis.annotate(frame, [_track(box=(100, 100, 140, 140))])
    assert tuple(int(c) for c in out[100, 100]) == VIS_COLOR_DEFAULT


def test_box_color_turns_blue_near_tripwire() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False, tripwire=((0, 200), (640, 200)))
    track = _track(box=(100, 180, 140, 220))  # centroid (120, 200) sits on the line
    out = vis.annotate(frame, [track])
    assert tuple(int(c) for c in out[180, 100]) == VIS_COLOR_NEAR_TRIPWIRE


def test_box_color_turns_green_after_in_crossing() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False)
    track = _track(track_id=2, box=(300, 300, 340, 340))
    out = vis.annotate(frame, [track], events=[_crossing_event(2, "in")])
    assert tuple(int(c) for c in out[300, 300]) == VIS_COLOR_IN


def test_box_color_turns_red_after_out_crossing() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False)
    track = _track(track_id=3, box=(300, 300, 340, 340))
    out = vis.annotate(frame, [track], events=[_crossing_event(3, "out")])
    assert tuple(int(c) for c in out[300, 300]) == VIS_COLOR_OUT


def test_crossing_highlight_expires_back_to_default() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    vis = VideoVisualizer(show_hud=False)
    track = _track(track_id=4, box=(300, 300, 340, 340))
    vis.annotate(frame, [track], events=[_crossing_event(4, "out")])
    for _ in range(VIS_CROSSING_HIGHLIGHT_FRAMES):
        out = vis.annotate(frame, [track])
    assert tuple(int(c) for c in out[300, 300]) == VIS_COLOR_DEFAULT
