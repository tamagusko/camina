#!/usr/bin/env python3
"""
Validate YOLO-format annotations and optionally visualize them,
filtering by specific class IDs.

Usage:

python validate_yolo_labels.py \
    --images-dir datasets/cyclist_yolo/images/train \
    --labels-dir datasets/cyclist_yolo/labels/train \
    --class-names "person,cyclist,car,motorcycle,bus,truck" \
    --filter-classes 1

Pass no filter to view all images. Press `q` to quit viewer.
"""

import argparse
import cv2
import os
from pathlib import Path

CLASS_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
                (255, 255, 0), (255, 0, 255), (0, 255, 255)]


def load_labels(label_path):
    boxes = []
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            cls, cx, cy, w, h = map(float, parts)
            boxes.append((int(cls), cx, cy, w, h))
    return boxes


def draw_boxes(img, boxes, class_names):
    h, w = img.shape[:2]
    for cls_id, cx, cy, bw, bh in boxes:
        x1 = int((cx - bw / 2) * w)
        y1 = int((cy - bh / 2) * h)
        x2 = int((cx + bw / 2) * w)
        y2 = int((cy + bh / 2) * h)
        color = CLASS_COLORS[cls_id % len(CLASS_COLORS)]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = class_names[cls_id] if cls_id < len(class_names) else str(cls_id)
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return img


def main():
    parser = argparse.ArgumentParser("YOLO label validator")
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--labels-dir", type=Path, required=True)
    parser.add_argument("--class-names", type=str, default="")
    parser.add_argument("--filter-classes", type=int, nargs="*", default=[])
    args = parser.parse_args()

    class_names = args.class_names.split(",") if args.class_names else []
    image_paths = sorted(args.images_dir.glob("*.jpg")) + sorted(args.images_dir.glob("*.png"))

    for img_path in image_paths:
        label_path = args.labels_dir / (img_path.stem + ".txt")
        if not label_path.exists():
            continue

        boxes = load_labels(label_path)
        if args.filter_classes:
            if not any(cls in args.filter_classes for cls, *_ in boxes):
                continue

        img = cv2.imread(str(img_path))
        if img is None:
            print(f"⚠️ Could not read: {img_path}")
            continue

        img = draw_boxes(img, boxes, class_names)
        cv2.imshow("YOLO Labels", img)
        key = cv2.waitKey(0)
        if key == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
