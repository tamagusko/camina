#!/usr/bin/env python3
"""
YOLO-World Supplement Script for CAMINA Dataset

This script runs YOLO-World detection on an existing dataset to detect e-scooter, SUV, and delivery_van classes
and merges the results with existing COCO + cyclist labels.

Author: CAMINA Team
Date: 2025-09-18
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import shutil

import cv2
import numpy as np
import torch
from tqdm import tqdm
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class YOLOWorldSupplementor:
    """YOLO-World supplementor for detecting new classes on existing dataset"""

    def __init__(self, config_path: str = "dataset_creator_config.json"):
        """Initialize with configuration"""
        self.config = self.load_config(config_path)
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")

        # Class mappings
        self.existing_classes = {
            0: "bus",
            1: "car",
            2: "cyclist",
            3: "motorcycle",
            4: "person",
            5: "truck"
        }

        self.new_classes = {
            6: "e-scooter",
            7: "SUV",
            8: "delivery_van"
        }

        # Combined mapping for output
        self.all_classes = {**self.existing_classes, **self.new_classes}

    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def initialize_yolo_world(self):
        """Initialize YOLO-World model"""
        try:
            from ultralytics import YOLO

            model_name = self.config['yolo_world_config']['model_name']
            logger.info(f"Initializing YOLO-World model: {model_name}")

            self.model = YOLO(model_name)

            # Set custom vocabulary for new classes
            text_prompts = []
            for class_name in self.new_classes.values():
                prompts = self.config['text_prompts'][class_name]
                text_prompts.extend(prompts)

            # Set the vocabulary
            self.model.set_classes(list(self.new_classes.values()))

            logger.info(f"YOLO-World initialized with classes: {list(self.new_classes.values())}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize YOLO-World: {e}")
            return False

    def detect_new_classes(self, image_path: str, confidence_threshold: float = 0.25) -> List[Dict]:
        """Detect new classes in image using YOLO-World"""
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                logger.warning(f"Could not load image: {image_path}")
                return []

            height, width = image.shape[:2]

            # Run detection
            results = self.model(image, conf=confidence_threshold, verbose=False)

            detections = []
            for result in results:
                if result.boxes is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()
                    confidences = result.boxes.conf.cpu().numpy()
                    class_ids = result.boxes.cls.cpu().numpy().astype(int)

                    for box, conf, cls_id in zip(boxes, confidences, class_ids):
                        if cls_id < len(self.new_classes):
                            class_name = list(self.new_classes.values())[cls_id]

                            # Apply class-specific confidence threshold
                            class_threshold = self.config['confidence_thresholds'][class_name]
                            if conf >= class_threshold:
                                # Convert to YOLO format (normalized)
                                x1, y1, x2, y2 = box
                                x_center = (x1 + x2) / 2 / width
                                y_center = (y1 + y2) / 2 / height
                                bbox_width = (x2 - x1) / width
                                bbox_height = (y2 - y1) / height

                                # Map to final class ID
                                final_class_id = 6 + cls_id  # e-scooter=6, SUV=7, delivery_van=8

                                detections.append({
                                    'class_id': final_class_id,
                                    'class_name': class_name,
                                    'confidence': float(conf),
                                    'bbox': [x_center, y_center, bbox_width, bbox_height]
                                })

            return detections

        except Exception as e:
            logger.error(f"Detection failed for {image_path}: {e}")
            return []

    def load_existing_labels(self, label_path: str) -> List[List[float]]:
        """Load existing YOLO format labels"""
        labels = []
        if os.path.exists(label_path):
            try:
                with open(label_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            parts = line.split()
                            # Convert to float: [class_id, x_center, y_center, width, height]
                            label = [float(parts[0])] + [float(x) for x in parts[1:]]
                            labels.append(label)
            except Exception as e:
                logger.warning(f"Failed to load labels from {label_path}: {e}")
        return labels

    def save_combined_labels(self, output_path: str, existing_labels: List[List[float]],
                           new_detections: List[Dict]):
        """Save combined labels in YOLO format"""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'w') as f:
                # Write existing labels
                for label in existing_labels:
                    class_id = int(label[0])
                    bbox = label[1:5]
                    f.write(f"{class_id} {' '.join(map(str, bbox))}\n")

                # Write new detections
                for detection in new_detections:
                    class_id = detection['class_id']
                    bbox = detection['bbox']
                    f.write(f"{class_id} {' '.join(map(str, bbox))}\n")

        except Exception as e:
            logger.error(f"Failed to save labels to {output_path}: {e}")

    def process_dataset(self, dataset_path: str, output_path: str):
        """Process entire dataset"""
        dataset_path = Path(dataset_path)
        output_path = Path(output_path)

        # Create output directory structure
        output_path.mkdir(parents=True, exist_ok=True)

        # Process train and test splits
        for split in ['train', 'test']:
            split_input = dataset_path / split
            split_output = output_path / split

            if not split_input.exists():
                logger.warning(f"Split directory not found: {split_input}")
                continue

            logger.info(f"Processing {split} split...")

            # Create output directories
            (split_output / 'images').mkdir(parents=True, exist_ok=True)
            (split_output / 'labels').mkdir(parents=True, exist_ok=True)

            # Copy images
            logger.info(f"Copying {split} images...")
            src_images = split_input / 'images'
            dst_images = split_output / 'images'
            if src_images.exists():
                shutil.copytree(src_images, dst_images, dirs_exist_ok=True)

            # Process labels
            images_dir = split_input / 'images'
            labels_dir = split_input / 'labels'

            if not images_dir.exists():
                logger.warning(f"Images directory not found: {images_dir}")
                continue

            image_files = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.png'))

            detection_stats = {class_name: 0 for class_name in self.new_classes.values()}

            for image_file in tqdm(image_files, desc=f"Processing {split}"):
                try:
                    # Get corresponding label file
                    label_file = labels_dir / f"{image_file.stem}.txt"

                    # Load existing labels
                    existing_labels = self.load_existing_labels(str(label_file))

                    # Detect new classes
                    new_detections = self.detect_new_classes(str(image_file))

                    # Update stats
                    for detection in new_detections:
                        detection_stats[detection['class_name']] += 1

                    # Save combined labels
                    output_label_file = split_output / 'labels' / f"{image_file.stem}.txt"
                    self.save_combined_labels(str(output_label_file), existing_labels, new_detections)

                except Exception as e:
                    logger.error(f"Failed to process {image_file}: {e}")
                    continue

            logger.info(f"{split.capitalize()} detection statistics:")
            for class_name, count in detection_stats.items():
                logger.info(f"  {class_name}: {count} detections")

        # Create updated data.yaml
        self.create_updated_data_yaml(output_path)

        # Generate summary report
        self.generate_summary_report(dataset_path, output_path)

    def create_updated_data_yaml(self, output_path: Path):
        """Create updated data.yaml with all 9 classes"""
        data_yaml = {
            'train': '../train/images',
            'val': '../valid/images',
            'test': '../test/images',
            'nc': 9,
            'names': [
                'bus',           # 0
                'car',           # 1
                'cyclist',       # 2
                'motorcycle',    # 3
                'person',        # 4
                'truck',         # 5
                'e-scooter',     # 6
                'SUV',           # 7
                'delivery_van'   # 8
            ]
        }

        with open(output_path / 'data.yaml', 'w') as f:
            import yaml
            yaml.dump(data_yaml, f, default_flow_style=False)

        logger.info(f"Updated data.yaml created with 9 classes")

    def generate_summary_report(self, input_path: Path, output_path: Path):
        """Generate summary report of detected instances"""
        logger.info("Generating summary report...")

        # Count instances in each split
        summary = {
            'dataset_info': {
                'input_path': str(input_path),
                'output_path': str(output_path),
                'total_classes': 9,
                'existing_classes': list(self.existing_classes.values()),
                'new_classes_added': list(self.new_classes.values())
            },
            'class_counts': {}
        }

        for split in ['train', 'test']:
            split_dir = output_path / split / 'labels'
            if not split_dir.exists():
                continue

            class_counts = {i: 0 for i in range(9)}

            for label_file in split_dir.glob('*.txt'):
                try:
                    with open(label_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                class_id = int(line.split()[0])
                                if 0 <= class_id < 9:
                                    class_counts[class_id] += 1
                except Exception as e:
                    logger.warning(f"Error reading {label_file}: {e}")

            summary['class_counts'][split] = {}
            for class_id, count in class_counts.items():
                class_name = self.all_classes[class_id]
                summary['class_counts'][split][class_name] = count

        # Save summary
        with open(output_path / 'detection_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)

        # Print summary
        logger.info("=== DETECTION SUMMARY ===")
        for split, counts in summary['class_counts'].items():
            logger.info(f"\n{split.upper()} split:")
            for class_name, count in counts.items():
                marker = "NEW" if class_name in self.new_classes.values() else "EXISTING"
                logger.info(f"  {class_name}: {count} instances ({marker})")


def main():
    parser = argparse.ArgumentParser(description="YOLO-World supplement for CAMINA dataset")
    parser.add_argument("--dataset", default="data/dataset_v4i_yolov11",
                       help="Path to input dataset")
    parser.add_argument("--output", default="outputs/dataset_v4i_yolov11_updated",
                       help="Path to output dataset")
    parser.add_argument("--config", default="dataset_creator_config.json",
                       help="Path to configuration file")

    args = parser.parse_args()

    logger.info("=== CAMINA YOLO-World Supplement ===")
    logger.info(f"Input dataset: {args.dataset}")
    logger.info(f"Output path: {args.output}")

    # Initialize supplementor
    supplementor = YOLOWorldSupplementor(args.config)

    # Initialize YOLO-World
    if not supplementor.initialize_yolo_world():
        logger.error("Failed to initialize YOLO-World model")
        sys.exit(1)

    # Process dataset
    supplementor.process_dataset(args.dataset, args.output)

    logger.info("=== PROCESSING COMPLETE ===")


if __name__ == "__main__":
    main()