"""Real-time overlay rendering for the Store Traffic Counter pipeline.

:class:`VideoVisualizer` draws tracked-person bounding boxes, ID and
confidence labels, an optional tripwire line, and a heads-up display with
frame/FPS and track statistics. Box color reflects each track's tripwire
status: grey by default, blue when approaching the line, then briefly
green/red after an IN/OUT crossing. Rendering is otherwise a pure function of
the input frame, so it is fully testable without a GUI.
"""

from __future__ import annotations

import colorsys
import logging
import math

import cv2
import numpy as np

from config import (
    VIS_BOX_THICKNESS,
    VIS_COLOR_DEFAULT,
    VIS_COLOR_IN,
    VIS_COLOR_NEAR_TRIPWIRE,
    VIS_COLOR_OUT,
    VIS_CROSSING_HIGHLIGHT_FRAMES,
    VIS_FONT_THICKNESS,
    VIS_HUD_BG_COLOR,
    VIS_HUD_COLOR,
    VIS_HUD_FONT_SCALE,
    VIS_ID_FONT_SCALE,
    VIS_TRIPWIRE_COLOR,
    VIS_TRIPWIRE_PROXIMITY_MAX_PX,
    VIS_TRIPWIRE_PROXIMITY_MIN_PX,
    VIS_TRIPWIRE_THICKNESS,
)
from counter import CountEvent, perpendicular_distance
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
            omit.
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
        self._highlights: dict[int, tuple[str, int]] = {}  # id -> (direction, frames_remaining)

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
        events: list[CountEvent] | None = None,
    ) -> np.ndarray:
        """Return a copy of ``frame`` with overlays drawn.

        Args:
            frame: Source BGR frame.
            tracked_objects: Tracks to draw for this frame.
            frame_number: Current frame index for the HUD.
            fps: Instantaneous processing FPS for the HUD.
            active_tracks: Number of currently active tracks for the HUD.
            total_tracks: Total unique tracks registered for the HUD.
            counts: Optional ``(in, out)`` tallies; drawn if provided.
            events: Tripwire crossings detected this frame; each starts a
                brief green/red (IN/OUT) highlight on the crossing track.
        """
        canvas = frame.copy()

        self._decay_highlights()
        if events:
            self._register_crossings(events)

        if self.tripwire is not None:
            self._draw_tripwire(canvas)

        for obj in tracked_objects:
            self._draw_track(canvas, obj)

        if self.show_hud:
            self._draw_hud(canvas, frame_number, fps, active_tracks, total_tracks, counts)

        return canvas

    def _register_crossings(self, events: list[CountEvent]) -> None:
        """Start a fresh green/red highlight for tracks that just crossed the tripwire."""
        for event in events:
            self._highlights[event.person_id] = (event.direction, VIS_CROSSING_HIGHLIGHT_FRAMES)

    def _decay_highlights(self) -> None:
        """Tick down one frame's worth of highlight duration, dropping expired entries."""
        expired = []
        for track_id, (direction, remaining) in self._highlights.items():
            remaining -= 1
            if remaining <= 0:
                expired.append(track_id)
            else:
                self._highlights[track_id] = (direction, remaining)
        for track_id in expired:
            del self._highlights[track_id]

    def _color_for_track(
        self, obj: TrackedObject, frame_height: int
    ) -> tuple[int, int, int]:
        """Return the status color for a track: crossing highlight > proximity > default."""
        highlight = self._highlights.get(obj.id)
        if highlight is not None:
            direction, _ = highlight
            return VIS_COLOR_IN if direction == "in" else VIS_COLOR_OUT
        if self.tripwire is not None:
            fx, fy = obj.foot
            distance = abs(perpendicular_distance((fx, fy), self.tripwire))
            if distance <= self._proximity_threshold(fy, frame_height):
                return VIS_COLOR_NEAR_TRIPWIRE
        return VIS_COLOR_DEFAULT

    @staticmethod
    def _proximity_threshold(foot_y: int, frame_height: int) -> float:
        """Depth-scaled blue-highlight band: narrow far away, wide near the camera."""
        scale = min(max(foot_y / (frame_height or 1), 0.0), 1.0)
        span = VIS_TRIPWIRE_PROXIMITY_MAX_PX - VIS_TRIPWIRE_PROXIMITY_MIN_PX
        return VIS_TRIPWIRE_PROXIMITY_MIN_PX + span * scale

    def _draw_tripwire(self, canvas: np.ndarray) -> None:
        assert self.tripwire is not None
        start, end = self.tripwire
        cv2.line(canvas, start, end, VIS_TRIPWIRE_COLOR, VIS_TRIPWIRE_THICKNESS)
        self._draw_direction_arrows(canvas, start, end)

    def _draw_direction_arrows(
        self, canvas: np.ndarray, start: tuple[int, int], end: tuple[int, int]
    ) -> None:
        """Draw arrows indicating the IN and OUT directions, following the line's angle."""
        x1, y1 = start
        x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length  # unit vector along the line
        px, py = -uy, ux  # unit vector perpendicular to the line ("below" side)
        arrow_len, gap = 25, 8

        in_anchor = (x1 + ux * length / 3, y1 + uy * length / 3)
        self._draw_arrow(canvas, in_anchor, (px, py), arrow_len, gap, "IN")

        out_anchor = (x1 + ux * 2 * length / 3, y1 + uy * 2 * length / 3)
        self._draw_arrow(canvas, out_anchor, (-px, -py), arrow_len, gap, "OUT")

    def _draw_arrow(
        self,
        canvas: np.ndarray,
        anchor: tuple[float, float],
        direction: tuple[float, float],
        arrow_len: int,
        gap: int,
        label: str,
    ) -> None:
        """Draw a short arrow pointing toward the line from one side, with a label."""
        ax, ay = anchor
        dx, dy = direction
        far = (int(ax - dx * (gap + arrow_len)), int(ay - dy * (gap + arrow_len)))
        near = (int(ax - dx * gap), int(ay - dy * gap))
        cv2.arrowedLine(canvas, far, near, VIS_TRIPWIRE_COLOR, 2, tipLength=0.4)
        label_pos = (int(ax - dx * (gap + arrow_len / 2)) + 8, int(ay - dy * (gap + arrow_len / 2)))
        cv2.putText(
            canvas, label, label_pos, _FONT, 0.5, VIS_TRIPWIRE_COLOR, 1, cv2.LINE_AA,
        )

    def _draw_track(self, canvas: np.ndarray, obj: TrackedObject) -> None:
        color = self._color_for_track(obj, canvas.shape[0])
        x1, y1, x2, y2 = obj.box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, VIS_BOX_THICKNESS)
        cv2.circle(canvas, obj.foot, 4, color, -1)

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
