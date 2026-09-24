"""YOLO NCNN + custom Kalman+Hungarian tracker adapter.

Wraps the fine-tuned 9-class CAMINAv1 YOLO11 NCNN detector and the existing
``src.camina.core.tracker.Sort`` (custom Kalman + Hungarian, NOT the SORT
PyPI package) into a single ``detect_and_track(frame)`` callable that yields
``(track_id_str, class_name)`` tuples for the daemon's ``WindowedCounter``.

Design notes:

- One ``Sort`` for all classes. Association ignores the class, so a detector
  that flips a vehicle between car and SUV keeps one track (it used to be
  counted once per class); the track's class is its confidence-weighted
  majority vote. The emitted id is ``"<class>-<int>"`` (``"car-7"``).
- Confidence is filtered before the tracker; ``Sort`` uses it only to
  weight class votes.
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
from src.camina.core.counting import CountGate
from src.camina.core.tracker import Sort
from src.camina.service.ncnn_detector import NcnnDetector
from src.camina.utils.taxonomy import load_class_aliases


logger = logging.getLogger(__name__)


# ---------- Public API ----------


def make_detect_and_track(
    ncnn_model_path: Path | str,
    classes: list[str],
    imgsz: int = 640,
    conf: float = 0.3,
    gate: CountGate | None = None,
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
        gate: When set, yield each track once, on the frame it crosses the
            screenline or has moved far enough (``CountGate``). When ``None``,
            yield every confirmed track on every frame.

    Returns:
        A closure ``detect_and_track(frame)`` that runs YOLO inference,
        feeds boxes into one ``Sort`` tracker, and yields
        ``(track_id_str, class_name)`` tuples for each confirmed track on
        the current frame, or only for the tracks ``gate`` counts.

    Raises:
        ValueError: when ``imgsz`` differs from the export's recorded size, or
            when the model's class names do not map onto ``classes``.
    """
    _check_export_imgsz(Path(ncnn_model_path), imgsz)

    detector = NcnnDetector(ncnn_model_path, imgsz=imgsz, conf=conf)
    model_names = [detector.names[i] for i in sorted(detector.names.keys())]
    model_to_class = _map_model_classes(model_names, classes)

    # One tracker for all classes: a class flicker (car/SUV) stays one track,
    # and the track's class is its confidence-weighted majority vote.
    tracker = Sort()
    n_model_classes = len(model_names)

    def detect_and_track(frame: np.ndarray) -> Iterable[tuple[str, str]]:
        dets = _to_canonical(detector(frame), model_to_class, n_model_classes, conf)
        tracks = [
            (int(track_id), classes[int(cls)], (x1, y1, x2, y2))
            for x1, y1, x2, y2, track_id, cls in tracker.update(dets)
        ]
        if gate is None:
            yield from ((f"{name}-{tid}", name) for tid, name, _ in tracks)
            return
        class_of = {str(tid): name for tid, name, _ in tracks}
        size = (frame.shape[1], frame.shape[0])
        for event in gate.step(((str(tid), box) for tid, _, box in tracks), size):
            name = class_of[event.key]
            logger.debug("counted %s-%s direction=%s", name, event.key, event.direction)
            yield (f"{name}-{event.key}", name)

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


def _to_canonical(
    dets: np.ndarray, model_to_class: dict[int, int], n_model_classes: int, conf: float
) -> np.ndarray:
    """Drop low-confidence detections and relabel model classes as canonical indices.

    Args:
        dets: ``(N, 6)`` rows ``[x1, y1, x2, y2, score, class]`` from ``NcnnDetector``.
        model_to_class: ``{model_idx: canonical_idx}`` from ``_map_model_classes``.
        n_model_classes: Number of model classes; other indices are an error.
        conf: Confidence floor; detections below it are dropped.

    Returns:
        ``(M, 6)`` rows with the class column in canonical indices.

    Raises:
        ValueError: when a detection's class index is outside the model's range.
    """
    dets = np.asarray(dets, dtype=float).reshape(-1, 6)
    bad = [int(c) for c in dets[:, 5] if not 0 <= int(c) < n_model_classes]
    if bad:
        raise ValueError(f"Unknown class index {bad[0]}, expected 0..{n_model_classes - 1}")
    dets = dets[dets[:, 4] >= conf].copy()
    dets[:, 5] = [model_to_class[int(c)] for c in dets[:, 5]]
    return dets


__all__ = ["make_detect_and_track"]
