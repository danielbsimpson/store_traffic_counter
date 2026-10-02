"""Store Traffic Counter - command-line entry point.

Loads an input source (video file or MOT17 image sequence), runs person
detection and centroid tracking, and renders real-time overlays that can be
displayed live and/or saved to an annotated video. Tripwire counting and data
export are added in later phases.
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
    ESC_KEY,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    OUTPUT_DIR,
)
from detector import DetectorError, create_detector
from tracker import CentroidTracker
from visualizer import VideoVisualizer
from video_loader import VideoLoadError, VideoProcessor

logger = logging.getLogger("store_traffic_counter")


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
    """Run detection, tracking, and real-time visualization."""
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
        )
    except DetectorError as exc:
        logger.error("Failed to initialize detector: %s", exc)
        return 1

    tracker = CentroidTracker()
    visualizer = VideoVisualizer()

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

            writer = _create_writer(args, info, output_dir) if args.save_video else None
            window = f"Store Traffic Counter - {info.name}"

            processed = 0
            total_detections = 0
            total_inference_ms = 0.0
            log_interval = max(1, info.frame_count // 20) if info.frame_count else 50

            try:
                for frame_number, frame in processor.frames():
                    loop_start = time.perf_counter()
                    result = detector.detect(frame)
                    tracked = tracker.update(result.detections, frame_number)

                    processed += 1
                    total_detections += len(result.detections)
                    total_inference_ms += result.inference_ms

                    fps = 1.0 / max(time.perf_counter() - loop_start, 1e-6)
                    annotated = visualizer.annotate(
                        frame,
                        tracked,
                        frame_number=frame_number,
                        fps=fps,
                        active_tracks=len(tracker.active_ids),
                        total_tracks=tracker.total_registered,
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
                if args.save_video:
                    logger.info("Saved annotated video to %s.", _output_video_path(info, output_dir))
            else:
                logger.warning("No frames were processed from '%s'.", info.name)
    except VideoLoadError as exc:
        logger.error("Failed to load input: %s", exc)
        return 1

    return 0


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
