"""Tests for the Montreal import rules (``training/import_montreal.py``).

Only parsing and the reconcile rules are tested; the detectors run in the GPU
environment and are not imported.
"""

from __future__ import annotations

from pathlib import Path

from training.autolabel import Box
from training.import_montreal import read_voc, reconcile


def box(cls: str, x1: float, y1: float, x2: float, y2: float, source: str = "coco") -> Box:
    return Box(cls, x1, y1, x2, y2, 0.9, source)


VOC = """<annotation><size><width>704</width><height>480</height><depth>3</depth></size>
<object><name>vehicle</name><bndbox><xmin>10</xmin><ymin>20</ymin><xmax>110</xmax>
<ymax>80</ymax></bndbox></object>
<object><name>construction</name><bndbox><xmin>1</xmin><ymin>1</ymin><xmax>5</xmax>
<ymax>5</ymax></bndbox></object>
</annotation>"""


def test_read_voc_returns_size_and_boxes(tmp_path: Path) -> None:
    xml = tmp_path / "a.xml"
    xml.write_text(VOC)
    (w, h), boxes = read_voc(xml)
    assert (w, h) == (704, 480)
    assert [(b.cls, b.x1, b.y2) for b in boxes] == [("vehicle", 10, 80), ("construction", 1, 5)]
    assert all(b.source == "montreal" for b in boxes)


def test_vehicle_takes_the_detector_class_and_keeps_the_human_box() -> None:
    human = box("vehicle", 0, 0, 100, 50, "montreal")
    out = reconcile([human], [box("truck", 2, 1, 101, 52)])
    assert [(b.cls, b.x1, b.x2, b.source) for b in out] == [("truck", 0, 100, "montreal+coco")]


def test_unmatched_vehicle_defaults_to_car_and_is_marked() -> None:
    out = reconcile([box("vehicle", 0, 0, 10, 8, "montreal")], [])
    assert [(b.cls, b.source) for b in out] == [("car", "montreal-default")]


def test_vehicle_matched_by_a_person_detection_stays_car() -> None:
    out = reconcile([box("vehicle", 0, 0, 100, 50, "montreal")], [box("person", 0, 0, 100, 50)])
    assert [b.cls for b in out] == ["car"]


def test_known_classes_are_renamed_to_canonical() -> None:
    labels = [
        box("pedestrian", 0, 0, 10, 30, "montreal"),
        box("cyclist", 50, 0, 70, 40, "montreal"),
        box("bus", 100, 0, 200, 60, "montreal"),
    ]
    assert [b.cls for b in reconcile(labels, [])] == ["person", "cyclist", "bus"]


def test_pedestrian_on_an_e_scooter_takes_the_scooter_box() -> None:
    walker = box("pedestrian", 10, 0, 30, 60, "montreal")
    scooter = box("e-scooter", 8, 0, 32, 70, "coco+sam3")
    out = reconcile([walker], [scooter])
    assert [(b.cls, b.y2) for b in out] == [("e-scooter", 70)]


def test_bus_label_is_kept_even_if_the_detector_says_truck() -> None:
    out = reconcile([box("bus", 0, 0, 100, 50, "montreal")], [box("truck", 0, 0, 100, 50)])
    assert [b.cls for b in out] == ["bus"]


def test_construction_is_dropped_and_blocks_detections_on_it() -> None:
    cone = box("construction", 0, 0, 20, 20, "montreal")
    out = reconcile([cone], [box("truck", 0, 0, 20, 20)])
    assert out == []


def test_new_detection_is_added_and_marked() -> None:
    out = reconcile([], [box("motorcyclist", 0, 0, 20, 40)])
    assert [(b.cls, b.source) for b in out] == [("motorcyclist", "coco-new")]


def test_detection_on_a_labelled_object_is_not_added_twice() -> None:
    out = reconcile([box("pedestrian", 0, 0, 10, 30, "montreal")], [box("person", 0, 0, 10, 31)])
    assert len(out) == 1
