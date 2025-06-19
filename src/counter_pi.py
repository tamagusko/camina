"""Head-less modal-share counter for Raspberry Pi 5."""

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO
from sort import Sort

with open("src/config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

with open("src/classes.yaml", "r") as f:
    CLASSES = yaml.safe_load(f)


def nearest_label(bbox, mapping):
    if not mapping:
        return None
    key = min(mapping, key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox)))
    return mapping[key]


class ModalShareCounter:
    def __init__(self) -> None:
        self.model = YOLO(CONFIG["model"])
        self.tracker = Sort(max_age=90, iou_threshold=0.15)

        src = CONFIG["camera_source"]
        self.cap = cv2.VideoCapture(src if isinstance(src, str) else int(src))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG["frame_width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG["frame_height"])

        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.last_interval = None
        self.frame_count = 0

    def process_frame(self, frame):
        result = self.model.predict(
            frame,
            imgsz=CONFIG["imgsz"],
            conf=CONFIG["confidence_threshold"],
            verbose=False,
        )[0]

        detections, cls_map = [], {}
        for box in result.boxes:
            cid = int(box.cls.item())
            if cid not in CLASSES:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append([x1, y1, x2, y2, float(box.conf.item())])
            cls_map[(x1, y1, x2, y2)] = CLASSES[cid]

        if detections:
            tracks = self.tracker.update(np.asarray(detections))
            for x1, y1, x2, y2, tid in tracks:
                label = nearest_label((x1, y1, x2, y2), cls_map)
                if label and tid not in self.seen_ids[label]:
                    self.seen_ids[label].add(tid)
                    self.counts[label] += 1

        self.maybe_log()

    def maybe_log(self):
        if not CONFIG["logging_enabled"]:
            return
        now = datetime.now()
        interval = now.minute // CONFIG["log_interval_minutes"]
        if interval == self.last_interval:
            return
        self.last_interval = interval

        Path("data").mkdir(exist_ok=True)
        log_path = Path("data") / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        line = ", ".join(f"{cls}:{self.counts[cls]}" for cls in CLASSES.values())
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{now:%Y-%m-%d %H:%M}, {line}\n")

    def run(self):
        try:
            while True:
                ok, frame = self.cap.read()
                if not ok:
                    break
                if self.frame_count % CONFIG["frame_skip"] == 0:
                    self.process_frame(frame)
                self.frame_count += 1
        except KeyboardInterrupt:
            pass
        finally:
            self.cap.release()
            print("\nFinal counts:")
            for cls, cnt in self.counts.items():
                print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
