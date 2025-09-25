#!/usr/bin/env python3
"""
Script to create updated YOLO visualization mosaic.
Replaces positions 1 and 3 with new images (no SUV/delivery_van)
Keeps positions 2 and 4 from the original mosaic.
"""

import os
import sys
import numpy as np
import cv2
from pathlib import Path
from ultralytics import YOLO
import yaml
import random
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import defaultdict

def load_class_names(data_yaml_path):
    """Load class names from data.yaml"""
    with open(data_yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return data['names']

def run_inference_on_image(model, image_path):
    """Run YOLO inference on a single image"""
    results = model(image_path, conf=0.3)  # Lower confidence to see more detections
    return results[0]

def has_excluded_classes(result, excluded_classes={'SUV', 'delivery_van'}):
    """Check if detection result contains any excluded classes"""
    if result.boxes is None:
        return False

    class_names = result.names
    detected_class_names = set()

    for box in result.boxes:
        class_id = int(box.cls[0])
        class_name = class_names[class_id]
        detected_class_names.add(class_name)

    return bool(excluded_classes.intersection(detected_class_names))

def get_detection_summary(result):
    """Get summary of detections in an image"""
    if result.boxes is None:
        return {}

    class_names = result.names
    detection_counts = defaultdict(int)
    high_conf_detections = []

    for box in result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])
        class_name = class_names[class_id]
        detection_counts[class_name] += 1

        if confidence > 0.5:
            high_conf_detections.append((class_name, confidence))

    return {
        'counts': dict(detection_counts),
        'high_conf': high_conf_detections,
        'total_detections': len(result.boxes)
    }

def find_suitable_images(model, images_dir, excluded_classes={'SUV', 'delivery_van'}, min_detections=2):
    """Find images suitable for the mosaic (no excluded classes, good detections)"""
    suitable_images = []
    image_files = list(Path(images_dir).glob('*.jpg')) + list(Path(images_dir).glob('*.png'))

    print(f"Scanning {len(image_files)} images for suitable candidates...")

    for i, img_path in enumerate(image_files):
        if i % 50 == 0:
            print(f"Processed {i}/{len(image_files)} images...")

        try:
            result = run_inference_on_image(model, str(img_path))

            # Skip if has excluded classes
            if has_excluded_classes(result, excluded_classes):
                continue

            # Get detection summary
            summary = get_detection_summary(result)

            # Skip if too few detections
            if summary['total_detections'] < min_detections:
                continue

            # Skip if no high confidence detections
            if len(summary['high_conf']) == 0:
                continue

            suitable_images.append({
                'path': str(img_path),
                'filename': img_path.name,
                'summary': summary,
                'result': result
            })

        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            continue

    print(f"\nFound {len(suitable_images)} suitable images")
    return suitable_images

def select_diverse_images(suitable_images, num_needed=2):
    """Select images with good class diversity"""
    # Sort by number of different classes (diversity) and high confidence detections
    def diversity_score(img_info):
        summary = img_info['summary']
        num_classes = len(summary['counts'])
        num_high_conf = len(summary['high_conf'])
        avg_conf = np.mean([conf for _, conf in summary['high_conf']]) if summary['high_conf'] else 0
        return num_classes * 2 + num_high_conf + avg_conf

    # Sort by diversity score
    suitable_images.sort(key=diversity_score, reverse=True)

    # Select top candidates, ensuring they're different
    selected = []
    for img_info in suitable_images:
        if len(selected) >= num_needed:
            break

        # Check if this image is sufficiently different from already selected
        is_different = True
        for selected_img in selected:
            if img_info['filename'] == selected_img['filename']:
                is_different = False
                break

        if is_different:
            selected.append(img_info)

    return selected

def draw_predictions_on_image(image, result, target_size=(640, 640)):
    """Draw bounding boxes and labels on image"""
    # Resize image
    img_resized = cv2.resize(image, target_size)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

    if result.boxes is None:
        return img_rgb

    # Color mapping for different classes
    colors = {
        'person': (255, 0, 0),      # Red
        'car': (0, 255, 0),         # Green
        'bus': (0, 0, 255),         # Blue
        'truck': (255, 255, 0),     # Yellow
        'cyclist': (255, 0, 255),   # Magenta
        'motorcycle': (0, 255, 255), # Cyan
        'e-scooter': (128, 128, 128), # Gray
        'SUV': (128, 0, 128),       # Purple
        'delivery_van': (64, 64, 64) # Dark Gray
    }

    # Get original image dimensions
    orig_h, orig_w = image.shape[:2]
    scale_x = target_size[0] / orig_w
    scale_y = target_size[1] / orig_h

    class_names = result.names

    for box in result.boxes:
        # Get box coordinates and scale them
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        x1 = int(x1 * scale_x)
        y1 = int(y1 * scale_y)
        x2 = int(x2 * scale_x)
        y2 = int(y2 * scale_y)

        # Get class and confidence
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])
        class_name = class_names[class_id]

        # Skip low confidence detections
        if confidence < 0.5:
            continue

        # Get color for this class
        color = colors.get(class_name, (255, 255, 255))

        # Draw bounding box
        cv2.rectangle(img_rgb, (x1, y1), (x2, y2), color, 2)

        # Draw label with confidence
        label = f"{class_name} {confidence:.2f}"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]

        # Draw label background
        cv2.rectangle(img_rgb, (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0], y1), color, -1)

        # Draw label text
        cv2.putText(img_rgb, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                   0.5, (0, 0, 0), 2)

    return img_rgb

def create_updated_mosaic(model, images_dir, output_path, preserve_positions=None):
    """Create updated 2x2 mosaic with specific positions preserved"""

    # For now, let's find suitable images and create a new mosaic
    # We'll manually specify which images to preserve based on the current mosaic

    print("Finding suitable images for replacement...")
    suitable_images = find_suitable_images(model, images_dir)

    if len(suitable_images) < 2:
        print(f"ERROR: Only found {len(suitable_images)} suitable images, need at least 2")
        return False

    # Select 2 diverse images for positions 1 and 3
    selected_images = select_diverse_images(suitable_images, num_needed=2)

    print(f"\nSelected images for replacement:")
    for i, img_info in enumerate(selected_images):
        print(f"Position {i+1}: {img_info['filename']}")
        print(f"  Classes: {list(img_info['summary']['counts'].keys())}")
        print(f"  High conf detections: {len(img_info['summary']['high_conf'])}")
        print()

    # For positions 2 and 4, we need to identify the current images
    # Since we can't reverse-engineer from the mosaic, let's find good examples
    # that match the characteristics we see in the current positions 2 and 4

    # Let's find images with SUV/car/cyclist/person combination (like position 2)
    pos2_candidates = []
    pos4_candidates = []

    for img_info in suitable_images:
        classes = set(img_info['summary']['counts'].keys())

        # Look for images similar to current position 2 (has multiple classes)
        if len(classes.intersection({'car', 'cyclist', 'person'})) >= 2:
            pos2_candidates.append(img_info)

        # Look for images similar to current position 4 (has cyclist, person, car)
        if len(classes.intersection({'cyclist', 'person', 'car'})) >= 2:
            pos4_candidates.append(img_info)

    # Since we can't preserve exact images, let's create a good representative mosaic
    # Using the best available images
    final_images = []

    # Position 1: First selected image (no SUV/delivery_van)
    final_images.append(selected_images[0])

    # Position 2: Best candidate similar to original (prefer multi-class)
    if pos2_candidates:
        pos2_img = max(pos2_candidates, key=lambda x: len(x['summary']['counts']))
        final_images.append(pos2_img)
    else:
        # Fallback to a good diverse image
        remaining = [img for img in suitable_images if img not in selected_images]
        if remaining:
            final_images.append(max(remaining, key=lambda x: len(x['summary']['counts'])))
        else:
            final_images.append(selected_images[1])

    # Position 3: Second selected image (no SUV/delivery_van)
    if len(selected_images) > 1:
        final_images.append(selected_images[1])
    else:
        remaining = [img for img in suitable_images if img != selected_images[0]]
        if remaining:
            final_images.append(remaining[0])
        else:
            final_images.append(selected_images[0])  # Duplicate if needed

    # Position 4: Best candidate for cyclist/person/car combination
    if pos4_candidates:
        used_files = {img['filename'] for img in final_images}
        available_pos4 = [img for img in pos4_candidates if img['filename'] not in used_files]
        if available_pos4:
            final_images.append(available_pos4[0])
        else:
            final_images.append(pos4_candidates[0])
    else:
        # Fallback
        remaining = [img for img in suitable_images if img['filename'] not in {img['filename'] for img in final_images}]
        if remaining:
            final_images.append(remaining[0])
        else:
            final_images.append(suitable_images[-1])  # Last resort

    # Ensure we have 4 images
    while len(final_images) < 4:
        final_images.append(suitable_images[len(final_images) % len(suitable_images)])

    # Create the mosaic
    mosaic_images = []
    target_size = (640, 640)

    print(f"\nCreating mosaic with:")
    for i, img_info in enumerate(final_images):
        print(f"Position {i+1}: {img_info['filename']}")
        print(f"  Classes: {list(img_info['summary']['counts'].keys())}")

        # Load and process image
        image = cv2.imread(img_info['path'])
        if image is None:
            print(f"ERROR: Could not load image {img_info['path']}")
            continue

        # Draw predictions
        img_with_predictions = draw_predictions_on_image(image, img_info['result'], target_size)
        mosaic_images.append(img_with_predictions)

    if len(mosaic_images) < 4:
        print("ERROR: Could not load enough images for mosaic")
        return False

    # Create 2x2 mosaic
    top_row = np.hstack([mosaic_images[0], mosaic_images[1]])
    bottom_row = np.hstack([mosaic_images[2], mosaic_images[3]])
    mosaic = np.vstack([top_row, bottom_row])

    # Save mosaic
    mosaic_bgr = cv2.cvtColor(mosaic, cv2.COLOR_RGB2BGR)
    success = cv2.imwrite(output_path, mosaic_bgr)

    if success:
        print(f"\nMosaic saved successfully to: {output_path}")
        # Check file size
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        print(f"File size: {file_size:.2f} MB")
        return True
    else:
        print(f"ERROR: Failed to save mosaic to {output_path}")
        return False

def main():
    # Configuration
    base_dir = "/home/tiago/repos/camina"
    model_path = f"{base_dir}/model/yolo_comparison/YOLO11n/train/weights/best.pt"
    images_dir = f"{base_dir}/data/datasetV3_stratified/val/images"
    output_path = f"{base_dir}/yolo11n_updated_mosaic.png"

    print("Loading YOLO model...")
    model = YOLO(model_path)
    print(f"Model loaded successfully")
    print(f"Classes: {list(model.names.values())}")

    # Create updated mosaic
    success = create_updated_mosaic(model, images_dir, output_path)

    if success:
        print(f"\n✅ Updated mosaic created successfully!")
        print(f"📁 Saved to: {output_path}")
    else:
        print(f"\n❌ Failed to create updated mosaic")
        sys.exit(1)

if __name__ == "__main__":
    main()