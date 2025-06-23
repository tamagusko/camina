import time
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

import yaml
import epaper

with open("src/config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

class EpaperCounterDisplay:
    def __init__(self):
        self.refresh_interval = CONFIG.get("refresh_interval_seconds", 30)
        self.last_update_time = 0

        self.epd = epaper.epaper('epd2in13_V4').EPD()
        self.epd.init()
        self.epd.Clear()

        self.width = self.epd.width
        self.height = self.epd.height
        self.font = ImageFont.load_default()

        self.display_labels = {
            "person": "Pedestrian",
            "cyclist": "Cyclist",
            "bus": "Bus",
            "car": "Car",
            "motorcycle": "Motorcycle",
            "truck": "Truck",
        }

    def update(self, counts):
        now = time.time()
        if now - self.last_update_time < self.refresh_interval:
            return

        self.last_update_time = now
        now_dt = datetime.now()
        timestamp = now_dt.strftime("%H:%M %y%m%d")

        image = Image.new("1", (self.width, self.height), 255)  # White background
        draw = ImageDraw.Draw(image)

        draw.text((5, 0), f"CAMINA {timestamp}", font=self.font, fill=0)

        for i, (cls, label) in enumerate(self.display_labels.items()):
            count = counts.get(cls, 0)
            draw.text((5, 12 + i * 16), f"{label}: {count}", font=self.font, fill=0)

        self.epd.display(self.epd.getbuffer(image))

    def clear(self):
        self.epd.Clear()
