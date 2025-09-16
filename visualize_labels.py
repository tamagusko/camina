#!/usr/bin/env python3
"""
CAMINA Label Visualization Script
Visualizes auto-generated labels from the dataset creator to inspect model output
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import json
import os
from datetime import datetime

class CAMINALabelVisualizer:
    def __init__(self, dataset_path):
        self.dataset_path = Path(dataset_path)
        self.images_dir = self.dataset_path / 'images'
        self.labels_dir = self.dataset_path / 'labels'

        # CAMINA 9-class names with colors
        self.class_names = [
            'pedestrian',    # 0
            'cyclist',       # 1
            'car',           # 2
            'motorcycle',    # 3
            'bus',           # 4
            'truck',         # 5
            'e-scooter',     # 6
            'SUV',           # 7
            'delivery_van'   # 8
        ]

        # Color palette for each class (BGR format for OpenCV)
        self.colors = [
            (255, 100, 100),  # pedestrian - light blue
            (100, 255, 100),  # cyclist - light green
            (100, 100, 255),  # car - light red
            (255, 255, 100),  # motorcycle - cyan
            (255, 100, 255),  # bus - magenta
            (100, 255, 255),  # truck - yellow
            (200, 150, 100),  # e-scooter - light brown
            (150, 100, 200),  # SUV - purple
            (100, 200, 150),  # delivery_van - teal
        ]

        # Statistics
        self.stats = {
            'total_images': 0,
            'images_with_labels': 0,
            'total_detections': 0,
            'class_counts': {name: 0 for name in self.class_names},
            'confidence_ranges': {name: [] for name in self.class_names}
        }

    def load_yolo_labels(self, label_file):
        """Load YOLO format labels from file"""
        labels = []
        if not label_file.exists():
            return labels

        with open(label_file, 'r') as f:
            for line in f.readlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])
                    confidence = float(parts[5]) if len(parts) > 5 else 1.0

                    labels.append({
                        'class_id': class_id,
                        'x_center': x_center,
                        'y_center': y_center,
                        'width': width,
                        'height': height,
                        'confidence': confidence
                    })
        return labels

    def draw_boxes_opencv(self, image, labels, show_confidence=True):
        """Draw bounding boxes on image using OpenCV"""
        img_height, img_width = image.shape[:2]

        for label in labels:
            class_id = label['class_id']
            if class_id >= len(self.class_names):
                continue

            # Convert normalized coordinates to pixel coordinates
            x_center = int(label['x_center'] * img_width)
            y_center = int(label['y_center'] * img_height)
            box_width = int(label['width'] * img_width)
            box_height = int(label['height'] * img_height)

            # Calculate box corners
            x1 = int(x_center - box_width // 2)
            y1 = int(y_center - box_height // 2)
            x2 = int(x_center + box_width // 2)
            y2 = int(y_center + box_height // 2)

            # Get class info
            class_name = self.class_names[class_id]
            color = self.colors[class_id]
            confidence = label['confidence']

            # Draw bounding box
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            # Prepare label text
            if show_confidence:
                text = f"{class_name}: {confidence:.2f}"
            else:
                text = class_name

            # Calculate text size and position
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)

            # Draw text background
            cv2.rectangle(image, (x1, y1 - text_height - 10),
                         (x1 + text_width + 10, y1), color, -1)

            # Draw text
            cv2.putText(image, text, (x1 + 5, y1 - 5), font, font_scale,
                       (0, 0, 0), thickness)

        return image

    def create_matplotlib_visualization(self, image_path, labels, output_path=None):
        """Create a matplotlib visualization with better formatting"""
        # Load image
        image = Image.open(image_path)
        img_width, img_height = image.size

        # Create figure
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        ax.imshow(image)

        # Draw bounding boxes
        for label in labels:
            class_id = label['class_id']
            if class_id >= len(self.class_names):
                continue

            # Convert normalized coordinates to pixel coordinates
            x_center = label['x_center'] * img_width
            y_center = label['y_center'] * img_height
            box_width = label['width'] * img_width
            box_height = label['height'] * img_height

            # Calculate box corners (matplotlib uses bottom-left origin)
            x = x_center - box_width / 2
            y = y_center - box_height / 2

            # Get class info
            class_name = self.class_names[class_id]
            color = np.array(self.colors[class_id]) / 255.0  # Normalize for matplotlib
            confidence = label['confidence']

            # Create rectangle patch
            rect = patches.Rectangle((x, y), box_width, box_height,
                                   linewidth=2, edgecolor=color,
                                   facecolor='none')
            ax.add_patch(rect)

            # Add text label
            text = f"{class_name}: {confidence:.2f}"
            ax.text(x, y - 10, text, color='white', fontsize=10,
                   bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.7))

        ax.set_xlim(0, img_width)
        ax.set_ylim(img_height, 0)  # Flip y-axis for image coordinates
        ax.axis('off')
        ax.set_title(f'CAMINA Auto-Labels: {image_path.name}', fontsize=14, pad=20)

        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def visualize_single_image(self, image_name, method='opencv', save_output=False, output_dir=None):
        """Visualize labels for a single image"""
        # Find image file
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        image_path = None

        for ext in image_extensions:
            potential_path = self.images_dir / f"{Path(image_name).stem}{ext}"
            if potential_path.exists():
                image_path = potential_path
                break

        if not image_path:
            print(f"❌ Image not found: {image_name}")
            return

        # Load labels
        label_file = self.labels_dir / f"{image_path.stem}.txt"
        labels = self.load_yolo_labels(label_file)

        if not labels:
            print(f"⚠️  No labels found for {image_name}")
            return

        print(f"🖼️  Visualizing {image_name}: {len(labels)} detections")

        if method == 'opencv':
            # OpenCV visualization
            image = cv2.imread(str(image_path))
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            visualized = self.draw_boxes_opencv(image.copy())

            if save_output and output_dir:
                output_path = Path(output_dir) / f"viz_{image_path.name}"
                cv2.imwrite(str(output_path), cv2.cvtColor(visualized, cv2.COLOR_RGB2BGR))
                print(f"💾 Saved: {output_path}")
            else:
                # Display with matplotlib
                plt.figure(figsize=(12, 8))
                plt.imshow(visualized)
                plt.axis('off')
                plt.title(f'CAMINA Auto-Labels: {image_path.name}')
                plt.show()

        elif method == 'matplotlib':
            # Matplotlib visualization
            if save_output and output_dir:
                output_path = Path(output_dir) / f"viz_{image_path.stem}.png"
                self.create_matplotlib_visualization(image_path, labels, output_path)
                print(f"💾 Saved: {output_path}")
            else:
                self.create_matplotlib_visualization(image_path, labels)

    def analyze_dataset(self):
        """Analyze the entire dataset and collect statistics"""
        print("📊 Analyzing dataset...")

        # Get all images
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        all_images = []
        for ext in image_extensions:
            all_images.extend(self.images_dir.glob(f"*{ext}"))
            all_images.extend(self.images_dir.glob(f"*{ext.upper()}"))

        self.stats['total_images'] = len(all_images)

        # Analyze each image
        for image_path in all_images:
            label_file = self.labels_dir / f"{image_path.stem}.txt"
            labels = self.load_yolo_labels(label_file)

            if labels:
                self.stats['images_with_labels'] += 1
                self.stats['total_detections'] += len(labels)

                for label in labels:
                    class_id = label['class_id']
                    if class_id < len(self.class_names):
                        class_name = self.class_names[class_id]
                        self.stats['class_counts'][class_name] += 1
                        self.stats['confidence_ranges'][class_name].append(label['confidence'])

    def print_statistics(self):
        """Print dataset statistics"""
        print("\n" + "="*60)
        print("📈 CAMINA Dataset Analysis")
        print("="*60)
        print(f"📁 Dataset path: {self.dataset_path}")
        print(f"🖼️  Total images: {self.stats['total_images']}")
        print(f"🏷️  Images with labels: {self.stats['images_with_labels']}")
        print(f"🎯 Total detections: {self.stats['total_detections']}")

        if self.stats['total_images'] > 0:
            label_rate = (self.stats['images_with_labels'] / self.stats['total_images']) * 100
            print(f"📊 Label coverage: {label_rate:.1f}%")

        if self.stats['total_detections'] > 0:
            avg_per_image = self.stats['total_detections'] / max(1, self.stats['images_with_labels'])
            print(f"🔢 Average detections/image: {avg_per_image:.1f}")

        print(f"\n🎯 Class Distribution:")
        for class_name, count in self.stats['class_counts'].items():
            if count > 0:
                percentage = (count / self.stats['total_detections']) * 100
                confidences = self.stats['confidence_ranges'][class_name]
                avg_conf = np.mean(confidences) if confidences else 0
                min_conf = np.min(confidences) if confidences else 0
                max_conf = np.max(confidences) if confidences else 0

                print(f"   {class_name:12}: {count:4d} ({percentage:5.1f}%) "
                      f"conf: {avg_conf:.2f} ({min_conf:.2f}-{max_conf:.2f})")

    def visualize_all_continuously(self, method='matplotlib', save_output=False, output_dir=None):
        """Continuously visualize all labeled images until interrupted"""
        print("\n🔄 Continuous Visualization Mode")
        print("=" * 50)
        print("📋 Controls:")
        print("   • Press Ctrl+C to stop")
        print("   • Close window to continue to next image")
        print("   • Each image will be shown individually")
        print("=" * 50)

        # Get all images with labels
        labeled_images = []
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']

        for ext in image_extensions:
            for image_path in self.images_dir.glob(f"*{ext}"):
                label_file = self.labels_dir / f"{image_path.stem}.txt"
                labels = self.load_yolo_labels(label_file)
                if labels:
                    labeled_images.append((image_path, labels))

        if not labeled_images:
            print("❌ No labeled images found")
            return

        print(f"\n🖼️  Found {len(labeled_images)} labeled images")
        print("Starting continuous visualization...\n")

        try:
            for idx, (image_path, labels) in enumerate(labeled_images):
                print(f"📸 [{idx+1}/{len(labeled_images)}] Showing: {image_path.name} ({len(labels)} objects)")

                try:
                    self.visualize_single_image(
                        image_path.name,
                        method=method,
                        save_output=save_output,
                        output_dir=output_dir
                    )
                except KeyboardInterrupt:
                    print("\n⏹️  Visualization interrupted by user")
                    break
                except Exception as e:
                    print(f"⚠️  Error visualizing {image_path.name}: {e}")
                    continue

        except KeyboardInterrupt:
            print("\n⏹️  Continuous visualization stopped by user")

        print("\n✅ Visualization session completed")

    def create_summary_visualization(self, output_path=None, max_images=9):
        """Create a summary grid showing multiple images with labels"""
        # Get images with labels
        labeled_images = []
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']

        for ext in image_extensions:
            for image_path in self.images_dir.glob(f"*{ext}"):
                label_file = self.labels_dir / f"{image_path.stem}.txt"
                labels = self.load_yolo_labels(label_file)
                if labels:
                    labeled_images.append((image_path, labels))

        if not labeled_images:
            print("❌ No labeled images found")
            return

        # Limit to max_images
        labeled_images = labeled_images[:max_images]

        # Calculate grid size
        n_images = len(labeled_images)
        cols = int(np.ceil(np.sqrt(n_images)))
        rows = int(np.ceil(n_images / cols))

        # Create figure
        fig, axes = plt.subplots(rows, cols, figsize=(4*cols, 4*rows))
        if rows == 1 and cols == 1:
            axes = [axes]
        elif rows == 1 or cols == 1:
            axes = axes.flatten()
        else:
            axes = axes.flatten()

        for idx, (image_path, labels) in enumerate(labeled_images):
            if idx >= len(axes):
                break

            ax = axes[idx]

            # Load and display image
            image = Image.open(image_path)
            img_width, img_height = image.size
            ax.imshow(image)

            # Draw bounding boxes
            for label in labels:
                class_id = label['class_id']
                if class_id >= len(self.class_names):
                    continue

                # Convert coordinates
                x_center = label['x_center'] * img_width
                y_center = label['y_center'] * img_height
                box_width = label['width'] * img_width
                box_height = label['height'] * img_height

                x = x_center - box_width / 2
                y = y_center - box_height / 2

                # Get class info
                color = np.array(self.colors[class_id]) / 255.0

                # Draw rectangle
                rect = patches.Rectangle((x, y), box_width, box_height,
                                       linewidth=1.5, edgecolor=color, facecolor='none')
                ax.add_patch(rect)

            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)
            ax.axis('off')
            ax.set_title(f"{image_path.name}\n{len(labels)} objects", fontsize=8)

        # Hide unused subplots
        for idx in range(len(labeled_images), len(axes)):
            axes[idx].axis('off')

        plt.suptitle('CAMINA Auto-Labeling Results - Sample Images', fontsize=16)
        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"💾 Summary saved: {output_path}")
            plt.close()
        else:
            plt.show()

def main():
    parser = argparse.ArgumentParser(
        description="CAMINA Label Visualization Tool - Inspect auto-generated labels"
    )
    parser.add_argument("dataset_path", help="Path to CAMINA dataset directory")
    parser.add_argument("--image", "-i", help="Specific image to visualize")
    parser.add_argument("--method", "-m", choices=['opencv', 'matplotlib'],
                       default='matplotlib', help="Visualization method")
    parser.add_argument("--save", "-s", action='store_true',
                       help="Save visualization instead of displaying")
    parser.add_argument("--output-dir", "-o", help="Output directory for saved visualizations")
    parser.add_argument("--summary", action='store_true',
                       help="Create summary visualization with multiple images")
    parser.add_argument("--continuous", "-c", action='store_true',
                       help="Continuously show all labeled images (Ctrl+C to stop)")
    parser.add_argument("--stats-only", action='store_true',
                       help="Only show statistics, no visualizations")

    args = parser.parse_args()

    # Initialize visualizer
    visualizer = CAMINALabelVisualizer(args.dataset_path)

    # Check if dataset exists
    if not visualizer.images_dir.exists() or not visualizer.labels_dir.exists():
        print(f"❌ Dataset not found at {args.dataset_path}")
        print("Expected structure:")
        print("  dataset_path/")
        print("    images/")
        print("    labels/")
        return

    # Create output directory if needed
    if args.save and args.output_dir:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"🔍 CAMINA Label Visualizer")
    print(f"📁 Dataset: {args.dataset_path}")

    # Analyze dataset
    visualizer.analyze_dataset()
    visualizer.print_statistics()

    # Exit if only stats requested
    if args.stats_only:
        return

    # Visualize specific image
    if args.image:
        print(f"\n🖼️  Visualizing specific image: {args.image}")
        visualizer.visualize_single_image(
            args.image,
            method=args.method,
            save_output=args.save,
            output_dir=args.output_dir
        )

    # Create summary visualization
    elif args.summary:
        print(f"\n📋 Creating summary visualization...")
        output_path = None
        if args.save and args.output_dir:
            output_path = Path(args.output_dir) / "camina_summary.png"
        visualizer.create_summary_visualization(output_path)

    # Continuous visualization mode
    elif args.continuous:
        visualizer.visualize_all_continuously(
            method=args.method,
            save_output=args.save,
            output_dir=args.output_dir
        )

    # Interactive mode - show first few images
    else:
        print(f"\n🎨 Interactive mode - showing first few labeled images...")
        print("Use --image <name> to visualize specific images")
        print("Use --summary to create a grid visualization")
        print("Use --continuous to show all images continuously (Ctrl+C to stop)")

        # Show first 3 images
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        count = 0
        for ext in image_extensions:
            for image_path in visualizer.images_dir.glob(f"*{ext}"):
                if count >= 3:
                    break
                label_file = visualizer.labels_dir / f"{image_path.stem}.txt"
                labels = visualizer.load_yolo_labels(label_file)
                if labels:
                    visualizer.visualize_single_image(
                        image_path.name,
                        method=args.method,
                        save_output=args.save,
                        output_dir=args.output_dir
                    )
                    count += 1
            if count >= 3:
                break

if __name__ == "__main__":
    main()