"""Road-user speed from two calibrated lines crossed at known frame times.

Two lines are drawn across the road in the image, ``line_a`` and ``line_b``,
whose ground positions are ``distance_m`` metres apart along the road
(measured on site; ``docs/CALIBRATION_SETUP.md``). A track that crosses one
line and then the other has speed ``distance_m / (t_second - t_first)``.

- Times are the frame timestamps passed to ``step``, which must be the frames'
  capture times; the processing clock would add inference jitter. The crossing
  time is interpolated between the two frames either side of the line, so the
  result does not snap to the frame period.
- Both directions of travel are measured (A then B, or B then A).
- A pair is **rejected**, and counted in ``rejected``, when the track crosses the
  two lines in different directions, or in an order its direction of travel
  cannot produce (both are what an ID switch between two road users looks
  like), or when the speed exceeds ``max_kmh`` (this also catches a jump over
  both lines between two frames).
- Each track gives at most one measurement. Like the count gate, a measurement
  is emitted only once the track's class is confirmed, and is lost if the track
  is forgotten before that.

The lines are ``Screenline`` segments: a move past either end of a segment is
not a crossing. Both lines must be drawn in the same orientation (e.g. both top
to bottom) so that one direction of travel has the same label on both.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterable
from dataclasses import dataclass

from camina.core.counting import FORGET_AFTER_S, Box, Point, Screenline

logger = logging.getLogger(__name__)

MAX_KMH = 150.0
_MS_TO_KMH = 3.6


@dataclass(frozen=True)
class SpeedLines:
    """Calibration of one site: two lines ``distance_m`` metres apart on the road.

    Args:
        line_a: First line, in fractions of the frame.
        line_b: Second line, drawn in the same orientation as ``line_a``.
        distance_m: Ground distance between the lines along the road, metres.
        max_kmh: Speeds above this are rejected as implausible.
    """

    line_a: Screenline
    line_b: Screenline
    distance_m: float
    max_kmh: float = MAX_KMH

    def __post_init__(self) -> None:
        """Reject a non-positive distance or limit, touching lines, or mixed orientations."""
        if self.distance_m <= 0:
            raise ValueError(f"distance_m must be > 0, got {self.distance_m}")
        if self.max_kmh <= 0:
            raise ValueError(f"max_kmh must be > 0, got {self.max_kmh}")
        a, b = self.line_a, self.line_b
        if _segments_touch(a.start, a.end, b.start, b.end):
            raise ValueError("speed lines must be apart: line_a and line_b touch or cross")
        da = (a.end[0] - a.start[0], a.end[1] - a.start[1])
        db = (b.end[0] - b.start[0], b.end[1] - b.start[1])
        if da[0] * db[0] + da[1] * db[1] <= 0:
            raise ValueError("draw line_a and line_b in the same orientation (e.g. both top down)")

    def first_line(self, direction: str) -> str:
        """The line (``"A"`` or ``"B"``) a road user moving in ``direction`` meets first."""
        b = self.line_b
        mid_b = ((b.start[0] + b.end[0]) / 2, (b.start[1] + b.end[1]) / 2)
        # "AB" moves from the positive side of a line to the negative side.
        b_ahead_of_ab = _side(self.line_a.start, self.line_a.end, mid_b) < 0
        return "A" if (direction == "AB") == b_ahead_of_ab else "B"


@dataclass(frozen=True)
class SpeedEvent:
    """One measured track: its key and speed in km/h."""

    key: str
    kmh: float


@dataclass(frozen=True)
class _Crossing:
    line: str  # "A" or "B"
    direction: str  # "AB" or "BA"
    t: float


@dataclass
class _Track:
    last: Point
    last_t: float
    last_seen: float
    first: _Crossing | None = None
    done: bool = False  # measured or rejected; never measured again
    kmh: float | None = None
    emitted: bool = False


class SpeedEstimator:
    """Per-track speed from the times a track crosses two calibrated lines.

    Args:
        lines: The site calibration.
        forget_after_s: Drop a track's state after this many seconds unseen;
            at least the tracker's ``max_occlusion_s``, as for the count gate.

    Attributes:
        rejected: Measurements rejected since start (wrong order or direction,
            or faster than ``lines.max_kmh``).
    """

    def __init__(self, lines: SpeedLines, forget_after_s: float = FORGET_AFTER_S) -> None:
        self.lines = lines
        self.forget_after_s = forget_after_s
        self.rejected = 0
        self._tracks: dict[str, _Track] = {}

    @property
    def n_tracks(self) -> int:
        """Number of tracks currently remembered."""
        return len(self._tracks)

    def step(
        self,
        tracks: Iterable[tuple[str, Box]],
        frame_size: tuple[int, int],
        t: float,
        unconfirmed: Collection[str] = frozenset(),
    ) -> list[SpeedEvent]:
        """Process one frame's confirmed tracks.

        Args:
            tracks: ``(key, (x1, y1, x2, y2))`` per confirmed track, pixels.
            frame_size: ``(width, height)`` of the frame in pixels.
            t: The frame's capture time in seconds.
            unconfirmed: Keys whose class is not confirmed on this frame.

        Returns:
            Speeds of the tracks released on this frame, in input order.
        """
        events: list[SpeedEvent] = []
        for key, (x1, y1, x2, y2) in tracks:
            centre = ((x1 + x2) / 2, (y1 + y2) / 2)
            tr = self._tracks.get(key)
            if tr is None:
                self._tracks[key] = _Track(centre, t, t)
                continue
            tr.last_seen = t
            if not tr.done:
                self._check_crossings(key, tr, centre, t, frame_size)
            if tr.kmh is not None and not tr.emitted and key not in unconfirmed:
                tr.emitted = True
                events.append(SpeedEvent(key, tr.kmh))
            if not self._on_a_line(centre, frame_size):
                # As in the count gate: an on-line point would hide the next crossing.
                tr.last, tr.last_t = centre, t
        self._forget(t)
        return events

    def _check_crossings(
        self, key: str, tr: _Track, centre: Point, t: float, frame_size: tuple[int, int]
    ) -> None:
        crossings = []
        for name, line in (("A", self.lines.line_a), ("B", self.lines.line_b)):
            direction = line.crossing(tr.last, centre, frame_size)
            if direction is not None:
                t_cross = _crossing_time(line, tr.last, tr.last_t, centre, t, frame_size)
                crossings.append(_Crossing(name, direction, t_cross))
        for c in sorted(crossings, key=lambda c: c.t):
            if tr.first is None or tr.first.line == c.line:
                tr.first = c  # (re)start from the latest crossing of this line
                continue
            tr.done = True
            tr.kmh = self._measure(key, tr.first, c)
            return

    def _measure(self, key: str, first: _Crossing, second: _Crossing) -> float | None:
        """Speed for the pair, or ``None`` (and ``rejected`` += 1) if implausible."""
        dt = second.t - first.t
        if first.direction != second.direction or self.lines.first_line(first.direction) != (
            first.line
        ):
            reason = "wrong order or direction"
        elif dt <= 0 or (kmh := self.lines.distance_m / dt * _MS_TO_KMH) > self.lines.max_kmh:
            reason = f"faster than {self.lines.max_kmh:g} km/h"
        else:
            return kmh
        self.rejected += 1
        logger.debug("speed of %s rejected: %s", key, reason)
        return None

    def _on_a_line(self, p: Point, frame_size: tuple[int, int]) -> bool:
        w, h = frame_size
        return any(
            _side((ln.start[0] * w, ln.start[1] * h), (ln.end[0] * w, ln.end[1] * h), p) == 0
            for ln in (self.lines.line_a, self.lines.line_b)
        )

    def _forget(self, now: float) -> None:
        stale = [k for k, tr in self._tracks.items() if now - tr.last_seen > self.forget_after_s]
        for k in stale:
            del self._tracks[k]


def _crossing_time(
    line: Screenline,
    prev: Point,
    t_prev: float,
    cur: Point,
    t_cur: float,
    frame_size: tuple[int, int],
) -> float:
    """Time the straight move ``prev -> cur`` meets ``line``, linearly interpolated."""
    w, h = frame_size
    a = (line.start[0] * w, line.start[1] * h)
    b = (line.end[0] * w, line.end[1] * h)
    s_prev, s_cur = _side(a, b, prev), _side(a, b, cur)
    return t_prev + (t_cur - t_prev) * s_prev / (s_prev - s_cur)


def _side(a: Point, b: Point, p: Point) -> float:
    """Cross product of ``a->b`` and ``a->p``: its sign says which side ``p`` is on."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _segments_touch(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """Whether segments ``p1p2`` and ``q1q2`` intersect or touch (inclusive)."""
    d1, d2 = _side(q1, q2, p1), _side(q1, q2, p2)
    d3, d4 = _side(p1, p2, q1), _side(p1, p2, q2)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True

    def on(a: Point, b: Point, p: Point, d: float) -> bool:
        return (
            d == 0
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and (min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
        )

    return on(q1, q2, p1, d1) or on(q1, q2, p2, d2) or on(p1, p2, q1, d3) or on(p1, p2, q2, d4)


__all__ = ["MAX_KMH", "SpeedEstimator", "SpeedEvent", "SpeedLines"]
