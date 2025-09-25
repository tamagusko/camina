#!/usr/bin/env python3
"""
CAMINA YOLO11n Detection Visualization Generator for Academic Publication
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from ultralytics import YOLO
import json
from pathlib import Path
import argparse
from collections import defaultdict
import matplotlib.patches as patches

# Class names and colors for visualization
CLASSES = [
    "Person", "Cyclist", "Car", "E-scooter", "SUV",
    "Motorcyclist", "Bus", "Delivery Van", "Truck"
]

# Professional color palette for academic publication
COLORS = {
    "Person": "#FF6B6B",        # Red
    "Cyclist": "#4ECDC4",       # Teal
    "Car": "#45B7D1",           # Blue
    "E-scooter": "#96CEB4",     # Light Green
    "SUV": "#FECA57",           # Yellow
    "Motorcyclist": "#FF9FF3",  # Pink
    "Bus": "#54A0FF",           # Light Blue
    "Delivery Van": "#5F27CD",  # Purple
    "Truck": "#00D2D3"          # Cyan
}

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def analyze_detections(model_path, test_images_dir, confidence_threshold=0.5):
    """
    Analyze all test images to find best candidates for visualization
    """
    print(f"Loading YOLO11n model from: {model_path}")
    model = YOLO(model_path)

    test_images = sorted([f for f in os.listdir(test_images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    print(f"Found {len(test_images)} test images")

    image_analysis = []

    for i, image_name in enumerate(test_images):
        if i % 10 == 0:
            print(f"Processing image {i+1}/{len(test_images)}: {image_name}")

        image_path = os.path.join(test_images_dir, image_name)

        # Run inference
        results = model(image_path, conf=confidence_threshold, verbose=False)

        if len(results) == 0 or results[0].boxes is None:
            continue

        boxes = results[0].boxes

        analysis = {
            'filename': image_name,
            'path': image_path,
            'num_detections': len(boxes),
            'classes_detected': [],
            'confidences': [],
            'avg_confidence': 0,
            'class_diversity': 0,
            'quality_score': 0
        }

        if len(boxes) > 0:
            # Extract detection info
            for box in boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                analysis['classes_detected'].append(CLASSES[class_id])
                analysis['confidences'].append(confidence)

            # Calculate metrics
            analysis['avg_confidence'] = np.mean(analysis['confidences'])
            analysis['class_diversity'] = len(set(analysis['classes_detected']))

            # Quality score: combination of confidence, diversity, and number of detections
            quality_score = (
                analysis['avg_confidence'] * 0.4 +  # 40% avg confidence
                (analysis['class_diversity'] / len(CLASSES)) * 0.3 +  # 30% diversity
                min(analysis['num_detections'] / 10, 1.0) * 0.3  # 30% detection count (capped)
            )
            analysis['quality_score'] = quality_score

        image_analysis.append(analysis)

    # Sort by quality score
    image_analysis.sort(key=lambda x: x['quality_score'], reverse=True)

    return image_analysis

def create_annotated_image(model, image_path, output_path, confidence_threshold=0.5):
    """
    Create professionally annotated detection visualization
    """
    # Load image
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Run inference
    results = model(image_path, conf=confidence_threshold, verbose=False)

    if len(results) == 0 or results[0].boxes is None:
        # Save original image if no detections
        cv2.imwrite(output_path, image)
        return []

    boxes = results[0].boxes
    detections_info = []

    # Convert to PIL for better text rendering
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    # Try to load a professional font
    try:
        # Try different font paths commonly available on Linux systems
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]

        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, 16)
                break

        if font is None:
            font = ImageFont.load_default()

    except:
        font = ImageFont.load_default()

    # Draw detections
    for box in boxes:
        # Extract box coordinates
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        class_name = CLASSES[class_id]
        color_hex = COLORS[class_name]
        color_rgb = hex_to_rgb(color_hex)

        # Store detection info
        detections_info.append({
            'class': class_name,
            'confidence': confidence,
            'bbox': [float(x1), float(y1), float(x2), float(y2)]
        })

        # Draw bounding box
        draw.rectangle([x1, y1, x2, y2], outline=color_rgb, width=3)

        # Prepare label
        label = f"{class_name}: {confidence:.2f}"

        # Calculate text size and background
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position label above the box, or inside if there's no space
        label_y = y1 - text_height - 5 if y1 - text_height - 5 > 0 else y1 + 5

        # Draw label background
        draw.rectangle([x1, label_y, x1 + text_width + 10, label_y + text_height + 5],
                      fill=color_rgb)

        # Draw label text
        draw.text((x1 + 5, label_y + 2), label, fill=(255, 255, 255), font=font)

    # Save annotated image
    pil_image.save(output_path, 'PNG', dpi=(300, 300))

    return detections_info

def create_mosaic(image_paths, output_path, title="Qualitative Detection Results using YOLO11n"):
    """
    Create publication-quality 2x2 mosaic
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(title, fontsize=20, fontweight='bold', y=0.95)

    for i, (ax, img_path) in enumerate(zip(axes.flat, image_paths)):
        # Load and display image
        img = plt.imread(img_path)
        ax.imshow(img)
        ax.axis('off')

        # Add subplot title with image filename
        filename = os.path.basename(img_path).replace('_annotated.png', '')
        ax.set_title(f"({chr(97+i)}) {filename[:20]}...", fontsize=12, pad=10)

    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(top=0.90, hspace=0.1, wspace=0.05)

    # Save with high DPI for publication
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"Mosaic saved to: {output_path}")

def main():
    # Paths
    model_path = "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt"
    test_images_dir = "/home/tiago/repos/camina/data/dataset_v4i_yolov11/test/images"
    output_dir = "/home/tiago/repos/camina/detection_visualizations"

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print("=== CAMINA YOLO11n Detection Visualization Generator ===")
    print(f"Model: {model_path}")
    print(f"Test images: {test_images_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Step 1: Analyze all images to find best candidates
    print("Step 1: Analyzing all test images...")
    model = YOLO(model_path)
    image_analysis = analyze_detections(model_path, test_images_dir, confidence_threshold=0.5)

    # Filter images with detections and good quality
    good_images = [img for img in image_analysis if img['num_detections'] > 0 and img['quality_score'] > 0.3]

    print(f"\nFound {len(good_images)} images with good quality detections")
    print("\nTop 10 candidates:")
    for i, img in enumerate(good_images[:10]):
        print(f"{i+1:2d}. {img['filename'][:30]:<30} | Score: {img['quality_score']:.3f} | "
              f"Detections: {img['num_detections']:2d} | Diversity: {img['class_diversity']} | "
              f"Avg Conf: {img['avg_confidence']:.3f}")

    # Step 2: Select 4 best images with diverse scenarios
    print("\nStep 2: Selecting 4 diverse images for mosaic...")

    selected_images = []
    used_scenarios = set()

    # Try to get diverse scenarios
    for img in good_images:
        classes_str = "_".join(sorted(set(img['classes_detected'])))

        if len(selected_images) >= 4:
            break

        # Prefer images with different class combinations
        if classes_str not in used_scenarios or len(selected_images) < 4:
            selected_images.append(img)
            used_scenarios.add(classes_str)

    # Ensure we have exactly 4 images
    if len(selected_images) > 4:
        selected_images = selected_images[:4]
    elif len(selected_images) < 4:
        # Fill with next best images
        for img in good_images:
            if img not in selected_images and len(selected_images) < 4:
                selected_images.append(img)

    print("Selected images:")
    for i, img in enumerate(selected_images):
        print(f"{i+1}. {img['filename']}")
        print(f"   Classes: {', '.join(set(img['classes_detected']))}")
        print(f"   Quality Score: {img['quality_score']:.3f}")
        print()

    # Step 3: Create annotated visualizations
    print("Step 3: Creating annotated visualizations...")

    annotated_paths = []
    all_detections = []

    for i, img_info in enumerate(selected_images):
        print(f"Processing image {i+1}/4: {img_info['filename']}")

        output_path = os.path.join(output_dir, f"image_{i+1}_annotated.png")
        detections = create_annotated_image(model, img_info['path'], output_path)

        annotated_paths.append(output_path)
        all_detections.append({
            'filename': img_info['filename'],
            'detections': detections
        })

    # Step 4: Create mosaic
    print("\nStep 4: Creating publication-quality mosaic...")
    mosaic_path = os.path.join(output_dir, "detection_results_mosaic.png")
    create_mosaic(annotated_paths, mosaic_path)

    # Step 5: Generate summary report
    print("\nStep 5: Generating summary report...")

    report = {
        'model_path': model_path,
        'test_dataset': test_images_dir,
        'total_test_images': len(image_analysis),
        'images_with_detections': len(good_images),
        'selected_images': [],
        'class_distribution': defaultdict(int),
        'confidence_stats': {
            'min': float('inf'),
            'max': 0,
            'avg': 0,
            'total_detections': 0
        }
    }

    total_conf = 0
    total_dets = 0

    for i, (img_info, detections) in enumerate(zip(selected_images, all_detections)):
        img_report = {
            'filename': img_info['filename'],
            'num_detections': len(detections['detections']),
            'classes': list(set([d['class'] for d in detections['detections']])),
            'confidences': [d['confidence'] for d in detections['detections']],
            'quality_score': img_info['quality_score']
        }

        # Update statistics
        for det in detections['detections']:
            report['class_distribution'][det['class']] += 1
            conf = det['confidence']
            total_conf += conf
            total_dets += 1
            report['confidence_stats']['min'] = min(report['confidence_stats']['min'], conf)
            report['confidence_stats']['max'] = max(report['confidence_stats']['max'], conf)

        report['selected_images'].append(img_report)

    if total_dets > 0:
        report['confidence_stats']['avg'] = total_conf / total_dets
        report['confidence_stats']['total_detections'] = total_dets

    # Save report
    report_path = os.path.join(output_dir, "detection_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    # Print final summary
    print("\n" + "="*60)
    print("DETECTION VISUALIZATION COMPLETE")
    print("="*60)
    print(f"Mosaic image: {mosaic_path}")
    print(f"Individual annotated images: {len(annotated_paths)}")
    print(f"Summary report: {report_path}")
    print()
    print("Selected Images Summary:")

    for i, img_report in enumerate(report['selected_images']):
        print(f"\nImage {i+1}: {img_report['filename']}")
        print(f"  Detections: {img_report['num_detections']}")
        print(f"  Classes: {', '.join(img_report['classes'])}")
        print(f"  Confidence range: {min(img_report['confidences']):.3f} - {max(img_report['confidences']):.3f}")
        print(f"  Quality score: {img_report['quality_score']:.3f}")

    print(f"\nOverall Statistics:")
    print(f"  Total detections: {report['confidence_stats']['total_detections']}")
    print(f"  Average confidence: {report['confidence_stats']['avg']:.3f}")
    print(f"  Confidence range: {report['confidence_stats']['min']:.3f} - {report['confidence_stats']['max']:.3f}")

    print(f"\nClass Distribution:")
    for class_name, count in sorted(report['class_distribution'].items()):
        print(f"  {class_name}: {count}")

    print(f"\nFiles created:")
    print(f"  - {mosaic_path}")
    for path in annotated_paths:
        print(f"  - {path}")
    print(f"  - {report_path}")

    return {
        'mosaic_path': mosaic_path,
        'annotated_images': annotated_paths,
        'selected_filenames': [img['filename'] for img in selected_images],
        'report': report
    }

if __name__ == "__main__":
    main()