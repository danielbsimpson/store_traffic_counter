"""Interactive storefront tripwire calibration.

Aligning tripwires by editing raw fractions is slow because you cannot see
where a line lands until you run the whole pipeline. This tool closes that loop:
it grabs one real frame, overlays a fraction grid and the current storefront
lines, and lets you click two points to reposition any line and save it back to
the JSON layout.

Usage::

    python src/calibrate.py --video data/birdseye_street.mp4

    # Just render a reference image (no window), e.g. for headless checks:
    python src/calibrate.py --video data/birdseye_street.mp4 --preview-only

Interactive controls (shown on-screen):
    1-9        select the storefront to edit
    left-click click the two endpoints of the selected line
    f          flip the selected line's IN/OUT direction
    g          toggle the fraction grid
    u          undo a half-placed point
    s          save the layout back to JSON
    r          reload the layout from JSON (discard changes)
    q / ESC    quit
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

from config import (
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    OUTPUT_DIR,
    STOREFRONTS_SUFFIX,
    VIS_STOREFRONT_COLORS,
)
from storefront import Storefront, StorefrontConfigError, load_storefronts, save_storefronts

logger = logging.getLogger("store_traffic_counter.calibrate")

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_DISPLAY_WIDTH = 1280  # downscale the (often 4K) frame to a workable window size
_WINDOW = "Storefront Calibration"
_GRID_COLOR = (90, 90, 90)
_GRID_LABEL_COLOR = (200, 200, 200)
_ACTIVE_OUTLINE = (255, 255, 255)
_PENDING_COLOR = (0, 255, 255)


def build_parser() -> argparse.ArgumentParser:
    """Construct the calibration CLI parser."""
    parser = argparse.ArgumentParser(
        prog="calibrate-storefronts",
        description="Visually align storefront tripwires on a reference frame.",
    )
    parser.add_argument("--video", required=True, help="Input video file or image-sequence frame.")
    parser.add_argument(
        "--storefronts",
        default=None,
        metavar="PATH",
        help=f"Storefront JSON layout (default: sibling '<video>{STOREFRONTS_SUFFIX}').",
    )
    parser.add_argument(
        "--frame",
        type=int,
        default=-1,
        help="Frame index to calibrate against (default: middle frame).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help=f"Preview image path (default: {OUTPUT_DIR}/storefront_calibration.jpg).",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Render the annotated reference image and exit (no interactive window).",
    )
    parser.add_argument("--no-grid", action="store_true", help="Hide the fraction grid.")
    return parser


def _resolve_layout_path(args: argparse.Namespace) -> Path:
    """Return the storefront layout path from --storefronts or the sibling convention."""
    if args.storefronts:
        return Path(args.storefronts)
    sibling = Path(args.video).with_suffix("")
    return sibling.with_name(sibling.name + STOREFRONTS_SUFFIX)


def _grab_frame(video: str, frame_index: int) -> np.ndarray:
    """Read a single frame from the video; -1 selects the middle frame."""
    capture = cv2.VideoCapture(video)
    if not capture.isOpened():
        raise RuntimeError(f"Failed to open video: {video}")
    try:
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        target = frame_index if frame_index >= 0 else max(0, total // 2)
        capture.set(cv2.CAP_PROP_POS_FRAMES, float(target))
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Failed to read frame {target} from {video}.")
        logger.info("Loaded frame %d/%d from %s.", target, total, video)
        return frame
    finally:
        capture.release()


class _CalibrationCanvas:
    """Holds the reference frame and renders storefront lines in display space.

    All interaction happens in a downscaled display image; endpoints are stored
    as frame fractions so the result is resolution-independent.
    """

    def __init__(self, frame: np.ndarray, storefronts: list[Storefront]) -> None:
        self._frame = frame
        self.height, self.width = frame.shape[:2]
        self.disp_w = _DISPLAY_WIDTH
        self.disp_h = round(_DISPLAY_WIDTH * self.height / self.width)
        self._base = cv2.resize(frame, (self.disp_w, self.disp_h))
        self.storefronts: list[Storefront] = list(storefronts)
        self.active = 0
        self.pending: tuple[int, int] | None = None
        self.show_grid = True

    def _to_px(self, fraction: tuple[float, float]) -> tuple[int, int]:
        return int(fraction[0] * self.disp_w), int(fraction[1] * self.disp_h)

    def to_fraction(self, px: tuple[int, int]) -> tuple[float, float]:
        """Convert a display-space click to clamped frame fractions."""
        x = min(max(px[0] / self.disp_w, 0.0), 1.0)
        y = min(max(px[1] / self.disp_h, 0.0), 1.0)
        return round(x, 4), round(y, 4)

    def color_for(self, index: int) -> tuple[int, int, int]:
        return VIS_STOREFRONT_COLORS[index % len(VIS_STOREFRONT_COLORS)]

    def place_point(self, px: tuple[int, int]) -> None:
        """Record a click: first sets a pending start, second commits the line."""
        if not self.storefronts:
            return
        if self.pending is None:
            self.pending = px
            return
        start = self.to_fraction(self.pending)
        end = self.to_fraction(px)
        current = self.storefronts[self.active]
        self.storefronts[self.active] = Storefront(
            name=current.name,
            start=start,
            end=end,
            hysteresis=current.hysteresis,
            debounce_frames=current.debounce_frames,
        )
        self.pending = None
        logger.info("Set %r line: start=%s end=%s.", current.name, start, end)

    def flip_active(self) -> None:
        """Swap the active line's endpoints, reversing which side counts as IN."""
        if not self.storefronts:
            return
        current = self.storefronts[self.active]
        self.storefronts[self.active] = Storefront(
            name=current.name,
            start=current.end,
            end=current.start,
            hysteresis=current.hysteresis,
            debounce_frames=current.debounce_frames,
        )
        logger.info("Flipped %r IN/OUT direction.", current.name)

    def render(self) -> np.ndarray:
        """Return the display image with grid, lines, labels, and help text."""
        canvas = self._base.copy()
        if self.show_grid:
            self._draw_grid(canvas)
        for index, store in enumerate(self.storefronts):
            self._draw_line(canvas, index, store)
        if self.pending is not None:
            cv2.circle(canvas, self.pending, 5, _PENDING_COLOR, -1)
        self._draw_help(canvas)
        return canvas

    def _draw_grid(self, canvas: np.ndarray) -> None:
        for i in range(1, 10):
            frac = i / 10
            x = int(frac * self.disp_w)
            y = int(frac * self.disp_h)
            cv2.line(canvas, (x, 0), (x, self.disp_h), _GRID_COLOR, 1)
            cv2.line(canvas, (0, y), (self.disp_w, y), _GRID_COLOR, 1)
            cv2.putText(canvas, f"{frac:.1f}", (x + 2, 14), _FONT, 0.4, _GRID_LABEL_COLOR, 1, cv2.LINE_AA)
            cv2.putText(canvas, f"{frac:.1f}", (2, y - 3), _FONT, 0.4, _GRID_LABEL_COLOR, 1, cv2.LINE_AA)

    def _draw_line(self, canvas: np.ndarray, index: int, store: Storefront) -> None:
        color = self.color_for(index)
        start = self._to_px(store.start)
        end = self._to_px(store.end)
        if index == self.active:
            cv2.line(canvas, start, end, _ACTIVE_OUTLINE, 5)  # halo behind the active line
        cv2.line(canvas, start, end, color, 2)
        self._draw_in_arrow(canvas, start, end, color)
        label = f"{index + 1}: {store.name}"
        mx, my = (start[0] + end[0]) // 2, (start[1] + end[1]) // 2
        (tw, th), base = cv2.getTextSize(label, _FONT, 0.5, 1)
        cv2.rectangle(canvas, (mx, my - th - base), (mx + tw, my), color, -1)
        cv2.putText(canvas, label, (mx, my - base), _FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    @staticmethod
    def _draw_in_arrow(
        canvas: np.ndarray, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]
    ) -> None:
        """Draw a short arrow from the line midpoint toward the IN ('below') side."""
        (x1, y1), (x2, y2) = start, end
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        px, py = -dy / length, dx / length  # perpendicular = IN side
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tip = (int(mx + px * 28), int(my + py * 28))
        cv2.arrowedLine(canvas, (int(mx), int(my)), tip, color, 2, tipLength=0.4)
        cv2.putText(canvas, "IN", (tip[0] + 3, tip[1]), _FONT, 0.4, color, 1, cv2.LINE_AA)

    def _draw_help(self, canvas: np.ndarray) -> None:
        lines = [
            "1-9 select | click 2 pts set line | f flip IN/OUT | g grid | u undo | s save | r reload | q quit",
        ]
        if self.storefronts:
            lines.append(f"editing [{self.active + 1}] {self.storefronts[self.active].name}")
        for i, text in enumerate(lines):
            (tw, th), _ = cv2.getTextSize(text, _FONT, 0.5, 1)
            top = self.disp_h - (len(lines) - i) * 24 - 6
            cv2.rectangle(canvas, (4, top), (4 + tw + 8, top + th + 10), (0, 0, 0), -1)
            cv2.putText(canvas, text, (8, top + th + 4), _FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def _run_interactive(canvas: _CalibrationCanvas, layout_path: Path) -> int:
    """Run the interactive click-to-align loop; returns a process exit code."""
    try:
        cv2.namedWindow(_WINDOW, cv2.WINDOW_AUTOSIZE)
    except cv2.error as exc:  # pragma: no cover - headless environments
        logger.error("No display available (%s). Re-run with --preview-only.", exc)
        return 1

    def on_mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            canvas.place_point((x, y))

    cv2.setMouseCallback(_WINDOW, on_mouse)
    logger.info("Interactive calibration ready. Edit lines, press 's' to save, 'q' to quit.")

    while True:
        cv2.imshow(_WINDOW, canvas.render())
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            break
        if ord("1") <= key <= ord("9"):
            index = key - ord("1")
            if index < len(canvas.storefronts):
                canvas.active = index
                canvas.pending = None
        elif key == ord("g"):
            canvas.show_grid = not canvas.show_grid
        elif key == ord("f"):
            canvas.flip_active()
        elif key == ord("u"):
            canvas.pending = None
        elif key == ord("s"):
            save_storefronts(layout_path, canvas.storefronts)
        elif key == ord("r"):
            try:
                canvas.storefronts = load_storefronts(layout_path)
                canvas.active = min(canvas.active, len(canvas.storefronts) - 1)
                canvas.pending = None
            except StorefrontConfigError as exc:
                logger.error("Reload failed: %s", exc)

    cv2.destroyAllWindows()
    return 0


def run(args: argparse.Namespace) -> int:
    """Load the frame and layout, then preview or calibrate interactively."""
    layout_path = _resolve_layout_path(args)
    try:
        storefronts = load_storefronts(layout_path)
    except StorefrontConfigError as exc:
        logger.error("Could not load storefront layout: %s", exc)
        return 2

    try:
        frame = _grab_frame(args.video, args.frame)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    canvas = _CalibrationCanvas(frame, storefronts)
    canvas.show_grid = not args.no_grid

    if args.preview_only:
        output = Path(args.output) if args.output else OUTPUT_DIR / "storefront_calibration.jpg"
        output.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output), canvas.render())
        logger.info("Saved calibration preview to %s.", output)
        return 0

    return _run_interactive(canvas, layout_path)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run calibration."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
