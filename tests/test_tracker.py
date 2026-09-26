"""Tests for the SORT tracker: one tracker for all classes, class by majority vote.

The detector can flip one vehicle between ``car`` and ``SUV`` from frame to
frame. With a tracker per class, each flip started a second track and the
vehicle was counted twice. One tracker keeps one track per object, and the
track's class is the confidence-weighted vote over its detections.
"""

from __future__ import annotations

import numpy as np

from camina.core.tracker import Sort

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
    pairs = enumerate(zip(classes, scores, strict=True))
    frames = [[_det(10 + 5 * i, s, c)] for i, (c, s) in pairs]

    assert _run(frames)[-1][0, 5] == CAR


def test_separate_objects_keep_separate_tracks_and_classes() -> None:
    frames = [[_det(10, 0.9, CAR), _det(400, 0.8, PERSON, y=300.0)]] * 4

    out = _run(frames)[-1]

    assert len({int(i) for i in out[:, 4]}) == 2
    assert sorted(out[:, 5].tolist()) == [PERSON, CAR]


def test_no_detections_returns_an_empty_six_column_array() -> None:
    assert Sort().update(np.empty((0, 6))).shape == (0, 6)


# ---------- IoU ----------


def test_iou_matrix_matches_the_pairwise_definition() -> None:
    from camina.core.tracker import iou_matrix

    a = np.array([[0, 0, 10, 10], [5, 5, 15, 15], [100, 100, 110, 120]], dtype=float)
    b = np.array([[0, 0, 10, 10], [5, 0, 15, 10]], dtype=float)

    iou = iou_matrix(a, b)

    assert iou.shape == (3, 2)
    np.testing.assert_allclose(iou, [[1.0, 50 / 150], [25 / 175, 50 / 150], [0.0, 0.0]], rtol=1e-12)
    assert iou_matrix(a, np.empty((0, 4))).shape == (3, 0)


# ---------- Occlusion, in seconds ----------


def _ids_after_gap(fps: float, gap_s: float, max_occlusion_s: float = 5.0) -> set[int]:
    """A parked car seen for 1 s, hidden for ``gap_s``, then seen again for 1 s."""
    tracker = Sort(min_hits=3, max_occlusion_s=max_occlusion_s)
    n, hidden = int(fps), round(gap_s * fps)
    ids: set[int] = set()
    for i in range(2 * n + hidden):
        visible = i < n or i >= n + hidden
        dets = np.asarray([_det(10, 0.9, CAR)] if visible else [], dtype=float).reshape(-1, 6)
        ids |= {int(r[4]) for r in tracker.update(dets, t=i / fps)}
    return ids


def test_a_track_survives_an_occlusion_shorter_than_max_occlusion_s_at_any_fps() -> None:
    for fps in (5.0, 15.0, 60.0):
        assert len(_ids_after_gap(fps, gap_s=4.8)) == 1, fps


def test_a_track_is_dropped_after_max_occlusion_s_at_any_fps() -> None:
    for fps in (5.0, 15.0, 60.0):
        assert len(_ids_after_gap(fps, gap_s=5.4)) == 2, fps


def test_max_occlusion_s_is_configurable() -> None:
    assert len(_ids_after_gap(30.0, gap_s=2.0, max_occlusion_s=1.0)) == 2


# ---------- Re-link after occlusion ----------

FPS = 30.0
PERSON_W, PERSON_H = 40.0, 100.0


def _person(x: float, cls: int = PERSON, w: float = PERSON_W, h: float = PERSON_H) -> list[float]:
    return [x, 300.0, x + w, 300.0 + h, 0.9, cls]


def _play(tracker: Sort, frames: list[list[list[float]]], t0: float = 0.0) -> list[np.ndarray]:
    out = []
    for i, rows in enumerate(frames):
        dets = np.asarray(rows, dtype=float).reshape(-1, 6)
        out.append(tracker.update(dets, t=t0 + i / FPS))
    return out


def _hidden_then(tracker: Sort, walk_s: float, hide_s: float, speed: float, row: list[float]):
    """Walk ``walk_s`` at ``speed`` px/frame from x=100, hide ``hide_s``, then show ``row``."""
    n = int(walk_s * FPS)
    seen = _play(tracker, [[_person(100.0 + speed * i)] for i in range(n)])
    hidden = int(hide_s * FPS)
    _play(tracker, [[]] * hidden, t0=n / FPS)
    return seen[-1], tracker.update(np.asarray([row], dtype=float), t=(n + hidden) / FPS)


def test_a_track_hidden_and_shifted_beyond_iou_is_relinked_with_its_id() -> None:
    """Walking at 2 px/frame, hidden 3 s, reappearing 30 px off the straight line:
    the IoU with the prediction is below 0.3, the re-link keeps the ID."""
    tracker = Sort(relink=True)
    speed, walk, hide = 2.0, 1.0, 3.0
    expected_x = 100.0 + speed * (walk + hide) * FPS
    before, after = _hidden_then(tracker, walk, hide, speed, _person(expected_x + 30.0))

    assert after.shape[0] == 1
    assert int(after[0, 4]) == int(before[0, 4])
    assert tracker.relinks == 1


def test_relinking_is_off_by_default() -> None:
    """Off until a second hand-counted clip shows it helps: on videos/test.mov it
    re-linked static false-positive 'person' tracks to passers-by (benchmark doc)."""
    tracker = Sort()
    speed, walk, hide = 2.0, 1.0, 3.0
    expected_x = 100.0 + speed * (walk + hide) * FPS
    before, after = _hidden_then(tracker, walk, hide, speed, _person(expected_x + 30.0))

    assert tracker.relinks == 0
    assert after.shape[0] == 0 or int(after[0, 4]) != int(before[0, 4])


def test_a_relinked_track_restarts_from_the_observation_not_the_prediction() -> None:
    tracker = Sort(relink=True)
    row = _person(100.0 + 2.0 * 4.0 * FPS + 30.0)
    _, after = _hidden_then(tracker, 1.0, 3.0, 2.0, row)

    np.testing.assert_allclose(after[0, :4], row[:4], atol=1e-6)


def test_a_detection_too_far_from_the_extrapolated_track_starts_a_new_track() -> None:
    # Gate after 3 s: RELINK_K * 100 * (1 + 3) = 200 px; this one is 400 px off.
    from camina.core.tracker import RELINK_K

    tracker = Sort(relink=True)
    off = RELINK_K * PERSON_H * 4.0 * 2.0
    before, after = _hidden_then(tracker, 1.0, 3.0, 2.0, _person(100.0 + 2.0 * 4 * FPS + off))

    assert int(after[0, 4]) != int(before[0, 4]) if len(after) else True
    assert tracker.relinks == 0


def test_a_detection_of_a_very_different_size_is_not_relinked() -> None:
    tracker = Sort(relink=True)
    row = _person(100.0 + 2.0 * 4.0 * FPS + 30.0, w=2.2 * PERSON_W, h=2.2 * PERSON_H)
    _hidden_then(tracker, 1.0, 3.0, 2.0, row)

    assert tracker.relinks == 0


def test_an_incompatible_class_is_not_relinked() -> None:
    tracker = Sort(relink=True)
    _hidden_then(tracker, 1.0, 3.0, 2.0, _person(100.0 + 2.0 * 4.0 * FPS + 30.0, cls=CAR))

    assert tracker.relinks == 0


def test_car_and_suv_are_compatible_for_relinking() -> None:
    from camina.core.tracker import class_groups

    classes = [
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
    tracker = Sort(compatible_classes=class_groups(classes), relink=True)
    n, hidden = int(FPS), int(3 * FPS)
    _play(tracker, [[_person(100.0 + 2.0 * i, cls=CAR)] for i in range(n)])
    _play(tracker, [[]] * hidden, t0=n / FPS)
    x = 100.0 + 2.0 * (n + hidden) + 30.0
    tracker.update(np.asarray([_person(x, cls=SUV)], dtype=float), t=(n + hidden) / FPS)

    assert tracker.relinks == 1


def test_class_groups_follow_the_owner_rule() -> None:
    from camina.core.tracker import class_groups

    classes = [
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
    groups = class_groups(classes)
    ok = {frozenset((a, b)) for g in groups for a in g for b in g if a != b}
    idx = classes.index

    assert frozenset((idx("car"), idx("SUV"))) in ok
    assert frozenset((idx("delivery_van"), idx("truck"))) in ok
    assert frozenset((idx("delivery_van"), idx("car"))) in ok
    assert frozenset((idx("truck"), idx("car"))) in ok
    assert frozenset((idx("SUV"), idx("truck"))) not in ok
    assert frozenset((idx("person"), idx("cyclist"))) not in ok


def test_relinking_is_an_optimal_assignment_not_greedy() -> None:
    """Two parked people A (x=0) and B (x=100) vanish for 0.5 s. Detections come
    back at 55 and 160. Greedy would take the cheapest pair B-55 first and leave
    160 too far from A; the optimal assignment gives A-55 and B-160."""
    tracker = Sort(relink=True)
    frames = [[_person(0.0), _person(100.0)]] * int(FPS)
    seen = _play(tracker, frames)[-1]
    id_at = {float(r[0]): int(r[4]) for r in seen}
    _play(tracker, [[]] * int(0.5 * FPS), t0=1.0)
    out = tracker.update(np.asarray([_person(55.0), _person(160.0)], dtype=float), t=1.0 + 0.5)

    got = {round(float(r[0])): int(r[4]) for r in out}
    assert got == {55: id_at[0.0], 160: id_at[100.0]}
    assert tracker.relinks == 2


# ---------- Class confirmation ----------


def _unconfirmed_after(frames: list[list[list[float]]], min_class_hits: int = 3) -> set[int]:
    tracker = Sort(min_hits=1, min_class_hits=min_class_hits)
    _play(tracker, frames)
    return tracker.unconfirmed_ids


def test_a_class_is_confirmed_after_min_class_hits_detections_of_it() -> None:
    frames = [[_det(10, 0.9, CAR)]] * 3

    assert len(_unconfirmed_after(frames[:2])) == 1
    assert _unconfirmed_after(frames) == set()


def test_the_winning_class_needs_its_own_hits_not_the_track_total() -> None:
    """Car wins the vote (2 x 0.9 > 3 x 0.3) but was seen as car on 2 frames only."""
    classes = [CAR, SUV, SUV, CAR, SUV]
    scores = [0.9, 0.3, 0.3, 0.9, 0.3]
    frames = [[_det(10, s, c)] for c, s in zip(classes, scores, strict=True)]

    assert len(_unconfirmed_after(frames)) == 1
    assert _unconfirmed_after([*frames, [_det(10, 0.9, CAR)]]) == set()


def test_min_class_hits_counts_total_not_consecutive_frames() -> None:
    frames = [[_det(10, 0.9, c)] for c in (CAR, SUV, CAR, SUV, CAR)]

    assert _unconfirmed_after(frames) == set()
