"""Store Traffic Counter - command-line entry point.

Phase 1 scope: load an input source (video file or MOT17 image sequence),
validate it, and report frame metadata. Detection, tracking, counting, and
export are added in later phases.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    OUTPUT_DIR,
)
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
        help="Show the real-time visualization window.",
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
    """Execute the Phase 1 pipeline: load and inspect the input source."""
    if not 0.0 <= args.confidence <= 1.0:
        logger.error("Confidence must be between 0.0 and 1.0 (got %s).", args.confidence)
        return 2

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Output directory ready: %s", output_dir)

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
            processed = 0
            for _frame_number, _frame in processor.frames():
                processed += 1
            logger.info("Read %d frames from '%s'.", processed, info.name)
    except VideoLoadError as exc:
        logger.error("Failed to load input: %s", exc)
        return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the pipeline."""
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
