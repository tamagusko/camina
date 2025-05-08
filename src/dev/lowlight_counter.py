import os
import cv2
import numpy as np
import datetime
from ultralytics import YOLO
from sort import Sort
from src.config import LOCATION, CAMERA_ID, LOGGING_ENABLED, LOG_INTERVAL_MINUTES


# Configuration
MODEL_PATH = 'models/yolov8n.pt'
FRAME_WIDTH = 416
FRAME_HEIGHT = 416
FRAME_SKIP = 5
CONFIDENCE_THRESHOLD = 0.25
LOG_DIR = "data"
os.makedirs(LOG_DIR, exist_ok=True)

# Classes to track
CLASSES = {
    0: 'person',
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck',
}


class LowLightCounter:
    def __init__(self):
        self.model = YOLO(MODEL_PATH)
        self.tracker = Sort()
        self.cap = self._init_camera()
        self.frame_count = 0
        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.last_log_time = datetime.datetime.now()

    def _init_camera(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        return cap

    def _enhance_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    def _get_class_label(self, bbox, class_map):
        return class_map.get(
            min(class_map.keys(), key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))),
            None
        )

    def _log_counts(self):
        if not LOGGING_ENABLED:
            return

        now = datetime.datetime.now()
        if (now - self.last_log_time).total_seconds() < LOG_INTERVAL_MINUTES * 60:
            return

        log_filename = f"{now.strftime('%Y%m%d')}-{LOCATION}-{CAMERA_ID}.log"
        log_path = os.path.join(LOG_DIR, log_filename)
        count_str = ", ".join(f"{k}:{v}" for k, v in self.counts.items())
        with open(log_path, "a") as f:
            f.write(f"{now.strftime('%Y-%m-%d %H:%M')}, LOW_LIGHT, {count_str}\n")
        self.last_log_time = now

    def _annotate_frame(self, frame):
        for idx, (cls, count) in enumerate(self.counts.items()):
            text = f"{cls}: {count}"
            position = (10, 30 + 20 * idx)
            cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    def run(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break

                if self.frame_count % FRAME_SKIP == 0:
                    enhanced_frame = self._enhance_frame(frame)
                    results = self.model.predict(enhanced_frame, imgsz=320, conf=CONFIDENCE_THRESHOLD)[0]

                    detections = []
                    class_map = {}
                    for box in results.boxes:
                        cls_id = int(box.cls.item())
                        conf = box.conf.item()
                        if cls_id in CLASSES:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            detections.append([x1, y1, x2, y2, conf])
                            class_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

                    detections_np = np.array(detections)
                    tracked = self.tracker.update(detections_np)

                    for x1, y1, x2, y2, obj_id in tracked:
                        bbox = (x1, y1, x2, y2)
                        class_label = self._get_class_label(bbox, class_map)
                        if class_label and obj_id not in self.seen_ids[class_label]:
                            self.seen_ids[class_label].add(obj_id)
                            self.counts[class_label] += 1

                    self._annotate_frame(enhanced_frame)
                    cv2.imshow('Low-Light Modal Counting (Edge Mode)', enhanced_frame)
                    self._log_counts()

                self.frame_count += 1

                if cv2.waitKey(1) & 0xFF in [27, ord('q')]:  # ESC or 'q'
                    break
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
            print('Final Modal Share Counts:')
            for cls, count in self.counts.items():
                print(f'{cls}: {count}')


if __name__ == '__main__':
    counter = LowLightCounter()
    counter.run()
