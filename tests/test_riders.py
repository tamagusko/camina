"""A rider is one road user, not two.

The detector often boxes the person on a bicycle, e-scooter or motorbike as a
separate ``person`` inside the rider's box. That person is dropped before
tracking when it lies mostly inside a rider box in the same frame.
"""

from __future__ import annotations

import numpy as np

from camina.core.riders import RIDER_OVERLAP, drop_riders

CLASSES = [
    "person",
    "cyclist",
    "car",
    "e-scooter",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
]
PERSON, CYCLIST, CAR, SCOOTER, MOTO = 0, 1, 2, 3, 5


def _det(x1: float, y1: float, x2: float, y2: float, cls: int, score: float = 0.9) -> list[float]:
    return [x1, y1, x2, y2, score, cls]


def _run(rows: list[list[float]]) -> np.ndarray:
    return drop_riders(np.asarray(rows, dtype=float).reshape(-1, 6), CLASSES)


def test_a_person_inside_a_cyclist_box_is_dropped() -> None:
    out = _run([_det(100, 100, 160, 220, CYCLIST), _det(110, 100, 150, 180, PERSON)])

    assert out[:, 5].tolist() == [CYCLIST]


def test_riders_of_e_scooters_and_motorbikes_are_dropped_too() -> None:
    out = _run(
        [
            _det(0, 0, 50, 100, SCOOTER),
            _det(5, 0, 45, 80, PERSON),
            _det(300, 0, 380, 100, MOTO),
            _det(310, 0, 370, 70, PERSON),
        ]
    )

    assert sorted(out[:, 5].tolist()) == [SCOOTER, MOTO]


def test_a_pedestrian_next_to_a_cyclist_is_kept() -> None:
    # Overlaps the cyclist box by a quarter of its own area only.
    out = _run([_det(100, 100, 160, 220, CYCLIST), _det(145, 100, 205, 220, PERSON)])

    assert sorted(out[:, 5].tolist()) == [PERSON, CYCLIST]


def test_the_threshold_is_inclusive_and_measured_on_the_person_box() -> None:
    # Person box 100 x 100; exactly RIDER_OVERLAP of it inside a large cyclist box.
    inside = 100 * RIDER_OVERLAP
    rows = [_det(0, 0, 1000, 1000, CYCLIST), _det(1000 - inside, 0, 1100 - inside, 100, PERSON)]

    assert _run(rows)[:, 5].tolist() == [CYCLIST]


def test_a_person_inside_a_car_box_is_kept() -> None:
    """Only rider classes absorb a person: someone walking past a car is a pedestrian."""
    out = _run([_det(0, 0, 200, 120, CAR), _det(50, 20, 90, 110, PERSON)])

    assert sorted(out[:, 5].tolist()) == [PERSON, CAR]


def test_no_rider_or_no_person_leaves_detections_unchanged() -> None:
    rows = np.asarray([_det(0, 0, 10, 10, PERSON), _det(20, 0, 30, 10, CAR)], dtype=float)

    np.testing.assert_array_equal(drop_riders(rows, CLASSES), rows)
    assert drop_riders(np.empty((0, 6)), CLASSES).shape == (0, 6)
