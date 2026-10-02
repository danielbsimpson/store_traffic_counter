"""Unit tests for the person detection module."""

from __future__ import annotations

import numpy as np
import pytest

from detector import (
    Detection,
    DetectionResult,
    Detector,
    DetectorError,
    OpenCVDetector,
    create_detector,
)


class _FakeDetector(Detector):
    """Test double returning a fixed set of raw detections."""

    def __init__(self, raw: list[Detection], **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._raw = raw

    def _infer(self, frame: np.ndarray) -> list[Detection]:
        return self._raw


def test_detection_centroid() -> None:
    det = Detection(box=(10, 20, 30, 40), confidence=0.9)
    assert det.centroid == (20, 30)
    assert det.class_label == "person"


def test_detect_filters_below_threshold() -> None:
    raw = [
        Detection(box=(0, 0, 10, 10), confidence=0.9),
        Detection(box=(0, 0, 10, 10), confidence=0.4),
        Detection(box=(0, 0, 10, 10), confidence=0.5),
    ]
    detector = _FakeDetector(raw, confidence_threshold=0.5)
    result = detector.detect(np.zeros((20, 20, 3), dtype=np.uint8))
    assert isinstance(result, DetectionResult)
    assert len(result.detections) == 2
    assert all(d.confidence >= 0.5 for d in result.detections)


def test_detect_records_inference_time() -> None:
    detector = _FakeDetector([], confidence_threshold=0.5)
    result = detector.detect(np.zeros((20, 20, 3), dtype=np.uint8))
    assert result.inference_ms >= 0.0


def test_invalid_threshold_raises() -> None:
    with pytest.raises(DetectorError):
        _FakeDetector([], confidence_threshold=1.5)
    with pytest.raises(DetectorError):
        _FakeDetector([], confidence_threshold=-0.1)


def test_create_detector_opencv_returns_opencv() -> None:
    detector = create_detector(model="opencv", confidence_threshold=0.5)
    assert isinstance(detector, OpenCVDetector)


def test_create_detector_unknown_raises() -> None:
    with pytest.raises(DetectorError):
        create_detector(model="nonexistent")


def test_opencv_detector_runs_and_returns_valid_format() -> None:
    detector = OpenCVDetector(confidence_threshold=0.5)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)
    assert isinstance(result.detections, list)
    for det in result.detections:
        assert len(det.box) == 4
        assert 0.0 <= det.confidence <= 1.0
        assert det.confidence >= 0.5
        assert det.class_label == "person"


def test_score_to_confidence_is_bounded() -> None:
    assert OpenCVDetector._score_to_confidence(0.0) == pytest.approx(0.5)
    assert 0.0 < OpenCVDetector._score_to_confidence(-10.0) < 0.5
    assert 0.5 < OpenCVDetector._score_to_confidence(10.0) < 1.0


def test_yolo_detector_returns_correct_format() -> None:
    """YOLO path is validated only when ultralytics is installed."""
    pytest.importorskip("ultralytics")
    from detector import YOLODetector

    detector = YOLODetector(confidence_threshold=0.5)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)
    for det in result.detections:
        assert len(det.box) == 4
        assert 0.0 <= det.confidence <= 1.0
        assert det.class_label == "person"
