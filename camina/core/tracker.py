"""SORT tracker: Kalman-filtered boxes matched to detections by IoU (Hungarian).

One tracker serves every class. Association ignores the class, so a detector
that flips an object between two classes (car/SUV) keeps one track; each track
keeps confidence-weighted class votes and reports the majority.

Time is in seconds, from the frame timestamps passed to ``Sort.update``: a
track survives ``max_occlusion_s`` without a detection whatever the frame
rate, so a slow Pi and a 60 fps clip lose a hidden object after the same time.
"""

from __future__ import annotations

import time

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment

MAX_OCCLUSION_S = 5.0  # seconds a track survives without a detection
IOU_THRESHOLD = 0.3  # minimum IoU to match a detection to a track


class KalmanBoxTracker:
    """One tracked object: a constant-velocity Kalman filter on (x, y, area, ratio)."""

    count = 0

    def __init__(self, det: np.ndarray, t: float) -> None:
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
        self.time_since_update = 0  # frames since the last detection
        self.t_obs = t  # time of the last detection, seconds
        self.hits = 0
        self.votes: dict[int, float] = {}
        self._vote(det)

    @property
    def cls(self) -> int:
        """The class with the highest summed confidence so far."""
        return max(self.votes, key=self.votes.get)

    def update(self, det: np.ndarray, t: float) -> None:
        """Correct the filter with a detection ``[x1, y1, x2, y2, score, cls]`` seen at ``t``."""
        self.time_since_update = 0
        self.t_obs = t
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
        max_occlusion_s: Seconds a track survives without a detection.
        iou_threshold: Minimum IoU to match a detection to a track.
    """

    def __init__(
        self,
        min_hits: int = 3,
        max_occlusion_s: float = MAX_OCCLUSION_S,
        iou_threshold: float = IOU_THRESHOLD,
    ) -> None:
        if max_occlusion_s <= 0:
            raise ValueError(f"max_occlusion_s must be > 0, got {max_occlusion_s}")
        self.min_hits = min_hits
        self.max_occlusion_s = max_occlusion_s
        self.iou_threshold = iou_threshold
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count = 0

    def update(self, dets: np.ndarray | None = None, t: float | None = None) -> np.ndarray:
        """Advance one frame.

        Args:
            dets: ``(N, 6)`` rows ``[x1, y1, x2, y2, score, class]``.
            t: Frame timestamp in seconds, on any clock that does not jump
                (capture time); ``None`` reads ``time.monotonic()``.

        Returns:
            ``(M, 6)`` rows ``[x1, y1, x2, y2, track_id, class]`` for the
            confirmed tracks matched on this frame; ``class`` is the vote.
        """
        dets = np.empty((0, 6)) if dets is None else dets
        t = time.monotonic() if t is None else t
        self.frame_count += 1

        # Past max_occlusion_s unseen, a track is gone: it cannot match any more.
        self.trackers = [k for k in self.trackers if t - k.t_obs <= self.max_occlusion_s]
        predictions = [k.predict() for k in self.trackers]
        alive = [i for i, p in enumerate(predictions) if not np.any(np.isnan(p))]
        self.trackers = [self.trackers[i] for i in alive]
        predictions = np.asarray([predictions[i] for i in alive]).reshape(-1, 4)

        matches, unmatched = _associate(dets, predictions, self.iou_threshold)
        for d, k in matches:
            self.trackers[k].update(dets[d], t)
        self.trackers += [KalmanBoxTracker(dets[d], t) for d in unmatched]

        confirmed = [
            [*k.box, k.id, k.cls]
            for k in self.trackers
            if k.time_since_update == 0
            and (k.hits >= self.min_hits or self.frame_count <= self.min_hits)
        ]
        return np.asarray(confirmed, dtype=float).reshape(-1, 6)


def _associate(
    dets: np.ndarray, boxes: np.ndarray, iou_threshold: float
) -> tuple[list[tuple[int, int]], list[int]]:
    """Match detections to predicted boxes; return ``(matches, unmatched detections)``."""
    if len(boxes) == 0 or len(dets) == 0:
        return [], list(range(len(dets)))
    iou = iou_matrix(dets[:, :4], boxes)
    rows, cols = linear_sum_assignment(-iou)
    matches = [(d, t) for d, t in zip(rows, cols, strict=True) if iou[d, t] >= iou_threshold]
    matched = {d for d, _ in matches}
    return matches, [d for d in range(len(dets)) if d not in matched]


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``(N, M)`` IoU of boxes ``a`` ``(N, 4)`` and ``b`` ``(M, 4)``, rows ``[x1, y1, x2, y2]``."""
    a, b = a[:, None, :4], b[None, :, :4]
    w = np.clip(np.minimum(a[..., 2], b[..., 2]) - np.maximum(a[..., 0], b[..., 0]), 0.0, None)
    h = np.clip(np.minimum(a[..., 3], b[..., 3]) - np.maximum(a[..., 1], b[..., 1]), 0.0, None)
    inter = w * h
    union = _area(a) + _area(b) - inter
    return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


def _area(box: np.ndarray) -> np.ndarray:
    return (box[..., 2] - box[..., 0]) * (box[..., 3] - box[..., 1])


def _box_to_z(box: np.ndarray) -> np.ndarray:
    w, h = box[2] - box[0], box[3] - box[1]
    return np.array([[box[0] + w / 2], [box[1] + h / 2], [w * h], [w / h]], dtype=float)


def _z_to_box(x: np.ndarray) -> np.ndarray:
    w = np.sqrt(x[2, 0] * x[3, 0])
    h = x[2, 0] / w
    return np.array([x[0, 0] - w / 2, x[1, 0] - h / 2, x[0, 0] + w / 2, x[1, 0] + h / 2])
