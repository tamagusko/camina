"""YOLO NCNN + custom Kalman+Hungarian tracker adapter.

Wraps the fine-tuned 9-class CAMINAv1 YOLO11 NCNN detector and the existing
``src.camina.core.tracker.Sort`` (custom Kalman + Hungarian, NOT the SORT
PyPI package) into a single ``detect_and_track(frame)`` callable that yields
``(track_id_str, class_name)`` tuples for the daemon's ``WindowedCounter``.

Design notes:

- One ``Sort`` instance per class. Each ``Sort`` only tracks bboxes that came
  from one detector class, so its integer track-ids are class-scoped. We
  prefix the emitted track-id string with the class name (``"car-7"``) so two
  classes can never collide on the same string key in ``WindowedCounter``.
- Confidence is filtered before the tracker (Test 2). ``Sort`` itself does
  not consult confidence.
- Class indices outside ``0..len(classes)-1`` raise ``ValueError`` (Test 3)
  — this catches the "wrong model loaded" failure mode loudly.
- ``model.names`` is verified against the configured ``classes`` list at
  closure creation (Test 4). Mismatch raises ``ValueError`` before any
  frame ever reaches the tracker.

Plan deviation note: the plan's interfaces block sketched a hypothetical
``Tracker`` class with a ``TrackedObject``-returning API. The codebase's
existing tracker is ``Sort`` (returning ``np.ndarray`` rows of
``[x1, y1, x2, y2, id]``). Per the plan's "reuse, do not reimplement"
directive, this adapter wires ``Sort`` directly. See plan 01-01-SUMMARY.md
for full deviation context.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from ultralytics import YOLO

from src.camina.core.tracker import Sort


logger = logging.getLogger(__name__)


# ---------- Public API ----------


def make_detect_and_track(
    ncnn_model_path: Path | str,
    classes: list[str],
    imgsz: int = 480,
    conf: float = 0.3,
) -> Callable[[np.ndarray], Iterable[tuple[str, str]]]:
    """Build a ``detect_and_track(frame)`` closure wiring YOLO NCNN -> Sort.

    Args:
        ncnn_model_path: Path to the exported NCNN model directory
            (e.g. ``models/20250629_warmup_best_ncnn_model/``).
        classes: Canonical class list in CAMINAv1 order. Must equal the
            loaded model's ``names`` attribute, in order.
        imgsz: Square YOLO inference size. Must match the NCNN export.
        conf: Confidence threshold; detections below this are dropped before
            the tracker.

    Returns:
        A closure ``detect_and_track(frame)`` that runs YOLO inference,
        feeds boxes into per-class ``Sort`` trackers, and yields
        ``(track_id_str, class_name)`` tuples for each confirmed track on
        the current frame.

    Raises:
        ValueError: when ``model.names`` does not match ``classes`` in order.
    """
    model = YOLO(str(ncnn_model_path))
    names_list = [model.names[i] for i in sorted(model.names.keys())]
    if names_list != classes:
        raise ValueError(
            f"Model classes {names_list} do not match config {classes}"
        )

    # One tracker per class so each Sort's integer ids stay class-scoped.
    trackers: dict[int, Sort] = {i: Sort() for i in range(len(classes))}
    n_classes = len(classes)

    def detect_and_track(frame: np.ndarray) -> Iterable[tuple[str, str]]:
        results = model(frame, verbose=False, imgsz=imgsz, conf=conf)
        if not results:
            return
        r = results[0]

        per_class_dets = _split_detections_by_class(r, n_classes, conf)

        for cls_idx, dets in per_class_dets.items():
            class_name = classes[cls_idx]
            tracker = trackers[cls_idx]
            tracked = tracker.update(dets) if dets.size else tracker.update()
            for row in tracked:
                track_id_int = int(row[4])
                yield (f"{class_name}-{track_id_int}", class_name)

    return detect_and_track


# ---------- Internal ----------


def _split_detections_by_class(
    result, n_classes: int, conf_threshold: float
) -> dict[int, np.ndarray]:
    """Group YOLO detections by class index.

    Args:
        result: A single Ultralytics ``Results`` object with ``boxes``.
        n_classes: Length of the class taxonomy; class indices outside
            ``0..n_classes-1`` raise ``ValueError``.
        conf_threshold: Confidence floor; detections below are dropped.

    Returns:
        ``{class_idx: np.ndarray of shape (N, 5)}`` where each row is
        ``[x1, y1, x2, y2, conf]``. Classes with no detections still get
        an empty entry so the per-class tracker still gets ``predict()``
        called via ``update()`` on the next frame.

    Raises:
        ValueError: when any detection has class index outside the valid
            range.
    """
    grouped: dict[int, list[list[float]]] = {i: [] for i in range(n_classes)}

    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return {i: np.empty((0, 5)) for i in range(n_classes)}

    cls_arr = np.asarray(boxes.cls).reshape(-1).astype(int)
    conf_arr = np.asarray(boxes.conf).reshape(-1).astype(float)
    xyxy_arr = np.asarray(boxes.xyxy).reshape(-1, 4).astype(float)

    for cls_idx, c, box in zip(cls_arr, conf_arr, xyxy_arr):
        if not (0 <= cls_idx < n_classes):
            raise ValueError(
                f"Unknown class index {cls_idx}, expected 0..{n_classes - 1}"
            )
        if c < conf_threshold:
            continue
        grouped[int(cls_idx)].append([box[0], box[1], box[2], box[3], c])

    return {
        i: (np.asarray(rows, dtype=float) if rows else np.empty((0, 5)))
        for i, rows in grouped.items()
    }


__all__ = ["make_detect_and_track"]
