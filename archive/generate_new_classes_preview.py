#!/usr/bin/env python3
"""
Generate preview images showing only the 3 new classes (e-scooter, SUV, delivery_van)
"""

import os
import cv2
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm

def load_class_info():
    """Load class information"""
    class_names = [
        'person',        # 0
        'cyclist',       # 1
        'car',           # 2
        'motorcycle',    # 3
        'bus',           # 4
        'truck',         # 5
        'e-scooter',     # 6
        'SUV',           # 7
        'delivery_van'   # 8
    ]

    # Define colors for new classes only
    colors = {
        6: (200, 50, 200),   # e-scooter - purple
        7: (50, 200, 200),   # SUV - orange
        8: (200, 200, 50)    # delivery_van - teal
    }

    return class_names, colors

def draw_bbox_with_label(image, bbox, class_id, class_names, colors, confidence=None):
    """Draw bounding box with label on image for new classes only"""
    if class_id not in [6, 7, 8]:  # Only draw new classes
        return image

    h, w = image.shape[:2]

    # Convert YOLO format to pixel coordinates
    x_center, y_center, width, height = bbox
    x1 = int((x_center - width / 2) * w)
    y1 = int((y_center - height / 2) * h)
    x2 = int((x_center + width / 2) * w)
    y2 = int((y_center + height / 2) * h)

    # Ensure coordinates are within image bounds
    x1 = max(0, min(x1, w-1))
    y1 = max(0, min(y1, h-1))
    x2 = max(0, min(x2, w-1))
    y2 = max(0, min(y2, h-1))

    # Get color for this class
    color = colors.get(class_id, (128, 128, 128))

    # Draw bounding box with thicker line for visibility
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)

    # Prepare label text
    class_name = class_names[class_id] if class_id < len(class_names) else f"class_{class_id}"
    if confidence is not None:
        label = f"{class_name}: {confidence:.2f}"
    else:
        label = class_name

    # Calculate text size and background
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)

    # Draw label background
    cv2.rectangle(image, (x1, y1 - text_height - 15), (x1 + text_width + 10, y1), color, -1)

    # Draw label text
    cv2.putText(image, label, (x1 + 5, y1 - 8), font, font_scale, (255, 255, 255), thickness)

    return image

def load_labels(label_path):
    """Load YOLO format labels"""
    labels = []
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split()
                    class_id = int(parts[0])
                    bbox = [float(x) for x in parts[1:5]]
                    labels.append((class_id, bbox))
    return labels

def has_new_classes(labels):
    """Check if labels contain any new classes (6, 7, 8)"""
    for class_id, _ in labels:
        if class_id in [6, 7, 8]:
            return True
    return False

def generate_new_classes_preview(dataset_path):
    """Generate preview images showing only new classes"""

    dataset_path = Path(dataset_path)
    preview_dir = dataset_path / "preview_3newclasses"
    preview_dir.mkdir(exist_ok=True)

    # Load class information
    class_names, colors = load_class_info()

    print(f"=== GENERATING PREVIEWS FOR 3 NEW CLASSES ===")
    print(f"Dataset: {dataset_path}")
    print(f"Output: {preview_dir}")
    print(f"Target classes: e-scooter (6), SUV (7), delivery_van (8)")

    # Collect images with new classes
    images_with_new_classes = []

    for split in ['train', 'test']:
        images_dir = dataset_path / split / 'images'
        labels_dir = dataset_path / split / 'labels'

        if images_dir.exists():
            for img_file in images_dir.glob('*.jpg'):
                label_file = labels_dir / f"{img_file.stem}.txt"
                if label_file.exists():
                    labels = load_labels(label_file)
                    if has_new_classes(labels):
                        images_with_new_classes.append((img_file, label_file, split))

    print(f"Found {len(images_with_new_classes)} images with new classes")

    if len(images_with_new_classes) == 0:
        print("❌ No images found with new classes!")
        return

    # Statistics tracking
    class_counts = {name: 0 for name in ['e-scooter', 'SUV', 'delivery_van']}
    split_counts = {'train': 0, 'test': 0}

    # Generate previews for all images with new classes
    for i, (img_path, label_path, split) in enumerate(tqdm(images_with_new_classes, desc="Generating new class previews")):
        try:
            # Load image
            image = cv2.imread(str(img_path))
            if image is None:
                print(f"Warning: Could not load image {img_path}")
                continue

            # Load labels
            labels = load_labels(label_path)

            # Filter to only new classes and draw bounding boxes
            new_class_count = 0
            for class_id, bbox in labels:
                if class_id in [6, 7, 8]:
                    class_counts[class_names[class_id]] += 1
                    new_class_count += 1
                    image = draw_bbox_with_label(image, bbox, class_id, class_names, colors)

            # Add image info text
            info_text = f"{split.upper()} | {new_class_count} NEW objects | {img_path.name}"
            cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)

            # Save preview
            output_name = f"newclasses_{i+1:03d}_{split}_{img_path.stem}.jpg"
            output_path = preview_dir / output_name
            cv2.imwrite(str(output_path), image)

            split_counts[split] += 1

        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            continue

    # Create summary
    summary = {
        "preview_info": {
            "total_previews": len(images_with_new_classes),
            "dataset_path": str(dataset_path),
            "preview_directory": str(preview_dir),
            "new_classes_only": True,
            "classes_shown": ["e-scooter", "SUV", "delivery_van"]
        },
        "split_distribution": split_counts,
        "new_class_distribution": class_counts,
        "color_mapping": {
            "e-scooter": "BGR(200, 50, 200)",
            "SUV": "BGR(50, 200, 200)",
            "delivery_van": "BGR(200, 200, 50)"
        }
    }

    # Save summary
    with open(preview_dir / "new_classes_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    # Create legend image for new classes only
    create_new_classes_legend(preview_dir, class_names, colors)

    # Print summary
    print(f"\n=== NEW CLASSES PREVIEW COMPLETE ===")
    print(f"Generated: {len(images_with_new_classes)} preview images")
    print(f"Saved to: {preview_dir}")
    print(f"\nSplit distribution:")
    for split, count in split_counts.items():
        print(f"  {split}: {count} images")

    print(f"\nNew class distribution:")
    for class_name, count in class_counts.items():
        print(f"  {class_name}: {count} instances")

    return preview_dir

def create_new_classes_legend(preview_dir, class_names, colors):
    """Create a legend image showing only new class colors"""

    new_classes = ['e-scooter', 'SUV', 'delivery_van']
    new_class_ids = [6, 7, 8]

    # Create legend image
    legend_height = len(new_classes) * 60 + 80
    legend_width = 400
    legend_img = np.zeros((legend_height, legend_width, 3), dtype=np.uint8)
    legend_img.fill(255)  # White background

    # Title
    cv2.putText(legend_img, "New Classes Legend", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    # Draw legend entries for new classes only
    for i, (class_name, class_id) in enumerate(zip(new_classes, new_class_ids)):
        y_pos = 80 + i * 60
        color = colors[class_id]

        # Draw color box
        cv2.rectangle(legend_img, (20, y_pos - 20), (60, y_pos + 10), color, -1)
        cv2.rectangle(legend_img, (20, y_pos - 20), (60, y_pos + 10), (0, 0, 0), 2)

        # Draw class name
        text = f"{class_id}: {class_name} (NEW)"
        cv2.putText(legend_img, text, (80, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    # Save legend
    cv2.imwrite(str(preview_dir / "new_classes_legend.jpg"), legend_img)
    print(f"New classes legend saved: {preview_dir / 'new_classes_legend.jpg'}")

def main():
    dataset_path = "outputs/dataset_v4i_yolov11_updated"

    # Generate previews
    preview_dir = generate_new_classes_preview(dataset_path)

    print(f"\n✅ New classes preview generation complete!")
    print(f"📁 Check the preview folder: {preview_dir}")
    print(f"📋 Files created:")
    print(f"   - Preview images with new class bounding boxes only")
    print(f"   - new_classes_legend.jpg (color coding reference)")
    print(f"   - new_classes_summary.json (detailed statistics)")

if __name__ == "__main__":
    main()