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
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

class OledCounterDisplay:
    def __init__(self):
        serial = i2c(port=1, address=0x3C)
        self.oled = ssd1306(serial)
        self.font = ImageFont.load_default()
        self.previous = {}
        self.labels = {
            "person": "Pedestrian",
            "cyclist": "Cyclist",
            "bus": "Bus",
            "car": "Car",
            "motorcycle": "Motorcycle",
            "truck": "Truck",
        }

    def update(self, counts: dict):
        if counts == self.previous:
            return
        self.previous = counts.copy()

        image = Image.new("1", self.oled.size)
        draw = ImageDraw.Draw(image)

        # Header line (yellow region - inverted)
        draw.rectangle((0, 0, self.oled.width, 10), outline=255, fill=255)
        header = f"Pedestrian: {counts.get('person', 0)} | Camina"
        draw.text((2, 0), header, font=self.font, fill=0)

        # Remaining lines (blue region - white text)
        y = 12
        draw.text((0, y +  0), f"Cyclist: {counts.get('cyclist', 0)}", font=self.font, fill=255)
        draw.text((0, y + 10), f"Bus : {counts.get('bus', 0)}", font=self.font, fill=255)
        draw.text((0, y + 20), f"Car : {counts.get('car', 0)}", font=self.font, fill=255)
        draw.text((0, y + 30), f"Motorcycle: {counts.get('motorcycle', 0)}", font=self.font, fill=255)
        draw.text((0, y + 40), f"Truck: {counts.get('truck', 0)}", font=self.font, fill=255)

        self.oled.display(image)
