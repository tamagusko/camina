""" Modal‑share counter.
Counts each class in classes.yaml and logs counts every log_interval_minutes.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

from sort import Sort

CONFIG = yaml.safe_load(Path("src/config.yaml").read_text())
CLASSES: dict[int, str] = yaml.safe_load(Path("src/classes.yaml").read_text())
DATA_DIR = Path("data")


def interval_index(now: datetime) -> int:
    return now.minute // CONFIG["log_interval_minutes"]


class ModalShareCounter:
    def __init__(self) -> None:
        model_path = CONFIG.get("ncnn_model_path") or CONFIG["model"]
        self.model = YOLO(model_path)
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
    def process_frame(self, frame: np.ndarray) -> None:
        pred = self.model.predict(frame, imgsz=CONFIG["imgsz"], conf=CONFIG["confidence_threshold"])[0]

        dets: list[list[float]] = []
        cls_map: dict[tuple[float, float, float, float], str] = {}
        for box in pred.boxes:
            cls_id = int(box.cls)
            if cls_id not in CLASSES:
                continue
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            dets.append([x1, y1, x2, y2, float(box.conf)])
            cls_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

        if not dets:
            return

        for x1, y1, x2, y2, tid in self.tracker.update(np.asarray(dets)):
            label = self._nearest_label((x1, y1, x2, y2), cls_map)
            if label and tid not in self.seen_ids[label]:
                self.seen_ids[label].add(tid)
                self.counts[label] += 1

        if CONFIG["logging_enabled"]:
            self._maybe_log()

    # ------------------------------------------------------------------
    @staticmethod
    def _nearest_label(box: tuple[float, float, float, float], mapping: dict) -> str | None:
        if not mapping:
            return None
        key = min(mapping, key=lambda b: np.linalg.norm(np.subtract(b, box)))
        return mapping[key]

    # ------------------------------------------------------------------
    def _maybe_log(self) -> None:
        now = datetime.now()
        idx = interval_index(now)
        if idx == self.last_interval:
            return
        self.last_interval = idx

        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        line = ", ".join(f"{c}:{self.counts[c]}" for c in CLASSES.values())
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{now:%Y-%m-%d %H:%M}, {line}\n")

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
            self._summary()

    def _summary(self) -> None:
        print("Final counts:")
        for cls, cnt in self.counts.items():
            print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
