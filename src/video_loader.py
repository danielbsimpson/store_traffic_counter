"""Video input handling for the Store Traffic Counter pipeline.

Supports two input modes:
  - Standard video files (MP4, AVI, MOV, MKV) via OpenCV's VideoCapture.
  - MOT17-style image sequences (a directory of ``%06d.jpg`` frames with a
    ``seqinfo.ini`` describing frame rate and resolution).
"""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from config import (
    DEFAULT_FRAME_RATE,
    IMAGE_EXTENSIONS,
    MIN_FRAME_HEIGHT,
    MIN_FRAME_WIDTH,
    MOT_IMAGE_SUBDIR,
    MOT_SEQINFO_FILE,
    VIDEO_EXTENSIONS,
)

logger = logging.getLogger(__name__)


class VideoLoadError(Exception):
    """Raised when an input source cannot be opened or is unsupported."""


@dataclass(frozen=True)
class SequenceInfo:
    """Metadata describing a video or image-sequence input source."""

    name: str
    frame_rate: float
    width: int
    height: int
    frame_count: int
    source_type: str  # "video" or "image_sequence"


class VideoProcessor:
    """Reads frames from a video file or MOT17-style image sequence.

    Use as a context manager or call :meth:`frames` to iterate. The input
    source is auto-detected: a file with a known video extension is treated as
    a video; a directory is treated as an image sequence.
    """

    def __init__(self, source: str | Path) -> None:
        self._source = Path(source)
        self._info: SequenceInfo | None = None
        self._capture: cv2.VideoCapture | None = None
        self._image_paths: list[Path] = []

        if not self._source.exists():
            raise VideoLoadError(f"Input source does not exist: {self._source}")

        if self._source.is_dir():
            self._init_image_sequence()
        elif self._source.suffix.lower() in VIDEO_EXTENSIONS:
            self._init_video_file()
        else:
            raise VideoLoadError(
                f"Unsupported input source: {self._source} "
                f"(expected a video file {VIDEO_EXTENSIONS} or an image-sequence directory)"
            )

    @property
    def info(self) -> SequenceInfo:
        """Return metadata for the opened source."""
        if self._info is None:  # pragma: no cover - guarded by constructor
            raise VideoLoadError("Input source has not been initialized.")
        return self._info

    def _init_video_file(self) -> None:
        capture = cv2.VideoCapture(str(self._source))
        if not capture.isOpened():
            raise VideoLoadError(f"Failed to open video file: {self._source}")

        frame_rate = capture.get(cv2.CAP_PROP_FPS) or DEFAULT_FRAME_RATE
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        self._capture = capture
        self._info = SequenceInfo(
            name=self._source.stem,
            frame_rate=float(frame_rate),
            width=width,
            height=height,
            frame_count=frame_count,
            source_type="video",
        )
        self._validate_dimensions()
        logger.info(
            "Opened video '%s': %dx%d @ %.2f FPS, %d frames",
            self._info.name,
            width,
            height,
            self._info.frame_rate,
            frame_count,
        )

    def _init_image_sequence(self) -> None:
        image_dir = self._resolve_image_dir()
        self._image_paths = self._collect_image_paths(image_dir)
        if not self._image_paths:
            raise VideoLoadError(f"No image frames found in: {image_dir}")

        meta = self._read_seqinfo()
        first = cv2.imread(str(self._image_paths[0]))
        if first is None:
            raise VideoLoadError(f"Failed to read first frame: {self._image_paths[0]}")
        height, width = first.shape[:2]

        self._info = SequenceInfo(
            name=meta.get("name", self._source.name),
            frame_rate=meta.get("frame_rate", DEFAULT_FRAME_RATE),
            width=meta.get("width", width),
            height=meta.get("height", height),
            frame_count=len(self._image_paths),
            source_type="image_sequence",
        )
        self._validate_dimensions()
        logger.info(
            "Opened image sequence '%s': %dx%d @ %.2f FPS, %d frames",
            self._info.name,
            self._info.width,
            self._info.height,
            self._info.frame_rate,
            self._info.frame_count,
        )

    def _resolve_image_dir(self) -> Path:
        """Return the directory holding frames (MOT17 nests them in img1/)."""
        nested = self._source / MOT_IMAGE_SUBDIR
        if nested.is_dir():
            return nested
        return self._source

    @staticmethod
    def _collect_image_paths(image_dir: Path) -> list[Path]:
        paths = [
            p
            for p in image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ]
        return sorted(paths, key=lambda p: p.name)

    def _read_seqinfo(self) -> dict[str, object]:
        """Parse MOT17 seqinfo.ini if present; return available metadata."""
        seqinfo_path = self._source / MOT_SEQINFO_FILE
        if not seqinfo_path.is_file():
            logger.warning(
                "No %s found in %s; using defaults and detected dimensions.",
                MOT_SEQINFO_FILE,
                self._source,
            )
            return {}

        parser = configparser.ConfigParser()
        parser.read(seqinfo_path)
        if not parser.has_section("Sequence"):
            logger.warning("%s missing [Sequence] section.", seqinfo_path)
            return {}

        section = parser["Sequence"]
        meta: dict[str, object] = {}
        if "name" in section:
            meta["name"] = section["name"]
        if "frameRate" in section:
            meta["frame_rate"] = section.getfloat("frameRate")
        if "imWidth" in section:
            meta["width"] = section.getint("imWidth")
        if "imHeight" in section:
            meta["height"] = section.getint("imHeight")
        return meta

    def _validate_dimensions(self) -> None:
        assert self._info is not None
        if self._info.width < MIN_FRAME_WIDTH or self._info.height < MIN_FRAME_HEIGHT:
            raise VideoLoadError(
                f"Frame dimensions {self._info.width}x{self._info.height} below "
                f"minimum {MIN_FRAME_WIDTH}x{MIN_FRAME_HEIGHT}."
            )

    def frames(self) -> Iterator[tuple[int, np.ndarray]]:
        """Yield ``(frame_number, frame)`` pairs, 1-indexed.

        Corrupted or unreadable frames are skipped with a warning rather than
        aborting the whole run.
        """
        if self._info is None:  # pragma: no cover - guarded by constructor
            raise VideoLoadError("Input source has not been initialized.")

        if self._info.source_type == "video":
            yield from self._iter_video_frames()
        else:
            yield from self._iter_image_frames()

    def _iter_video_frames(self) -> Iterator[tuple[int, np.ndarray]]:
        assert self._capture is not None
        frame_number = 0
        while True:
            ok, frame = self._capture.read()
            if not ok:
                break
            frame_number += 1
            if frame is None:
                logger.warning("Skipping unreadable frame %d.", frame_number)
                continue
            yield frame_number, frame

    def _iter_image_frames(self) -> Iterator[tuple[int, np.ndarray]]:
        for index, path in enumerate(self._image_paths, start=1):
            frame = cv2.imread(str(path))
            if frame is None:
                logger.warning("Skipping corrupted frame %d: %s", index, path)
                continue
            yield index, frame

    def release(self) -> None:
        """Release any underlying OpenCV resources."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "VideoProcessor":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()
