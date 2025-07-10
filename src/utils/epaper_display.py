import time
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camina.utils.config import load_config

try:
    import epaper
except ImportError:
    print("Warning: epaper module not found. Display functionality will be disabled.")
    epaper = None


class EpaperCounterDisplay:
    def __init__(self, config_file: str = "main_config.yaml"):
        self.config = load_config(config_file)
        self.refresh_interval = self.config.get("refresh_interval_seconds", 30)
        self.last_update_time = 0
        
        self.epd = None
        self.width = 250
        self.height = 122
        self.font = None
        
        if epaper is not None:
            try:
                self.epd = epaper.epaper('epd2in13_V4').EPD()
                self.epd.init()
                self.epd.Clear()
                
                self.width = self.epd.width
                self.height = self.epd.height
                self.font = ImageFont.load_default()
                print("E-paper display initialized successfully")
            except Exception as e:
                print(f"Failed to initialize e-paper display: {e}")
                self.epd = None
        else:
            print("E-paper display not available - running in simulation mode")
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

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        draw.text((5, 0), f"CAMINA {timestamp}", font=self.font, fill=0)

        for i, (cls, label) in enumerate(self.display_labels.items()):
            count = counts.get(cls, 0)
            draw.text((5, 12 + i * 16), f"{label}: {count}", font=self.font, fill=0)

        if self.epd is not None:
            try:
                self.epd.display(self.epd.getbuffer(image))
            except Exception as e:
                print(f"Error updating e-paper display: {e}")
        else:
            print("Display update (simulation mode):")
            print(f"CAMINA {timestamp}")
            for cls, label in self.display_labels.items():
                count = counts.get(cls, 0)
                print(f"{label}: {count}")

    def clear(self):
        if self.epd is not None:
            try:
                self.epd.Clear()
            except Exception as e:
                print(f"Error clearing e-paper display: {e}")
        else:
            print("Display cleared (simulation mode)")