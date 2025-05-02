# CAMINA: Counting Active Mobility In Neighbourhood Areas
# A citizen science tool for participatory sensing of active and motorized travel patterns.
# YOLOv8n with SORT-based tracking for unique object counting on Raspberry Pi 3 (edge-based)

import cv2
import torch
import numpy as np
from ultralytics import YOLO
from sort import Sort  # Requires sort.py in the same directory

# Initialize YOLOv8n model
model = YOLO('yolov8n.pt')

# Classes to detect
CLASSES = {
    0: 'person',
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck',
}

# Initialize video capture (USB camera or Raspberry Pi Camera)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 416)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 416)

# Initialize tracker
tracker = Sort()

# Unique ID tracking per class
seen_ids = {cls: set() for cls in CLASSES.values()}
counts = {cls: 0 for cls in CLASSES.values()}

frame_skip = 5
frame_count = 0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_skip == 0:
            results = model.predict(frame, imgsz=320, conf=0.4)[0]

            detections = []
            class_map = {}

            for box in results.boxes:
                cls_id = int(box.cls.item())
                conf = box.conf.item()
                if cls_id in CLASSES:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append([x1, y1, x2, y2, conf])
                    class_map[(x1, y1, x2, y2)] = CLASSES[cls_id]

            detections = np.array(detections)
            tracked = tracker.update(detections)

            for obj in tracked:
                x1, y1, x2, y2, obj_id = obj
                bbox = (x1, y1, x2, y2)
                # Find closest match to original bbox
                class_label = class_map.get(min(class_map.keys(), key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))), None)
                if class_label and obj_id not in seen_ids[class_label]:
                    seen_ids[class_label].add(obj_id)
                    counts[class_label] += 1

            # Optional display
            for cls, count in counts.items():
                cv2.putText(frame, f'{cls}: {count}', (10, 30 + 20 * list(CLASSES.values()).index(cls)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow('Modal Share Counting (Edge Mode)', frame)

        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()

    print('Final Modal Share Counts:')
    for cls, count in counts.items():
        print(f'{cls}: {count}')
