"""SORT tracker: Kalman-filtered boxes matched to detections by IoU (Hungarian).

One tracker serves every class. Association ignores the class, so a detector
that flips an object between two classes (car/SUV) keeps one track; each track
keeps confidence-weighted class votes and reports the majority.
"""

from __future__ import annotations

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment

MAX_AGE = 90  # frames a track survives without a detection
IOU_THRESHOLD = 0.3  # minimum IoU to match a detection to a track


class KalmanBoxTracker:
    """One tracked object: a constant-velocity Kalman filter on (x, y, area, ratio)."""

    count = 0

    def __init__(self, det: np.ndarray) -> None:
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.eye(7) + np.eye(7, k=4)
        self.kf.H = np.eye(4, 7)
        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        self.kf.x[:4] = _box_to_z(det)

        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.time_since_update = 0
        self.hits = 0
        self.votes: dict[int, float] = {}
        self._vote(det)

    @property
    def cls(self) -> int:
        """The class with the highest summed confidence so far."""
        return max(self.votes, key=self.votes.get)

    def update(self, det: np.ndarray) -> None:
        """Correct the filter with a matched detection ``[x1, y1, x2, y2, score, cls]``."""
        self.time_since_update = 0
        self.hits += 1
        self.kf.update(_box_to_z(det))
        self._vote(det)

    def predict(self) -> np.ndarray:
        """Advance the filter one frame and return the predicted box."""
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] = 0.0
        self.kf.predict()
        self.time_since_update += 1
        return self.box

    @property
    def box(self) -> np.ndarray:
        """Current box estimate ``[x1, y1, x2, y2]``."""
        return _z_to_box(self.kf.x)

    def _vote(self, det: np.ndarray) -> None:
        cls = int(det[5])
        self.votes[cls] = self.votes.get(cls, 0.0) + float(det[4])


class Sort:
    """Multi-object tracker.

    Args:
        min_hits: Detections a track needs before it is reported.
        max_age: Frames a track survives without a detection.
        iou_threshold: Minimum IoU to match a detection to a track.
    """

    def __init__(
        self, min_hits: int = 3, max_age: int = MAX_AGE, iou_threshold: float = IOU_THRESHOLD
    ) -> None:
        self.min_hits = min_hits
        self.max_age = max_age
        self.iou_threshold = iou_threshold
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count = 0

    def update(self, dets: np.ndarray | None = None) -> np.ndarray:
        """Advance one frame.

        Args:
            dets: ``(N, 6)`` rows ``[x1, y1, x2, y2, score, class]``.

        Returns:
            ``(M, 6)`` rows ``[x1, y1, x2, y2, track_id, class]`` for the
            confirmed tracks matched on this frame; ``class`` is the vote.
        """
        dets = np.empty((0, 6)) if dets is None else dets
        self.frame_count += 1

        predictions = [t.predict() for t in self.trackers]
        alive = [i for i, p in enumerate(predictions) if not np.any(np.isnan(p))]
        self.trackers = [self.trackers[i] for i in alive]
        predictions = np.asarray([predictions[i] for i in alive]).reshape(-1, 4)

        matches, unmatched = _associate(dets, predictions, self.iou_threshold)
        for d, t in matches:
            self.trackers[t].update(dets[d])
        self.trackers += [KalmanBoxTracker(dets[d]) for d in unmatched]

        confirmed = [
            [*t.box, t.id, t.cls]
            for t in self.trackers
            if t.time_since_update == 0
            and (t.hits >= self.min_hits or self.frame_count <= self.min_hits)
        ]
        self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_age]
        return np.asarray(confirmed, dtype=float).reshape(-1, 6)


def _associate(
    dets: np.ndarray, boxes: np.ndarray, iou_threshold: float
) -> tuple[list[tuple[int, int]], list[int]]:
    """Match detections to predicted boxes; return ``(matches, unmatched detections)``."""
    if len(boxes) == 0 or len(dets) == 0:
        return [], list(range(len(dets)))
    iou = np.array([[_iou(d, b) for b in boxes] for d in dets])
    rows, cols = linear_sum_assignment(-iou)
    matches = [(d, t) for d, t in zip(rows, cols, strict=True) if iou[d, t] >= iou_threshold]
    matched = {d for d, _ in matches}
    return matches, [d for d in range(len(dets)) if d not in matched]


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _box_to_z(box: np.ndarray) -> np.ndarray:
    w, h = box[2] - box[0], box[3] - box[1]
    return np.array([[box[0] + w / 2], [box[1] + h / 2], [w * h], [w / h]], dtype=float)


def _z_to_box(x: np.ndarray) -> np.ndarray:
    w = np.sqrt(x[2, 0] * x[3, 0])
    h = x[2, 0] / w
    return np.array([x[0, 0] - w / 2, x[1, 0] - h / 2, x[0, 0] + w / 2, x[1, 0] + h / 2])
