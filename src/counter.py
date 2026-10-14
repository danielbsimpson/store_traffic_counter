"""Virtual tripwire crossing detection and in/out counting.

:class:`TripwireCounter` watches each tracked person's foot point (bottom-center
of the box) relative to an (optionally angled) line and emits a
:class:`CountEvent` whenever a track crosses from one side to the other. A
hysteresis band around the line absorbs small jitter, and a debounce requires
the track to hold the new side for several consecutive frames before the
crossing counts — together these suppress the back-and-forth bounce that people
walking roughly parallel to the line would otherwise produce.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from config import (
    TRIPWIRE_DEBOUNCE_FRAMES,
    TRIPWIRE_DISAPPEAR_FRAMES,
    TRIPWIRE_DOOR_APPROACH_PX,
    TRIPWIRE_DOOR_BAND_PX,
    TRIPWIRE_DOOR_MOTION_WINDOW,
    TRIPWIRE_FRAME_EDGE_MARGIN_PX,
    TRIPWIRE_HYSTERESIS,
    TRIPWIRE_POSITION,
)
from tracker import TrackedObject

logger = logging.getLogger(__name__)

# A tripwire line expressed as ((x1, y1), (x2, y2)).
Line = tuple[tuple[int, int], tuple[int, int]]


def perpendicular_distance(point: tuple[int, int], line: Line) -> float:
    """Signed perpendicular distance in pixels from a point to a line.

    Positive/negative sign indicates which side of the line the point falls
    on (consistent with :class:`Side` below); magnitude is the pixel distance.
    """
    (x1, y1), (x2, y2) = line
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0  # guard a zero-length line
    cx, cy = point
    cross = dx * (cy - y1) - dy * (cx - x1)
    return cross / length


def distance_to_segment(point: tuple[int, int], line: Line) -> float:
    """Unsigned pixel distance from a point to the finite line *segment*.

    Unlike :func:`perpendicular_distance` (distance to the infinite line), this
    accounts for the endpoints, so a point beyond a short tripwire's ends is
    correctly far away - essential for deciding whether a vanished/appeared
    track was really *at the door* rather than merely near the line's extension.
    """
    (x1, y1), (x2, y2) = line
    px, py = point
    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class Side(Enum):
    """Which side of the tripwire a tracked centroid currently occupies."""

    ABOVE = "above"
    BELOW = "below"


@dataclass(frozen=True)
class CountEvent:
    """A single tripwire crossing.

    Attributes:
        timestamp: UTC time the crossing was detected.
        frame_number: Frame index the crossing occurred on.
        person_id: Track ID that crossed the line.
        direction: ``"in"`` or ``"out"``, based on which side of the line
            (``Side.ABOVE`` vs ``Side.BELOW``) the track approached from.
        cumulative_in: Running total of entries at the time of this event.
        cumulative_out: Running total of exits at the time of this event.
        storefront: Name of the storefront whose tripwire was crossed, or
            ``None`` for a single unnamed tripwire.
    """

    timestamp: datetime
    frame_number: int
    person_id: int
    direction: str
    cumulative_in: int
    cumulative_out: int
    storefront: str | None = None


class TripwireCounter:
    """Counts entries/exits as tracked centroids cross a tripwire line.

    The line may be angled (e.g. to follow a storefront's perspective) rather
    than strictly horizontal, defined by ``start``/``end`` endpoints expressed
    as fractions of the frame's width/height.

    Args:
        frame_width: Frame width in pixels, used to convert fractions to px.
        frame_height: Frame height in pixels, used to convert fractions to px.
        start: ``(x, y)`` fraction (each 0.0-1.0) for the line's start point.
        end: ``(x, y)`` fraction (each 0.0-1.0) for the line's end point.
        hysteresis: Minimum perpendicular pixel distance past the line
            required before a crossing is counted, preventing double-counts
            from jitter.
        debounce_frames: Consecutive frames a track must remain on the new
            side before the crossing is committed, suppressing spurious
            in/out bounce from tracks moving parallel to the line.
        name: Optional storefront name stamped onto each emitted
            :class:`CountEvent`; ``None`` for a single unnamed tripwire.
    """

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        start: tuple[float, float] = (0.0, TRIPWIRE_POSITION),
        end: tuple[float, float] = (1.0, TRIPWIRE_POSITION),
        hysteresis: int = TRIPWIRE_HYSTERESIS,
        debounce_frames: int = TRIPWIRE_DEBOUNCE_FRAMES,
        name: str | None = None,
        door_mode: bool = False,
        door_band: int = TRIPWIRE_DOOR_BAND_PX,
        disappear_frames: int = TRIPWIRE_DISAPPEAR_FRAMES,
        edge_margin: int = TRIPWIRE_FRAME_EDGE_MARGIN_PX,
        approach_px: int = TRIPWIRE_DOOR_APPROACH_PX,
        motion_window: int = TRIPWIRE_DOOR_MOTION_WINDOW,
    ) -> None:
        for frac in (*start, *end):
            if not 0.0 <= frac <= 1.0:
                raise ValueError(
                    f"tripwire start/end coordinates must be fractions in [0.0, 1.0], got {frac}."
                )
        x1, y1 = int(start[0] * frame_width), int(start[1] * frame_height)
        x2, y2 = int(end[0] * frame_width), int(end[1] * frame_height)
        self.line: Line = ((x1, y1), (x2, y2))
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.name = name
        self.hysteresis = hysteresis
        self.debounce_frames = debounce_frames
        self.door_mode = door_mode
        self.door_band = door_band
        self.disappear_frames = disappear_frames
        self.edge_margin = edge_margin
        self.approach_px = approach_px
        self.motion_window = motion_window
        self.total_in = 0
        self.total_out = 0
        self._sides: dict[int, Side] = {}
        # Candidate crossings awaiting debounce: id -> (new side, frames held).
        self._pending: dict[int, tuple[Side, int]] = {}
        # Doorway-reinforcement state (used only when door_mode is True).
        self._last_foot: dict[int, tuple[int, int]] = {}  # last foot point of a live track
        self._foot_hist: dict[int, deque[tuple[int, int]]] = {}  # trailing feet for approach test
        self._absent: dict[int, int] = {}  # consecutive frames a known track has been missing
        self._door_born: set[int] = set()  # tracks whose first sighting was at the door
        self._counted: set[int] = set()  # tracks already tallied, to avoid double counting

    @property
    def counts(self) -> tuple[int, int]:
        """Return the current ``(total_in, total_out)`` tally."""
        return self.total_in, self.total_out

    def _side_of(self, cx: int, cy: int) -> Side | None:
        """Classify a point, or ``None`` if inside the hysteresis band."""
        distance = perpendicular_distance((cx, cy), self.line)
        if distance < -self.hysteresis:
            return Side.ABOVE
        if distance > self.hysteresis:
            return Side.BELOW
        return None

    def update(
        self, tracked_objects: list[TrackedObject], frame_number: int
    ) -> list[CountEvent]:
        """Check each tracked object's foot point against the tripwire.

        A crossing is only committed once the track has stayed on the new side
        for ``debounce_frames`` consecutive frames. When ``door_mode`` is set,
        two extra signals reinforce threshold entries/exits that never complete
        a clean two-sided crossing: a track that *appears* at the door and steps
        outside is counted OUT, and a track that *vanishes* at the door is
        counted IN. Returns the events confirmed this frame.
        """
        events: list[CountEvent] = []
        current_ids: set[int] = set()

        for obj in tracked_objects:
            current_ids.add(obj.id)
            cx, cy = obj.foot
            foot = (cx, cy)
            side = self._side_of(cx, cy)

            if self.door_mode:
                first_sighting = obj.id not in self._last_foot and obj.id not in self._sides
                # Door-born = first seen at the door (not already clearly
                # outside, and away from the frame border where people simply
                # enter the camera's view), so a genuine emergence from the
                # store can be told apart from a plaza pedestrian or FOV entry.
                if (
                    first_sighting
                    and side != Side.ABOVE
                    and not self._near_frame_edge(foot)
                    and distance_to_segment(foot, self.line) <= self.door_band
                ):
                    self._door_born.add(obj.id)
                self._last_foot[obj.id] = foot
                self._foot_hist.setdefault(
                    obj.id, deque(maxlen=self.motion_window)
                ).append(foot)
                self._absent.pop(obj.id, None)

            if side is None:
                continue  # inside the hysteresis band; wait for a clear side

            previous = self._sides.get(obj.id)
            if previous is None:
                self._sides[obj.id] = side
                # Appearance reinforcement: a track born at the door whose first
                # clear reading is outside has emerged from the store -> OUT.
                if (
                    self.door_mode
                    and obj.id in self._door_born
                    and side == Side.ABOVE
                    and obj.id not in self._counted
                ):
                    events.append(self._emit("out", frame_number, obj.id, "appeared at"))
                continue

            if side == previous:
                self._pending.pop(obj.id, None)  # settled back; cancel candidate
                continue

            # Side differs from the confirmed side: run it through the debounce.
            pending = self._pending.get(obj.id)
            held = pending[1] + 1 if pending is not None and pending[0] == side else 1
            if held < self.debounce_frames:
                self._pending[obj.id] = (side, held)
                continue

            self._pending.pop(obj.id, None)
            direction = "in" if previous == Side.ABOVE else "out"
            events.append(self._emit(direction, frame_number, obj.id, "crossed"))
            self._sides[obj.id] = side

        if self.door_mode:
            events.extend(self._finalize_disappearances(current_ids, frame_number))

        return events

    def _emit(
        self, direction: str, frame_number: int, person_id: int, reason: str
    ) -> CountEvent:
        """Tally a crossing, mark the track counted, and build its event."""
        if direction == "in":
            self.total_in += 1
        else:
            self.total_out += 1
        self._counted.add(person_id)
        logger.debug(
            "Track %d %s %s tripwire (%s). in=%d out=%d",
            person_id,
            reason,
            self.name or "",
            direction,
            self.total_in,
            self.total_out,
        )
        return CountEvent(
            timestamp=datetime.now(timezone.utc),
            frame_number=frame_number,
            person_id=person_id,
            direction=direction,
            cumulative_in=self.total_in,
            cumulative_out=self.total_out,
            storefront=self.name,
        )

    def _finalize_disappearances(
        self, current_ids: set[int], frame_number: int
    ) -> list[CountEvent]:
        """Count IN for near-door tracks that vanished while heading inside.

        A vanish only counts as an entry when the track was at the door, not at
        the frame border (FOV exit), and was moving inward beforehand - which
        rejects occlusion dropouts of people walking parallel to the frontage.
        """
        events: list[CountEvent] = []
        for obj_id in list(self._last_foot):
            if obj_id in current_ids:
                continue
            self._absent[obj_id] = self._absent.get(obj_id, 0) + 1
            if self._absent[obj_id] < self.disappear_frames:
                continue
            last_foot = self._last_foot[obj_id]
            if (
                obj_id not in self._counted
                and not self._near_frame_edge(last_foot)
                and distance_to_segment(last_foot, self.line) <= self.door_band
                and self._approached_inward(obj_id)
            ):
                events.append(self._emit("in", frame_number, obj_id, "vanished at"))
            self._forget(obj_id)
        return events

    def _near_frame_edge(self, foot: tuple[int, int]) -> bool:
        """True if a foot point sits within the border margin (likely FOV edge)."""
        x, y = foot
        return (
            x < self.edge_margin
            or y < self.edge_margin
            or x > self.frame_width - self.edge_margin
            or y > self.frame_height - self.edge_margin
        )

    def _approached_inward(self, obj_id: int) -> bool:
        """True if the track's recent travel moved it toward the IN side."""
        history = self._foot_hist.get(obj_id)
        if history is None or len(history) < 2:
            return False
        start_perp = perpendicular_distance(history[0], self.line)
        end_perp = perpendicular_distance(history[-1], self.line)
        # IN is the positive (BELOW) side, so inward travel raises the distance.
        return end_perp - start_perp >= self.approach_px

    def _forget(self, obj_id: int) -> None:
        """Drop all per-track state once a track is resolved and gone."""
        self._sides.pop(obj_id, None)
        self._pending.pop(obj_id, None)
        self._last_foot.pop(obj_id, None)
        self._foot_hist.pop(obj_id, None)
        self._absent.pop(obj_id, None)
        self._door_born.discard(obj_id)
        self._counted.discard(obj_id)
