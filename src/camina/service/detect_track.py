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
- Class indices outside the model's ``0..len(names)-1`` raise ``ValueError``
  (Test 3) — this catches the "wrong model loaded" failure mode loudly.
- ``model.names`` is mapped onto the configured ``classes`` BY NAME through
  ``custom_model_train/class_mapping.yaml`` at closure creation. The TRA 2026
  export lists classes alphabetically and says ``motorcycle``; the mapping
  turns each model index into the canonical index. An unknown, missing or
  duplicated class raises ``ValueError`` before any frame reaches the tracker.
- The requested ``imgsz`` is checked against the export's ``metadata.yaml``.
  An NCNN model run at a size other than its export size returns garbage
  boxes (audit 2026-09-15: 300 boxes per image at 480 for a 640 export).

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
import yaml
from ultralytics import YOLO

from src.camina.core.tracker import Sort
from src.utils.export_ncnn import load_class_aliases


logger = logging.getLogger(__name__)


# ---------- Public API ----------


def make_detect_and_track(
    ncnn_model_path: Path | str,
    classes: list[str],
    imgsz: int = 640,
    conf: float = 0.3,
) -> Callable[[np.ndarray], Iterable[tuple[str, str]]]:
    """Build a ``detect_and_track(frame)`` closure wiring YOLO NCNN -> Sort.

    Args:
        ncnn_model_path: Path to the exported NCNN model directory
            (e.g. ``models/camina_v1_yolo11n_ncnn_model/``).
        classes: Canonical class list in CAMINAv1 order. The loaded model's
            ``names`` must cover exactly these classes after alias mapping;
            their order may differ.
        imgsz: Square YOLO inference size. Must match the NCNN export.
        conf: Confidence threshold; detections below this are dropped before
            the tracker.

    Returns:
        A closure ``detect_and_track(frame)`` that runs YOLO inference,
        feeds boxes into per-class ``Sort`` trackers, and yields
        ``(track_id_str, class_name)`` tuples for each confirmed track on
        the current frame.

    Raises:
        ValueError: when ``imgsz`` differs from the export's recorded size, or
            when the model's class names do not map onto ``classes``.
    """
    _check_export_imgsz(Path(ncnn_model_path), imgsz)

    model = YOLO(str(ncnn_model_path))
    model_names = [model.names[i] for i in sorted(model.names.keys())]
    model_to_class = _map_model_classes(model_names, classes)

    # One tracker per class so each Sort's integer ids stay class-scoped.
    trackers: dict[int, Sort] = {i: Sort() for i in range(len(classes))}
    n_model_classes = len(model_names)

    def detect_and_track(frame: np.ndarray) -> Iterable[tuple[str, str]]:
        results = model(frame, verbose=False, imgsz=imgsz, conf=conf)
        if not results:
            return
        r = results[0]

        per_class_dets = _split_detections_by_class(r, n_model_classes, conf)

        for model_idx, dets in per_class_dets.items():
            cls_idx = model_to_class[model_idx]
            class_name = classes[cls_idx]
            tracker = trackers[cls_idx]
            tracked = tracker.update(dets) if dets.size else tracker.update()
            for row in tracked:
                track_id_int = int(row[4])
                yield (f"{class_name}-{track_id_int}", class_name)

    return detect_and_track


# ---------- Internal ----------


def _check_export_imgsz(ncnn_model_path: Path, imgsz: int) -> None:
    """Refuse an inference size that differs from the NCNN export size.

    Args:
        ncnn_model_path: NCNN model directory; its ``metadata.yaml`` records
            the export ``imgsz`` (``[h, w]`` or a single int).
        imgsz: Requested square inference size.

    Raises:
        ValueError: when the recorded export size differs from ``imgsz``.
    """
    meta_path = ncnn_model_path / "metadata.yaml"
    if not meta_path.is_file():
        logger.warning(
            "No metadata.yaml in %s; cannot verify the export imgsz", ncnn_model_path
        )
        return
    with meta_path.open("r", encoding="utf-8") as f:
        exported = (yaml.safe_load(f) or {}).get("imgsz")
    if isinstance(exported, list):
        exported = exported[0]
    if exported is not None and int(exported) != imgsz:
        raise ValueError(
            f"imgsz {imgsz} does not match the NCNN export imgsz {exported} "
            f"({meta_path}); set imgsz to the export size"
        )


def _map_model_classes(model_names: list[str], classes: list[str]) -> dict[int, int]:
    """Map each model class index to its index in the canonical ``classes``.

    Args:
        model_names: The loaded model's class names, in model index order.
        classes: Canonical class list in CAMINAv1 order.

    Returns:
        ``{model_idx: canonical_idx}`` covering every model class.

    Raises:
        ValueError: when a model name has no alias entry, or when the mapped
            names are not exactly the canonical classes (missing, extra or
            duplicated).
    """
    aliases = load_class_aliases()
    unmapped = [n for n in model_names if n not in aliases]
    if unmapped:
        raise ValueError(
            f"Model class name(s) {unmapped} have no entry in "
            f"custom_model_train/class_mapping.yaml"
        )
    mapped = [aliases[n] for n in model_names]
    if sorted(mapped) != sorted(classes) or len(set(mapped)) != len(mapped):
        raise ValueError(
            f"Model classes {mapped} (after alias mapping) do not match config {classes}"
        )
    return {i: classes.index(name) for i, name in enumerate(mapped)}


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
