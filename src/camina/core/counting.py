"""Count gate: decides which confirmed tracks become counts.

The tracker confirms anything the detector sees for three frames, including
bollards, railings and parked cars, and keeps it for as long as it is in view.
Counting every confirmed track therefore counts street furniture (on the test
clip, 287 of 325 ``person`` tracks never moved more than half a box height).
The gate counts a track at most once, and only when it has travelled:

- **Screenline mode** (``screenline`` set): when the track's centre crosses the
  line segment. The event carries the direction, ``"AB"`` or ``"BA"``.
- **Movement mode** (no screenline): when the centre is ``min_move`` of the
  track's own mean box heights away from where it was first seen. Measuring in
  box heights makes one threshold work for near and far objects.

Counting once per track, at the moment it qualifies, also stops a slow track
from being counted again in every 15-minute window it spans.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
    last_frame: int
    counted: bool = False


class CountGate:
    """Turns per-frame confirmed tracks into one count event per travelling track.

    Args:
        screenline: Count on crossing this line; ``None`` counts on movement.
        min_move: Movement mode threshold, in mean box heights. Must be > 0.
        forget_after: Drop a track's state after this many frames unseen.
    """

    def __init__(
        self,
        screenline: Screenline | None = None,
        min_move: float = 1.0,
        forget_after: int = 300,
    ) -> None:
        if min_move <= 0:
            raise ValueError(f"min_move must be > 0, got {min_move}")
        self.screenline = screenline
        self.min_move = min_move
        self.forget_after = forget_after
        self._tracks: dict[str, _Track] = {}
        self._frame = 0

    @property
    def n_tracks(self) -> int:
        """Number of tracks currently remembered."""
        return len(self._tracks)

    def step(self, tracks: Iterable[tuple[str, Box]], frame_size: tuple[int, int]) -> list[CountEvent]:
        """Process one frame's confirmed tracks.

        Args:
            tracks: ``(key, (x1, y1, x2, y2))`` for every confirmed track in
                the frame, boxes in pixels. Keys must be unique per object.
            frame_size: ``(width, height)`` of the frame in pixels.

        Returns:
            The tracks that qualified on this frame, in input order.
        """
        self._frame += 1
        events: list[CountEvent] = []
        for key, (x1, y1, x2, y2) in tracks:
            centre, height = ((x1 + x2) / 2, (y1 + y2) / 2), y2 - y1
            t = self._tracks.get(key)
            if t is None:
                self._tracks[key] = _Track(centre, centre, height, 1, self._frame)
                continue
            t.height_sum += height
            t.n += 1
            t.last_frame = self._frame
            if not t.counted:
                counts, direction = self._qualifies(t, centre, frame_size)
                if counts:
                    t.counted = True
                    events.append(CountEvent(key, direction))
            if not self._on_line(centre, frame_size):
                t.last = centre  # keep the last point off the line, so on-line frames can't hide a crossing
        self._forget()
        return events

    def _qualifies(self, t: _Track, centre: Point, frame_size: tuple[int, int]) -> tuple[bool, str | None]:
        """Whether ``t`` counts on this frame, and its direction (``None`` in movement mode)."""
        if self.screenline is not None:
            direction = self.screenline.crossing(t.last, centre, frame_size)
            return direction is not None, direction
        dx, dy = centre[0] - t.first[0], centre[1] - t.first[1]
        return (dx * dx + dy * dy) ** 0.5 >= self.min_move * t.height_sum / t.n, None

    def _on_line(self, p: Point, frame_size: tuple[int, int]) -> bool:
        if self.screenline is None:
            return False
        w, h = frame_size
        line = self.screenline
        return _side((line.start[0] * w, line.start[1] * h), (line.end[0] * w, line.end[1] * h), p) == 0

    def _forget(self) -> None:
        stale = [k for k, t in self._tracks.items() if self._frame - t.last_frame > self.forget_after]
        for k in stale:
            del self._tracks[k]


def _side(a: Point, b: Point, p: Point) -> float:
    """Cross product of ``a->b`` and ``a->p``: its sign says which side ``p`` is on."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


__all__ = ["CountEvent", "CountGate", "Screenline"]
