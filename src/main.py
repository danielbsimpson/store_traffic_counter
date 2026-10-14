"""Store Traffic Counter - command-line entry point.

Loads an input source (video file or MOT17 image sequence), runs person
detection, centroid tracking, and tripwire crossing counting, and renders
real-time overlays that can be displayed live and/or saved to an annotated
video. Structured CSV/JSON data export is added in a later phase.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2

from config import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_YOLO_IMGSZ,
    ESC_KEY,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    OUTPUT_DIR,
    STOREFRONTS_SUFFIX,
    TRIPWIRE_POSITION,
)
from counter import TripwireCounter
from detector import DetectorError, create_detector
from storefront import StorefrontConfigError, StorefrontCounter, load_storefronts
from tracker import CentroidTracker
from visualizer import VideoVisualizer
from video_loader import VideoLoadError, VideoProcessor

logger = logging.getLogger("store_traffic_counter")


def _parse_fraction_pair(value: str) -> tuple[float, float]:
    """Parse a tripwire endpoint given as 'X,Y' fractions (each 0.0-1.0)."""
    try:
        x_str, y_str = value.split(",")
        return float(x_str), float(y_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected 'X,Y' fractions (e.g. '0.0,0.5'), got {value!r}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="store-traffic-counter",
        description="Count customers entering/exiting a store from video or image sequences.",
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Path to an input video file or a MOT17-style image-sequence directory.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR),
        help=f"Directory for logs and results (default: {OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--model",
        choices=("yolo", "opencv"),
        default="yolo",
        help="Vision model to use for person detection (default: yolo).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Detection confidence threshold 0.0-1.0 (default: {DEFAULT_CONFIDENCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=DEFAULT_YOLO_IMGSZ,
        help=(
            "YOLO inference resolution (long edge). Larger values recover small, "
            f"distant people in high-res scenes at the cost of speed (default: {DEFAULT_YOLO_IMGSZ}). "
            "YOLO only; ignored for --model opencv."
        ),
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "gpu"),
        default="cpu",
        help="Processing device (default: cpu).",
    )
    parser.add_argument(
        "--display",
        action="store_true",
        help="Show the real-time visualization window (press ESC to quit).",
    )
    parser.add_argument(
        "--save-video",
        action="store_true",
        help="Save an annotated output video to the output directory.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Process at most this many frames (0 = all). Useful for quick visual checks.",
    )
    parser.add_argument(
        "--tripwire-start",
        type=_parse_fraction_pair,
        default=(0.0, TRIPWIRE_POSITION),
        metavar="X,Y",
        help=(
            "Tripwire start point as 'X,Y' fractions of frame width/height "
            f"(default: 0.0,{TRIPWIRE_POSITION}). Use with --tripwire-end to angle "
            "the line, e.g. to follow a storefront's perspective."
        ),
    )
    parser.add_argument(
        "--tripwire-end",
        type=_parse_fraction_pair,
        default=(1.0, TRIPWIRE_POSITION),
        metavar="X,Y",
        help=(
            "Tripwire end point as 'X,Y' fractions of frame width/height "
            f"(default: 1.0,{TRIPWIRE_POSITION})."
        ),
    )
    parser.add_argument(
        "--storefronts",
        default=None,
        metavar="PATH",
        help=(
            "Path to a JSON storefront layout defining one named tripwire per "
            "store entrance, each with its own in/out tally. When omitted, a "
            f"sibling '<video>{STOREFRONTS_SUFFIX}' file is auto-loaded if present; "
            "otherwise the single --tripwire line is used."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser


def configure_logging(verbose: bool) -> None:
    """Configure root logging format and level."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )


def run(args: argparse.Namespace) -> int:
    """Run detection, tracking, tripwire counting, and real-time visualization."""
    if not 0.0 <= args.confidence <= 1.0:
        logger.error("Confidence must be between 0.0 and 1.0 (got %s).", args.confidence)
        return 2

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Output directory ready: %s", output_dir)

    try:
        detector = create_detector(
            model=args.model,
            confidence_threshold=args.confidence,
            device=args.device,
            imgsz=args.imgsz,
        )
    except DetectorError as exc:
        logger.error("Failed to initialize detector: %s", exc)
        return 1

    tracker = CentroidTracker()

    try:
        storefronts = _resolve_storefronts(args)
    except StorefrontConfigError as exc:
        logger.error("Invalid storefront layout: %s", exc)
        return 2

    try:
        with VideoProcessor(args.video) as processor:
            info = processor.info
            logger.info(
                "Input '%s' ready: type=%s, %dx%d, %.2f FPS, %d frames.",
                info.name,
                info.source_type,
                info.width,
                info.height,
                info.frame_rate,
                info.frame_count,
            )

            window = f"Store Traffic Counter - {info.name}"
            use_stores = storefronts is not None
            try:
                if use_stores:
                    counter: TripwireCounter | StorefrontCounter = StorefrontCounter(
                        frame_width=info.width,
                        frame_height=info.height,
                        storefronts=storefronts,  # type: ignore[arg-type]
                    )
                    visualizer = VideoVisualizer(storefronts=counter.lines)
                    logger.info(
                        "Tracking %d storefront(s): %s.",
                        len(counter.names),
                        ", ".join(counter.names),
                    )
                else:
                    counter = TripwireCounter(
                        frame_width=info.width,
                        frame_height=info.height,
                        start=args.tripwire_start,
                        end=args.tripwire_end,
                    )
                    visualizer = VideoVisualizer(tripwire=counter.line)
            except ValueError as exc:
                logger.error("Invalid tripwire configuration: %s", exc)
                return 2
            writer = _create_writer(args, info, output_dir) if args.save_video else None

            processed = 0
            total_detections = 0
            total_inference_ms = 0.0
            log_interval = max(1, info.frame_count // 20) if info.frame_count else 50

            try:
                for frame_number, frame in processor.frames():
                    loop_start = time.perf_counter()
                    result = detector.detect(frame)
                    tracked = tracker.update(result.detections, frame_number)
                    # Drop fixed scene objects (mannequins, standees, signage)
                    # so they neither count nor clutter the overlay as people.
                    people = [t for t in tracked if not t.is_static]
                    events = counter.update(people, frame_number)
                    for event in events:
                        where = f"{event.storefront} " if event.storefront else ""
                        logger.info(
                            "Track %d crossed %stripwire -> %s (in=%d, out=%d).",
                            event.person_id,
                            where,
                            event.direction.upper(),
                            event.cumulative_in,
                            event.cumulative_out,
                        )

                    processed += 1
                    total_detections += len(result.detections)
                    total_inference_ms += result.inference_ms

                    fps = 1.0 / max(time.perf_counter() - loop_start, 1e-6)
                    annotated = visualizer.annotate(
                        frame,
                        people,
                        frame_number=frame_number,
                        fps=fps,
                        active_tracks=len(people),
                        total_tracks=tracker.total_registered,
                        counts=counter.totals if use_stores else counter.counts,
                        store_counts=counter.counts if use_stores else None,
                        events=events,
                    )

                    if writer is not None:
                        writer.write(annotated)

                    if args.display and not _show_frame(window, annotated):
                        logger.info("Display closed by user (ESC).")
                        break

                    if frame_number % log_interval == 0:
                        logger.info(
                            "Frame %d/%d: %d persons, %d active tracks (%.1f ms).",
                            frame_number,
                            info.frame_count,
                            len(result.detections),
                            len(tracked),
                            result.inference_ms,
                        )

                    if args.max_frames and processed >= args.max_frames:
                        logger.info("Reached --max-frames limit (%d).", args.max_frames)
                        break
            finally:
                if writer is not None:
                    writer.release()
                if args.display:
                    cv2.destroyAllWindows()

            if processed:
                avg_ms = total_inference_ms / processed
                avg_per_frame = total_detections / processed
                logger.info(
                    "Processed %d frames | %d total detections | %d unique tracks | "
                    "%.2f avg persons/frame | %.1f ms avg inference (%.1f FPS).",
                    processed,
                    total_detections,
                    tracker.total_registered,
                    avg_per_frame,
                    avg_ms,
                    1000.0 / avg_ms if avg_ms else 0.0,
                )
                _log_counts(counter, use_stores)
                if args.save_video:
                    logger.info("Saved annotated video to %s.", _output_video_path(info, output_dir))
            else:
                logger.warning("No frames were processed from '%s'.", info.name)
    except VideoLoadError as exc:
        logger.error("Failed to load input: %s", exc)
        return 1

    return 0


def _resolve_storefronts(args: argparse.Namespace) -> list | None:
    """Resolve storefront definitions from --storefronts or a sibling file.

    Returns the parsed storefronts, or ``None`` to fall back to the single
    --tripwire line. An explicit --storefronts path that is missing/invalid
    propagates a :class:`StorefrontConfigError`; the auto-detected sibling is
    best-effort and only used when it exists.
    """
    if args.storefronts:
        return load_storefronts(args.storefronts)

    sibling = Path(args.video).with_suffix("")
    sibling = sibling.with_name(sibling.name + STOREFRONTS_SUFFIX)
    if sibling.is_file():
        logger.info("Auto-loading storefront layout: %s", sibling)
        return load_storefronts(sibling)
    return None


def _log_counts(counter: TripwireCounter | StorefrontCounter, use_stores: bool) -> None:
    """Log the final in/out tally, per storefront when applicable."""
    if use_stores:
        assert isinstance(counter, StorefrontCounter)
        for name, (store_in, store_out) in counter.counts.items():
            logger.info(
                "  %s: IN=%d | OUT=%d | net=%d.",
                name,
                store_in,
                store_out,
                store_in - store_out,
            )
        total_in, total_out = counter.totals
    else:
        total_in, total_out = counter.counts
    logger.info(
        "Tripwire counts: IN=%d | OUT=%d | net occupancy=%d.",
        total_in,
        total_out,
        total_in - total_out,
    )


def _output_video_path(info: object, output_dir: Path) -> Path:
    """Return the annotated output video path for an input source."""
    return output_dir / f"annotated_{info.name}.mp4"  # type: ignore[attr-defined]


def _create_writer(
    args: argparse.Namespace, info: object, output_dir: Path
) -> cv2.VideoWriter:
    """Create a VideoWriter matching the input's dimensions and frame rate."""
    path = _output_video_path(info, output_dir)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        str(path),
        fourcc,
        info.frame_rate,  # type: ignore[attr-defined]
        (info.width, info.height),  # type: ignore[attr-defined]
    )
    logger.info("Writing annotated video to %s.", path)
    return writer


def _show_frame(window: str, frame: object) -> bool:
    """Display a frame; return False if the user pressed ESC."""
    try:
        cv2.imshow(window, frame)
        return (cv2.waitKey(1) & 0xFF) != ESC_KEY
    except cv2.error as exc:  # pragma: no cover - headless environments
        logger.warning("Display unavailable (%s); continuing without window.", exc)
        return True


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the pipeline."""
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
