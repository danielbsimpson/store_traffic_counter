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
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from config import TRIPWIRE_DEBOUNCE_FRAMES, TRIPWIRE_HYSTERESIS, TRIPWIRE_POSITION
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
    """

    timestamp: datetime
    frame_number: int
    person_id: int
    direction: str
    cumulative_in: int
    cumulative_out: int


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
    """

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        start: tuple[float, float] = (0.0, TRIPWIRE_POSITION),
        end: tuple[float, float] = (1.0, TRIPWIRE_POSITION),
        hysteresis: int = TRIPWIRE_HYSTERESIS,
        debounce_frames: int = TRIPWIRE_DEBOUNCE_FRAMES,
    ) -> None:
        for frac in (*start, *end):
            if not 0.0 <= frac <= 1.0:
                raise ValueError(
                    f"tripwire start/end coordinates must be fractions in [0.0, 1.0], got {frac}."
                )
        x1, y1 = int(start[0] * frame_width), int(start[1] * frame_height)
        x2, y2 = int(end[0] * frame_width), int(end[1] * frame_height)
        self.line: Line = ((x1, y1), (x2, y2))
        self.hysteresis = hysteresis
        self.debounce_frames = debounce_frames
        self.total_in = 0
        self.total_out = 0
        self._sides: dict[int, Side] = {}
        # Candidate crossings awaiting debounce: id -> (new side, frames held).
        self._pending: dict[int, tuple[Side, int]] = {}

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
        for ``debounce_frames`` consecutive frames. Returns chronologically
        ordered events for crossings confirmed this frame (typically 0 or 1,
        but more if several tracks cross at once).
        """
        events: list[CountEvent] = []

        for obj in tracked_objects:
            cx, cy = obj.foot
            side = self._side_of(cx, cy)
            if side is None:
                continue  # inside the hysteresis band; wait for a clear side

            previous = self._sides.get(obj.id)
            if previous is None:
                self._sides[obj.id] = side
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
            if direction == "in":
                self.total_in += 1
            else:
                self.total_out += 1
            events.append(
                CountEvent(
                    timestamp=datetime.now(timezone.utc),
                    frame_number=frame_number,
                    person_id=obj.id,
                    direction=direction,
                    cumulative_in=self.total_in,
                    cumulative_out=self.total_out,
                )
            )
            logger.debug(
                "Track %d crossed tripwire (%s). in=%d out=%d",
                obj.id,
                direction,
                self.total_in,
                self.total_out,
            )
            self._sides[obj.id] = side

        return events
