"""Tests for count evaluation: hand-count files and count error against them.

A hand count is done one class per pass: every screenline crossing of that
class, with its direction. A pass is complete only when the whole clip was
played; only complete classes are compared. S7's done-test passes a class and
direction when the error is within 20 % (at least 20 true crossings) or within
5 counts (rarer).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from camina.core.counting import Screenline
from training.count_eval import (
    compare,
    mark_complete,
    read_truth,
    start_pass,
    write_event,
    write_header,
)

LINE = Screenline((0.65, 0.15), (0.65, 0.72))


def test_a_hand_count_file_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "clip.counts.csv"
    write_header(path, LINE)
    write_event(path, 120, "person", "AB")
    write_event(path, 480, "car", "BA")
    write_event(path, 481, "car", "BA")
    mark_complete(path, "car")

    line, counts, complete = read_truth(path)

    assert line == LINE
    assert counts == Counter({("person", "AB"): 1, ("car", "BA"): 2})
    assert complete == {"car"}


def test_starting_a_pass_replaces_that_class_only(tmp_path: Path) -> None:
    path = tmp_path / "clip.counts.csv"
    write_header(path, LINE)
    write_event(path, 10, "person", "AB")
    write_event(path, 20, "car", "AB")
    mark_complete(path, "person")
    mark_complete(path, "car")

    start_pass(path, "person")

    _, counts, complete = read_truth(path)
    assert counts == Counter({("car", "AB"): 1})
    assert complete == {"car"}


def test_an_unknown_direction_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "clip.counts.csv"
    write_header(path, LINE)
    write_event(path, 10, "car", "left")

    with pytest.raises(ValueError, match="direction"):
        read_truth(path)


def test_only_complete_classes_are_compared() -> None:
    truth = Counter({("car", "AB"): 12})
    counted = Counter({("car", "AB"): 12, ("person", "AB"): 3})

    rows = compare(truth, counted, classes={"car"})

    assert [(r.cls, r.direction) for r in rows] == [("car", "AB")]


def test_compare_reports_error_per_class_and_direction() -> None:
    truth = Counter({("car", "AB"): 12, ("car", "BA"): 10, ("person", "AB"): 3})
    counted = Counter({("car", "AB"): 12, ("car", "BA"): 11, ("person", "BA"): 1})

    rows = {(r.cls, r.direction): r for r in compare(truth, counted, {"car", "person"})}

    assert rows[("car", "BA")].truth == 10 and rows[("car", "BA")].counted == 11
    assert rows[("person", "AB")].error == -3
    assert rows[("person", "BA")].error == 1


def test_s7_threshold_is_20_percent_for_common_classes_else_5_counts() -> None:
    truth = Counter({("car", "AB"): 25, ("person", "AB"): 4})

    ok = {
        r.cls: r.passes
        for r in compare(
            truth, Counter({("car", "AB"): 30, ("person", "AB"): 9}), {"car", "person"}
        )
    }
    bad = {
        r.cls: r.passes
        for r in compare(
            truth, Counter({("car", "AB"): 31, ("person", "AB"): 10}), {"car", "person"}
        )
    }

    assert ok == {"car": True, "person": True}  # 5/25 = 20 %; |9 - 4| = 5
    assert bad == {"car": False, "person": False}
