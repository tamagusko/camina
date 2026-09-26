"""Count gate: decides which confirmed tracks become counts.

The tracker confirms anything the detector sees for three frames, including
bollards, railings and parked cars, and keeps it for as long as it is in view.
Counting every confirmed track therefore counts street furniture (on the test
clip, 287 of 325 ``person`` tracks never moved more than half a box height).
The gate counts a track at most once, and only when it has travelled:

- **Screenline mode** (``screenline`` set): when the track's centre has crossed
  the line segment *and* moved ``min_move`` box heights, so a bollard whose
  box jitters across the line never counts. The event carries the direction,
  ``"AB"`` or ``"BA"``.
- **Movement mode** (no screenline): when the centre is ``min_move`` of the
  track's own mean box heights away from where it was first seen. Measuring in
  box heights makes one threshold work for near and far objects.

Counting once per track, at the moment it qualifies, also stops a slow track
from being counted again in every 15-minute window it spans.

A track whose class is not confirmed yet (``unconfirmed`` in ``step``; see
``camina.core.tracker``) is held when it qualifies, and counted, with the
direction it qualified in, on the first frame its class is confirmed. If it is
forgotten still unconfirmed it is not counted; ``unconfirmed_dropped`` counts
those.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Collection, Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

FORGET_AFTER_S = 10.0  # twice the tracker's default max_occlusion_s

Point = tuple[float, float]
Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Screenline:
    """A counting line from ``start`` to ``end``, in fractions of the frame (0..1).

    Fractions keep one config valid at any camera resolution. Side ``A`` is the
    side a track comes from when it crosses in direction ``"AB"``: for a line
    drawn top to bottom, A is the left; for one drawn left to right, A is the
    bottom. ``scripts/view_detections.py`` draws both labels.
    """

    start: Point
    end: Point

    def __post_init__(self) -> None:
        """Reject coordinates outside the frame and zero-length lines."""
        if not all(0.0 <= v <= 1.0 for v in (*self.start, *self.end)):
            raise ValueError(f"screenline coordinates must be fractions 0..1, got {self}")
        if self.start == self.end:
            raise ValueError("screenline start and end must differ")

    def crossing(self, prev: Point, cur: Point, frame_size: tuple[int, int]) -> str | None:
        """Direction in which the move ``prev -> cur`` (pixels) crosses the line.

        Args:
            prev: Previous track centre in pixels.
            cur: Current track centre in pixels.
            frame_size: ``(width, height)`` of the frame in pixels.

        Returns:
            ``"AB"`` or ``"BA"``, or ``None`` when the move does not cross the
            segment (including passing beyond either end of it).
        """
        w, h = frame_size
        a = (self.start[0] * w, self.start[1] * h)
        b = (self.end[0] * w, self.end[1] * h)
        s_prev, s_cur = _side(a, b, prev), _side(a, b, cur)
        if s_prev * s_cur >= 0:
            return None
        if _side(prev, cur, a) * _side(prev, cur, b) > 0:
            return None  # the move crosses the line's extension, not the segment
        return "AB" if s_prev > 0 else "BA"


@dataclass(frozen=True)
class CountEvent:
    """One counted track. ``direction`` is ``None`` in movement mode."""

    key: str
    direction: str | None


@dataclass
class _Track:
    first: Point
    last: Point
    height_sum: float
    n: int
    last_seen: float  # seconds
    counted: bool = False
    crossed: str | None = None  # latest screenline crossing direction
    qualified: bool = False  # travelled far enough; counted or pending its class
    direction: str | None = None  # direction when it qualified


class CountGate:
    """Turns per-frame confirmed tracks into one count event per travelling track.

    Args:
        screenline: Count on crossing this line; ``None`` counts on movement.
        min_move: Distance a track must travel to count, in its mean box
            heights; applies in both modes. Must be > 0.
        forget_after_s: Drop a track's state after this many seconds unseen.
            Must be at least the tracker's ``max_occlusion_s``: a track the
            gate forgot but the tracker revives would be counted again.

    Attributes:
        unconfirmed_dropped: Tracks that qualified but were forgotten before
            their class was confirmed, since start.
    """

    def __init__(
        self,
        screenline: Screenline | None = None,
        min_move: float = 1.0,
        forget_after_s: float = FORGET_AFTER_S,
    ) -> None:
        if min_move <= 0:
            raise ValueError(f"min_move must be > 0, got {min_move}")
        self.screenline = screenline
        self.min_move = min_move
        self.forget_after_s = forget_after_s
        self._tracks: dict[str, _Track] = {}
        self.unconfirmed_dropped = 0

    @property
    def n_tracks(self) -> int:
        """Number of tracks currently remembered."""
        return len(self._tracks)

    @property
    def n_pending(self) -> int:
        """Tracks that qualified and wait for their class to be confirmed."""
        return sum(tr.qualified and not tr.counted for tr in self._tracks.values())

    def step(
        self,
        tracks: Iterable[tuple[str, Box]],
        frame_size: tuple[int, int],
        t: float | None = None,
        unconfirmed: Collection[str] = frozenset(),
    ) -> list[CountEvent]:
        """Process one frame's confirmed tracks.

        Args:
            tracks: ``(key, (x1, y1, x2, y2))`` for every confirmed track in
                the frame, boxes in pixels. Keys must be unique per object.
            frame_size: ``(width, height)`` of the frame in pixels.
            t: Frame timestamp in seconds, the clock the tracker uses;
                ``None`` reads ``time.monotonic()``.
            unconfirmed: Keys whose class is not confirmed on this frame.

        Returns:
            The tracks that qualified on this frame, in input order.
        """
        t = time.monotonic() if t is None else t
        events: list[CountEvent] = []
        for key, (x1, y1, x2, y2) in tracks:
            centre, height = ((x1 + x2) / 2, (y1 + y2) / 2), y2 - y1
            tr = self._tracks.get(key)
            if tr is None:
                self._tracks[key] = _Track(centre, centre, height, 1, t)
                continue
            tr.height_sum += height
            tr.n += 1
            tr.last_seen = t
            if not tr.qualified:
                tr.qualified, tr.direction = self._qualifies(tr, centre, frame_size)
            if tr.qualified and not tr.counted and key not in unconfirmed:
                tr.counted = True
                events.append(CountEvent(key, tr.direction))
            if not self._on_line(centre, frame_size):
                # Keep the last point off the line, so on-line frames can't hide a crossing.
                tr.last = centre
        self._forget(t)
        return events

    def _qualifies(
        self, t: _Track, centre: Point, frame_size: tuple[int, int]
    ) -> tuple[bool, str | None]:
        """Whether ``t`` counts on this frame, and its direction (``None`` in movement mode)."""
        dx, dy = centre[0] - t.first[0], centre[1] - t.first[1]
        moved = (dx * dx + dy * dy) ** 0.5 >= self.min_move * t.height_sum / t.n
        if self.screenline is None:
            return moved, None
        t.crossed = self.screenline.crossing(t.last, centre, frame_size) or t.crossed
        return moved and t.crossed is not None, t.crossed

    def _on_line(self, p: Point, frame_size: tuple[int, int]) -> bool:
        if self.screenline is None:
            return False
        w, h = frame_size
        line = self.screenline
        return (
            _side((line.start[0] * w, line.start[1] * h), (line.end[0] * w, line.end[1] * h), p)
            == 0
        )

    def _forget(self, now: float) -> None:
        stale = [k for k, tr in self._tracks.items() if now - tr.last_seen > self.forget_after_s]
        for k in stale:
            if self._tracks[k].qualified and not self._tracks[k].counted:
                self.unconfirmed_dropped += 1
                logger.debug("dropped %s: qualified but its class never confirmed", k)
            del self._tracks[k]


def _side(a: Point, b: Point, p: Point) -> float:
    """Cross product of ``a->b`` and ``a->p``: its sign says which side ``p`` is on."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


__all__ = ["CountEvent", "CountGate", "Screenline"]
