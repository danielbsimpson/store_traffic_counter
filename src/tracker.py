"""Centroid-based multi-object tracking for the Store Traffic Counter pipeline.

Assigns persistent integer IDs to person detections across frames by matching
each new detection to the nearest existing track (by centroid distance). Tracks
that go unseen for longer than a timeout are deregistered.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from config import TRACKER_MAX_DISAPPEARED, TRACKER_MAX_DISTANCE
from detector import Detection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackedObject:
    """A person detection associated with a persistent track ID."""

    id: int
    box: tuple[int, int, int, int]
    centroid: tuple[int, int]
    confidence: float
    frame_number: int


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
    ) -> None:
        self.max_distance = max_distance
        self.max_disappeared = max_disappeared
        self._next_id = 0
        self._objects: dict[int, TrackedObject] = {}
        self._disappeared: dict[int, int] = {}

    @property
    def active_ids(self) -> list[int]:
        """IDs currently being tracked (including temporarily unseen)."""
        return list(self._objects.keys())

    @property
    def total_registered(self) -> int:
        """Total number of distinct tracks registered over the tracker's life."""
        return self._next_id

    def _register(self, detection: Detection, frame_number: int) -> None:
        obj = TrackedObject(
            id=self._next_id,
            box=detection.box,
            centroid=detection.centroid,
            confidence=detection.confidence,
            frame_number=frame_number,
        )
        self._objects[self._next_id] = obj
        self._disappeared[self._next_id] = 0
        logger.debug("Registered track %d at %s (frame %d).", self._next_id, obj.centroid, frame_number)
        self._next_id += 1

    def _deregister(self, object_id: int) -> None:
        logger.debug("Deregistered track %d.", object_id)
        self._objects.pop(object_id, None)
        self._disappeared.pop(object_id, None)

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
            self._objects[object_id] = TrackedObject(
                id=object_id,
                box=detection.box,
                centroid=detection.centroid,
                confidence=detection.confidence,
                frame_number=frame_number,
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
