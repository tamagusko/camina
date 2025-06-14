import os
import cv2
import yaml
import numpy as np
from datetime import datetime
from ultralytics import YOLO
from sort import Sort

# Load config from YAML
with open("src/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Load class labels from YAML
with open("src/classes.yaml", "r") as f:
    CLASSES = yaml.safe_load(f)


class ModalShareCounter:
    def __init__(self):
        self.model = YOLO(config['model'])
        self.tracker = Sort()
        self.cap = self._init_camera()
        self.frame_count = 0
        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.class_id_mapping = {cls: {} for cls in CLASSES.values()}
        self.class_id_counters = {cls: 1 for cls in CLASSES.values()}
        self.last_log_minute = None

    def _init_camera(self):
        # cap = cv2.VideoCapture(config['camera_index'])
        cap = cv2.VideoCapture("test_video/test.mov")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config['frame_width'])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config['frame_height'])
        return cap

    def _get_class_label(self, bbox, class_map):
        return class_map.get(
            min(class_map.keys(), key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))),
            None
        )

    def run(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break

                if self.frame_count % config['frame_skip'] == 0:
                    self._process_frame(frame)

                self.frame_count += 1

                key = cv2.waitKey(1)
                if key == ord('q') or key == 27:
                    break
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _process_frame(self, frame):
        results = self.model.predict(frame, imgsz=config['imgsz'], conf=config['confidence_threshold'])[0]

        detections = []
        class_map = {}

        for box in results.boxes:
            cls_id = int(box.cls.item())
            conf = box.conf.item()
            if cls_id in CLASSES:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append([x1, y1, x2, y2, conf])
                class_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

        if len(detections) == 0:
            self._annotate_frame(frame)
            cv2.imshow('Modal Share Counting (Edge Mode)', frame)
            return

        detections_np = np.array(detections)
        tracked = self.tracker.update(detections_np)

        for x1, y1, x2, y2, obj_id in tracked:
            bbox = (x1, y1, x2, y2)
            class_label = self._get_class_label(bbox, class_map)
            if class_label:
                if obj_id not in self.class_id_mapping[class_label]:
                    self.class_id_mapping[class_label][obj_id] = self.class_id_counters[class_label]
                    self.class_id_counters[class_label] += 1
                if obj_id not in self.seen_ids[class_label]:
                    self.seen_ids[class_label].add(obj_id)
                    self.counts[class_label] += 1
                if config['draw_bbox']:
                    display_id = self.class_id_mapping[class_label][obj_id]
                    self._draw_bbox(frame, bbox, class_label, display_id)

        self._annotate_frame(frame)
        cv2.imshow('Modal Share Counting (Edge Mode)', frame)

        if config['logging_enabled']:
            self._log_counts()

    def _draw_bbox(self, frame, bbox, label, display_id):
        x1, y1, x2, y2 = map(int, bbox)
        text = f"{label} #{display_id}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

    def _annotate_frame(self, frame):
        for idx, (cls, count) in enumerate(self.counts.items()):
            text = f'{cls}: {count}'
            position = (10, 30 + 20 * idx)
            cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    def _log_counts(self):
        now = datetime.now()
        current_interval = now.minute // config['log_interval_minutes']
        if self.last_log_minute == current_interval:
            return

        self.last_log_minute = current_interval

        log_dir = 'data'
        os.makedirs(log_dir, exist_ok=True)
        log_filename = f"{now.strftime('%Y%m%d')}-{config['location']}-{config['camera_id']}.log"
        log_path = os.path.join(log_dir, log_filename)

        timestamp = now.strftime("%Y-%m-%d %H:%M")
        counts_str = ", ".join([f"{cls}:{self.counts[cls]}" for cls in CLASSES.values()])
        log_line = f"{timestamp}, {counts_str}\n"

        with open(log_path, 'a') as f:
            f.write(log_line)

    def _print_summary(self):
        print('Final Modal Share Counts:')
        for cls, count in self.counts.items():
            print(f'{cls}: {count}')


if __name__ == '__main__':
    counter = ModalShareCounter()
    counter.run()
