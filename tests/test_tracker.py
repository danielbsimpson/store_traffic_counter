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


def test_stationary_track_flagged_static_after_window() -> None:
    tracker = CentroidTracker(static_window=5, static_max_displacement=10)
    # A fixed object (mannequin/standee) at the same spot every frame.
    for frame in range(1, 5):
        tracked = tracker.update([_det(300, 300)], frame_number=frame)
        assert tracked[0].is_static is False  # window not yet filled
    fifth = tracker.update([_det(300, 300)], frame_number=5)
    assert fifth[0].is_static is True


def test_moving_track_not_flagged_static() -> None:
    tracker = CentroidTracker(
        max_distance=50, static_window=5, static_max_displacement=10
    )
    track_id = tracker.update([_det(100, 100)], frame_number=1)[0].id
    # Walks steadily well past the displacement threshold each frame.
    last = None
    for step, frame in enumerate(range(2, 8), start=1):
        last = tracker.update([_det(100 + step * 15, 100)], frame_number=frame)[0]
    assert last is not None
    assert last.id == track_id
    assert last.is_static is False


def test_static_flag_clears_when_object_moves_again() -> None:
    tracker = CentroidTracker(
        max_distance=200, static_window=4, static_max_displacement=10
    )
    for frame in range(1, 5):
        tracker.update([_det(300, 300)], frame_number=frame)
    assert tracker.update([_det(300, 300)], frame_number=5)[0].is_static is True
    # Resumes moving; the trailing window fills with motion and clears the flag.
    for step, frame in enumerate(range(6, 10), start=1):
        moved = tracker.update([_det(300 + step * 40, 300)], frame_number=frame)[0]
    assert moved.is_static is False

