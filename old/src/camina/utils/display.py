import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

import yaml
from .config import load_config

try:
    import epaper
except ImportError:
    print("Warning: epaper module not found. E-paper display functionality will be disabled.")
    epaper = None

CONFIG = load_config()

class EpaperCounterDisplay:
    """E-paper display for showing vehicle counts."""
    
    def __init__(self) -> None:
        self.refresh_interval = CONFIG.get("refresh_interval_seconds", 30)
        self.last_update_time = 0
        self.epd = None
        self.width = 250
        self.height = 122
        self.font = ImageFont.load_default()

        if epaper is not None:
            try:
                self.epd = epaper.epaper('epd2in13_V4').EPD()
                self.epd.init()
                self.epd.Clear()
                self.width = self.epd.width
                self.height = self.epd.height
                print("E-paper display initialized successfully")
            except Exception as e:
                print(f"Failed to initialize e-paper display: {e}")
                self.epd = None
        else:
            print("E-paper display not available - running in simulation mode")

        self.display_labels = {
            "person": "Pedestrian",
            "cyclist": "Cyclist",
            "bus": "Bus",
            "car": "Car",
            "motorcycle": "Motorcycle",
            "truck": "Truck",
        }

    def update(self, counts: Dict[str, int], avg_speeds: Dict[str, float] = None) -> None:
        """Update the e-paper display with new counts and speeds."""
        now = time.time()
        if now - self.last_update_time < self.refresh_interval:
            return

        self.last_update_time = now
        now_dt = datetime.now()
        timestamp = now_dt.strftime("%H:%M %y%m%d")

        image = Image.new("1", (self.width, self.height), 255)  # White background
        draw = ImageDraw.Draw(image)

        draw.text((5, 0), f"CAMINA {timestamp}", font=self.font, fill=0)

        if avg_speeds is None:
            avg_speeds = {}

        for i, (cls, label) in enumerate(self.display_labels.items()):
            count = counts.get(cls, 0)
            speed = avg_speeds.get(cls, 0.0)
            # Format: "Pedestrian: 15 | 3.2 km/h"
            display_text = f"{label}: {count} | {speed:.1f} km/h"
            draw.text((5, 12 + i * 16), display_text, font=self.font, fill=0)

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
                speed = avg_speeds.get(cls, 0.0)
                print(f"{label}: {count} | {speed:.1f} km/h")

    def clear(self) -> None:
        """Clear the e-paper display."""
        if self.epd is not None:
            try:
                self.epd.Clear()
            except Exception as e:
                print(f"Error clearing e-paper display: {e}")
        else:
            print("Display cleared (simulation mode)")


class OledCounterDisplay:
    """OLED display for showing vehicle counts."""
    
    def __init__(self) -> None:
        self.oled = None
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
        
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import ssd1306
            
            serial = i2c(port=1, address=0x3C)
            self.oled = ssd1306(serial)
            print("OLED display initialized successfully")
        except ImportError:
            print("Warning: luma.oled not available, OLED display disabled")
        except Exception as e:
            print(f"Failed to initialize OLED display: {e}")
            self.oled = None

    def update(self, counts: Dict[str, int], avg_speeds: Dict[str, float] = None) -> None:
        """Update the OLED display with new counts and speeds."""
        if avg_speeds is None:
            avg_speeds = {}
            
        if self.oled is None:
            print("OLED display update (simulation mode):")
            for cls, label in self.labels.items():
                count = counts.get(cls, 0)
                speed = avg_speeds.get(cls, 0.0)
                print(f"{label}: {count} | {speed:.1f} km/h")
            return
            
        # Check if data has changed
        current_data = {**counts, **{f"{k}_speed": v for k, v in avg_speeds.items()}}
        if current_data == self.previous:
            return
        self.previous = current_data.copy()

        try:
            image = Image.new("1", self.oled.size)
            draw = ImageDraw.Draw(image)

            # Header line (yellow region - inverted)
            draw.rectangle((0, 0, self.oled.width, 10), outline=255, fill=255)
            ped_count = counts.get('person', 0)
            ped_speed = avg_speeds.get('person', 0.0)
            header = f"Person: {ped_count} | {ped_speed:.1f} km/h"
            draw.text((2, 0), header, font=self.font, fill=0)

            # Remaining lines (blue region - white text)
            y = 12
            cyc_count = counts.get('cyclist', 0)
            cyc_speed = avg_speeds.get('cyclist', 0.0)
            draw.text((0, y +  0), f"Cyclist: {cyc_count} | {cyc_speed:.1f}", font=self.font, fill=255)
            
            bus_count = counts.get('bus', 0)
            bus_speed = avg_speeds.get('bus', 0.0)
            draw.text((0, y + 10), f"Bus: {bus_count} | {bus_speed:.1f}", font=self.font, fill=255)
            
            car_count = counts.get('car', 0)
            car_speed = avg_speeds.get('car', 0.0)
            draw.text((0, y + 20), f"Car: {car_count} | {car_speed:.1f}", font=self.font, fill=255)
            
            mot_count = counts.get('motorcycle', 0)
            mot_speed = avg_speeds.get('motorcycle', 0.0)
            draw.text((0, y + 30), f"Moto: {mot_count} | {mot_speed:.1f}", font=self.font, fill=255)
            
            truck_count = counts.get('truck', 0)
            truck_speed = avg_speeds.get('truck', 0.0)
            draw.text((0, y + 40), f"Truck: {truck_count} | {truck_speed:.1f}", font=self.font, fill=255)

            self.oled.display(image)
        except Exception as e:
            print(f"Error updating OLED display: {e}")

    def clear(self) -> None:
        """Clear the OLED display."""
        if self.oled is not None:
            try:
                self.oled.clear()
            except Exception as e:
                print(f"Error clearing OLED display: {e}")
        else:
            print("OLED display cleared (simulation mode)")


class NoDisplay:
    """Dummy display class for when no display is configured."""
    
    def __init__(self) -> None:
        print("No display configured")
    
    def update(self, counts: Dict[str, int], avg_speeds: Dict[str, float] = None) -> None:
        """No-op update."""
        pass
    
    def clear(self) -> None:
        """No-op clear."""
        pass


def create_display(display_type: Optional[str] = None) -> Any:
    """Factory function to create display instances based on configuration.
    
    Args:
        display_type: Type of display to create. If None, reads from config.
        
    Returns:
        Display instance based on the specified type.
    """
    if display_type is None:
        display_type = CONFIG.get("display_type", "None")
    
    display_type = display_type.lower()
    
    if display_type == "epaper":
        return EpaperCounterDisplay()
    elif display_type == "oled":
        return OledCounterDisplay()
    elif display_type == "none" or display_type is None:
        return NoDisplay()
    else:
        print(f"Unknown display type: {display_type}. Using NoDisplay.")
        return NoDisplay()
