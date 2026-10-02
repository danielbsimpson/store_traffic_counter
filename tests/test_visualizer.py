"""Unit tests for the VideoVisualizer overlay renderer."""

from __future__ import annotations

import numpy as np

from tracker import TrackedObject
from visualizer import VideoVisualizer


def _track(track_id: int = 0) -> TrackedObject:
    return TrackedObject(
        id=track_id,
        box=(100, 100, 200, 300),
        centroid=(150, 200),
        confidence=0.88,
        frame_number=1,
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
