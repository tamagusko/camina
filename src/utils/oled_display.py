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
