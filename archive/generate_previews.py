#!/usr/bin/env python3
"""
Generate preview images with bounding boxes for CAMINA dataset
"""

import os
import cv2
import numpy as np
import random
from pathlib import Path
from tqdm import tqdm
import json

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

    # Define colors for each class (BGR format for OpenCV)
    colors = [
        (255, 100, 100),  # person - light blue
        (100, 255, 100),  # cyclist - light green
        (100, 100, 255),  # car - light red
        (255, 255, 100),  # motorcycle - cyan
        (255, 100, 255),  # bus - magenta
        (100, 255, 255),  # truck - yellow
        (200, 50, 200),   # e-scooter - purple
        (50, 200, 200),   # SUV - orange
        (200, 200, 50)    # delivery_van - teal
    ]

    return class_names, colors

def draw_bbox_with_label(image, bbox, class_id, class_names, colors, confidence=None):
    """Draw bounding box with label on image"""
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
    color = colors[class_id] if class_id < len(colors) else (128, 128, 128)

    # Draw bounding box
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

    # Prepare label text
    class_name = class_names[class_id] if class_id < len(class_names) else f"class_{class_id}"
    if confidence is not None:
        label = f"{class_name}: {confidence:.2f}"
    else:
        label = class_name

    # Calculate text size and background
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 1
    (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)

    # Draw label background
    cv2.rectangle(image, (x1, y1 - text_height - 10), (x1 + text_width + 5, y1), color, -1)

    # Draw label text
    cv2.putText(image, label, (x1 + 2, y1 - 5), font, font_scale, (255, 255, 255), thickness)

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

def generate_previews(dataset_path, num_previews=100):
    """Generate preview images with bounding boxes"""

    dataset_path = Path(dataset_path)
    preview_dir = dataset_path / "preview"
    preview_dir.mkdir(exist_ok=True)

    # Load class information
    class_names, colors = load_class_info()

    print(f"=== GENERATING {num_previews} PREVIEW IMAGES ===")
    print(f"Dataset: {dataset_path}")
    print(f"Output: {preview_dir}")
    print(f"Classes: {len(class_names)}")

    # Collect all image files from both train and test
    all_images = []

    for split in ['train', 'test']:
        images_dir = dataset_path / split / 'images'
        labels_dir = dataset_path / split / 'labels'

        if images_dir.exists():
            for img_file in images_dir.glob('*.jpg'):
                label_file = labels_dir / f"{img_file.stem}.txt"
                if label_file.exists():
                    all_images.append((img_file, label_file, split))

    print(f"Found {len(all_images)} images with labels")

    # Randomly sample images for preview
    if len(all_images) < num_previews:
        print(f"Warning: Only {len(all_images)} images available, generating all of them")
        selected_images = all_images
    else:
        selected_images = random.sample(all_images, num_previews)

    # Statistics tracking
    class_counts = {name: 0 for name in class_names}
    split_counts = {'train': 0, 'test': 0}

    # Generate previews
    for i, (img_path, label_path, split) in enumerate(tqdm(selected_images, desc="Generating previews")):
        try:
            # Load image
            image = cv2.imread(str(img_path))
            if image is None:
                print(f"Warning: Could not load image {img_path}")
                continue

            # Load labels
            labels = load_labels(label_path)

            # Draw bounding boxes
            for class_id, bbox in labels:
                if class_id < len(class_names):
                    class_counts[class_names[class_id]] += 1
                    image = draw_bbox_with_label(image, bbox, class_id, class_names, colors)

            # Add image info text
            info_text = f"{split.upper()} | {len(labels)} objects | {img_path.name}"
            cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)

            # Save preview
            output_name = f"preview_{i+1:03d}_{split}_{img_path.stem}.jpg"
            output_path = preview_dir / output_name
            cv2.imwrite(str(output_path), image)

            split_counts[split] += 1

        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            continue

    # Create summary
    summary = {
        "preview_info": {
            "total_previews": len(selected_images),
            "dataset_path": str(dataset_path),
            "preview_directory": str(preview_dir),
            "class_names": class_names
        },
        "split_distribution": split_counts,
        "class_distribution": class_counts,
        "color_mapping": {
            class_names[i]: f"BGR{colors[i]}" for i in range(len(class_names))
        }
    }

    # Save summary
    with open(preview_dir / "preview_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    # Create legend image
    create_legend_image(preview_dir, class_names, colors)

    # Print summary
    print(f"\n=== PREVIEW GENERATION COMPLETE ===")
    print(f"Generated: {len(selected_images)} preview images")
    print(f"Saved to: {preview_dir}")
    print(f"\nSplit distribution:")
    for split, count in split_counts.items():
        print(f"  {split}: {count} images")

    print(f"\nClass distribution in previews:")
    for class_name, count in class_counts.items():
        print(f"  {class_name}: {count} instances")

    return preview_dir

def create_legend_image(preview_dir, class_names, colors):
    """Create a legend image showing class colors"""

    # Create legend image
    legend_height = len(class_names) * 40 + 60
    legend_width = 400
    legend_img = np.zeros((legend_height, legend_width, 3), dtype=np.uint8)
    legend_img.fill(255)  # White background

    # Title
    cv2.putText(legend_img, "CAMINA Dataset Classes", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Draw legend entries
    for i, (class_name, color) in enumerate(zip(class_names, colors)):
        y_pos = 60 + i * 40

        # Draw color box
        cv2.rectangle(legend_img, (20, y_pos - 15), (50, y_pos + 5), color, -1)
        cv2.rectangle(legend_img, (20, y_pos - 15), (50, y_pos + 5), (0, 0, 0), 1)

        # Draw class name
        marker = "NEW" if class_name in ['e-scooter', 'SUV', 'delivery_van'] else "EXISTING"
        text = f"{i}: {class_name} ({marker})"
        cv2.putText(legend_img, text, (60, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    # Save legend
    cv2.imwrite(str(preview_dir / "class_legend.jpg"), legend_img)
    print(f"Legend saved: {preview_dir / 'class_legend.jpg'}")

def main():
    dataset_path = "outputs/dataset_v4i_yolov11_updated"

    # Set random seed for reproducible sampling
    random.seed(42)

    # Generate previews
    preview_dir = generate_previews(dataset_path, num_previews=100)

    print(f"\n✅ Preview generation complete!")
    print(f"📁 Check the preview folder: {preview_dir}")
    print(f"📋 Files created:")
    print(f"   - 100 preview images with bounding boxes")
    print(f"   - class_legend.jpg (color coding reference)")
    print(f"   - preview_summary.json (detailed statistics)")

if __name__ == "__main__":
    main()