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
from src.camina.utils.display import EpaperCounterDisplay, OledCounterDisplay


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

    def log(self, counts: Dict[str, int]) -> None:
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
            f.write(
                f"{now:%Y-%m-%d %H:%M}, "
                + ", ".join(f"{cls}:{counts[cls]}" for cls in self.classes.values())
                + "\n"
            )


class Display:
    """Handles displaying results on screen or an e-paper/OLED display."""

    def __init__(self, display_type: Optional[str], classes: Dict[int, str]) -> None:
        self.display_type = display_type
        self.classes = classes
        if self.display_type == "epaper":
            self.display = EpaperCounterDisplay()
        elif self.display_type == "oled":
            self.display = OledCounterDisplay()
        else:
            self.display = None

    def update(self, frame: np.ndarray, counts: Dict[str, int], local_ids: Dict[str, Dict[int, int]]) -> None:
        if self.display_type == "epaper" or self.display_type == "oled":
            self.display.update(counts)
        else:
            y_offset = 20
            for idx, (cls_name, cnt) in enumerate(counts.items()):
                cv2.putText(
                    frame,
                    f"{cls_name}: {cnt}",
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

    def _process_frame(self, frame: np.ndarray) -> None:
        results = self.detector.predict(frame)
        detections, cls_map = self._parse_detections(results)
        tracks = self.tracker.update(detections)
        self._update_counts(tracks, cls_map)

        if self.config.get("draw_bbox", True):
            self._draw_bounding_boxes(frame, tracks, cls_map)

        self.display.update(frame, self.counts, self.local_ids)

        if self.config["logging_enabled"]:
            self.logger.log(self.counts)

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
