"""Unit tests for the storefront multi-tripwire counter and layout loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from storefront import (
    Storefront,
    StorefrontConfigError,
    StorefrontCounter,
    load_storefronts,
    save_storefronts,
)
from tracker import TrackedObject


def _obj(track_id: int, cy: int, cx: int = 100, frame_number: int = 1) -> TrackedObject:
    """Build a tracked object whose foot point (bottom-center) is (cx, cy)."""
    return TrackedObject(
        id=track_id,
        box=(cx - 10, cy - 20, cx + 10, cy),
        centroid=(cx, cy - 10),
        confidence=0.9,
        frame_number=frame_number,
    )


def _two_stores() -> list[Storefront]:
    # Two horizontal tripwires at different heights (y = 120 and y = 360 on a
    # 480px-tall frame), so a track can cross one without touching the other.
    return [
        Storefront(name="North", start=(0.0, 0.25), end=(1.0, 0.25), debounce_frames=1),
        Storefront(name="South", start=(0.0, 0.75), end=(1.0, 0.75), debounce_frames=1),
    ]


def test_requires_at_least_one_storefront() -> None:
    with pytest.raises(ValueError):
        StorefrontCounter(frame_width=640, frame_height=480, storefronts=[])


def test_duplicate_names_rejected() -> None:
    stores = [
        Storefront(name="Shop", start=(0.0, 0.25), end=(1.0, 0.25)),
        Storefront(name="Shop", start=(0.0, 0.75), end=(1.0, 0.75)),
    ]
    with pytest.raises(ValueError):
        StorefrontCounter(frame_width=640, frame_height=480, storefronts=stores)


def test_lines_scaled_to_pixels() -> None:
    counter = StorefrontCounter(
        frame_width=640, frame_height=480, storefronts=_two_stores()
    )
    assert counter.lines == {
        "North": ((0, 120), (640, 120)),
        "South": ((0, 360), (640, 360)),
    }
    assert counter.names == ["North", "South"]


def test_each_store_counts_independently() -> None:
    counter = StorefrontCounter(
        frame_width=640, frame_height=480, storefronts=_two_stores()
    )
    # Cross only the North line (y=120): start above it, move just below it but
    # still well above the South line (y=360).
    counter.update([_obj(0, cy=60)], frame_number=1)
    events = counter.update([_obj(0, cy=200)], frame_number=2)
    assert len(events) == 1
    assert events[0].storefront == "North"
    assert events[0].direction == "in"
    assert counter.counts == {"North": (1, 0), "South": (0, 0)}
    assert counter.totals == (1, 0)


def test_totals_aggregate_across_stores() -> None:
    counter = StorefrontCounter(
        frame_width=640, frame_height=480, storefronts=_two_stores()
    )
    # Track 0 enters via North; track 1 exits via South.
    counter.update([_obj(0, cy=60), _obj(1, cy=460)], frame_number=1)
    counter.update([_obj(0, cy=200), _obj(1, cy=300)], frame_number=2)
    assert counter.counts == {"North": (1, 0), "South": (0, 1)}
    assert counter.totals == (1, 1)


def test_load_storefronts_parses_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "layout.storefronts.json"
    path.write_text(
        json.dumps(
            {
                "storefronts": [
                    {"name": "A", "start": [0.1, 0.2], "end": [0.3, 0.4]},
                    {
                        "name": "B",
                        "start": [0.5, 0.6],
                        "end": [0.7, 0.8],
                        "hysteresis": 12,
                        "debounce_frames": 4,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    stores = load_storefronts(path)
    assert [s.name for s in stores] == ["A", "B"]
    assert stores[0].start == (0.1, 0.2)
    assert stores[1].hysteresis == 12
    assert stores[1].debounce_frames == 4


def test_load_storefronts_missing_file(tmp_path: Path) -> None:
    with pytest.raises(StorefrontConfigError):
        load_storefronts(tmp_path / "nope.json")


def test_load_storefronts_rejects_empty_array(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"storefronts": []}), encoding="utf-8")
    with pytest.raises(StorefrontConfigError):
        load_storefronts(path)


def test_load_storefronts_rejects_out_of_range_fraction(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"storefronts": [{"name": "A", "start": [0.1, 1.5], "end": [0.3, 0.4]}]}),
        encoding="utf-8",
    )
    with pytest.raises(StorefrontConfigError):
        load_storefronts(path)


def test_load_storefronts_rejects_missing_name(tmp_path: Path) -> None:
    path = tmp_path / "noname.json"
    path.write_text(
        json.dumps({"storefronts": [{"start": [0.1, 0.2], "end": [0.3, 0.4]}]}),
        encoding="utf-8",
    )
    with pytest.raises(StorefrontConfigError):
        load_storefronts(path)


def test_save_storefronts_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    original = [
        Storefront(name="A", start=(0.1, 0.2), end=(0.3, 0.4)),
        Storefront(name="B", start=(0.5, 0.6), end=(0.7, 0.8), hysteresis=12),
    ]
    save_storefronts(path, original)
    reloaded = load_storefronts(path)
    assert [(s.name, s.start, s.end, s.hysteresis) for s in reloaded] == [
        ("A", (0.1, 0.2), (0.3, 0.4), 5),
        ("B", (0.5, 0.6), (0.7, 0.8), 12),
    ]


def test_save_storefronts_preserves_notes(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    path.write_text(
        json.dumps(
            {
                "_note": "top guidance",
                "storefronts": [
                    {"name": "A", "_note": "store note", "start": [0.1, 0.2], "end": [0.3, 0.4]}
                ],
            }
        ),
        encoding="utf-8",
    )
    # Re-save with a moved line; the human-written notes must survive.
    save_storefronts(path, [Storefront(name="A", start=(0.15, 0.25), end=(0.35, 0.45))])
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["_note"] == "top guidance"
    assert raw["storefronts"][0]["_note"] == "store note"
    assert raw["storefronts"][0]["start"] == [0.15, 0.25]
