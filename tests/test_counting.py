"""Tests for the count gate: which tracks become counts, and in which direction.

A tracker keeps boxes on bollards, railings and parked cars for as long as they
are in view; counting every confirmed track counts street furniture. The gate
counts a track once, and only when it has actually travelled: across a
screenline (with direction) when one is configured, otherwise a minimum
distance measured in its own box heights.
"""
from __future__ import annotations

import pytest

from src.camina.core.counting import CountEvent, CountGate, Screenline

FRAME = (1000, 1000)  # (width, height) in pixels


def _box(cx: float, cy: float, h: float = 100.0) -> tuple[float, float, float, float]:
    """A box of height ``h`` (and width h/2) centred on (cx, cy)."""
    return (cx - h / 4, cy - h / 2, cx + h / 4, cy + h / 2)


def _walk(gate: CountGate, key: str, xs: list[float], y: float = 500.0) -> list[CountEvent]:
    events: list[CountEvent] = []
    for x in xs:
        events += gate.step([(key, _box(x, y))], FRAME)
    return events


# ---------- Screenline geometry ----------

def test_crossing_left_to_right_of_a_vertical_line_is_a_to_b() -> None:
    line = Screenline((0.5, 0.0), (0.5, 1.0))

    assert line.crossing((400, 500), (600, 500), FRAME) == "AB"
    assert line.crossing((600, 500), (400, 500), FRAME) == "BA"


def test_no_crossing_when_both_points_are_on_one_side() -> None:
    line = Screenline((0.5, 0.0), (0.5, 1.0))

    assert line.crossing((100, 500), (400, 500), FRAME) is None


def test_passing_beyond_the_end_of_the_segment_is_not_a_crossing() -> None:
    """The line covers the road, not the whole image: the pavement above it is out."""
    line = Screenline((0.5, 0.4), (0.5, 1.0))

    assert line.crossing((400, 100), (600, 100), FRAME) is None


def test_screenline_rejects_coordinates_outside_the_frame() -> None:
    with pytest.raises(ValueError, match="0..1"):
        Screenline((0.5, 0.0), (1.5, 1.0))


# ---------- Movement mode (no screenline) ----------

def test_a_static_track_is_never_counted() -> None:
    gate = CountGate(min_move=1.0)

    assert _walk(gate, "person-1", [500.0] * 50) == []


def test_jitter_below_the_threshold_is_not_counted() -> None:
    gate = CountGate(min_move=1.0)

    assert _walk(gate, "person-1", [500, 540, 470, 530, 480, 560] * 5) == []


def test_a_track_is_counted_once_when_it_has_moved_far_enough() -> None:
    gate = CountGate(min_move=1.0)  # 1 box height = 100 px

    events = _walk(gate, "person-1", [500, 550, 599, 601, 700, 900])

    assert events == [CountEvent("person-1", None)]


def test_min_move_is_measured_in_box_heights() -> None:
    gate = CountGate(min_move=2.0)

    assert _walk(gate, "car-3", [500, 650]) == []
    assert _walk(gate, "car-3", [701]) == [CountEvent("car-3", None)]


# ---------- Screenline mode ----------

def test_a_track_crossing_the_line_is_counted_with_its_direction() -> None:
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))

    assert _walk(gate, "car-1", [300, 400, 490, 520, 700]) == [CountEvent("car-1", "AB")]
    assert _walk(gate, "car-2", [700, 520, 480, 300]) == [CountEvent("car-2", "BA")]


def test_a_centre_landing_exactly_on_the_line_still_counts_the_crossing() -> None:
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))

    assert _walk(gate, "car-1", [400, 500, 600]) == [CountEvent("car-1", "AB")]


def test_a_static_object_jittering_across_the_line_is_not_counted() -> None:
    """A bollard on the line: its box centre wobbles a few pixels either side."""
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)), min_move=1.0)

    assert _walk(gate, "person-453", [495, 505, 497, 503] * 10) == []


def test_a_crossing_counts_once_the_track_has_also_moved_far_enough() -> None:
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)), min_move=1.0)

    # Crosses at 480 -> 520, but has travelled only 80 px (< 1 box height) by 560.
    assert _walk(gate, "car-1", [480, 520, 560]) == []
    assert _walk(gate, "car-1", [590]) == [CountEvent("car-1", "AB")]


def test_a_track_that_moves_but_never_crosses_is_not_counted() -> None:
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))

    assert _walk(gate, "person-1", [0, 100, 200, 300, 400]) == []


def test_crossing_back_and_forth_counts_only_the_first_crossing() -> None:
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))

    events = _walk(gate, "person-1", [450, 550, 450, 550, 450])

    assert events == [CountEvent("person-1", "AB")]


def test_tracks_are_independent() -> None:
    gate = CountGate(screenline=Screenline((0.5, 0.0), (0.5, 1.0)))
    events: list[CountEvent] = []
    for a, b in [(400, 600), (600, 400)]:
        events += gate.step([("car-1", _box(a, 500)), ("car-2", _box(b, 500))], FRAME)

    assert events == [CountEvent("car-1", "AB"), CountEvent("car-2", "BA")]


# ---------- Memory ----------

def test_tracks_not_seen_for_a_while_are_forgotten() -> None:
    gate = CountGate(forget_after=3)
    gate.step([("person-1", _box(500, 500))], FRAME)
    for _ in range(4):
        gate.step([], FRAME)

    assert gate.n_tracks == 0


def test_min_move_must_be_positive() -> None:
    with pytest.raises(ValueError, match="min_move"):
        CountGate(min_move=0)
