from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from camina.core.tracker import Sort
from camina.utils.config import load_config, load_classes

CONFIG = load_config()
CLASSES = load_classes()


class ModalShareCounter:
    def __init__(self):
        self.model = YOLO(CONFIG["model"])
        self.tracker = Sort()
        self.cap = cv2.VideoCapture(CONFIG["camera_source"])
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG["frame_width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG["frame_height"])
        self.frame_count = 0
        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.local_ids = {cls: {} for cls in CLASSES.values()}
        self.next_local_id = {cls: 1 for cls in CLASSES.values()}
        self.last_interval = None

    @staticmethod
    def _get_class_label(bbox, cls_map):
        return cls_map.get(min(cls_map, key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))), None)

    def _log(self):
        now = datetime.now()
        interval = now.minute // CONFIG["log_interval_minutes"]
        if interval == self.last_interval:
            return
        self.last_interval = interval

        log_path = Path("data") / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        log_path.parent.mkdir(exist_ok=True)
        with log_path.open("a") as f:
            f.write(f"{now:%Y-%m-%d %H:%M}, " + ", ".join(f"{cls}:{self.counts[cls]}" for cls in CLASSES.values()) + "\n")

    def _process_frame(self, frame):
        results = self.model.predict(frame,
                                     imgsz=CONFIG["imgsz"],
                                     conf=CONFIG["confidence_threshold"])[0]

        detections = []
        cls_map = {}
        for box in results.boxes:
            cls_id = int(box.cls.item())
            if cls_id not in CLASSES:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf.item())
            detections.append([x1, y1, x2, y2, conf])
            cls_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

        if not detections:
            return

        tracks = self.tracker.update(np.array(detections))
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

            if CONFIG.get("draw_bbox", True):
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)
                cv2.putText(frame, f"{label} #{self.local_ids[label][obj_id]}", (int(x1), int(y1) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        y_offset = 20
        for idx, (cls_name, cnt) in enumerate(self.counts.items()):
            cv2.putText(frame, f"{cls_name}: {cnt}", (10, y_offset + idx * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("Modal-Share Counter", frame)
        if CONFIG["logging_enabled"]:
            self._log()

    def run(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break
                if self.frame_count % CONFIG["frame_skip"] == 0:
                    self._process_frame(frame)
                self.frame_count += 1
                if cv2.waitKey(1) in (ord("q"), 27):
                    break
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
            print("Final counts:")
            for cls, cnt in self.counts.items():
                print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
