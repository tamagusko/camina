import time
import cv2
from ultralytics import YOLO
from config import MODEL_PATH, CONFIDENCE_THRESHOLD, IMGSZ

# Configuration
IMAGE_PATH = "data/img/0391.jpg"

# Load model
model = YOLO(MODEL_PATH)

# Run prediction
start = time.time()
results = model.predict(IMAGE_PATH, imgsz=IMGSZ, conf=CONFIDENCE_THRESHOLD)
end = time.time()

results[0].show()

# Print inference time
print(f"Time cost: {end - start:.2f}s")
