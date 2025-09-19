#!/usr/bin/env python3
"""
Generate preview images with bounding boxes for CAMINA dataset using configuration file.

This script creates preview images with labeled bounding boxes, using all
configurations from dataset_creator_config.json for consistency and maintainability.

Author: CAMINA Team
Date: 2025-09-18
Optimized: 2025-09-18
"""

import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ConfigDrivenPreviewGenerator:
    """
    Config-driven preview generator for CAMINA dataset.

    Generates preview images with labeled bounding boxes using
    class information from the configuration file.
    """

    def __init__(self, config_path: str = "dataset_creator_config.json") -> None:
        """
        Initialize the preview generator.

        Args:
            config_path: Path to the configuration JSON file

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config contains invalid values
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)

        # Load class information from config
        self._setup_class_info()

        # Setup color palette
        self._setup_color_palette()

        # Configure logging from config
        self._setup_logging()

        logger.info("Preview generator initialized")
        logger.info(f"Configuration loaded from: {config_path}")
        logger.info(f"Total classes: {len(self.class_names)}")

    def _load_config(self, config_path: str) -> Dict:
        """
        Load and validate configuration file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")

        # Validate required sections
        required_sections = ['classes', 'hybrid_config', 'detection_settings']
        missing_sections = [sec for sec in required_sections if sec not in config]
        if missing_sections:
            raise ValueError(f"Missing required config sections: {missing_sections}")

        return config

    def _setup_logging(self) -> None:
        """Setup logging based on config."""
        log_level = getattr(logging,
                           self.config.get('logging', {}).get('level', 'INFO').upper())
        logging.getLogger().setLevel(log_level)

    def _setup_class_info(self) -> None:
        """Setup class information from configuration."""
        # Load class mappings from config
        config_classes = self.config['classes']
        self.class_mapping = {int(k): v for k, v in config_classes.items()}

        # Create ordered list of class names
        self.class_names = []
        for i in sorted(self.class_mapping.keys()):
            self.class_names.append(self.class_mapping[i])

        # Get class categories from hybrid config
        coco_classes = set(self.config['hybrid_config']['coco_classes'].values())
        new_classes = set(self.config['hybrid_config']['new_classes'].values())

        self.existing_classes = coco_classes
        self.new_classes = new_classes

    def _setup_color_palette(self) -> None:
        """
        Setup color palette for different classes.

        Uses distinct colors for better visualization, with special
        highlighting for new classes.
        """
        # Base color palette (BGR format for OpenCV)
        base_colors = [
            (255, 100, 100),  # Light blue
            (100, 255, 100),  # Light green
            (100, 100, 255),  # Light red
            (255, 255, 100),  # Cyan
            (255, 100, 255),  # Magenta
            (100, 255, 255),  # Yellow
            (200, 50, 200),   # Purple
            (50, 200, 200),   # Orange
            (200, 200, 50),   # Teal
            (150, 150, 150),  # Gray
            (255, 200, 150),  # Light orange
            (150, 255, 200),  # Light mint
        ]

        # Assign colors to classes
        self.class_colors = {}
        for i, class_name in enumerate(self.class_names):
            color_idx = i % len(base_colors)
            base_color = base_colors[color_idx]

            # Enhance colors for new classes
            if class_name in self.new_classes:
                # Make new classes more vibrant
                enhanced_color = tuple(min(255, int(c * 1.2)) for c in base_color)
                self.class_colors[i] = enhanced_color
            else:
                self.class_colors[i] = base_color

    def draw_bbox_with_label(self, image: np.ndarray, bbox: List[float],
                           class_id: int, confidence: Optional[float] = None) -> np.ndarray:
        """
        Draw bounding box with label on image.

        Args:
            image: Input image array
            bbox: Bounding box in YOLO format [x_center, y_center, width, height]
            class_id: Class ID
            confidence: Optional confidence score

        Returns:
            Image with drawn bounding box
        """
        h, w = image.shape[:2]

        # Convert YOLO format to pixel coordinates
        x_center, y_center, width, height = bbox
        x1 = int((x_center - width / 2) * w)
        y1 = int((y_center - height / 2) * h)
        x2 = int((x_center + width / 2) * w)
        y2 = int((y_center + height / 2) * h)

        # Ensure coordinates are within image bounds
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))

        # Skip invalid boxes
        if x2 <= x1 or y2 <= y1:
            return image

        # Get color for this class
        color = self.class_colors.get(class_id, (128, 128, 128))

        # Draw bounding box
        thickness = 2
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)

        # Prepare label text
        class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"

        # Add marker for new classes
        if class_name in self.new_classes:
            class_name += " (NEW)"

        if confidence is not None:
            label = f"{class_name}: {confidence:.2f}"
        else:
            label = class_name

        # Calculate text size and background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        text_thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(
            label, font, font_scale, text_thickness
        )

        # Draw label background
        bg_y1 = max(0, y1 - text_height - 10)
        bg_y2 = y1
        bg_x1 = x1
        bg_x2 = min(w, x1 + text_width + 10)

        cv2.rectangle(image, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)

        # Draw label text
        text_y = max(text_height + 5, y1 - 5)
        cv2.putText(image, label, (x1 + 5, text_y), font, font_scale,
                   (255, 255, 255), text_thickness)

        return image

    def load_labels(self, label_path: Path) -> List[Tuple[int, List[float]]]:
        """
        Load YOLO format labels with validation.

        Args:
            label_path: Path to label file

        Returns:
            List of (class_id, bbox) tuples
        """
        labels = []
        if not label_path.exists():
            return labels

        try:
            with open(label_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    try:
                        parts = line.split()
                        if len(parts) < 5:
                            logger.warning(f"Invalid label format in {label_path}:{line_num}")
                            continue

                        class_id = int(parts[0])
                        bbox = [float(x) for x in parts[1:5]]

                        # Validate class ID
                        if not (0 <= class_id < len(self.class_names)):
                            logger.warning(f"Invalid class ID {class_id} in {label_path}:{line_num}")
                            continue

                        # Validate bbox coordinates
                        if not all(0 <= coord <= 1 for coord in bbox):
                            logger.warning(f"Invalid bbox coordinates in {label_path}:{line_num}")
                            continue

                        labels.append((class_id, bbox))

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing line {line_num} in {label_path}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to read labels from {label_path}: {e}")

        return labels

    def generate_previews(self, dataset_path: str, output_dir: Optional[str] = None,
                         num_previews: int = 100, random_seed: int = 42) -> bool:
        """
        Generate preview images with bounding boxes.

        Args:
            dataset_path: Path to dataset directory
            output_dir: Output directory (default: dataset_path/preview)
            num_previews: Number of preview images to generate
            random_seed: Random seed for reproducible sampling

        Returns:
            True if successful, False otherwise
        """
        dataset_path = Path(dataset_path)

        if not dataset_path.exists():
            logger.error(f"Dataset path not found: {dataset_path}")
            return False

        # Setup output directory
        if output_dir is None:
            preview_dir = dataset_path / "preview"
        else:
            preview_dir = Path(output_dir)

        preview_dir.mkdir(exist_ok=True)

        # Set random seed for reproducible results
        random.seed(random_seed)

        logger.info("=" * 60)
        logger.info("GENERATING PREVIEW IMAGES")
        logger.info("=" * 60)
        logger.info(f"Dataset: {dataset_path}")
        logger.info(f"Output: {preview_dir}")
        logger.info(f"Target previews: {num_previews}")
        logger.info(f"Classes: {len(self.class_names)}")
        logger.info("=" * 60)

        # Collect all image files from both train and test
        image_files = self._collect_image_files(dataset_path)

        if not image_files:
            logger.error("No valid image files found")
            return False

        logger.info(f"Found {len(image_files)} images with labels")

        # Sample images for preview
        selected_images = self._sample_images(image_files, num_previews)

        # Generate previews
        processing_stats = self._generate_preview_images(selected_images, preview_dir)

        # Create legend image
        if not self._create_legend_image(preview_dir):
            logger.warning("Failed to create legend image")

        # Generate summary report
        if not self._generate_summary_report(preview_dir, processing_stats, dataset_path):
            logger.warning("Failed to generate summary report")

        # Log final results
        self._log_final_results(processing_stats, preview_dir)

        return True

    def _collect_image_files(self, dataset_path: Path) -> List[Tuple[Path, Path, str]]:
        """
        Collect all valid image files with corresponding labels.

        Args:
            dataset_path: Path to dataset

        Returns:
            List of (image_path, label_path, split) tuples
        """
        supported_formats = self.config['detection_settings']['supported_formats']
        image_files = []

        for split in ['train', 'test']:
            images_dir = dataset_path / split / 'images'
            labels_dir = dataset_path / split / 'labels'

            if not images_dir.exists():
                logger.warning(f"Images directory not found: {images_dir}")
                continue

            for fmt in supported_formats:
                pattern = f"*{fmt}"
                for img_file in images_dir.glob(pattern):
                    label_file = labels_dir / f"{img_file.stem}.txt"
                    if label_file.exists():
                        image_files.append((img_file, label_file, split))

        return image_files

    def _sample_images(self, image_files: List[Tuple[Path, Path, str]],
                      num_previews: int) -> List[Tuple[Path, Path, str]]:
        """
        Sample images for preview generation.

        Args:
            image_files: List of available image files
            num_previews: Number of previews to generate

        Returns:
            List of selected image files
        """
        if len(image_files) <= num_previews:
            logger.info(f"Using all {len(image_files)} available images")
            return image_files
        else:
            logger.info(f"Randomly sampling {num_previews} from {len(image_files)} images")
            return random.sample(image_files, num_previews)

    def _generate_preview_images(self, selected_images: List[Tuple[Path, Path, str]],
                                preview_dir: Path) -> Dict:
        """
        Generate preview images with bounding boxes.

        Args:
            selected_images: List of selected image files
            preview_dir: Output directory

        Returns:
            Processing statistics
        """
        processing_stats = {
            'images_processed': 0,
            'images_generated': 0,
            'processing_errors': 0,
            'class_counts': {name: 0 for name in self.class_names},
            'split_counts': {'train': 0, 'test': 0}
        }

        for i, (img_path, label_path, split) in enumerate(
            tqdm(selected_images, desc="Generating previews")
        ):
            try:
                # Load image
                image = cv2.imread(str(img_path))
                if image is None:
                    logger.warning(f"Could not load image: {img_path}")
                    processing_stats['processing_errors'] += 1
                    continue

                # Load labels
                labels = self.load_labels(label_path)

                # Draw bounding boxes
                for class_id, bbox in labels:
                    if class_id < len(self.class_names):
                        class_name = self.class_names[class_id]
                        processing_stats['class_counts'][class_name] += 1
                        image = self.draw_bbox_with_label(image, bbox, class_id)

                # Add image info overlay
                self._add_info_overlay(image, split, len(labels), img_path.name)

                # Save preview
                output_name = f"preview_{i+1:03d}_{split}_{img_path.stem}.jpg"
                output_path = preview_dir / output_name

                if cv2.imwrite(str(output_path), image):
                    processing_stats['images_generated'] += 1
                    processing_stats['split_counts'][split] += 1
                else:
                    logger.warning(f"Failed to save preview: {output_path}")
                    processing_stats['processing_errors'] += 1

                processing_stats['images_processed'] += 1

            except Exception as e:
                logger.error(f"Error processing {img_path}: {e}")
                processing_stats['processing_errors'] += 1

        return processing_stats

    def _add_info_overlay(self, image: np.ndarray, split: str,
                         num_objects: int, filename: str) -> None:
        """
        Add information overlay to the image.

        Args:
            image: Image array to modify
            split: Dataset split name
            num_objects: Number of detected objects
            filename: Image filename
        """
        info_text = f"{split.upper()} | {num_objects} objects | {filename}"

        # Add white background for better readability
        cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                   0.7, (255, 255, 255), 3)
        # Add black text on top
        cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                   0.7, (0, 0, 0), 1)

    def _create_legend_image(self, preview_dir: Path) -> bool:
        """
        Create a legend image showing class colors.

        Args:
            preview_dir: Output directory

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate legend dimensions
            legend_height = len(self.class_names) * 40 + 80
            legend_width = 500
            legend_img = np.ones((legend_height, legend_width, 3), dtype=np.uint8) * 255

            # Title
            title = "CAMINA Dataset Classes"
            cv2.putText(legend_img, title, (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

            # Draw legend entries
            for i, class_name in enumerate(self.class_names):
                y_pos = 80 + i * 40
                color = self.class_colors[i]

                # Draw color box
                cv2.rectangle(legend_img, (20, y_pos - 15), (60, y_pos + 5), color, -1)
                cv2.rectangle(legend_img, (20, y_pos - 15), (60, y_pos + 5), (0, 0, 0), 1)

                # Determine marker
                if class_name in self.new_classes:
                    marker = "NEW"
                elif class_name in self.existing_classes:
                    marker = "EXISTING"
                else:
                    marker = "UNKNOWN"

                # Draw class information
                text = f"{i}: {class_name} ({marker})"
                cv2.putText(legend_img, text, (80, y_pos),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

            # Save legend
            legend_path = preview_dir / "class_legend.jpg"
            success = cv2.imwrite(str(legend_path), legend_img)

            if success:
                logger.info(f"Legend created: {legend_path}")

            return success

        except Exception as e:
            logger.error(f"Failed to create legend: {e}")
            return False

    def _generate_summary_report(self, preview_dir: Path, processing_stats: Dict,
                               dataset_path: Path) -> bool:
        """
        Generate summary report.

        Args:
            preview_dir: Preview output directory
            processing_stats: Processing statistics
            dataset_path: Original dataset path

        Returns:
            True if successful, False otherwise
        """
        try:
            summary = {
                "preview_info": {
                    "total_previews_generated": processing_stats['images_generated'],
                    "images_processed": processing_stats['images_processed'],
                    "processing_errors": processing_stats['processing_errors'],
                    "dataset_path": str(dataset_path),
                    "preview_directory": str(preview_dir),
                    "config_file": self.config_path
                },
                "dataset_metadata": {
                    "version": self.config['metadata']['version'],
                    "description": self.config['metadata']['description'],
                    "total_classes": len(self.class_names),
                    "class_names": self.class_names,
                    "existing_classes": list(self.existing_classes),
                    "new_classes": list(self.new_classes)
                },
                "split_distribution": processing_stats['split_counts'],
                "class_distribution": processing_stats['class_counts'],
                "color_mapping": {
                    self.class_names[i]: f"BGR{self.class_colors[i]}"
                    for i in range(len(self.class_names))
                }
            }

            summary_path = preview_dir / "preview_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, sort_keys=True)

            logger.info(f"Summary report saved: {summary_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
            return False

    def _log_final_results(self, processing_stats: Dict, preview_dir: Path) -> None:
        """Log final processing results."""
        logger.info("\n" + "=" * 60)
        logger.info("PREVIEW GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Images processed: {processing_stats['images_processed']}")
        logger.info(f"Previews generated: {processing_stats['images_generated']}")
        logger.info(f"Processing errors: {processing_stats['processing_errors']}")
        logger.info(f"Output directory: {preview_dir}")

        logger.info(f"\nSplit distribution:")
        for split, count in processing_stats['split_counts'].items():
            logger.info(f"  {split}: {count} images")

        logger.info(f"\nClass distribution in previews:")
        for class_name, count in processing_stats['class_counts'].items():
            if count > 0:
                marker = "NEW" if class_name in self.new_classes else "EXISTING"
                logger.info(f"  {class_name}: {count} instances ({marker})")

        logger.info("\nFiles created:")
        logger.info(f"  - {processing_stats['images_generated']} preview images")
        logger.info("  - class_legend.jpg (color coding reference)")
        logger.info("  - preview_summary.json (detailed statistics)")
        logger.info("=" * 60)


def main() -> None:
    """Main function for preview generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate previews for CAMINA dataset using configuration",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--dataset",
        default="outputs/dataset_v4i_yolov11_updated",
        help="Path to dataset directory"
    )
    parser.add_argument(
        "--output",
        help="Output directory for previews (default: dataset/preview)"
    )
    parser.add_argument(
        "--config",
        default="dataset_creator_config.json",
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--num-previews",
        type=int,
        default=100,
        help="Number of preview images to generate"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("CAMINA Dataset Preview Generator")
    logger.info("=" * 60)
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Config: {args.config}")
    logger.info(f"Previews to generate: {args.num_previews}")
    logger.info(f"Random seed: {args.seed}")
    if args.output:
        logger.info(f"Output directory: {args.output}")
    logger.info("=" * 60)

    try:
        # Initialize generator
        generator = ConfigDrivenPreviewGenerator(args.config)

        # Generate previews
        success = generator.generate_previews(
            dataset_path=args.dataset,
            output_dir=args.output,
            num_previews=args.num_previews,
            random_seed=args.seed
        )

        if success:
            logger.info("\nPreview generation completed successfully!")
        else:
            logger.error("Preview generation failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()