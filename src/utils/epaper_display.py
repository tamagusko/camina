import time
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from waveshare_epd import epd2in13_V3

import yaml

with open("src/config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

class EpaperCounterDisplay:
    def __init__(self):
        self.refresh_interval = CONFIG.get("refresh_interval_seconds", 30)
        self.last_update_time = 0
        self.previous = {}

        self.epd = epd2in13_V3.EPD()
        self.epd.init()
        self.epd.Clear(0xFF)

        self.width = self.epd.height  # 250
        self.height = self.epd.width  # 122
        self.font = ImageFont.load_default()

        self.display_labels = {
            "person": "Pedestrian",
            "cyclist": "Cyclist",
            "bus": "Bus",
            "car": "Car",
            "motorcycle": "Moto",
            "truck": "Truck",
        }

    def update(self, counts):
        now = time.time()
        if now - self.last_update_time < self.refresh_interval:
            return

        self.last_update_time = now

        image = Image.new("1", (self.width, self.height), 255)  # 1-bit white background
        draw = ImageDraw.Draw(image)

        title = "CAMINA COUNT"
        draw.text((5, 0), title, font=self.font, fill=0)

        for i, (cls, label) in enumerate(self.display_labels.items()):
            count = counts.get(cls, 0)
            draw.text((5, 12 + i * 16), f"{label}: {count}", font=self.font, fill=0)

        self.epd.display(self.epd.getbuffer(image))

    def clear(self):
        self.epd.Clear(0xFF)

if __name__ == "__main__":
    display = EpaperCounterDisplay()
    test_counts = {"person": 5, "cyclist": 2, "bus": 1, "car": 3, "motorcycle": 0, "truck": 1}
    display.update(test_counts)
