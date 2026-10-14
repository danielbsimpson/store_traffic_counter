"""Per-storefront tripwire counting.

Where :class:`~counter.TripwireCounter` watches a single line, a store street
has several entrances that each need their own independent in/out tally. This
module layers that multiplicity on top of the existing counter:

  - :class:`Storefront` is the editable definition of one entrance (a name plus
    tripwire endpoints expressed as frame fractions).
  - :class:`StorefrontCounter` owns one :class:`~counter.TripwireCounter` per
    storefront, fans each frame's tracks out to all of them, and exposes the
    per-store lines and tallies the visualizer and summary need.
  - :func:`load_storefronts` reads a storefront layout from JSON so tripwire
    positions can be tuned per video without touching code.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from config import TRIPWIRE_DEBOUNCE_FRAMES, TRIPWIRE_HYSTERESIS
from counter import CountEvent, Line, TripwireCounter
from tracker import TrackedObject

logger = logging.getLogger(__name__)


class StorefrontConfigError(Exception):
    """Raised when a storefront layout file is missing or malformed."""


@dataclass(frozen=True)
class Storefront:
    """One store entrance and the tripwire that guards it.

    Attributes:
        name: Human-readable label shown on the overlay and in logs.
        start: ``(x, y)`` fraction (each 0.0-1.0) for the tripwire start point.
        end: ``(x, y)`` fraction (each 0.0-1.0) for the tripwire end point.
        hysteresis: Per-store override for the crossing hysteresis band (px).
        debounce_frames: Per-store override for the crossing debounce window.
    """

    name: str
    start: tuple[float, float]
    end: tuple[float, float]
    hysteresis: int = TRIPWIRE_HYSTERESIS
    debounce_frames: int = TRIPWIRE_DEBOUNCE_FRAMES


class StorefrontCounter:
    """Counts entries/exits independently for several storefronts.

    Args:
        frame_width: Frame width in pixels, used to convert fractions to px.
        frame_height: Frame height in pixels, used to convert fractions to px.
        storefronts: Storefront definitions to track. Names must be unique.

    Raises:
        ValueError: If ``storefronts`` is empty or contains duplicate names,
            or if any tripwire coordinate is outside ``[0.0, 1.0]``.
    """

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        storefronts: list[Storefront],
    ) -> None:
        if not storefronts:
            raise ValueError("StorefrontCounter requires at least one storefront.")

        self._counters: dict[str, TripwireCounter] = {}
        for store in storefronts:
            if store.name in self._counters:
                raise ValueError(f"Duplicate storefront name: {store.name!r}.")
            self._counters[store.name] = TripwireCounter(
                frame_width=frame_width,
                frame_height=frame_height,
                start=store.start,
                end=store.end,
                hysteresis=store.hysteresis,
                debounce_frames=store.debounce_frames,
                name=store.name,
                door_mode=True,
            )

    @property
    def names(self) -> list[str]:
        """Storefront names in definition order."""
        return list(self._counters.keys())

    @property
    def lines(self) -> dict[str, Line]:
        """Map each storefront name to its pixel-space tripwire line."""
        return {name: counter.line for name, counter in self._counters.items()}

    @property
    def counts(self) -> dict[str, tuple[int, int]]:
        """Map each storefront name to its ``(in, out)`` tally."""
        return {name: counter.counts for name, counter in self._counters.items()}

    @property
    def totals(self) -> tuple[int, int]:
        """Aggregate ``(in, out)`` across every storefront."""
        total_in = sum(c.total_in for c in self._counters.values())
        total_out = sum(c.total_out for c in self._counters.values())
        return total_in, total_out

    def update(
        self, tracked_objects: list[TrackedObject], frame_number: int
    ) -> list[CountEvent]:
        """Run every storefront's tripwire against this frame's tracks.

        Returns all crossing events detected this frame, each already tagged
        with the storefront it belongs to (via :attr:`CountEvent.storefront`).
        """
        events: list[CountEvent] = []
        for counter in self._counters.values():
            events.extend(counter.update(tracked_objects, frame_number))
        return events


def load_storefronts(path: str | Path) -> list[Storefront]:
    """Load storefront definitions from a JSON layout file.

    The file must contain a ``storefronts`` array; each entry needs ``name``,
    ``start`` and ``end`` (``[x, y]`` fraction pairs) and may optionally set
    ``hysteresis`` and ``debounce_frames``. Example::

        {
          "storefronts": [
            {"name": "Studio F", "start": [0.57, 0.46], "end": [0.70, 0.30]}
          ]
        }

    Args:
        path: Path to the JSON layout file.

    Returns:
        The parsed storefront definitions in file order.

    Raises:
        StorefrontConfigError: If the file is missing, is not valid JSON, or
            does not match the expected schema.
    """
    layout_path = Path(path)
    if not layout_path.is_file():
        raise StorefrontConfigError(f"Storefront layout not found: {layout_path}")

    try:
        raw = json.loads(layout_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorefrontConfigError(f"Invalid JSON in {layout_path}: {exc}") from exc

    entries = raw.get("storefronts") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise StorefrontConfigError(
            f"{layout_path} must contain a non-empty 'storefronts' array."
        )

    storefronts = [_parse_storefront(entry, layout_path, i) for i, entry in enumerate(entries)]
    logger.info("Loaded %d storefront(s) from %s.", len(storefronts), layout_path)
    return storefronts


def save_storefronts(path: str | Path, storefronts: list[Storefront]) -> None:
    """Write storefront definitions back to a JSON layout file.

    Any ``_note`` annotations already present in the file (top-level or per
    storefront, matched by name) are preserved, so re-saving after a
    calibration session keeps the human-written guidance intact. Non-default
    ``hysteresis``/``debounce_frames`` values are written; defaults are omitted.

    Args:
        path: Destination layout file (overwritten).
        storefronts: Storefront definitions to serialize, in output order.
    """
    layout_path = Path(path)
    top_note, store_notes = _read_notes(layout_path)

    entries: list[dict[str, object]] = []
    for store in storefronts:
        entry: dict[str, object] = {"name": store.name}
        if store.name in store_notes:
            entry["_note"] = store_notes[store.name]
        entry["start"] = [round(store.start[0], 4), round(store.start[1], 4)]
        entry["end"] = [round(store.end[0], 4), round(store.end[1], 4)]
        if store.hysteresis != TRIPWIRE_HYSTERESIS:
            entry["hysteresis"] = store.hysteresis
        if store.debounce_frames != TRIPWIRE_DEBOUNCE_FRAMES:
            entry["debounce_frames"] = store.debounce_frames
        entries.append(entry)

    data: dict[str, object] = {}
    if top_note is not None:
        data["_note"] = top_note
    data["storefronts"] = entries

    layout_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved %d storefront(s) to %s.", len(storefronts), layout_path)


def _read_notes(layout_path: Path) -> tuple[str | None, dict[str, str]]:
    """Return any existing top-level and per-storefront ``_note`` annotations."""
    if not layout_path.is_file():
        return None, {}
    try:
        raw = json.loads(layout_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, {}
    if not isinstance(raw, dict):
        return None, {}

    top_note = raw.get("_note") if isinstance(raw.get("_note"), str) else None
    store_notes: dict[str, str] = {}
    for entry in raw.get("storefronts", []) or []:
        if isinstance(entry, dict):
            name, note = entry.get("name"), entry.get("_note")
            if isinstance(name, str) and isinstance(note, str):
                store_notes[name] = note
    return top_note, store_notes


def _parse_storefront(entry: object, source: Path, index: int) -> Storefront:
    """Validate and convert one raw JSON storefront entry."""
    if not isinstance(entry, dict):
        raise StorefrontConfigError(f"{source}: storefront #{index} must be an object.")

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise StorefrontConfigError(f"{source}: storefront #{index} needs a non-empty 'name'.")

    start = _parse_point(entry.get("start"), source, name, "start")
    end = _parse_point(entry.get("end"), source, name, "end")

    kwargs: dict[str, int] = {}
    for key in ("hysteresis", "debounce_frames"):
        if key in entry:
            value = entry[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise StorefrontConfigError(
                    f"{source}: storefront {name!r} '{key}' must be a non-negative integer."
                )
            kwargs[key] = value

    return Storefront(name=name.strip(), start=start, end=end, **kwargs)


def _parse_point(value: object, source: Path, name: str, field: str) -> tuple[float, float]:
    """Validate an ``[x, y]`` fraction pair from JSON."""
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
    ):
        raise StorefrontConfigError(
            f"{source}: storefront {name!r} '{field}' must be an [x, y] pair of numbers."
        )
    x, y = float(value[0]), float(value[1])
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise StorefrontConfigError(
            f"{source}: storefront {name!r} '{field}' coordinates must be fractions in [0.0, 1.0]."
        )
    return x, y
