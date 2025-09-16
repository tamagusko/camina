# not implemented yet

# plugged_counter.py
# CAMINA full-feature mode: modal share, speed estimation, near misses (plugged-in, no energy constraints)

import cv2
import torch
import numpy as np
import time
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
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

tracker = Sort()
seen_ids = {cls: set() for cls in CLASSES.values()}
counts = {cls: 0 for cls in CLASSES.values()}
last_positions = {}
speeds = {}
fps = 10  # assumed frame rate (adjust to real camera rate)
meters_per_pixel = 0.05  # estimated (adjust with calibration)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model.predict(frame, imgsz=640, conf=0.4)[0]

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
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            bbox = (x1, y1, x2, y2)
            class_label = class_map.get(min(class_map.keys(), key=lambda b: np.linalg.norm(np.array(b) - np.array(bbox))), None)

            if class_label:
                # Count unique objects
                if obj_id not in seen_ids[class_label]:
                    seen_ids[class_label].add(obj_id)
                    counts[class_label] += 1

                # Speed estimation
                if obj_id in last_positions:
                    dx = cx - last_positions[obj_id][0]
                    dy = cy - last_positions[obj_id][1]
                    pixel_distance = np.sqrt(dx**2 + dy**2)
                    meters = pixel_distance * meters_per_pixel
                    speed = meters * fps * 3.6  # km/h
                    speeds[obj_id] = round(speed, 1)
                last_positions[obj_id] = (cx, cy)

                # Near-miss zone visualization (dummy logic)
                if class_label in ['person', 'bicycle']:
                    for oid2, pos2 in last_positions.items():
                        if oid2 != obj_id:
                            dist = np.linalg.norm(np.array([cx, cy]) - np.array(pos2))
                            if dist < 50:
                                cv2.putText(frame, 'NEAR MISS', (int(cx), int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Draw tracking box and label
                label = f'{class_label} ID {int(obj_id)}'
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame, label, (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                if obj_id in speeds:
                    cv2.putText(frame, f"{speeds[obj_id]} km/h", (int(x1), int(y2) + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # Display counts
        for cls, count in counts.items():
            cv2.putText(frame, f'{cls}: {count}', (10, 30 + 20 * list(CLASSES.values()).index(cls)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow('Modal, Speed & Near Miss (Plugged Mode)', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    print('Final Modal Share Counts:')
    for cls, count in counts.items():
        print(f'{cls}: {count}')
