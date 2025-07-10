from __future__ import annotations

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment

from src.camina.utils.config import load_config

CONFIG = load_config()


class KalmanBoxTracker:
    count = 0

    def __init__(self, bbox: np.ndarray):
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array(
            [[1, 0, 0, 0, 1, 0, 0],
             [0, 1, 0, 0, 0, 1, 0],
             [0, 0, 1, 0, 0, 0, 1],
             [0, 0, 0, 1, 0, 0, 0],
             [0, 0, 0, 0, 1, 0, 0],
             [0, 0, 0, 0, 0, 1, 0],
             [0, 0, 0, 0, 0, 0, 1]],
            dtype=float,
        )
        self.kf.H = np.array(
            [[1, 0, 0, 0, 0, 0, 0],
             [0, 1, 0, 0, 0, 0, 0],
             [0, 0, 1, 0, 0, 0, 0],
             [0, 0, 0, 1, 0, 0, 0]],
            dtype=float,
        )
        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        self.kf.x[:4] = self._bbox_to_z(bbox)

        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.time_since_update = 0
        self.hits = 0
        self.hit_streak = 0
        self.age = 0

    def update(self, bbox: np.ndarray) -> None:
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(self._bbox_to_z(bbox))

    def predict(self) -> np.ndarray:
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] = 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        return self._x_to_bbox(self.kf.x)

    def get_state(self) -> np.ndarray:
        return self._x_to_bbox(self.kf.x)

    @staticmethod
    def _bbox_to_z(bbox: np.ndarray) -> np.ndarray:
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = bbox[0] + w / 2.0, bbox[1] + h / 2.0
        s, r = w * h, w / float(h)
        return np.array([[x], [y], [s], [r]], dtype=float)

    @staticmethod
    def _x_to_bbox(x: np.ndarray) -> np.ndarray:
        w, h = np.sqrt(x[2] * x[3]), x[2] / np.sqrt(x[2] * x[3])
        return np.array([x[0] - w / 2.0, x[1] - h / 2.0,
                         x[0] + w / 2.0, x[1] + h / 2.0]).reshape((4,))


class Sort:
    def __init__(self, min_hits: int = 3):
        self.max_age = CONFIG.get("sort_max_age")
        self.min_hits = min_hits
        self.iou_threshold = CONFIG.get("sort_iou_threshold")
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count = 0

    def update(self, dets: np.ndarray = np.empty((0, 5))) -> np.ndarray:
        self.frame_count += 1

        predictions, dead_idx = [], []
        for t, trk in enumerate(self.trackers):
            pos = trk.predict()
            if np.any(np.isnan(pos)):
                dead_idx.append(t)
            else:
                predictions.append(pos)

        for idx in reversed(dead_idx):
            self.trackers.pop(idx)

        matches, unmatched_dets, unmatched_trks = _associate(
            dets, np.asarray(predictions), self.iou_threshold
        )

        for det_idx, trk_idx in matches:
            self.trackers[trk_idx].update(dets[det_idx, :])

        for idx in unmatched_dets:
            self.trackers.append(KalmanBoxTracker(dets[idx, :]))

        ret = []
        for trk in self.trackers[:]:
            d = trk.get_state()
            if (trk.time_since_update < 1
                    and (trk.hits >= self.min_hits or self.frame_count <= self.min_hits)):
                ret.append(np.concatenate((d, [trk.id])).reshape(1, -1))
            if trk.time_since_update > self.max_age:
                self.trackers.remove(trk)

        return np.concatenate(ret) if ret else np.empty((0, 5))


def _associate(detections: np.ndarray, trackers: np.ndarray,
               iou_threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if trackers.size == 0:
        return (np.empty((0, 2), dtype=int),
                np.arange(len(detections)),
                np.empty((0,), dtype=int))

    iou_mat = np.zeros((len(detections), len(trackers)), dtype=float)
    for d, det in enumerate(detections):
        for t, trk in enumerate(trackers):
            iou_mat[d, t] = _iou(det, trk)

    row, col = linear_sum_assignment(-iou_mat)
    matches, unmatched_dets, unmatched_trks = [], list(range(len(detections))), list(range(len(trackers)))

    for d, t in zip(row, col):
        if iou_mat[d, t] >= iou_threshold:
            matches.append([d, t])
            unmatched_dets.remove(d)
            unmatched_trks.remove(t)

    return (np.asarray(matches, dtype=int),
            np.asarray(unmatched_dets, dtype=int),
            np.asarray(unmatched_trks, dtype=int))


def _iou(bb1: np.ndarray, bb2: np.ndarray) -> float:
    xx1, yy1 = np.maximum(bb1[0], bb2[0]), np.maximum(bb1[1], bb2[1])
    xx2, yy2 = np.minimum(bb1[2], bb2[2]), np.minimum(bb1[3], bb2[3])
    w, h = np.maximum(0.0, xx2 - xx1), np.maximum(0.0, yy2 - yy1)
    inter = w * h
    union = ((bb1[2] - bb1[0]) * (bb1[3] - bb1[1])
             + (bb2[2] - bb2[0]) * (bb2[3] - bb2[1]) - inter)
    return inter / union if union > 0 else 0.0
