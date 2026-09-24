"""Tests for the SORT tracker: one tracker for all classes, class by majority vote.

The detector can flip one vehicle between ``car`` and ``SUV`` from frame to
frame. With a tracker per class, each flip started a second track and the
vehicle was counted twice. One tracker keeps one track per object, and the
track's class is the confidence-weighted vote over its detections.
"""
from __future__ import annotations

import numpy as np

from src.camina.core.tracker import Sort

CAR, SUV, PERSON = 2, 4, 0


def _det(x: float, score: float, cls: int, y: float = 100.0) -> list[float]:
    return [x, y, x + 60.0, y + 40.0, score, cls]


def _run(frames: list[list[list[float]]]) -> list[np.ndarray]:
    tracker = Sort(min_hits=3)
    return [tracker.update(np.asarray(f, dtype=float).reshape(-1, 6)) for f in frames]


def test_output_rows_are_box_id_and_class() -> None:
    out = _run([[_det(10, 0.9, CAR)]] * 4)[-1]

    assert out.shape == (1, 6)
    assert out[0, 5] == CAR


def test_class_flicker_keeps_one_track() -> None:
    frames = [[_det(10 + 5 * i, 0.9, CAR if i % 2 else SUV)] for i in range(10)]

    ids = {int(row[4]) for out in _run(frames) for row in out}

    assert len(ids) == 1


def test_track_class_is_the_confidence_weighted_majority() -> None:
    # Three SUV frames at 0.4 (total 1.2) lose to two car frames at 0.9 (1.8).
    classes = [SUV, CAR, SUV, CAR, SUV]
    scores = [0.4, 0.9, 0.4, 0.9, 0.4]
    frames = [[_det(10 + 5 * i, s, c)] for i, (c, s) in enumerate(zip(classes, scores))]

    assert _run(frames)[-1][0, 5] == CAR


def test_separate_objects_keep_separate_tracks_and_classes() -> None:
    frames = [[_det(10, 0.9, CAR), _det(400, 0.8, PERSON, y=300.0)]] * 4

    out = _run(frames)[-1]

    assert len({int(i) for i in out[:, 4]}) == 2
    assert sorted(out[:, 5].tolist()) == [PERSON, CAR]


def test_no_detections_returns_an_empty_six_column_array() -> None:
    assert Sort().update(np.empty((0, 6))).shape == (0, 6)
