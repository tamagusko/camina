"""Unit tests for speed from two calibrated lines (``camina.core.speed``)."""

from __future__ import annotations

import pytest

from camina.core.counting import Screenline
from camina.core.speed import SpeedEstimator, SpeedLines

FRAME = (1000, 100)  # width, height in pixels
# Two vertical lines, both drawn top to bottom, 20 m apart on the road.
LINE_A = Screenline((0.25, 0.0), (0.25, 1.0))  # x = 250 px
LINE_B = Screenline((0.75, 0.0), (0.75, 1.0))  # x = 750 px


def _lines(distance_m: float = 20.0, max_kmh: float = 150.0) -> SpeedLines:
    return SpeedLines(LINE_A, LINE_B, distance_m=distance_m, max_kmh=max_kmh)


def _box(x: float, y: float = 50.0) -> tuple[float, float, float, float]:
    return (x - 10.0, y - 10.0, x + 10.0, y + 10.0)


def _run(est: SpeedEstimator, path: list[tuple[float, float, float]], key: str = "1", **kw):
    """Feed ``(t, x, y)`` centres of one track; return every event emitted."""
    events = []
    for t, x, y in path:
        events += est.step([(key, _box(x, y))], FRAME, t, **kw)
    return events


def _straight(x0: float, px_per_s: float, t0: float, n: int, dt: float = 0.1):
    return [(t0 + i * dt, x0 + px_per_s * i * dt, 50.0) for i in range(n)]


# ---------- Speed from crossing times ----------


def test_speed_is_distance_over_the_time_between_the_two_crossings() -> None:
    # 500 px/s: crosses x=250 at t=1.0 and x=750 at t=2.0 -> 20 m in 1 s = 72 km/h.
    # Frames at t = 0.93, 1.03, ... so neither crossing falls on a frame.
    path = [(0.93 + 0.1 * i, 250 + 500 * (0.93 + 0.1 * i - 1.0), 50.0) for i in range(15)]
    est = SpeedEstimator(_lines())

    events = _run(est, path)

    assert len(events) == 1
    assert events[0].key == "1"
    assert events[0].kmh == pytest.approx(72.0)
    assert est.rejected == 0


def test_crossing_times_are_the_frame_times_passed_in_not_the_wall_clock() -> None:
    """Same path, frames stamped twice as far apart: half the speed."""
    fast = [(0.93 + 0.1 * i, 250 + 500 * (0.1 * i - 0.07), 50.0) for i in range(15)]
    slow = [(2 * t, x, y) for t, x, y in fast]

    assert _run(SpeedEstimator(_lines()), fast)[0].kmh == pytest.approx(72.0)
    assert _run(SpeedEstimator(_lines()), slow)[0].kmh == pytest.approx(36.0)


def test_travel_in_the_other_direction_is_measured_too() -> None:
    """Two-way road: B then A, right to left, is a valid measurement."""
    path = _straight(x0=900, px_per_s=-500, t0=0.03, n=20)
    events = _run(SpeedEstimator(_lines()), path)

    assert len(events) == 1
    assert events[0].kmh == pytest.approx(72.0)


def test_a_track_is_measured_once() -> None:
    est = SpeedEstimator(_lines())
    there = _straight(x0=100, px_per_s=500, t0=0.03, n=20)  # ends at x ~ 1050
    back = _straight(x0=1000, px_per_s=-500, t0=2.03, n=20)

    assert len(_run(est, there + back)) == 1


def test_a_track_crossing_only_one_line_gives_no_speed() -> None:
    est = SpeedEstimator(_lines())
    assert _run(est, _straight(x0=100, px_per_s=500, t0=0.03, n=8)) == []
    assert est.rejected == 0


# ---------- Rejections ----------


def test_turning_back_before_the_second_line_gives_no_speed() -> None:
    """Crosses A, turns back between the lines and re-crosses A: no baseline run."""
    est = SpeedEstimator(_lines())
    out = _straight(x0=100, px_per_s=500, t0=0.03, n=8)  # 100 -> 450
    back = _straight(x0=450, px_per_s=-500, t0=0.83, n=8)  # 450 -> 100

    assert _run(est, out + back) == []
    assert est.rejected == 0


def test_crossing_the_two_lines_in_opposite_directions_is_rejected() -> None:
    """Short segments: A left to right, round the end of B, then B right to left.
    One road user cannot do that on a road; it is usually an ID switch."""
    a = Screenline((0.25, 0.0), (0.25, 0.5))
    b = Screenline((0.75, 0.0), (0.75, 0.5))
    est = SpeedEstimator(SpeedLines(a, b, distance_m=20.0))
    path = [
        (0.0, 100, 25),
        (1.0, 300, 25),  # crosses A left to right
        (2.0, 300, 80),  # below the segments
        (3.0, 900, 80),  # passes under B
        (4.0, 900, 25),
        (5.0, 700, 25),  # crosses B right to left
    ]

    assert _run(est, path) == []
    assert est.rejected == 1


def test_crossing_in_the_wrong_order_is_rejected() -> None:
    """Short segments: the track crosses B then A, both left to right, which a
    road user driving left to right cannot do (A lies before B)."""
    a = Screenline((0.25, 0.0), (0.25, 0.5))
    b = Screenline((0.75, 0.0), (0.75, 0.5))
    est = SpeedEstimator(SpeedLines(a, b, distance_m=20.0))
    path = [
        (0.0, 700, 25),  # between the lines, above y = 50
        (1.0, 800, 25),  # crosses B left to right
        (2.0, 800, 80),  # below the segments
        (3.0, 100, 80),  # back left, under both segments
        (4.0, 100, 25),
        (5.0, 300, 25),  # crosses A left to right
    ]

    assert _run(est, path) == []
    assert est.rejected == 1


def test_a_speed_above_the_limit_is_rejected() -> None:
    # 20 m in 0.4 s = 180 km/h
    est = SpeedEstimator(_lines(max_kmh=150.0))
    assert _run(est, _straight(x0=100, px_per_s=1250, t0=0.03, n=10)) == []
    assert est.rejected == 1


def test_both_lines_in_one_frame_step_is_rejected_as_too_fast() -> None:
    """A jump over both lines between two frames 0.1 s apart is > 150 km/h."""
    est = SpeedEstimator(_lines())
    assert _run(est, [(0.0, 100, 50), (0.1, 900, 50)]) == []
    assert est.rejected == 1


def test_a_plausible_speed_below_the_limit_is_kept() -> None:
    # 20 m in 0.5 s = 144 km/h, under 150
    est = SpeedEstimator(_lines(max_kmh=150.0))
    events = _run(est, _straight(x0=100, px_per_s=1000, t0=0.03, n=10))
    assert [round(e.kmh, 6) for e in events] == [144.0]


# ---------- Class confirmation ----------


def test_a_speed_waits_for_the_track_class_to_be_confirmed() -> None:
    est = SpeedEstimator(_lines())
    path = [(0.93 + 0.1 * i, 250 + 500 * (0.1 * i - 0.07), 50.0) for i in range(15)]

    held = _run(est, path, unconfirmed={"1"})
    released = est.step([("1", _box(1100))], FRAME, 2.5)

    assert held == []
    assert len(released) == 1 and released[0].kmh == pytest.approx(72.0)


def test_a_forgotten_track_is_dropped() -> None:
    est = SpeedEstimator(_lines(), forget_after_s=1.0)
    _run(est, _straight(x0=100, px_per_s=500, t0=0.03, n=4))
    est.step([], FRAME, 10.0)
    assert est.n_tracks == 0


# ---------- Configuration ----------


@pytest.mark.parametrize("distance_m", [0.0, -5.0])
def test_distance_must_be_positive(distance_m: float) -> None:
    with pytest.raises(ValueError, match="distance_m"):
        SpeedLines(LINE_A, LINE_B, distance_m=distance_m)


def test_max_kmh_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_kmh"):
        SpeedLines(LINE_A, LINE_B, distance_m=20.0, max_kmh=0.0)


def test_lines_drawn_in_opposite_orientations_are_refused() -> None:
    flipped_b = Screenline((0.75, 1.0), (0.75, 0.0))
    with pytest.raises(ValueError, match="same orientation"):
        SpeedLines(LINE_A, flipped_b, distance_m=20.0)


def test_lines_that_touch_are_refused() -> None:
    crossing_b = Screenline((0.0, 0.5), (1.0, 0.6))
    with pytest.raises(ValueError, match="apart"):
        SpeedLines(LINE_A, crossing_b, distance_m=20.0)
