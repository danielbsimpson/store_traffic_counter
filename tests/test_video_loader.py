"""Unit tests for the VideoProcessor input loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_loader import VideoLoadError, VideoProcessor


def test_load_image_sequence(image_sequence_dir: Path) -> None:
    """MOT17-style sequence loads and reads seqinfo.ini metadata."""
    with VideoProcessor(image_sequence_dir) as processor:
        info = processor.info
        assert info.source_type == "image_sequence"
        assert info.name == "MOT17-TEST"
        assert info.frame_rate == 30.0
        assert info.width == 640
        assert info.height == 480
        assert info.frame_count == 5


def test_image_sequence_yields_all_frames(image_sequence_dir: Path) -> None:
    """All frames are yielded with sequential 1-indexed numbering."""
    with VideoProcessor(image_sequence_dir) as processor:
        frame_numbers = [n for n, _ in processor.frames()]
    assert frame_numbers == [1, 2, 3, 4, 5]


def test_load_valid_mp4(video_file: Path) -> None:
    """A standard MP4 opens and reports video metadata."""
    with VideoProcessor(video_file) as processor:
        info = processor.info
        assert info.source_type == "video"
        assert info.width == 640
        assert info.height == 480
        assert info.frame_rate > 0


def test_video_yields_frames(video_file: Path) -> None:
    """Frames iterate and are 1-indexed."""
    with VideoProcessor(video_file) as processor:
        frame_numbers = [n for n, _ in processor.frames()]
    assert frame_numbers[0] == 1
    assert len(frame_numbers) >= 1


def test_missing_source_raises(tmp_path: Path) -> None:
    """A non-existent path raises VideoLoadError."""
    with pytest.raises(VideoLoadError):
        VideoProcessor(tmp_path / "does_not_exist.mp4")


def test_unsupported_format_raises(tmp_path: Path) -> None:
    """An unsupported file extension raises VideoLoadError."""
    bogus = tmp_path / "notes.txt"
    bogus.write_text("not a video")
    with pytest.raises(VideoLoadError):
        VideoProcessor(bogus)


def test_empty_image_dir_raises(tmp_path: Path) -> None:
    """A directory with no frames raises VideoLoadError."""
    empty = tmp_path / "empty_seq"
    empty.mkdir()
    with pytest.raises(VideoLoadError):
        VideoProcessor(empty)


def test_image_sequence_without_seqinfo(tmp_path: Path) -> None:
    """A flat image directory without seqinfo.ini still loads using defaults."""
    import cv2
    import numpy as np

    seq_dir = tmp_path / "flat_seq"
    seq_dir.mkdir()
    for i in range(1, 4):
        frame = np.full((480, 640, 3), i * 10, dtype=np.uint8)
        cv2.imwrite(str(seq_dir / f"{i:06d}.jpg"), frame)

    with VideoProcessor(seq_dir) as processor:
        info = processor.info
        assert info.frame_count == 3
        assert info.frame_rate == 30.0  # default
        assert info.width == 640
