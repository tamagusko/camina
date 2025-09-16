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
        
        # Speed tracking
        self.history = []  # Store center positions and timestamps
        self.speeds = []   # Store calculated speeds for averaging

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
        
        # Update position history for speed calculation
        pred_bbox = self._x_to_bbox(self.kf.x)
        cx = float((pred_bbox[0] + pred_bbox[2]) / 2)
        cy = float((pred_bbox[1] + pred_bbox[3]) / 2)
        
        import time
        current_time = time.time()
        self.history.append((cx, cy, current_time))
        
        # Keep only recent history (last 2 seconds worth)
        if len(self.history) > 60:  # Assuming ~30 FPS
            self.history.pop(0)
            
        return pred_bbox

    def get_state(self) -> np.ndarray:
        return self._x_to_bbox(self.kf.x)
    
    def calculate_speed_kmh(self, object_class: str = "person") -> float:
        """Calculate speed in km/h based on position history."""
        if len(self.history) < 2:
            return 0.0
            
        # Use the last few positions for more stable speed calculation
        recent_positions = self.history[-5:] if len(self.history) >= 5 else self.history
        
        if len(recent_positions) < 2:
            return 0.0
            
        # Calculate average speed over the trajectory
        total_distance = 0.0
        total_time = 0.0
        
        for i in range(1, len(recent_positions)):
            x1, y1, t1 = recent_positions[i-1]
            x2, y2, t2 = recent_positions[i]
            
            # Calculate pixel distance
            pixel_distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            time_diff = t2 - t1
            
            if time_diff > 0:
                total_distance += pixel_distance
                total_time += time_diff
        
        if total_time <= 0:
            return 0.0
            
        # Convert to real-world speed
        pixels_per_meter = CONFIG.get("pixels_per_meter", 10)
        speed_mps = (total_distance / pixels_per_meter) / total_time  # meters per second
        speed_kmh = speed_mps * 3.6  # Convert to km/h
        
        # Apply thresholds to filter out unrealistic speeds
        speed_thresholds = CONFIG.get("speed_thresholds", {})
        min_speed = CONFIG.get("speed_min_threshold", 1.0)
        max_speed = speed_thresholds.get(object_class, 100.0)
        
        if speed_kmh < min_speed or speed_kmh > max_speed:
            return 0.0
            
        return speed_kmh
    
    def get_average_speed(self) -> float:
        """Get the average speed from stored speed calculations."""
        if not self.speeds:
            return 0.0
        return sum(self.speeds) / len(self.speeds)
    
    def add_speed_measurement(self, speed: float) -> None:
        """Add a speed measurement to the running average."""
        if speed > 0:  # Only add valid speeds
            self.speeds.append(speed)
            # Keep only recent measurements (last 10)
            if len(self.speeds) > 10:
                self.speeds.pop(0)

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
    
    def get_tracker_by_id(self, track_id: int) -> KalmanBoxTracker:
        """Get tracker by ID for speed calculation."""
        for tracker in self.trackers:
            if tracker.id == track_id:
                return tracker
        return None


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
