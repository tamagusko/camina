"""Drop the ``person`` box the detector puts on a rider.

A cyclist, e-scooter rider or motorcyclist is often detected twice: once as the
rider class and once as a ``person`` inside that box. Tracked as is, the rider
is counted twice, once as a pedestrian. Before tracking, a ``person`` detection
is dropped when at least ``RIDER_OVERLAP`` of its own box area lies inside a
rider detection of the same frame. Measuring on the person box (not IoU) keeps
a pedestrian walking beside a bicycle: their boxes overlap, but most of the
pedestrian is outside it.
"""

from __future__ import annotations

import numpy as np

RIDER_OVERLAP = 0.6  # share of the person box inside a rider box to call it the rider
RIDER_CLASSES = ("cyclist", "e-scooter", "motorcyclist")
PERSON = "person"


def drop_riders(dets: np.ndarray, classes: list[str]) -> np.ndarray:
    """Remove ``person`` rows that lie mostly inside a rider row.

    Args:
        dets: ``(N, 6)`` rows ``[x1, y1, x2, y2, score, class]``, class as an
            index into ``classes``.
        classes: Class names in index order.

    Returns:
        ``dets`` without the rider ``person`` rows.
    """
    if PERSON not in classes or len(dets) == 0:
        return dets
    rider_ids = [classes.index(c) for c in RIDER_CLASSES if c in classes]
    is_person = dets[:, 5] == classes.index(PERSON)
    is_rider = np.isin(dets[:, 5], rider_ids)
    if not is_person.any() or not is_rider.any():
        return dets
    persons, riders = dets[is_person, None, :4], dets[None, is_rider, :4]
    w = np.minimum(persons[..., 2], riders[..., 2]) - np.maximum(persons[..., 0], riders[..., 0])
    h = np.minimum(persons[..., 3], riders[..., 3]) - np.maximum(persons[..., 1], riders[..., 1])
    inter = np.clip(w, 0.0, None) * np.clip(h, 0.0, None)
    area = (persons[..., 2] - persons[..., 0]) * (persons[..., 3] - persons[..., 1])
    ratio = np.divide(inter, area, out=np.zeros_like(inter), where=area > 0)
    keep = np.ones(len(dets), dtype=bool)
    keep[np.flatnonzero(is_person)[(ratio >= RIDER_OVERLAP).any(axis=1)]] = False
    return dets[keep]


__all__ = ["RIDER_CLASSES", "RIDER_OVERLAP", "drop_riders"]
