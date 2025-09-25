#!/usr/bin/env python3
"""
Create corrected detection visualization with proper class name mapping and no title.
"""

import sys
import os
sys.path.append('/home/tiago/repos/camina/venv_viz/lib/python3.13/site-packages')

import cv2
import numpy as np
from ultralytics import YOLO
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image, ImageDraw, ImageFont
import json

def create_class_mapping():
    """Create mapping from model class names to display names."""
    # Model classes (alphabetical order from training)
    model_to_display = {
        'SUV': 'SUV',
        'bus': 'Bus',
        'car': 'Car',
        'cyclist': 'Cyclist',
        'delivery_van': 'Delivery Van',
        'e-scooter': 'E-scooter',
        'motorcycle': 'Motorcyclist',
        'person': 'Person',
        'truck': 'Truck'
    }
    return model_to_display

def get_selected_images():
    """Get the same 4 images used in previous visualization."""
    # Use the same images that were used before
    base_path = "/home/tiago/repos/camina/datasets/CAMINA_dataset/test/images"

    # These are representative images with good variety of objects
    selected_images = [
        f"{base_path}/00000031_00498_d_0000012.jpg",  # Person + vehicles
        f"{base_path}/00000031_00498_d_0000024.jpg",  # Multiple objects
        f"{base_path}/00000031_00498_d_0000047.jpg",  # Bus + other objects
        f"{base_path}/00000031_00498_d_0000068.jpg",  # Various vehicles
    ]

    return selected_images

def run_detection_on_images(model, image_paths):
    """Run detection on selected images and return results with corrected labels."""
    results = []
    class_mapping = create_class_mapping()

    for i, img_path in enumerate(image_paths):
        print(f"Processing image {i+1}: {os.path.basename(img_path)}")

        if not os.path.exists(img_path):
            print(f"Warning: Image not found: {img_path}")
            continue

        # Run detection
        detection_results = model(img_path, conf=0.25, iou=0.5)

        # Process results
        img_result = {
            'image_path': img_path,
            'image_name': os.path.basename(img_path),
            'detections': []
        }

        for r in detection_results:
            boxes = r.boxes
            if boxes is not None:
                for j in range(len(boxes)):
                    # Get detection info
                    xyxy = boxes.xyxy[j].cpu().numpy()
                    conf = float(boxes.conf[j].cpu().numpy())
                    cls = int(boxes.cls[j].cpu().numpy())

                    # Get model class name and map to display name
                    model_class_name = model.names[cls]
                    display_class_name = class_mapping.get(model_class_name, model_class_name)

                    detection = {
                        'bbox': [float(x) for x in xyxy],
                        'confidence': conf,
                        'class_id': cls,
                        'model_class_name': model_class_name,
                        'display_class_name': display_class_name
                    }
                    img_result['detections'].append(detection)

        results.append(img_result)
        print(f"  Found {len(img_result['detections'])} detections")

        # Print class distribution for this image
        class_counts = {}
        for det in img_result['detections']:
            display_name = det['display_class_name']
            class_counts[display_name] = class_counts.get(display_name, 0) + 1

        if class_counts:
            print(f"  Classes detected: {', '.join([f'{name}({count})' for name, count in class_counts.items()])}")

    return results

def create_annotated_image(image_path, detections, output_path):
    """Create an annotated image with bounding boxes and corrected labels."""

    # Load image
    image = cv2.imread(image_path)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.imshow(image)
    ax.axis('off')

    # Define colors for each class
    colors = {
        'Person': '#FF6B6B',         # Red
        'Cyclist': '#4ECDC4',        # Teal
        'Car': '#45B7D1',           # Blue
        'E-scooter': '#96CEB4',     # Light Green
        'SUV': '#FECA57',           # Yellow
        'Motorcyclist': '#FF9FF3',   # Pink
        'Bus': '#54A0FF',           # Light Blue
        'Delivery Van': '#5F27CD',   # Purple
        'Truck': '#00D2D3'          # Cyan
    }

    # Add bounding boxes and labels
    for detection in detections:
        bbox = detection['bbox']
        conf = detection['confidence']
        display_name = detection['display_class_name']

        # Get color for this class
        color = colors.get(display_name, '#FFFFFF')

        # Create rectangle
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1

        rect = patches.Rectangle(
            (x1, y1), width, height,
            linewidth=2, edgecolor=color, facecolor='none'
        )
        ax.add_patch(rect)

        # Add label with confidence
        label = f'{display_name} {conf:.2f}'
        ax.text(x1, y1-10, label,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8),
                fontsize=10, color='white', weight='bold')

    # Save the annotated image
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close()

    print(f"Saved annotated image: {output_path}")

def create_detection_mosaic(detection_results, output_path):
    """Create a 2x2 mosaic of detection results WITHOUT title."""

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()

    # Define colors for each class
    colors = {
        'Person': '#FF6B6B',         # Red
        'Cyclist': '#4ECDC4',        # Teal
        'Car': '#45B7D1',           # Blue
        'E-scooter': '#96CEB4',     # Light Green
        'SUV': '#FECA57',           # Yellow
        'Motorcyclist': '#FF9FF3',   # Pink
        'Bus': '#54A0FF',           # Light Blue
        'Delivery Van': '#5F27CD',   # Purple
        'Truck': '#00D2D3'          # Cyan
    }

    for i, result in enumerate(detection_results):
        if i >= 4:  # Only show first 4 images
            break

        ax = axes[i]

        # Load and display image
        image = cv2.imread(result['image_path'])
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        ax.imshow(image)
        ax.axis('off')

        # Add bounding boxes and labels
        for detection in result['detections']:
            bbox = detection['bbox']
            conf = detection['confidence']
            display_name = detection['display_class_name']

            # Get color for this class
            color = colors.get(display_name, '#FFFFFF')

            # Create rectangle
            x1, y1, x2, y2 = bbox
            width = x2 - x1
            height = y2 - y1

            rect = patches.Rectangle(
                (x1, y1), width, height,
                linewidth=2, edgecolor=color, facecolor='none'
            )
            ax.add_patch(rect)

            # Add label with confidence
            label = f'{display_name} {conf:.2f}'
            ax.text(x1, y1-10, label,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8),
                    fontsize=9, color='white', weight='bold')

        # Add image identifier in bottom right
        ax.text(0.98, 0.02, f'Image {i+1}',
                transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7),
                fontsize=10, color='white', weight='bold',
                ha='right', va='bottom')

    # Remove any unused subplots
    for i in range(len(detection_results), 4):
        axes[i].remove()

    # NO TITLE - Remove any title text as requested
    plt.tight_layout()
    plt.subplots_adjust(wspace=0.05, hspace=0.05)

    # Save the mosaic
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close()

    print(f"Saved detection mosaic: {output_path}")

def save_detection_report(detection_results, output_path):
    """Save detailed detection report with corrected class names."""

    report = {
        'model_path': "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt",
        'confidence_threshold': 0.25,
        'iou_threshold': 0.5,
        'class_mapping_corrected': True,
        'total_images': len(detection_results),
        'images': []
    }

    total_detections = 0
    class_distribution = {}

    for result in detection_results:
        img_report = {
            'image_name': result['image_name'],
            'image_path': result['image_path'],
            'num_detections': len(result['detections']),
            'detections': []
        }

        for detection in result['detections']:
            det_report = {
                'display_class_name': detection['display_class_name'],
                'model_class_name': detection['model_class_name'],
                'confidence': detection['confidence'],
                'bbox': detection['bbox']
            }
            img_report['detections'].append(det_report)

            # Update statistics
            total_detections += 1
            class_name = detection['display_class_name']
            class_distribution[class_name] = class_distribution.get(class_name, 0) + 1

        report['images'].append(img_report)

    report['total_detections'] = total_detections
    report['class_distribution'] = class_distribution

    # Save report
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Saved detection report: {output_path}")

    # Print summary
    print(f"\nDETECTION SUMMARY:")
    print(f"Total detections: {total_detections}")
    print(f"Class distribution:")
    for class_name, count in sorted(class_distribution.items()):
        print(f"  {class_name}: {count}")

def main():
    """Main function to create corrected detection visualization."""

    print("="*80)
    print("CREATING CORRECTED DETECTION VISUALIZATION")
    print("="*80)

    # Load model
    model_path = "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt"
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)

    # Print model classes and mapping
    print(f"\nModel classes: {model.names}")
    class_mapping = create_class_mapping()
    print(f"Class mapping:")
    for model_name, display_name in class_mapping.items():
        print(f"  '{model_name}' -> '{display_name}'")

    # Get selected images
    image_paths = get_selected_images()
    print(f"\nSelected {len(image_paths)} images for detection")

    # Run detection
    detection_results = run_detection_on_images(model, image_paths)

    # Create output directory
    output_dir = "/home/tiago/repos/camina/detection_visualizations"
    os.makedirs(output_dir, exist_ok=True)

    # Create individual annotated images
    for i, result in enumerate(detection_results):
        output_path = os.path.join(output_dir, f"image_{i+1}_annotated_corrected.png")
        create_annotated_image(result['image_path'], result['detections'], output_path)

    # Create mosaic without title
    mosaic_path = os.path.join(output_dir, "detection_results_mosaic_corrected.png")
    create_detection_mosaic(detection_results, mosaic_path)

    # Save detection report
    report_path = os.path.join(output_dir, "detection_report_corrected.json")
    save_detection_report(detection_results, report_path)

    print("="*80)
    print("CORRECTED VISUALIZATION COMPLETE")
    print("="*80)
    print(f"Files saved in: {output_dir}")
    print("- Individual annotated images: image_*_annotated_corrected.png")
    print("- Detection mosaic (no title): detection_results_mosaic_corrected.png")
    print("- Detection report: detection_report_corrected.json")

if __name__ == "__main__":
    main()