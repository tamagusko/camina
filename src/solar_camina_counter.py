# CAMINA: Counting Active Mobility In Neighbourhood Areas
# Solar Powered Camina Counter
# This script uses YOLOv8 for object detection to count modal share.

import cv2
import torch
from ultralytics import YOLO

# Initialize YOLOv8n model
model = YOLO('yolov8n.pt')  # Ensure this is downloaded

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

# Counters initialization
counts = {cls: 0 for cls in CLASSES.values()}

frame_skip = 5  # Skip frames to save energy
frame_count = 0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Skip frames to conserve power
        if frame_count % frame_skip == 0:
            results = model(frame, size=320, conf=0.4)[0]

            # Temporary counters per frame
            temp_counts = {cls: 0 for cls in CLASSES.values()}

            # Process detections
            for det in results.boxes.data.cpu().numpy():
                class_id, confidence = int(det[-1]), det[-2]
                if class_id in CLASSES:
                    label = CLASSES[class_id]
                    temp_counts[label] += 1

            # Update global counts
            for cls in counts:
                counts[cls] += temp_counts[cls]

            # Optional: Display frame with counts (remove for further energy saving)
            for label, count in temp_counts.items():
                cv2.putText(frame, f'{label}: {count}', (10, 30 + 20 * list(CLASSES.values()).index(label)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow('Modal Share Counting (Edge Mode)', frame)

        frame_count += 1

        # Exit loop on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()

    # Print final counts
    print('Final Modal Share Counts:')
    for cls, count in counts.items():
        print(f'{cls}: {count}')
