"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

# Make the src/ package importable in tests.
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))


@pytest.fixture()
def image_sequence_dir(tmp_path: Path) -> Path:
    """Create a minimal MOT17-style image sequence with a seqinfo.ini."""
    seq_dir = tmp_path / "MOT17-TEST"
    img_dir = seq_dir / "img1"
    img_dir.mkdir(parents=True)

    frame_count = 5
    width, height = 640, 480
    for i in range(1, frame_count + 1):
        frame = np.full((height, width, 3), i * 10, dtype=np.uint8)
        cv2.imwrite(str(img_dir / f"{i:06d}.jpg"), frame)

    seqinfo = seq_dir / "seqinfo.ini"
    seqinfo.write_text(
        "[Sequence]\n"
        "name=MOT17-TEST\n"
        "imDir=img1\n"
        "frameRate=30\n"
        f"seqLength={frame_count}\n"
        f"imWidth={width}\n"
        f"imHeight={height}\n"
        "imExt=.jpg\n"
    )
    return seq_dir


@pytest.fixture()
def video_file(tmp_path: Path) -> Path:
    """Create a small synthetic MP4 video file."""
    path = tmp_path / "sample.mp4"
    width, height, frame_count = 640, 480, 10
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (width, height))
    for i in range(frame_count):
        frame = np.full((height, width, 3), i * 20, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path
