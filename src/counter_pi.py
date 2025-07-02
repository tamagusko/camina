"""Modal share counter
Counts object classes defined in classes.yaml, logs results per interval.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

from sort import Sort

CONFIG: dict = yaml.safe_load(Path("src/config.yaml").read_text())
CLASSES: dict[int, str] = yaml.safe_load(Path("src/classes.yaml").read_text())
DATA_DIR = Path("data")


def current_interval() -> tuple[int, datetime]:
    """Return (interval_index, now)."""
    now = datetime.now()
    return now.minute // CONFIG["log_interval_minutes"], now


class ModalShareCounter:
    """Headless object counter that logs detections by class."""

    def __init__(self) -> None:
        self.model = YOLO(CONFIG["model"])
        self.tracker = Sort()

        self.cap = cv2.VideoCapture(CONFIG["camera_source"])
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG["frame_width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG["frame_height"])

        self.frame_count = 0
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.local_ids = {cls: {} for cls in CLASSES.values()}
        self.next_local_id = {cls: 1 for cls in CLASSES.values()}
        self.last_interval: int | None = None

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------
    def process_frame(self, frame: np.ndarray) -> None:
        result = self.model.predict(
            frame,
            imgsz=CONFIG["imgsz"],
            conf=CONFIG["confidence_threshold"],
        )[0]

        dets, cls_map = [], {}
        for box in result.boxes:
            cls_id = int(box.cls)
            if cls_id not in CLASSES:
                continue
            x1, y1, x2, y2 = box.xyxy[0]
            dets.append([x1, y1, x2, y2, float(box.conf)])
            cls_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

        if not dets:
            return

        for x1, y1, x2, y2, track_id in self.tracker.update(np.asarray(dets)):
            label = self._match_class((x1, y1, x2, y2), cls_map)
            if label is None:
                continue
            self._update_counts(label, track_id)

        if CONFIG["logging_enabled"]:
            self._maybe_log()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _match_class(
        bbox: tuple[float, float, float, float],
        cls_map: dict[tuple[float, float, float, float], str],
    ) -> str | None:
        key = min(cls_map, key=lambda b: np.linalg.norm(np.subtract(b, bbox)))
        return cls_map.get(key)

    def _update_counts(self, label: str, track_id: int) -> None:
        if track_id not in self.local_ids[label]:
            self.local_ids[label][track_id] = self.next_local_id[label]
            self.next_local_id[label] += 1
        if track_id not in self.seen_ids[label]:
            self.seen_ids[label].add(track_id)
            self.counts[label] += 1

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _maybe_log(self) -> None:
        interval_idx, now = current_interval()
        if interval_idx == self.last_interval:
            return
        self.last_interval = interval_idx

        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        line = ", ".join(f"{c}:{self.counts[c]}" for c in CLASSES.values())
        path.write_text(f"{now:%Y-%m-%d %H:%M}, {line}\n", encoding="utf-8", append=True)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        try:
            while True:
                ok, frame = self.cap.read()
                if not ok:
                    break
                if self.frame_count % CONFIG["frame_skip"] == 0:
                    self.process_frame(frame)
                self.frame_count += 1
        finally:
            self.cap.release()
            self._print_summary()

    def _print_summary(self) -> None:
        print("Final counts:")
        for cls, cnt in self.counts.items():
            print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
