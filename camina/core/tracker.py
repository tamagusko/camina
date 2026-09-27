"""SORT tracker: Kalman-filtered boxes matched to detections by IoU (Hungarian).

One tracker serves every class. Association ignores the class, so a detector
that flips an object between two classes (car/SUV) keeps one track; each track
keeps confidence-weighted class votes and reports the majority.

Time is in seconds, from the frame timestamps passed to ``Sort.update``: a
track survives ``max_occlusion_s`` without a detection whatever the frame
rate, so a slow Pi and a 60 fps clip lose a hidden object after the same time.

Re-link after occlusion (after OC-SORT's observation-centric recovery). While
an object is hidden the Kalman prediction drifts, so when it reappears the IoU
with the prediction is often too low and SORT starts a second track, which the
count gate may count again. After the IoU association, the detections left
over are matched (Hungarian) to the tracks left over by distance to each
track's last *observed* centre, moved on by its last observed velocity. A pair
is allowed only when

- the distance is at most ``RELINK_K`` box heights times ``1 + elapsed s``,
- the areas are within ``RELINK_SIZE_RATIO`` of each other, and
- the classes are the same or in one ``COMPATIBLE_CLASSES`` group.

A re-linked track keeps its ID and restarts its filter from the observation.

Class confirmation: a track's class is *confirmed* when its winning vote was
also detected on at least ``min_class_hits`` frames (in total, not in a row).
``Sort.unconfirmed_ids`` lists the reported tracks whose class is not, so the
count gate can hold them until it is.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment

from camina.core.tracking_rules import check_tracking_rules

MAX_OCCLUSION_S = 5.0  # seconds a track survives without a detection
MIN_CLASS_HITS = 3  # detections of the winning class before it is confirmed
IOU_THRESHOLD = 0.3  # minimum IoU to match a detection to a track

# Re-link gate radius, in the track's last observed box heights per (1 + s hidden):
# half a box height at once, 3 box heights after 5 s. Kept low on purpose; a
# larger radius starts stealing detections of the next road user in a queue.
RELINK_K = 0.5
RELINK_SIZE_RATIO = (0.5, 2.0)  # allowed detection/track box-area ratio
VELOCITY_WINDOW_S = 0.5  # observed velocity: displacement over about this span
# Classes the detector confuses on one vehicle; a re-link may cross them.
COMPATIBLE_CLASSES = (("car", "SUV"), ("delivery_van", "truck", "car"))


class KalmanBoxTracker:
    """One tracked object: a constant-velocity Kalman filter on (x, y, area, ratio)."""

    count = 0

    def __init__(self, det: np.ndarray, t: float) -> None:
        self.kf = _new_filter(det)
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.time_since_update = 0  # frames since the last detection
        self.t_obs = t  # time of the last detection, seconds
        self.last_obs = np.asarray(det[:4], dtype=float)  # last detected box
        self._centres: deque[tuple[float, float, float]] = deque(maxlen=64)  # (t, cx, cy)
        self._centres.append((t, *_centre(self.last_obs)))
        self.hits = 0
        self.votes: dict[int, float] = {}
        self.class_hits: dict[int, int] = {}  # frames detected as each class
        self._vote(det)

    @property
    def cls(self) -> int:
        """The class with the highest summed confidence so far."""
        return max(self.votes, key=self.votes.get)

    def class_confirmed(self, min_class_hits: int) -> bool:
        """Whether the winning class was detected on at least ``min_class_hits`` frames."""
        return self.class_hits.get(self.cls, 0) >= min_class_hits

    def update(self, det: np.ndarray, t: float) -> None:
        """Correct the filter with a detection ``[x1, y1, x2, y2, score, cls]`` seen at ``t``."""
        self.time_since_update = 0
        self.t_obs = t
        self.hits += 1
        self.kf.update(_box_to_z(det))
        self._observe(det, t)

    def relink(self, det: np.ndarray, t: float) -> None:
        """Take ``det`` after an occlusion: restart the filter from it, keep the ID.

        The drifted prediction is discarded. The new filter's velocity is the
        displacement from the last observation spread over the hidden frames.
        """
        frames = max(self.time_since_update, 1)
        (cx0, cy0), (cx1, cy1) = _centre(self.last_obs), _centre(det)
        self.kf = _new_filter(det)
        self.kf.x[4:6] = [[(cx1 - cx0) / frames], [(cy1 - cy0) / frames]]
        self.time_since_update = 0
        self.hits += 1
        self._observe(det, t)

    def velocity(self) -> tuple[float, float]:
        """Observed centre velocity, px/s, over the last ``VELOCITY_WINDOW_S`` of detections."""
        t1, x1, y1 = self._centres[-1]
        t0, x0, y0 = next(c for c in self._centres if c[0] >= t1 - VELOCITY_WINDOW_S)
        if t1 - t0 <= 0:
            return 0.0, 0.0
        return (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)

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

    def _observe(self, det: np.ndarray, t: float) -> None:
        self.t_obs = t
        self.last_obs = np.asarray(det[:4], dtype=float)
        self._centres.append((t, *_centre(self.last_obs)))
        self._vote(det)

    def _vote(self, det: np.ndarray) -> None:
        cls = int(det[5])
        self.votes[cls] = self.votes.get(cls, 0.0) + float(det[4])
        self.class_hits[cls] = self.class_hits.get(cls, 0) + 1


class Sort:
    """Multi-object tracker.

    Args:
        min_hits: Detections a track needs before it is reported.
        max_occlusion_s: Seconds a track survives without a detection.
        iou_threshold: Minimum IoU to match a detection to a track.
        compatible_classes: Groups of class indices a re-link may cross
            (``class_groups``); by default a re-link keeps the class.
        min_class_hits: Detections of its winning class a track needs before
            its class is confirmed.
        relink: Re-link unmatched detections to lost tracks after an
            occlusion. Off by default: on the hand-counted clip it handed
            static false-positive tracks (bollards as 'person') to passers-by
            and doubled the error (docs/benchmarks/2026-09-27_tracker_occlusion.md).

    Attributes:
        relinks: Detections re-linked to a lost track since start.
        unconfirmed_ids: IDs among the last ``update``'s rows whose class is
            not confirmed yet.
    """

    def __init__(
        self,
        min_hits: int = 3,
        max_occlusion_s: float = MAX_OCCLUSION_S,
        iou_threshold: float = IOU_THRESHOLD,
        compatible_classes: Iterable[Iterable[int]] = (),
        min_class_hits: int = MIN_CLASS_HITS,
        relink: bool = False,
    ) -> None:
        check_tracking_rules(max_occlusion_s, min_class_hits, relink)
        self.min_hits = min_hits
        self.max_occlusion_s = max_occlusion_s
        self.iou_threshold = iou_threshold
        self.compatible = {(a, b) for g in compatible_classes for a in g for b in g}
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count = 0
        self.relinks = 0
        self.min_class_hits = min_class_hits
        self.relink = relink
        self.unconfirmed_ids: set[int] = set()

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
        matched = {k for _, k in matches}
        lost = [k for k in range(len(self.trackers)) if k not in matched and self.relink]
        for d, k in self._relink(dets, unmatched, lost, t):
            self.trackers[k].relink(dets[d], t)
            self.relinks += 1
            unmatched.remove(d)
        self.trackers += [KalmanBoxTracker(dets[d], t) for d in unmatched]

        reported = [
            k
            for k in self.trackers
            if k.time_since_update == 0
            and (k.hits >= self.min_hits or self.frame_count <= self.min_hits)
        ]
        self.unconfirmed_ids = {
            k.id for k in reported if not k.class_confirmed(self.min_class_hits)
        }
        confirmed = [[*k.box, k.id, k.cls] for k in reported]
        return np.asarray(confirmed, dtype=float).reshape(-1, 6)

    def _relink(
        self, dets: np.ndarray, det_idx: list[int], track_idx: list[int], t: float
    ) -> list[tuple[int, int]]:
        """Match leftover detections to lost confirmed tracks; ``(det, track)`` pairs.

        Only tracks confirmed by ``min_hits`` qualify, so a one-frame false
        positive cannot absorb the next road user.
        """
        tracks = [self.trackers[k] for k in track_idx]
        track_idx = [k for k, tr in zip(track_idx, tracks, strict=True) if tr.hits >= self.min_hits]
        if not det_idx or not track_idx:
            return []
        tracks = [self.trackers[k] for k in track_idx]
        d = dets[det_idx]
        last = np.asarray([tr.last_obs for tr in tracks])
        elapsed = np.asarray([t - tr.t_obs for tr in tracks])
        vel = np.asarray([tr.velocity() for tr in tracks])
        expected = _centres(last) + vel * elapsed[:, None]
        dist = np.linalg.norm(_centres(d[:, :4])[:, None, :] - expected[None], axis=2)
        radius = RELINK_K * (last[:, 3] - last[:, 1]) * (1.0 + elapsed)
        ratio = _area(d[:, None, :4]) / np.maximum(_area(last[None]), 1e-9)
        same = np.asarray(
            [[self._compatible(int(c), tr.cls) for tr in tracks] for c in d[:, 5]], dtype=bool
        )
        ok = (dist <= radius) & (ratio >= RELINK_SIZE_RATIO[0])
        ok &= (ratio <= RELINK_SIZE_RATIO[1]) & same
        cost = np.where(ok, dist / np.maximum(radius, 1e-9), 1e6)
        rows, cols = linear_sum_assignment(cost)
        return [(det_idx[r], track_idx[c]) for r, c in zip(rows, cols, strict=True) if ok[r, c]]

    def _compatible(self, a: int, b: int) -> bool:
        return a == b or (a, b) in self.compatible


def class_groups(classes: list[str]) -> list[frozenset[int]]:
    """``COMPATIBLE_CLASSES`` as index groups over ``classes`` (names not in it are skipped)."""
    return [frozenset(classes.index(n) for n in g if n in classes) for g in COMPATIBLE_CLASSES]


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


def _new_filter(det: np.ndarray) -> KalmanFilter:
    """Constant-velocity filter on (x, y, area, ratio), started at ``det``, at rest."""
    kf = KalmanFilter(dim_x=7, dim_z=4)
    kf.F = np.eye(7) + np.eye(7, k=4)
    kf.H = np.eye(4, 7)
    kf.R[2:, 2:] *= 10.0
    kf.P[4:, 4:] *= 1000.0
    kf.P *= 10.0
    kf.Q[-1, -1] *= 0.01
    kf.Q[4:, 4:] *= 0.01
    kf.x[:4] = _box_to_z(det)
    return kf


def _centre(box: np.ndarray) -> tuple[float, float]:
    return float(box[0] + box[2]) / 2, float(box[1] + box[3]) / 2


def _centres(boxes: np.ndarray) -> np.ndarray:
    return np.stack([(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2], axis=1)


def _box_to_z(box: np.ndarray) -> np.ndarray:
    w, h = box[2] - box[0], box[3] - box[1]
    return np.array([[box[0] + w / 2], [box[1] + h / 2], [w * h], [w / h]], dtype=float)


def _z_to_box(x: np.ndarray) -> np.ndarray:
    w = np.sqrt(x[2, 0] * x[3, 0])
    h = x[2, 0] / w
    return np.array([x[0, 0] - w / 2, x[1, 0] - h / 2, x[0, 0] + w / 2, x[1, 0] + h / 2])
