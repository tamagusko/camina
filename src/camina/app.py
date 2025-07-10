"""This module contains the main application logic for the Camina project."""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from ultralytics import YOLO

from src.camina.core.tracker import Sort
from src.camina.utils.config import load_config, load_classes
from src.camina.utils.display import create_display
from src.camina.utils.calibration import DepthCalibrator


class VideoCapture:
    """Handles video capture from a camera source."""

    def __init__(self, source: Union[str, int], width: int, height: int) -> None:
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self) -> Tuple[bool, np.ndarray]:
        return self.cap.read()

    def release(self) -> None:
        self.cap.release()


class Detector:
    """Handles object detection using a YOLO model."""

    def __init__(self, model_path: str, imgsz: int, confidence_threshold: float) -> None:
        self.model = YOLO(model_path)
        self.imgsz = imgsz
        self.confidence_threshold = confidence_threshold

    def predict(self, frame: np.ndarray):
        return self.model.predict(
            frame, imgsz=self.imgsz, conf=self.confidence_threshold
        )[0]


class ObjectTracker:
    """Tracks detected objects using the SORT algorithm."""

    def __init__(self) -> None:
        self.tracker = Sort()

    def update(self, detections: List[List[float]]) -> np.ndarray:
        if not detections:
            return np.empty((0, 5))
        return self.tracker.update(np.array(detections))


class DataLogger:
    """Logs object counts to a file."""

    def __init__(self, log_interval_minutes: int, location: str, camera_id: str, classes: Dict[int, str]) -> None:
        self.log_interval_minutes = log_interval_minutes
        self.location = location
        self.camera_id = camera_id
        self.classes = classes
        self.last_interval: Optional[int] = None

    def log(self, counts: Dict[str, int], avg_speeds: Dict[str, float]) -> None:
        now = datetime.now()
        interval = now.minute // self.log_interval_minutes
        if interval == self.last_interval:
            return
        self.last_interval = interval

        log_path = (
            Path("data") / f"{now:%Y%m%d}-{self.location}-{self.camera_id}.log"
        )
        log_path.parent.mkdir(exist_ok=True)
        with log_path.open("a") as f:
            # Build log entry with counts and speeds
            log_entries = []
            for cls in self.classes.values():
                count = counts.get(cls, 0)
                speed = avg_speeds.get(cls, 0.0)
                log_entries.append(f"{cls}:{count}")
                log_entries.append(f"{cls}_speed:{speed:.1f}")
            
            f.write(
                f"{now:%Y-%m-%d %H:%M}, "
                + ", ".join(log_entries)
                + "\n"
            )


class Display:
    """Handles displaying results on screen or an e-paper/OLED display."""

    def __init__(self, display_type: Optional[str], classes: Dict[int, str]) -> None:
        self.display_type = display_type
        self.classes = classes
        self.display = create_display(display_type)

    def update(self, frame: np.ndarray, counts: Dict[str, int], avg_speeds: Dict[str, float], local_ids: Dict[str, Dict[int, int]]) -> None:
        if self.display_type and self.display_type.lower() != "none":
            self.display.update(counts, avg_speeds)
        
        # Always show on screen as well (unless headless)
        if self.display_type != "headless":
            y_offset = 20
            for idx, (cls_name, cnt) in enumerate(counts.items()):
                speed = avg_speeds.get(cls_name, 0.0)
                cv2.putText(
                    frame,
                    f"{cls_name}: {cnt} | {speed:.1f} km/h",
                    (10, y_offset + idx * 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
            cv2.imshow("Modal-Share Counter", frame)

    def clear(self) -> None:
        if self.display:
            self.display.clear()
        cv2.destroyAllWindows()


class CalibrationMonitor:
    """Monitors camera position and handles recalibration."""
    
    def __init__(self, config: Dict[str, Union[str, int, float, bool]]):
        self.config = config
        self.calibrator = DepthCalibrator()
        self.last_position_check = 0
        self.check_interval = config.get("camera_alignment_hours", [6, 18])  # Check at 6 AM and 6 PM
        self.position_change_threshold = 0.1
        
    def should_check_position(self) -> bool:
        """Check if it's time to verify camera position."""
        current_hour = datetime.now().hour
        return current_hour in self.check_interval
    
    def check_and_prompt_recalibration(self, frame: np.ndarray) -> bool:
        """
        Check if camera position changed and prompt for recalibration.
        
        Returns:
            True if recalibration was performed or not needed, False if user declined
        """
        if not self.should_check_position():
            return True
            
        # Avoid checking too frequently
        now = time.time()
        if now - self.last_position_check < 3600:  # Don't check more than once per hour
            return True
            
        self.last_position_check = now
        
        # Check if camera position changed
        if self.calibrator.check_camera_position_changed(frame, self.position_change_threshold):
            print("\n" + "="*50)
            print("CAMERA POSITION CHANGE DETECTED!")
            print("The camera appears to have moved from its original position.")
            print("Recalibration is recommended for accurate speed measurements.")
            print("="*50)
            
            # Prompt user for recalibration
            response = input("Would you like to recalibrate now? (y/n): ").lower().strip()
            
            if response in ['y', 'yes']:
                print("Starting recalibration...")
                success = self.calibrator.run_calibration(frame)
                if success:
                    print("Recalibration completed successfully!")
                    return True
                else:
                    print("Recalibration failed. Please run manual calibration later.")
                    return False
            else:
                print("Skipping recalibration. You can run it manually later with:")
                print("python scripts/calibrate_camera.py")
                return False
        
        return True


class ModalShareCounterApp:
    """Main application for counting modal share."""

    def __init__(self, config: Dict[str, Union[str, int, float, bool]]) -> None:
        self.config = config
        self.classes = load_classes()
        self.video_capture = VideoCapture(
            config["camera_source"],
            config["frame_width"],
            config["frame_height"],
        )
        self.detector = Detector(
            config.get("ncnn_model_path") or config["model"],
            config["imgsz"],
            config["confidence_threshold"],
        )
        self.tracker = ObjectTracker()
        self.logger = DataLogger(
            config["log_interval_minutes"],
            config["location"],
            config["camera_id"],
            self.classes,
        )
        self.display = Display(config.get("display_type"), self.classes)
        self.frame_count = 0
        self.seen_ids = {cls: set() for cls in self.classes.values()}
        self.counts = {cls: 0 for cls in self.classes.values()}
        self.local_ids = {cls: {} for cls in self.classes.values()}
        self.next_local_id = {cls: 1 for cls in self.classes.values()}
        
        # Speed tracking
        self.speed_measurements = {cls: [] for cls in self.classes.values()}
        self.avg_speeds = {cls: 0.0 for cls in self.classes.values()}
        
        # Calibration monitoring
        self.calibration_monitor = CalibrationMonitor(config)

    def _process_frame(self, frame: np.ndarray) -> None:
        # Check camera position periodically
        self.calibration_monitor.check_and_prompt_recalibration(frame)
        
        results = self.detector.predict(frame)
        detections, cls_map = self._parse_detections(results)
        tracks = self.tracker.update(detections)
        self._update_counts(tracks, cls_map)

        if self.config.get("draw_bbox", True):
            self._draw_bounding_boxes(frame, tracks, cls_map)

        self._update_speeds(tracks, cls_map)
        self.display.update(frame, self.counts, self.avg_speeds, self.local_ids)

        if self.config["logging_enabled"]:
            self.logger.log(self.counts, self.avg_speeds)

    def _parse_detections(self, results) -> Tuple[List[List[float]], Dict[Tuple[float, float, float, float], str]]:
        detections = []
        cls_map = {}
        for box in results.boxes:
            cls_id = int(box.cls.item())
            if cls_id not in self.classes:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf.item())
            detections.append([x1, y1, x2, y2, conf])
            cls_map[(x1, y1, x2, y2)] = self.classes[cls_id]
        return detections, cls_map

    def _update_counts(self, tracks: np.ndarray, cls_map: Dict[Tuple[float, float, float, float], str]) -> None:
        for x1, y1, x2, y2, obj_id in tracks:
            label = self._get_class_label((x1, y1, x2, y2), cls_map)
            if label is None:
                continue

            if obj_id not in self.local_ids[label]:
                self.local_ids[label][obj_id] = self.next_local_id[label]
                self.next_local_id[label] += 1
            if obj_id not in self.seen_ids[label]:
                self.seen_ids[label].add(obj_id)
                self.counts[label] += 1
    
    def _update_speeds(self, tracks: np.ndarray, cls_map: Dict[Tuple[float, float, float, float], str]) -> None:
        """Calculate and update average speeds for each class."""
        for x1, y1, x2, y2, obj_id in tracks:
            label = self._get_class_label((x1, y1, x2, y2), cls_map)
            if label is None:
                continue
                
            # Get the tracker for this object
            tracker = self.tracker.get_tracker_by_id(int(obj_id))
            if tracker is None:
                continue
                
            # Calculate speed for this object
            speed = tracker.calculate_speed_kmh(label)
            
            # Add speed measurement if valid
            if speed > 0:
                self.speed_measurements[label].append(speed)
                # Keep only recent measurements (last 20 for each class)
                if len(self.speed_measurements[label]) > 20:
                    self.speed_measurements[label].pop(0)
                    
        # Update average speeds for each class
        for cls in self.classes.values():
            if self.speed_measurements[cls]:
                self.avg_speeds[cls] = sum(self.speed_measurements[cls]) / len(self.speed_measurements[cls])
            else:
                self.avg_speeds[cls] = 0.0

    def _draw_bounding_boxes(self, frame: np.ndarray, tracks: np.ndarray, cls_map: Dict[Tuple[float, float, float, float], str]) -> None:
        for x1, y1, x2, y2, obj_id in tracks:
            label = self._get_class_label((x1, y1, x2, y2), cls_map)
            if label is None:
                continue
            cv2.rectangle(
                frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2
            )
            cv2.putText(
                frame,
                f"{label} #{self.local_ids[label][obj_id]}",
                (int(x1), int(y1) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
            )

    @staticmethod
    def _get_class_label(bbox: Tuple[float, float, float, float], cls_map: Dict[Tuple[float, float, float, float], str]) -> Optional[str]:
        if not cls_map:
            return None
        return cls_map.get(
            min(cls_map, key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox)))
        )

    def run(self) -> None:
        try:
            while True:
                ret, frame = self.video_capture.read()
                if not ret:
                    break
                if self.frame_count % self.config["frame_skip"] == 0:
                    self._process_frame(frame)
                self.frame_count += 1
                if cv2.waitKey(1) in (ord("q"), 27):
                    break
        finally:
            self.video_capture.release()
            self.display.clear()
            print("Final counts:")
            for cls, cnt in self.counts.items():
                print(f"{cls}: {cnt}")
