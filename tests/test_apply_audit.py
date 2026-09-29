"""Tests for applying audit decisions to YOLO labels (``training/apply_audit.py``).

Only the label logic is tested; the Roboflow push needs the network and a key.
"""

from __future__ import annotations

from training.apply_audit import (
    Decision,
    apply_edits,
    find_line,
    roboflow_labelmap,
    tags_for,
)

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
# A 200x100 image with two boxes: an SUV (x 20-60, y 10-50) and a person (x 100-120, y 0-80).
LINES = ["4 0.200000 0.300000 0.200000 0.400000", "0 0.550000 0.400000 0.100000 0.800000"]


def test_find_line_matches_the_box_by_position() -> None:
    assert find_line(LINES, (100.0, 0.0, 120.0, 80.0), 200, 100) == 1
    assert find_line(LINES, (20.5, 10.0, 60.0, 49.5), 200, 100) == 0


def test_find_line_returns_none_for_a_box_not_in_the_labels() -> None:
    # A box the pre-labeller added: nothing in the file overlaps it.
    assert find_line(LINES, (150.0, 60.0, 190.0, 95.0), 200, 100) is None


def test_change_rewrites_only_the_class_id() -> None:
    out = apply_edits(LINES, {0: Decision("change", "car")}, CLASSES)
    assert out == ["2 0.200000 0.300000 0.200000 0.400000", LINES[1]]


def test_delete_removes_the_line_and_keep_leaves_it() -> None:
    edits = {0: Decision("delete", ""), 1: Decision("keep", "person")}
    assert apply_edits(LINES, edits, CLASSES) == [LINES[1]]


def test_fix_box_leaves_the_labels_alone() -> None:
    assert apply_edits(LINES, {0: Decision("fix_box", "")}, CLASSES) == LINES


def test_tags_mark_label_changes_and_boxes_to_redraw() -> None:
    assert tags_for([Decision("change", "car"), Decision("keep", "SUV")]) == ["audit-fixed"]
    assert tags_for([Decision("fix_box", ""), Decision("delete", "")]) == [
        "audit-box",
        "audit-fixed",
    ]
    assert tags_for([Decision("keep", "SUV")]) == []


def test_labelmap_uses_the_roboflow_project_names() -> None:
    lm = roboflow_labelmap(CLASSES)
    assert lm["0"] == "person" and lm["4"] == "SUV"
    assert lm["5"] == "motorcycle"  # the project's name for motorcyclist
