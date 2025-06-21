from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
import yaml
from ultralytics import YOLO
from sort import Sort
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

# Load config and classes
with open("src/config.yaml") as f:
    CONFIG = yaml.safe_load(f)
with open("src/classes.yaml") as f:
    CLASSES = yaml.safe_load(f)


class OledCounterDisplay:
    def __init__(self):
        serial = i2c(port=1, address=0x3C)
        self.oled = ssd1306(serial)
        self.font = ImageFont.load_default()
        self.prev_counts = {}
        self.labels = {
            "person": "Ped", "cyclist": "Bike", "bus": "Bus",
            "car": "Car", "motorcycle": "Moto", "truck": "Truck"
        }

    def update(self, counts):
        if counts == self.prev_counts:
            return
        self.prev_counts = counts.copy()

        image = Image.new("1", self.oled.size)
        draw = ImageDraw.Draw(image)

        # Title bar
        draw.rectangle((0, 0, self.oled.width, 10), outline=255, fill=255)
        header = f"{Path(CONFIG['model']).stem} {CONFIG['ver']}"
        draw.text((2, 0), header, font=self.font, fill=0)

        # Class counts
        for i, (cls, label) in enumerate(self.labels.items()):
            count = counts.get(cls, 0)
            draw.text((0, 12 + i * 10), f"{label}: {count}", font=self.font, fill=255)

        self.oled.display(image)


class ModalShareCounter:
    def __init__(self):
        self.model = YOLO(CONFIG["ncnn_model_path"])  # use NCNN-exported model folder
        self.tracker = Sort()
        self.cap = cv2.VideoCapture(CONFIG["camera_source"])
        self.frame_count = 0
        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.local_ids = {cls: {} for cls in CLASSES.values()}
        self.next_id = {cls: 1 for cls in CLASSES.values()}
        self.last_interval = None
        self.display = OledCounterDisplay()

    def _log(self):
        now = datetime.now()
        interval = now.minute // CONFIG["log_interval_minutes"]
        if interval == self.last_interval:
            return
        self.last_interval = interval

        log_path = Path("data") / f"{now:%Y%m%d}-{CONFIG['location']}-{CONFIG['camera_id']}.log"
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, "a") as f:
            line = f"{now:%Y-%m-%d %H:%M}, " + ", ".join(f"{c}:{self.counts[c]}" for c in CLASSES.values())
            f.write(line + "\n")

    @staticmethod
    def _get_class_label(bbox, cls_map):
        return cls_map.get(min(cls_map, key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))), None)

    def _process_frame(self, frame):
        results = self.model.predict(frame, imgsz=CONFIG["imgsz"], conf=CONFIG["confidence_threshold"])[0]

        detections, cls_map = [], {}
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
            if not label:
                continue
            obj_id = int(obj_id)

            if obj_id not in self.local_ids[label]:
                self.local_ids[label][obj_id] = self.next_id[label]
                self.next_id[label] += 1
            if obj_id not in self.seen_ids[label]:
                self.seen_ids[label].add(obj_id)
                self.counts[label] += 1

        print("Current Counts:", ", ".join(f"{c}:{self.counts[c]}" for c in CLASSES.values()))
        self.display.update(self.counts)
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
        finally:
            self.cap.release()
            print("Final Counts:")
            for cls, cnt in self.counts.items():
                print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
