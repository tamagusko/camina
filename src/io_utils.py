#!/usr/bin/env python3
"""
CAMINA I/O Utilities

Handles file I/O operations including image loading, annotation saving,
and format conversions between different annotation formats.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any
import numpy as np
from PIL import Image
import cv2

logger = logging.getLogger(__name__)


class ImageLoader:
    """
    Efficient image loading with caching and format validation.
    """

    def __init__(self, cache_size: int = 50):
        """
        Initialize image loader.

        Args:
            cache_size: Maximum number of images to cache in memory
        """
        self.cache = {}
        self.access_order = []
        self.cache_size = cache_size
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

    def load_image(self, image_path: Union[str, Path]) -> Tuple[Optional[Image.Image], Optional[Tuple[int, int]]]:
        """
        Load image with caching.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (PIL Image, (width, height)) or (None, None) if failed
        """
        image_path = Path(image_path)

        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return None, None

        if image_path.suffix.lower() not in self.supported_formats:
            logger.error(f"Unsupported image format: {image_path.suffix}")
            return None, None

        # Check cache
        path_str = str(image_path)
        if path_str in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(path_str)
            self.access_order.append(path_str)
            return self.cache[path_str]

        try:
            # Load image
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            dimensions = image.size  # (width, height)

            # Add to cache
            self._add_to_cache(path_str, (image, dimensions))

            return image, dimensions

        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {e}")
            return None, None

    def load_image_cv2(self, image_path: Union[str, Path]) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int]]]:
        """
        Load image using OpenCV.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (numpy array in BGR format, (width, height)) or (None, None) if failed
        """
        image_path = Path(image_path)

        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return None, None

        try:
            image = cv2.imread(str(image_path))
            if image is None:
                logger.error(f"Failed to load image with OpenCV: {image_path}")
                return None, None

            height, width = image.shape[:2]
            return image, (width, height)

        except Exception as e:
            logger.error(f"Failed to load image {image_path} with OpenCV: {e}")
            return None, None

    def _add_to_cache(self, path_str: str, data: Tuple[Image.Image, Tuple[int, int]]):
        """Add image to cache with LRU eviction."""
        if len(self.cache) >= self.cache_size:
            # Remove least recently used
            oldest_path = self.access_order.pop(0)
            del self.cache[oldest_path]

        self.cache[path_str] = data
        self.access_order.append(path_str)

    def clear_cache(self):
        """Clear image cache."""
        self.cache.clear()
        self.access_order.clear()


class AnnotationWriter:
    """
    Handles writing annotations in various formats (COCO, YOLO, etc.).
    """

    def __init__(self, output_dir: Union[str, Path]):
        """
        Initialize annotation writer.

        Args:
            output_dir: Output directory for annotations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_coco_annotations(self,
                            detections_per_image: List[Tuple[str, List[Dict]]],
                            class_mapping: Dict[int, str],
                            output_file: Optional[str] = None) -> str:
        """
        Save detections in COCO format.

        Args:
            detections_per_image: List of (image_path, detections) tuples
            class_mapping: Mapping from class_id to class_name
            output_file: Output filename (default: annotations.json)

        Returns:
            Path to saved annotation file
        """
        if output_file is None:
            output_file = "annotations.json"

        output_path = self.output_dir / output_file

        # Build COCO structure
        coco_data = {
            "info": {
                "description": "CAMINA Urban Mobility Detection Dataset",
                "version": "2.0",
                "contributor": "CAMINA Team",
                "date_created": ""
            },
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": []
        }

        # Add categories
        for class_id, class_name in class_mapping.items():
            category = {
                "id": class_id,
                "name": class_name,
                "supercategory": "mobility"
            }
            coco_data["categories"].append(category)

        # Process images and annotations
        image_id = 1
        annotation_id = 1

        for image_path, detections in detections_per_image:
            image_path = Path(image_path)

            # Get image dimensions
            try:
                with Image.open(image_path) as img:
                    width, height = img.size
            except Exception as e:
                logger.warning(f"Could not get dimensions for {image_path}: {e}")
                continue

            # Add image info
            image_info = {
                "id": image_id,
                "width": width,
                "height": height,
                "file_name": image_path.name,
                "path": str(image_path)
            }
            coco_data["images"].append(image_info)

            # Add annotations
            for detection in detections:
                # Convert YOLO format to COCO bbox format
                x_center = detection['x_center']
                y_center = detection['y_center']
                box_width = detection['width']
                box_height = detection['height']

                # COCO bbox: [x, y, width, height] (top-left corner)
                x = (x_center - box_width / 2) * width
                y = (y_center - box_height / 2) * height
                bbox_width = box_width * width
                bbox_height = box_height * height

                bbox = [x, y, bbox_width, bbox_height]
                area = bbox_width * bbox_height

                annotation = {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": detection['class_id'],
                    "bbox": bbox,
                    "area": area,
                    "iscrowd": 0,
                    "confidence": detection.get('confidence', 1.0),
                    "source": detection.get('source', 'unknown')
                }

                # Add additional metadata if available
                if 'components' in detection:
                    annotation['components'] = detection['components']

                coco_data["annotations"].append(annotation)
                annotation_id += 1

            image_id += 1

        # Save to file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(coco_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved COCO annotations to: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to save COCO annotations: {e}")
            raise

    def save_yolo_annotations(self,
                            detections_per_image: List[Tuple[str, List[Dict]]],
                            class_mapping: Dict[int, str]) -> List[str]:
        """
        Save detections in YOLO format (one .txt file per image).

        Args:
            detections_per_image: List of (image_path, detections) tuples
            class_mapping: Mapping from class_id to class_name

        Returns:
            List of saved annotation file paths
        """
        saved_files = []

        for image_path, detections in detections_per_image:
            image_path = Path(image_path)
            annotation_path = self.output_dir / f"{image_path.stem}.txt"

            try:
                with open(annotation_path, 'w', encoding='utf-8') as f:
                    for detection in detections:
                        class_id = detection['class_id']
                        x_center = detection['x_center']
                        y_center = detection['y_center']
                        width = detection['width']
                        height = detection['height']

                        # YOLO format: class_id x_center y_center width height
                        line = f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"
                        f.write(line)

                saved_files.append(str(annotation_path))

            except Exception as e:
                logger.error(f"Failed to save YOLO annotation for {image_path}: {e}")

        logger.info(f"Saved {len(saved_files)} YOLO annotation files")
        return saved_files

    def save_summary_ndjson(self,
                          detections_per_image: List[Tuple[str, List[Dict]]],
                          class_mapping: Dict[int, str],
                          output_file: Optional[str] = None) -> str:
        """
        Save detection summary in NDJSON format.

        Args:
            detections_per_image: List of (image_path, detections) tuples
            class_mapping: Mapping from class_id to class_name
            output_file: Output filename (default: summary.ndjson)

        Returns:
            Path to saved summary file
        """
        if output_file is None:
            output_file = "summary.ndjson"

        output_path = self.output_dir / output_file

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for image_path, detections in detections_per_image:
                    image_path = Path(image_path)

                    # Create summary record
                    summary = {
                        "image_path": str(image_path),
                        "image_name": image_path.name,
                        "total_detections": len(detections),
                        "class_counts": {},
                        "confidence_stats": {},
                        "sources": set()
                    }

                    # Calculate statistics
                    for detection in detections:
                        class_id = detection['class_id']
                        class_name = class_mapping.get(class_id, f"unknown_{class_id}")
                        confidence = detection.get('confidence', 0.0)
                        source = detection.get('source', 'unknown')

                        # Count classes
                        if class_name not in summary["class_counts"]:
                            summary["class_counts"][class_name] = 0
                            summary["confidence_stats"][class_name] = []

                        summary["class_counts"][class_name] += 1
                        summary["confidence_stats"][class_name].append(confidence)
                        summary["sources"].add(source)

                    # Calculate confidence statistics
                    for class_name, confidences in summary["confidence_stats"].items():
                        if confidences:
                            summary["confidence_stats"][class_name] = {
                                "mean": float(np.mean(confidences)),
                                "max": float(np.max(confidences)),
                                "min": float(np.min(confidences)),
                                "std": float(np.std(confidences))
                            }

                    # Convert sets to lists for JSON serialization
                    summary["sources"] = list(summary["sources"])

                    # Write as NDJSON
                    f.write(json.dumps(summary, ensure_ascii=False) + '\n')

            logger.info(f"Saved detection summary to: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to save summary NDJSON: {e}")
            raise


class DatasetValidator:
    """
    Validates dataset consistency and quality.
    """

    def __init__(self):
        self.validation_errors = []
        self.validation_warnings = []

    def validate_detections(self,
                          detections_per_image: List[Tuple[str, List[Dict]]],
                          class_mapping: Dict[int, str]) -> Dict[str, Any]:
        """
        Validate detection data for consistency and quality.

        Args:
            detections_per_image: List of (image_path, detections) tuples
            class_mapping: Mapping from class_id to class_name

        Returns:
            Validation report dictionary
        """
        self.validation_errors.clear()
        self.validation_warnings.clear()

        total_images = len(detections_per_image)
        total_detections = sum(len(detections) for _, detections in detections_per_image)

        # Validate each image
        for image_path, detections in detections_per_image:
            self._validate_image_detections(image_path, detections, class_mapping)

        # Generate report
        report = {
            "total_images": total_images,
            "total_detections": total_detections,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "error_count": len(self.validation_errors),
            "warning_count": len(self.validation_warnings),
            "is_valid": len(self.validation_errors) == 0
        }

        if report["error_count"] > 0:
            logger.warning(f"Validation found {report['error_count']} errors")

        if report["warning_count"] > 0:
            logger.info(f"Validation found {report['warning_count']} warnings")

        return report

    def _validate_image_detections(self,
                                 image_path: str,
                                 detections: List[Dict],
                                 class_mapping: Dict[int, str]):
        """Validate detections for a single image."""
        image_path = Path(image_path)

        # Check if image exists
        if not image_path.exists():
            self.validation_errors.append(f"Image not found: {image_path}")
            return

        # Validate each detection
        for i, detection in enumerate(detections):
            self._validate_single_detection(image_path, i, detection, class_mapping)

    def _validate_single_detection(self,
                                 image_path: Path,
                                 detection_idx: int,
                                 detection: Dict,
                                 class_mapping: Dict[int, str]):
        """Validate a single detection."""
        required_fields = ['class_id', 'confidence', 'x_center', 'y_center', 'width', 'height']

        # Check required fields
        for field in required_fields:
            if field not in detection:
                self.validation_errors.append(
                    f"{image_path.name} detection {detection_idx}: Missing field '{field}'"
                )

        # Validate class_id
        class_id = detection.get('class_id')
        if class_id is not None:
            if class_id not in class_mapping:
                self.validation_errors.append(
                    f"{image_path.name} detection {detection_idx}: Unknown class_id {class_id}"
                )

        # Validate coordinates
        for coord_field in ['x_center', 'y_center', 'width', 'height']:
            value = detection.get(coord_field)
            if value is not None:
                if not (0.0 <= value <= 1.0):
                    self.validation_errors.append(
                        f"{image_path.name} detection {detection_idx}: "
                        f"{coord_field} out of range [0,1]: {value}"
                    )

        # Validate confidence
        confidence = detection.get('confidence')
        if confidence is not None:
            if not (0.0 <= confidence <= 1.0):
                self.validation_warnings.append(
                    f"{image_path.name} detection {detection_idx}: "
                    f"Confidence out of range [0,1]: {confidence}"
                )

        # Check for very small bounding boxes
        width = detection.get('width', 0)
        height = detection.get('height', 0)
        if width * height < 0.0001:  # Less than 0.01% of image area
            self.validation_warnings.append(
                f"{image_path.name} detection {detection_idx}: Very small bounding box "
                f"(area: {width * height:.6f})"
            )


def create_output_directories(base_output_dir: Union[str, Path],
                            formats: List[str] = None) -> Dict[str, Path]:
    """
    Create organized output directory structure.

    Args:
        base_output_dir: Base output directory
        formats: List of formats to create directories for

    Returns:
        Dictionary mapping format names to directory paths
    """
    if formats is None:
        formats = ['coco', 'yolo', 'summary', 'visualizations']

    base_path = Path(base_output_dir)
    directories = {}

    for format_name in formats:
        format_dir = base_path / format_name
        format_dir.mkdir(parents=True, exist_ok=True)
        directories[format_name] = format_dir

    # Create additional subdirectories
    if 'visualizations' in directories:
        (directories['visualizations'] / 'detections').mkdir(exist_ok=True)
        (directories['visualizations'] / 'confidence_maps').mkdir(exist_ok=True)

    logger.info(f"Created output directories in: {base_path}")
    return directories