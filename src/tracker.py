"""Centroid-based multi-object tracking for the Store Traffic Counter pipeline.

Assigns persistent integer IDs to person detections across frames by matching
each new detection to the nearest existing track (by centroid distance). Tracks
that go unseen for longer than a timeout are deregistered.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from config import (
    TRACK_STATIC_MAX_DISPLACEMENT,
    TRACK_STATIC_WINDOW,
    TRACKER_MAX_DISAPPEARED,
    TRACKER_MAX_DISTANCE,
)
from detector import Detection

logger = logging.getLogger(__name__)


def _foot_point(box: tuple[int, int, int, int]) -> tuple[int, int]:
    """Bottom-center of a box, where the person meets the floor."""
    x1, _, x2, y2 = box
    return (x1 + x2) // 2, y2


@dataclass(frozen=True)
class TrackedObject:
    """A person detection associated with a persistent track ID."""

    id: int
    box: tuple[int, int, int, int]
    centroid: tuple[int, int]
    confidence: float
    frame_number: int
    is_static: bool = False  # fixed scene object (mannequin/standee/sign), not a pedestrian

    @property
    def foot(self) -> tuple[int, int]:
        """Bottom-center of the box, where the person meets the floor.

        More reliable than the centroid for ground-plane reasoning (tripwire
        crossings, proximity) in perspective scenes, since feet sit on the
        floor while the centroid floats at torso height.
        """
        return _foot_point(self.box)


class CentroidTracker:
    """Tracks persons across frames using nearest-centroid matching.

    Args:
        max_distance: Maximum centroid distance (pixels) allowed to match a
            detection to an existing track.
        max_disappeared: Number of consecutive frames a track may be unseen
            before it is removed.
    """

    def __init__(
        self,
        max_distance: float = TRACKER_MAX_DISTANCE,
        max_disappeared: int = TRACKER_MAX_DISAPPEARED,
        static_window: int = TRACK_STATIC_WINDOW,
        static_max_displacement: float = TRACK_STATIC_MAX_DISPLACEMENT,
    ) -> None:
        self.max_distance = max_distance
        self.max_disappeared = max_disappeared
        self.static_window = static_window
        self.static_max_displacement = static_max_displacement
        self._next_id = 0
        self._objects: dict[int, TrackedObject] = {}
        self._disappeared: dict[int, int] = {}
        self._history: dict[int, deque[tuple[int, int]]] = {}

    @property
    def active_ids(self) -> list[int]:
        """IDs currently being tracked (including temporarily unseen)."""
        return list(self._objects.keys())

    @property
    def total_registered(self) -> int:
        """Total number of distinct tracks registered over the tracker's life."""
        return self._next_id

    def _register(self, detection: Detection, frame_number: int) -> None:
        object_id = self._next_id
        self._record_position(object_id, detection)
        obj = TrackedObject(
            id=object_id,
            box=detection.box,
            centroid=detection.centroid,
            confidence=detection.confidence,
            frame_number=frame_number,
            is_static=self._is_static(object_id),
        )
        self._objects[object_id] = obj
        self._disappeared[object_id] = 0
        logger.debug("Registered track %d at %s (frame %d).", object_id, obj.centroid, frame_number)
        self._next_id += 1

    def _deregister(self, object_id: int) -> None:
        logger.debug("Deregistered track %d.", object_id)
        self._objects.pop(object_id, None)
        self._disappeared.pop(object_id, None)
        self._history.pop(object_id, None)

    def _record_position(self, object_id: int, detection: Detection) -> None:
        """Append this frame's foot point to the track's trailing motion window."""
        history = self._history.get(object_id)
        if history is None:
            history = deque(maxlen=self.static_window)
            self._history[object_id] = history
        history.append(_foot_point(detection.box))

    def _is_static(self, object_id: int) -> bool:
        """True once a track has filled its window with near-zero net motion."""
        history = self._history.get(object_id)
        if history is None or len(history) < self.static_window:
            return False
        (x0, y0), (x1, y1) = history[0], history[-1]
        return math.hypot(x1 - x0, y1 - y0) < self.static_max_displacement

    def _mark_all_disappeared(self) -> None:
        for object_id in list(self._disappeared.keys()):
            self._disappeared[object_id] += 1
            if self._disappeared[object_id] > self.max_disappeared:
                self._deregister(object_id)

    def update(
        self, detections: list[Detection], frame_number: int
    ) -> list[TrackedObject]:
        """Update tracks with the current frame's detections.

        Returns the tracked objects matched or registered in this frame (i.e.
        those with a current position). Temporarily unseen tracks are retained
        internally but not returned until seen again.
        """
        if not detections:
            self._mark_all_disappeared()
            return []

        input_centroids = np.array([d.centroid for d in detections], dtype=float)

        if not self._objects:
            for detection in detections:
                self._register(detection, frame_number)
        else:
            self._match_detections(detections, input_centroids, frame_number)

        return [
            obj for obj_id, obj in self._objects.items() if self._disappeared[obj_id] == 0
        ]

    def _match_detections(
        self,
        detections: list[Detection],
        input_centroids: np.ndarray,
        frame_number: int,
    ) -> None:
        object_ids = list(self._objects.keys())
        object_centroids = np.array(
            [self._objects[oid].centroid for oid in object_ids], dtype=float
        )

        # Pairwise Euclidean distances: rows = existing tracks, cols = new detections.
        distances = np.linalg.norm(
            object_centroids[:, None, :] - input_centroids[None, :, :], axis=2
        )

        # Greedily match smallest distances first.
        rows = distances.min(axis=1).argsort()
        cols = distances.argmin(axis=1)[rows]

        used_rows: set[int] = set()
        used_cols: set[int] = set()
        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if distances[row, col] > self.max_distance:
                continue
            object_id = object_ids[row]
            detection = detections[col]
            self._record_position(object_id, detection)
            self._objects[object_id] = TrackedObject(
                id=object_id,
                box=detection.box,
                centroid=detection.centroid,
                confidence=detection.confidence,
                frame_number=frame_number,
                is_static=self._is_static(object_id),
            )
            self._disappeared[object_id] = 0
            used_rows.add(row)
            used_cols.add(col)

        unused_rows = set(range(distances.shape[0])) - used_rows
        unused_cols = set(range(distances.shape[1])) - used_cols

        for row in unused_rows:
            object_id = object_ids[row]
            self._disappeared[object_id] += 1
            if self._disappeared[object_id] > self.max_disappeared:
                self._deregister(object_id)

        for col in unused_cols:
            self._register(detections[col], frame_number)
