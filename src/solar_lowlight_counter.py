# solar_lowlight_counter.py
# CAMINA low-light mode with CLAHE preprocessing for infrared/night scenes

import cv2
import torch
import numpy as np
from ultralytics import YOLO
from sort import Sort

model = YOLO('yolov8n.pt')

CLASSES = {
    0: 'person',
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck',
}

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 416)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 416)

tracker = Sort()
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
            # CLAHE preprocessing for low-light enhancement
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            frame = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

            results = model.predict(frame, imgsz=320, conf=0.25)[0]

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
                class_label = class_map.get(min(class_map.keys(), key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))), None)
                if class_label and obj_id not in seen_ids[class_label]:
                    seen_ids[class_label].add(obj_id)
                    counts[class_label] += 1

            for cls, count in counts.items():
                cv2.putText(frame, f'{cls}: {count}', (10, 30 + 20 * list(CLASSES.values()).index(cls)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow('Low-Light Modal Counting (Edge Mode)', frame)

        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    print('Final Modal Share Counts:')
    for cls, count in counts.items():
        print(f'{cls}: {count}')
