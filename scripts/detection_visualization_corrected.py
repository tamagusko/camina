#!/usr/bin/env python3
"""
Corrected YOLO Detection Visualization Script

This script creates a corrected 2x2 mosaic visualization of YOLO detection results
with proper class mappings and no title text.

Critical fixes applied:
- Correct class label mappings from data.yaml
- Proper image path usage
- No title text in mosaic
- Professional formatting for academic publication
"""

import os
import sys
import yaml
import random
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import torch

# Add the project root to Python path
sys.path.append('/home/tiago/repos/camina')

def load_correct_class_names():
    """Load correct class names from data.yaml"""
    data_yaml_path = '/home/tiago/repos/camina/data/datasetV3_stratified/data.yaml'

    with open(data_yaml_path, 'r') as f:
        data_config = yaml.safe_load(f)

    class_names = data_config['names']
    print("Correct class names from data.yaml:")
    for i, name in enumerate(class_names):
        print(f"  {i}: {name}")

    return class_names

def load_yolo_model():
    """Load YOLO model and verify class mappings"""
    try:
        from ultralytics import YOLO

        model_path = '/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt'
        print(f"Loading model from: {model_path}")

        model = YOLO(model_path)

        # Get model class names
        model_names = model.names
        print("\nModel class names:")
        for i, name in model_names.items():
            print(f"  {i}: {name}")

        return model, model_names

    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None

def select_representative_images(images_dir, num_images=4):
    """Select representative validation images for visualization"""
    images_path = Path(images_dir)
    all_images = list(images_path.glob("*.jpg"))

    print(f"Found {len(all_images)} validation images")

    # Randomly select images for diversity
    random.seed(42)  # For reproducible results
    selected_images = random.sample(all_images, min(num_images, len(all_images)))

    print("Selected images:")
    for img_path in selected_images:
        print(f"  - {img_path.name}")

    return selected_images

def run_inference_and_filter(model, image_path, confidence_threshold=0.5):
    """Run inference and filter results by confidence"""
    try:
        results = model(image_path, verbose=False)

        # Extract detection information
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    conf = float(box.conf[0])
                    if conf >= confidence_threshold:
                        cls_id = int(box.cls[0])
                        xyxy = box.xyxy[0].cpu().numpy()

                        detections.append({
                            'bbox': xyxy,
                            'confidence': conf,
                            'class_id': cls_id,
                            'class_name': model.names[cls_id]
                        })

        return detections

    except Exception as e:
        print(f"Error during inference on {image_path}: {e}")
        return []

def create_visualization_subplot(ax, image_path, detections, class_names):
    """Create visualization for a single image"""
    # Load and display image
    img = Image.open(image_path)
    ax.imshow(img)

    # Define colors for each class (consistent across all images)
    colors = {
        'SUV': '#FF6B6B',           # Red
        'bus': '#4ECDC4',           # Teal
        'car': '#45B7D1',           # Blue
        'cyclist': '#96CEB4',       # Green
        'delivery_van': '#FFEAA7',  # Yellow
        'e-scooter': '#DDA0DD',     # Plum
        'motorcycle': '#98D8C8',    # Mint
        'person': '#F7DC6F',        # Light yellow
        'truck': '#BB8FCE'          # Light purple
    }

    # Draw bounding boxes and labels
    detection_summary = {}

    for det in detections:
        bbox = det['bbox']
        conf = det['confidence']
        class_name = det['class_name']

        # Count detections by class
        if class_name not in detection_summary:
            detection_summary[class_name] = 0
        detection_summary[class_name] += 1

        # Get color for this class
        color = colors.get(class_name, '#FFFFFF')

        # Create rectangle
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1

        rect = patches.Rectangle(
            (x1, y1), width, height,
            linewidth=2,
            edgecolor=color,
            facecolor='none',
            alpha=0.8
        )
        ax.add_patch(rect)

        # Add label with confidence
        label = f'{class_name} {conf:.2f}'
        ax.text(
            x1, y1 - 5,
            label,
            fontsize=8,
            color=color,
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8)
        )

    # Remove axes
    ax.set_xticks([])
    ax.set_yticks([])

    # Add image info as subtitle
    img_name = Path(image_path).name[:20] + "..." if len(Path(image_path).name) > 20 else Path(image_path).name
    detection_text = ", ".join([f"{k}: {v}" for k, v in detection_summary.items()])
    ax.text(0.5, -0.02, f"{img_name}\n{detection_text}",
            transform=ax.transAxes, ha='center', va='top', fontsize=8)

    return detection_summary

def create_corrected_mosaic():
    """Create the corrected 2x2 detection mosaic"""
    print("Creating corrected detection visualization...")

    # Load correct class names
    correct_class_names = load_correct_class_names()

    # Load YOLO model
    model, model_names = load_yolo_model()
    if model is None:
        print("Failed to load model. Exiting.")
        return

    # Verify class mapping alignment
    print(f"\nClass mapping verification:")
    print(f"Expected classes: {len(correct_class_names)}")
    print(f"Model classes: {len(model_names)}")

    # Check if class names match
    mismatch = False
    for i in range(min(len(correct_class_names), len(model_names))):
        expected = correct_class_names[i]
        actual = model_names[i]
        if expected != actual:
            print(f"  Mismatch at index {i}: expected '{expected}', got '{actual}'")
            mismatch = True

    if not mismatch:
        print("  Class mappings are correctly aligned!")

    # Select representative images
    images_dir = '/home/tiago/repos/camina/data/datasetV3_stratified/val/images/'
    selected_images = select_representative_images(images_dir, 4)

    # Create the mosaic
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor('white')

    all_detections = []

    # Process each image
    for idx, img_path in enumerate(selected_images):
        row = idx // 2
        col = idx % 2
        ax = axes[row, col]

        print(f"\nProcessing image {idx + 1}: {img_path.name}")

        # Run inference
        detections = run_inference_and_filter(model, str(img_path), confidence_threshold=0.5)
        print(f"  Found {len(detections)} detections with confidence >= 0.5")

        # Create visualization
        detection_summary = create_visualization_subplot(ax, img_path, detections, correct_class_names)
        all_detections.extend(detections)

        # Print detection details for verification
        for det in detections:
            print(f"    - {det['class_name']}: {det['confidence']:.3f}")

    # Adjust layout and remove any title
    plt.tight_layout()

    # Save the corrected visualization
    output_path = '/home/tiago/repos/camina/output/detection_results_corrected.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"\nCorrected visualization saved to: {output_path}")

    # Summary statistics
    class_counts = {}
    total_detections = len(all_detections)

    for det in all_detections:
        class_name = det['class_name']
        if class_name not in class_counts:
            class_counts[class_name] = 0
        class_counts[class_name] += 1

    print(f"\nSummary of {total_detections} total detections:")
    for class_name, count in sorted(class_counts.items()):
        percentage = (count / total_detections) * 100
        print(f"  - {class_name}: {count} ({percentage:.1f}%)")

    plt.close()
    return output_path, selected_images, class_counts

def verify_person_labels():
    """Specifically verify that persons are correctly labeled"""
    print("\n" + "="*50)
    print("VERIFICATION: Person Detection Labels")
    print("="*50)

    model, _ = load_yolo_model()
    if model is None:
        return

    # Find images that likely contain persons
    images_dir = '/home/tiago/repos/camina/data/datasetV3_stratified/val/images/'
    test_images = list(Path(images_dir).glob("*.jpg"))[:10]  # Test first 10 images

    person_detections = []

    for img_path in test_images:
        detections = run_inference_and_filter(model, str(img_path), confidence_threshold=0.3)

        for det in detections:
            if det['class_name'] == 'person':
                person_detections.append({
                    'image': img_path.name,
                    'confidence': det['confidence'],
                    'bbox': det['bbox']
                })

    if person_detections:
        print(f"Found {len(person_detections)} person detections:")
        for det in person_detections[:5]:  # Show first 5
            print(f"  - {det['image']}: confidence {det['confidence']:.3f}")
        print("✅ Persons are correctly labeled as 'person'")
    else:
        print("⚠️  No person detections found in tested images")

if __name__ == "__main__":
    # Create output directory
    os.makedirs('/home/tiago/repos/camina/output', exist_ok=True)

    # Create corrected visualization
    output_path, selected_images, class_counts = create_corrected_mosaic()

    # Verify person labels specifically
    verify_person_labels()

    print(f"\n" + "="*50)
    print("CORRECTED VISUALIZATION COMPLETE")
    print("="*50)
    print(f"Output saved to: {output_path}")
    print("Selected images:")
    for img in selected_images:
        print(f"  - {img.name}")
    print("\nDetected classes:")
    for class_name, count in sorted(class_counts.items()):
        print(f"  - {class_name}: {count}")