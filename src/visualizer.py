"""Real-time overlay rendering for the Store Traffic Counter pipeline.

:class:`VideoVisualizer` draws tracked-person bounding boxes (color-coded by
track ID), ID and confidence labels, an optional tripwire line, and a heads-up
display with frame/FPS and track statistics. Rendering is a pure function of the
input frame, so it is fully testable without a GUI.
"""

from __future__ import annotations

import colorsys
import logging

import cv2
import numpy as np

from config import (
    VIS_BOX_THICKNESS,
    VIS_FONT_THICKNESS,
    VIS_HUD_BG_COLOR,
    VIS_HUD_COLOR,
    VIS_HUD_FONT_SCALE,
    VIS_ID_FONT_SCALE,
    VIS_TRIPWIRE_COLOR,
    VIS_TRIPWIRE_THICKNESS,
)
from tracker import TrackedObject

logger = logging.getLogger(__name__)

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_GOLDEN_RATIO_CONJUGATE = 0.618033988749895

# A tripwire line expressed as ((x1, y1), (x2, y2)).
Line = tuple[tuple[int, int], tuple[int, int]]


class VideoVisualizer:
    """Draws detection/tracking overlays onto frames.

    Args:
        show_confidence: Draw each detection's confidence next to its ID.
        show_hud: Draw the heads-up display (frame number, FPS, track counts).
        tripwire: Optional ``((x1, y1), (x2, y2))`` line to render; ``None`` to
            omit (the tripwire is defined in Phase 4).
    """

    def __init__(
        self,
        show_confidence: bool = True,
        show_hud: bool = True,
        tripwire: Line | None = None,
    ) -> None:
        self.show_confidence = show_confidence
        self.show_hud = show_hud
        self.tripwire = tripwire

    @staticmethod
    def color_for_id(object_id: int) -> tuple[int, int, int]:
        """Return a deterministic, visually distinct BGR color for a track ID."""
        hue = (object_id * _GOLDEN_RATIO_CONJUGATE) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.7, 1.0)
        return int(b * 255), int(g * 255), int(r * 255)

    def annotate(
        self,
        frame: np.ndarray,
        tracked_objects: list[TrackedObject],
        *,
        frame_number: int | None = None,
        fps: float | None = None,
        active_tracks: int | None = None,
        total_tracks: int | None = None,
        counts: tuple[int, int] | None = None,
    ) -> np.ndarray:
        """Return a copy of ``frame`` with overlays drawn.

        Args:
            frame: Source BGR frame.
            tracked_objects: Tracks to draw for this frame.
            frame_number: Current frame index for the HUD.
            fps: Instantaneous processing FPS for the HUD.
            active_tracks: Number of currently active tracks for the HUD.
            total_tracks: Total unique tracks registered for the HUD.
            counts: Optional ``(in, out)`` tallies (Phase 4); drawn if provided.
        """
        canvas = frame.copy()

        if self.tripwire is not None:
            self._draw_tripwire(canvas)

        for obj in tracked_objects:
            self._draw_track(canvas, obj)

        if self.show_hud:
            self._draw_hud(canvas, frame_number, fps, active_tracks, total_tracks, counts)

        return canvas

    def _draw_tripwire(self, canvas: np.ndarray) -> None:
        assert self.tripwire is not None
        start, end = self.tripwire
        cv2.line(canvas, start, end, VIS_TRIPWIRE_COLOR, VIS_TRIPWIRE_THICKNESS)

    def _draw_track(self, canvas: np.ndarray, obj: TrackedObject) -> None:
        color = self.color_for_id(obj.id)
        x1, y1, x2, y2 = obj.box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, VIS_BOX_THICKNESS)
        cv2.circle(canvas, obj.centroid, 3, color, -1)

        label = f"ID {obj.id}"
        if self.show_confidence:
            label += f" {obj.confidence:.2f}"
        self._draw_label(canvas, label, (x1, y1), color)

    def _draw_label(
        self,
        canvas: np.ndarray,
        text: str,
        anchor: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        """Draw text with a filled background just above the anchor point."""
        (tw, th), baseline = cv2.getTextSize(
            text, _FONT, VIS_ID_FONT_SCALE, VIS_FONT_THICKNESS
        )
        x, y = anchor
        top = max(0, y - th - baseline)
        cv2.rectangle(canvas, (x, top), (x + tw, y), color, -1)
        cv2.putText(
            canvas,
            text,
            (x, y - baseline),
            _FONT,
            VIS_ID_FONT_SCALE,
            (0, 0, 0),
            VIS_FONT_THICKNESS,
            cv2.LINE_AA,
        )

    def _draw_hud(
        self,
        canvas: np.ndarray,
        frame_number: int | None,
        fps: float | None,
        active_tracks: int | None,
        total_tracks: int | None,
        counts: tuple[int, int] | None,
    ) -> None:
        lines: list[str] = []
        if counts is not None:
            lines.append(f"IN: {counts[0]} | OUT: {counts[1]}")
        stats: list[str] = []
        if active_tracks is not None:
            stats.append(f"active: {active_tracks}")
        if total_tracks is not None:
            stats.append(f"total: {total_tracks}")
        if stats:
            lines.append("tracks  " + "  ".join(stats))

        self._draw_hud_block(canvas, lines, origin=(10, 10))

        corner: list[str] = []
        if frame_number is not None:
            corner.append(f"frame {frame_number}")
        if fps is not None:
            corner.append(f"{fps:.1f} FPS")
        if corner:
            self._draw_corner_text(canvas, "  ".join(corner))

    def _draw_hud_block(
        self, canvas: np.ndarray, lines: list[str], origin: tuple[int, int]
    ) -> None:
        if not lines:
            return
        x, y = origin
        pad = 6
        line_h = int(30 * VIS_HUD_FONT_SCALE) + pad
        for i, text in enumerate(lines):
            (tw, th), _ = cv2.getTextSize(
                text, _FONT, VIS_HUD_FONT_SCALE, VIS_FONT_THICKNESS
            )
            top = y + i * line_h
            cv2.rectangle(
                canvas,
                (x - pad, top),
                (x + tw + pad, top + th + pad * 2),
                VIS_HUD_BG_COLOR,
                -1,
            )
            cv2.putText(
                canvas,
                text,
                (x, top + th + pad),
                _FONT,
                VIS_HUD_FONT_SCALE,
                VIS_HUD_COLOR,
                VIS_FONT_THICKNESS,
                cv2.LINE_AA,
            )

    def _draw_corner_text(self, canvas: np.ndarray, text: str) -> None:
        (tw, th), _ = cv2.getTextSize(
            text, _FONT, VIS_HUD_FONT_SCALE, VIS_FONT_THICKNESS
        )
        pad = 6
        x = canvas.shape[1] - tw - pad - 10
        y = 10
        cv2.rectangle(
            canvas, (x - pad, y), (x + tw + pad, y + th + pad * 2), VIS_HUD_BG_COLOR, -1
        )
        cv2.putText(
            canvas,
            text,
            (x, y + th + pad),
            _FONT,
            VIS_HUD_FONT_SCALE,
            VIS_HUD_COLOR,
            VIS_FONT_THICKNESS,
            cv2.LINE_AA,
        )
