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


class ModalShareCounter:
    def __init__(self):
        self.model = YOLO(CONFIG["model"])
        self.tracker = Sort()
        self.cap = self._init_capture()
        self.frame_count = 0
        self.seen_ids = {c: set() for c in CLASSES.values()}
        self.counts = {c: 0 for c in CLASSES.values()}
        self.local_ids = {c: {} for c in CLASSES.values()}
        self.next_local_id = {c: 1 for c in CLASSES.values()}
        self.last_interval = None

    @staticmethod
    def _get_class_label(bbox, cls_map):
        return cls_map.get(
            min(cls_map, key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))),
            None,
        )

    def _init_capture(self):
        src = CONFIG["camera_source"]
        cap = cv2.VideoCapture(src if isinstance(src, str) else int(src))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG["frame_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG["frame_height"])
        return cap

    def _draw_bbox(self, frame, bbox, label, disp_id, conf):
        x1, y1, x2, y2 = map(int, bbox)
        txt = f"{label} #{disp_id} {conf:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(frame, txt, (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    def _overlay_totals(self, frame):
        for idx, (cls_name, cnt) in enumerate(self.counts.items()):
            cv2.putText(frame, f"{cls_name}: {cnt}", (10, 30 + 20 * idx),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    def _log(self):
        now = datetime.now()
        interval = now.minute // CONFIG["log_interval_minutes"]
        if interval == self.last_interval:
            return
        self.last_interval = interval

        log_dir = Path("data")
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        counts_str = ", ".join(f"{c}:{self.counts[c]}" for c in CLASSES.values())
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{now:%Y-%m-%d %H:%M}, {counts_str}\n")

    def _process_frame(self, frame):
        res = self.model.predict(frame,
                                 imgsz=CONFIG["imgsz"],
                                 conf=CONFIG["confidence_threshold"])[0]

        detections, cls_map = [], {}
        for box in res.boxes:
            cls_id = int(box.cls.item())
            if cls_id not in CLASSES:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf.item())
            detections.append([x1, y1, x2, y2, conf])
            cls_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

        if not detections:
            self._overlay_totals(frame)
            cv2.imshow("Modal-Share Counter", frame)
            return

        tracks = self.tracker.update(np.array(detections))
        for x1, y1, x2, y2, obj_id in tracks:
            label = self._get_class_label((x1, y1, x2, y2), cls_map)
            if label is None:
                continue
            obj_id = int(obj_id)

            if obj_id not in self.local_ids[label]:
                self.local_ids[label][obj_id] = self.next_local_id[label]
                self.next_local_id[label] += 1
            if obj_id not in self.seen_ids[label]:
                self.seen_ids[label].add(obj_id)
                self.counts[label] += 1

            if CONFIG["draw_bbox"]:
                self._draw_bbox(frame, (x1, y1, x2, y2),
                                label, self.local_ids[label][obj_id],
                                cls_map_inverse := res.boxes.conf.tolist()[0])

        self._overlay_totals(frame)
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
            for cls_name, cnt in self.counts.items():
                print(f"{cls_name}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
