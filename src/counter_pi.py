from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from sort import Sort
from yolov5_ncnn_py import YOLOv5NCNN  # Custom wrapper you must have implemented for NCNN
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

with open("src/config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

with open("src/classes.yaml", "r") as f:
    CLASSES = yaml.safe_load(f)


class OledCounterDisplay:
    def __init__(self):
        serial = i2c(port=1, address=0x3C)
        self.oled = ssd1306(serial)
        self.font = ImageFont.load_default()
        self.previous = {}

        self.display_labels = {
            "person": "Ped",
            "cyclist": "Bike",
            "bus": "Bus",
            "car": "Car",
            "motorcycle": "Moto",
            "truck": "Truck",
        }

    def update(self, counts):
        if counts == self.previous:
            return
        self.previous = counts.copy()

        image = Image.new("1", self.oled.size)
        draw = ImageDraw.Draw(image)

        # Top yellow title area: model + version
        draw.rectangle((0, 0, self.oled.width, 10), outline=255, fill=255)
        header = f"{Path(CONFIG['model']).stem} {CONFIG['ver']}"
        draw.text((2, 0), header, font=self.font, fill=0)

        # Class counts
        for i, (cls, label) in enumerate(self.display_labels.items()):
            count = counts.get(cls, 0)
            draw.text((0, 12 + i * 10), f"{label}: {count}", font=self.font, fill=255)

        self.oled.display(image)


class ModalShareCounter:
    def __init__(self):
        self.model = YOLOv5NCNN(CONFIG["ncnn_model_path"])
        self.tracker = Sort()
        self.cap = cv2.VideoCapture(CONFIG["camera_source"])
        self.frame_count = 0
        self.seen_ids = {cls: set() for cls in CLASSES.values()}
        self.counts = {cls: 0 for cls in CLASSES.values()}
        self.local_ids = {cls: {} for cls in CLASSES.values()}
        self.next_local_id = {cls: 1 for cls in CLASSES.values()}
        self.last_interval = None
        self.display = OledCounterDisplay()

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
        results = self.model.infer(frame)

        detections = []
        cls_map = {}
        for x1, y1, x2, y2, conf, cls_id in results:
            if cls_id not in CLASSES:
                continue
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

        print("Current Counts:", ", ".join(f"{cls}:{self.counts[cls]}" for cls in CLASSES.values()))
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
            print("Final counts:")
            for cls, cnt in self.counts.items():
                print(f"{cls}: {cnt}")


if __name__ == "__main__":
    ModalShareCounter().run()
