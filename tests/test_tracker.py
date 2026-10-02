"""Unit tests for the centroid tracker."""

from __future__ import annotations

from detector import Detection
from tracker import CentroidTracker, TrackedObject


def _det(cx: int, cy: int, size: int = 20, confidence: float = 0.9) -> Detection:
    """Build a detection whose centroid is (cx, cy)."""
    half = size // 2
    return Detection(
        box=(cx - half, cy - half, cx + half, cy + half), confidence=confidence
    )


def test_registers_new_detection_with_id() -> None:
    tracker = CentroidTracker()
    tracked = tracker.update([_det(100, 100)], frame_number=1)
    assert len(tracked) == 1
    assert isinstance(tracked[0], TrackedObject)
    assert tracked[0].centroid == (100, 100)
    assert tracked[0].frame_number == 1


def test_id_persistence_for_moving_person() -> None:
    tracker = CentroidTracker(max_distance=50)
    first = tracker.update([_det(100, 100)], frame_number=1)
    track_id = first[0].id
    # Small movement should keep the same ID across frames.
    second = tracker.update([_det(110, 105)], frame_number=2)
    third = tracker.update([_det(120, 110)], frame_number=3)
    assert second[0].id == track_id
    assert third[0].id == track_id


def test_distinct_ids_for_two_people() -> None:
    tracker = CentroidTracker()
    tracked = tracker.update([_det(50, 50), _det(400, 400)], frame_number=1)
    ids = {t.id for t in tracked}
    assert len(ids) == 2


def test_new_id_when_beyond_max_distance() -> None:
    tracker = CentroidTracker(max_distance=50)
    first = tracker.update([_det(100, 100)], frame_number=1)
    original_id = first[0].id
    # A jump larger than max_distance should be treated as a new person.
    second = tracker.update([_det(300, 300)], frame_number=2)
    assert second[0].id != original_id
    assert tracker.total_registered == 2


def test_object_deregistered_after_timeout() -> None:
    tracker = CentroidTracker(max_disappeared=3)
    tracker.update([_det(100, 100)], frame_number=1)
    assert tracker.active_ids == [0]
    # No detections for more than max_disappeared frames.
    for frame in range(2, 7):
        tracker.update([], frame_number=frame)
    assert tracker.active_ids == []


def test_object_survives_brief_disappearance() -> None:
    tracker = CentroidTracker(max_distance=50, max_disappeared=5)
    tracker.update([_det(100, 100)], frame_number=1)
    tracker.update([], frame_number=2)
    tracker.update([], frame_number=3)
    # Reappears nearby within the timeout window -> same ID.
    reappeared = tracker.update([_det(105, 102)], frame_number=4)
    assert reappeared[0].id == 0


def test_empty_detections_returns_empty_list() -> None:
    tracker = CentroidTracker()
    assert tracker.update([], frame_number=1) == []


def test_tracked_object_fields_populated() -> None:
    tracker = CentroidTracker()
    det = _det(200, 150, confidence=0.77)
    tracked = tracker.update([det], frame_number=9)[0]
    assert tracked.box == det.box
    assert tracked.centroid == (200, 150)
    assert tracked.confidence == 0.77
    assert tracked.frame_number == 9
