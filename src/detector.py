"""Person detection for the Store Traffic Counter pipeline.

Provides a common :class:`Detector` interface with two implementations:
  - :class:`YOLODetector` - Ultralytics YOLOv8 (auto-downloads weights).
  - :class:`OpenCVDetector` - OpenCV's built-in HOG + SVM pedestrian detector
    (fully offline, no weight download required).

All detectors return person detections in a standardized format and apply a
shared confidence threshold and inference-timing wrapper.
"""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import cv2
import numpy as np

from config import DEFAULT_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

PERSON_CLASS_LABEL: str = "person"
COCO_PERSON_CLASS_ID: int = 0


class DetectorError(Exception):
    """Raised when a detector cannot be constructed or run."""


@dataclass(frozen=True)
class Detection:
    """A single person detection.

    Attributes:
        box: Bounding box as ``(x1, y1, x2, y2)`` in pixel coordinates.
        confidence: Detection confidence in the range ``[0.0, 1.0]``.
        class_label: Object class label (always ``"person"`` in this PoC).
    """

    box: tuple[int, int, int, int]
    confidence: float
    class_label: str = PERSON_CLASS_LABEL

    @property
    def centroid(self) -> tuple[int, int]:
        """Return the box center as ``(cx, cy)``."""
        x1, y1, x2, y2 = self.box
        return (x1 + x2) // 2, (y1 + y2) // 2


@dataclass
class DetectionResult:
    """Detections for one frame plus the inference time that produced them."""

    detections: list[Detection] = field(default_factory=list)
    inference_ms: float = 0.0


class Detector(ABC):
    """Abstract base class defining the detection interface.

    Subclasses implement :meth:`_infer`; the public :meth:`detect` wraps it with
    confidence filtering and inference-time measurement.
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        device: str = "cpu",
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise DetectorError(
                f"confidence_threshold must be in [0.0, 1.0], got {confidence_threshold}."
            )
        self.confidence_threshold = confidence_threshold
        self.device = device

    @abstractmethod
    def _infer(self, frame: np.ndarray) -> list[Detection]:
        """Run model inference on a BGR frame and return raw detections."""

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """Detect persons in a frame, filtering by confidence and timing it."""
        start = time.perf_counter()
        raw = self._infer(frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        filtered = [d for d in raw if d.confidence >= self.confidence_threshold]
        return DetectionResult(detections=filtered, inference_ms=elapsed_ms)


class YOLODetector(Detector):
    """Person detector backed by Ultralytics YOLOv8.

    Weights are downloaded automatically on first use (default ``yolov8n.pt``).
    """

    def __init__(
        self,
        weights: str = "yolov8n.pt",
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        device: str = "cpu",
    ) -> None:
        super().__init__(confidence_threshold, device)
        try:
            from ultralytics import YOLO  # lazy import: heavy dependency
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise DetectorError(
                "ultralytics is not installed. Install it with "
                "'pip install ultralytics' to use the YOLO detector."
            ) from exc

        self._device = 0 if device == "gpu" else "cpu"
        try:
            self._model = YOLO(weights)
        except Exception as exc:  # pragma: no cover - network/weights dependent
            raise DetectorError(f"Failed to load YOLO weights '{weights}': {exc}") from exc
        logger.info("Loaded YOLO detector (weights=%s, device=%s).", weights, device)

    def _infer(self, frame: np.ndarray) -> list[Detection]:
        results = self._model.predict(
            frame,
            classes=[COCO_PERSON_CLASS_ID],
            conf=self.confidence_threshold,
            device=self._device,
            verbose=False,
        )
        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append(
                    Detection(box=(x1, y1, x2, y2), confidence=float(box.conf[0]))
                )
        return detections


class OpenCVDetector(Detector):
    """Person detector using OpenCV's built-in HOG + SVM pedestrian model.

    Requires no external weights, making it a fully offline fallback. HOG SVM
    decision scores are mapped to a ``[0, 1]`` confidence via a logistic
    function so they are comparable to YOLO confidences.
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        device: str = "cpu",
    ) -> None:
        super().__init__(confidence_threshold, device)
        if device == "gpu":
            logger.warning("OpenCV HOG detector runs on CPU only; ignoring --device gpu.")
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        logger.info("Loaded OpenCV HOG pedestrian detector.")

    @staticmethod
    def _score_to_confidence(score: float) -> float:
        """Map an unbounded HOG SVM score to a [0, 1] confidence."""
        return 1.0 / (1.0 + math.exp(-score))

    def _infer(self, frame: np.ndarray) -> list[Detection]:
        rects, weights = self._hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        detections: list[Detection] = []
        for (x, y, w, h), score in zip(rects, weights):
            confidence = self._score_to_confidence(float(score))
            detections.append(
                Detection(box=(int(x), int(y), int(x + w), int(y + h)), confidence=confidence)
            )
        return detections


def create_detector(
    model: str = "yolo",
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    device: str = "cpu",
    weights: str | None = None,
) -> Detector:
    """Construct a detector by name.

    Args:
        model: ``"yolo"`` or ``"opencv"``.
        confidence_threshold: Minimum confidence to keep a detection.
        device: ``"cpu"`` or ``"gpu"`` (YOLO only).
        weights: Optional YOLO weights path/name; ignored for OpenCV.

    Raises:
        DetectorError: If ``model`` is not recognized.
    """
    if model == "yolo":
        return YOLODetector(
            weights=weights or "yolov8n.pt",
            confidence_threshold=confidence_threshold,
            device=device,
        )
    if model == "opencv":
        return OpenCVDetector(confidence_threshold=confidence_threshold, device=device)
    raise DetectorError(f"Unknown model '{model}'. Choose 'yolo' or 'opencv'.")
