"""Tests for the box logic of the auto-labeller (``training/autolabel.py``).

Only the pure geometry and merging rules are tested here; the detectors
(YOLO26x, SAM 3) run in the GPU environment and are not imported.
"""

from __future__ import annotations

import pytest

from training.autolabel import (
    Box,
    apply_open_vocab,
    build_riders,
    drop_fragments,
    iou,
    merge_existing,
    to_yolo_lines,
)


def box(cls: str, x1: float, y1: float, x2: float, y2: float, conf: float = 0.9) -> Box:
    return Box(cls, x1, y1, x2, y2, conf, "test")


def test_iou_identical_and_disjoint() -> None:
    a = box("car", 0, 0, 10, 10)
    assert iou(a, a) == pytest.approx(1.0)
    assert iou(a, box("car", 20, 20, 30, 30)) == 0.0


def test_person_on_bicycle_becomes_one_cyclist_box() -> None:
    person = box("person", 10, 0, 30, 60)
    bike = box("bicycle", 5, 35, 35, 80)
    out = build_riders([person, bike])
    assert [b.cls for b in out] == ["cyclist"]
    assert (out[0].x1, out[0].y1, out[0].x2, out[0].y2) == (5, 0, 35, 80)


def test_person_on_motorcycle_becomes_motorcyclist() -> None:
    out = build_riders([box("person", 10, 0, 30, 60), box("motorcycle", 0, 30, 45, 85)])
    assert [b.cls for b in out] == ["motorcyclist"]


def test_parked_bicycle_is_dropped_and_pedestrian_kept() -> None:
    pedestrian = box("person", 200, 0, 220, 60)
    parked = box("bicycle", 5, 35, 35, 80)
    out = build_riders([pedestrian, parked])
    assert [b.cls for b in out] == ["person"]


def test_person_beside_a_bicycle_is_not_a_rider() -> None:
    # Overlaps the bicycle's edge, but stands next to it (centre outside the bicycle).
    out = build_riders([box("person", 30, 0, 50, 70), box("bicycle", 0, 35, 34, 80)])
    assert sorted(b.cls for b in out) == ["person"]


def test_each_person_rides_at_most_one_vehicle() -> None:
    person = box("person", 10, 0, 30, 60)
    bikes = [box("bicycle", 5, 35, 35, 80), box("bicycle", 8, 36, 33, 79)]
    out = build_riders([person, *bikes])
    assert [b.cls for b in out] == ["cyclist"]


def test_suv_prompt_relabels_the_matching_car_and_adds_nothing() -> None:
    car = box("car", 0, 0, 100, 60)
    suv = box("SUV", 2, 1, 98, 62, conf=0.6)
    stray = box("SUV", 300, 300, 400, 360, conf=0.9)
    out = apply_open_vocab([car], [suv, stray])
    assert [(b.cls, b.source) for b in out] == [("SUV", "test+sam3")]


def test_van_beats_suv_when_both_match_one_box() -> None:
    truck = box("truck", 0, 0, 100, 60)
    prompts = [box("SUV", 0, 0, 100, 60, conf=0.4), box("delivery_van", 0, 0, 100, 60, conf=0.7)]
    out = apply_open_vocab([truck], prompts)
    assert [b.cls for b in out] == ["delivery_van"]


def test_bus_is_never_relabelled() -> None:
    out = apply_open_vocab([box("bus", 0, 0, 100, 60)], [box("delivery_van", 0, 0, 100, 60)])
    assert [b.cls for b in out] == ["bus"]


def test_escooter_replaces_the_person_riding_it() -> None:
    person = box("person", 10, 0, 30, 60)
    scooter = box("e-scooter", 8, 0, 34, 75, conf=0.5)
    out = apply_open_vocab([person], [scooter])
    assert [b.cls for b in out] == ["e-scooter"]
    assert (out[0].x1, out[0].y2) == (8, 75)


def test_escooter_without_a_person_is_added_and_riders_are_not_duplicated() -> None:
    cyclist = box("cyclist", 0, 0, 40, 80)
    alone = box("e-scooter", 200, 0, 230, 70)
    on_cyclist = box("e-scooter", 1, 1, 40, 80)
    out = apply_open_vocab([cyclist], [alone, on_cyclist])
    assert sorted(b.cls for b in out) == ["cyclist", "e-scooter"]


def test_existing_labels_are_kept_and_only_new_objects_added() -> None:
    existing = [box("SUV", 0, 0, 100, 60)]
    auto = [box("car", 2, 2, 98, 58), box("person", 300, 0, 320, 60)]
    out = merge_existing(existing, auto)
    assert [(b.cls, b.source) for b in out] == [("SUV", "existing"), ("person", "test")]


def test_existing_box_absorbs_a_fragment_inside_it() -> None:
    existing = [box("SUV", 0, 0, 100, 60)]
    half = box("car", 0, 0, 50, 58)  # IoU < 0.5, but wholly inside the SUV
    assert [b.source for b in merge_existing(existing, [half])] == ["existing"]


def test_vehicle_fragment_inside_a_larger_vehicle_is_dropped() -> None:
    whole = box("car", 0, 0, 100, 60)
    half = box("car", 50, 2, 100, 58)
    person = box("person", 10, 10, 20, 50)  # a person in front of a car is kept
    out = drop_fragments([whole, half, person])
    assert [b.cls for b in out] == ["car", "person"]
    assert (out[0].x1, out[0].x2) == (0, 100)


def test_a_distant_car_partly_behind_a_bus_is_kept() -> None:
    bus = box("bus", 0, 0, 200, 120)
    car = box("car", 180, 60, 260, 110)  # only a quarter of it is inside the bus box
    assert len(drop_fragments([bus, car])) == 2


def test_yolo_lines_use_canonical_ids_and_clip_to_image() -> None:
    classes = ["person", "cyclist", "car"]
    lines = to_yolo_lines([box("car", -10, 0, 50, 50)], width=100, height=100, classes=classes)
    assert lines == ["2 0.250000 0.250000 0.500000 0.500000"]


def test_yolo_lines_reject_non_canonical_class() -> None:
    with pytest.raises(ValueError, match="bicycle"):
        to_yolo_lines([box("bicycle", 0, 0, 1, 1)], width=10, height=10, classes=["person"])
