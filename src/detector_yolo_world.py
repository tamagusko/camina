#!/usr/bin/env python3
"""
CAMINA Stage B Detector - YOLO-World for Open Vocabulary Detection

Implements the second stage of the two-stage detection pipeline using YOLO-World
for detecting new classes: e-scooter, SUV, delivery_van.
"""

import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
import numpy as np
import torch
from PIL import Image

from .config import StageConfig

logger = logging.getLogger(__name__)


class YOLOWorldDetector:
    """
    Stage B detector using YOLO-World for open vocabulary detection.

    This detector:
    1. Runs YOLO-World inference with text prompts for new classes
    2. Applies confidence thresholds specific to each class
    3. Returns detections for e-scooter, SUV, and delivery_van classes
    """

    def __init__(self,
                 stage_config: StageConfig,
                 text_prompts: Dict[str, List[str]]):
        """
        Initialize YOLO-World detector.

        Args:
            stage_config: Stage B configuration
            text_prompts: Text prompts for each class
        """
        self.stage_config = stage_config
        self.text_prompts = text_prompts
        self.model = None
        self.device = stage_config.device
        self.model_path = Path(stage_config.model_path)

        # Output class mapping for Stage B
        self.output_class_mapping = {
            'e-scooter': 6,
            'SUV': 7,
            'delivery_van': 8
        }

        # Confidence thresholds per class
        self.confidence_thresholds = stage_config.confidence_thresholds or {}

        # Prepare text prompts for model
        self.class_names = list(self.output_class_mapping.keys())
        self.prepared_prompts = self._prepare_prompts()

        logger.info(f"Initialized YOLO-World detector with model: {self.model_path}")
        logger.info(f"Target classes: {self.class_names}")

    def initialize(self) -> bool:
        """
        Initialize the YOLO-World model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Import YOLO here to avoid dependency issues if not available
            from ultralytics import YOLO

            if not self.model_path.exists():
                logger.warning(f"Model file not found: {self.model_path}, will download")

            self.model = YOLO(str(self.model_path))

            # Set custom classes with text prompts
            if hasattr(self.model.model, 'set_classes'):
                self.model.model.set_classes(self.prepared_prompts)
            else:
                logger.warning("YOLO-World set_classes method not available, using default prompts")

            # Set device
            if torch.cuda.is_available() and 'cuda' in self.device:
                self.model.to(self.device)
                logger.info(f"YOLO-World model loaded on device: {self.device}")
            else:
                logger.warning(f"CUDA not available, using CPU")
                self.device = 'cpu'

            return True

        except ImportError as e:
            logger.error(f"Failed to import ultralytics: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize YOLO-World model: {e}")
            return False

    def is_initialized(self) -> bool:
        """Check if model is properly initialized."""
        return self.model is not None

    def detect(self,
               image: Union[np.ndarray, Image.Image, str, Path],
               confidence_threshold: Optional[float] = None) -> List[Dict]:
        """
        Run Stage B detection with YOLO-World.

        Args:
            image: Input image (numpy array, PIL Image, or path)
            confidence_threshold: Override default confidence threshold

        Returns:
            List of detections in standardized format
        """
        if not self.is_initialized():
            logger.error("Model not initialized. Call initialize() first.")
            return []

        confidence = confidence_threshold or self.stage_config.confidence_threshold

        try:
            # Run YOLO-World inference
            results = self.model(image, conf=confidence, verbose=False)

            if not results or len(results) == 0:
                return []

            result = results[0]  # Single image
            image_shape = result.orig_shape  # (height, width)
            img_height, img_width = image_shape

            # Extract detections
            detections = self._extract_detections(result, img_width, img_height)

            # Apply class-specific confidence filtering
            filtered_detections = self._apply_confidence_filtering(detections)

            logger.debug(
                f"Stage B detection: {len(detections)} raw detections -> "
                f"{len(filtered_detections)} filtered detections"
            )

            return filtered_detections

        except Exception as e:
            logger.error(f"Error during YOLO-World detection: {e}")
            return []

    def _prepare_prompts(self) -> List[str]:
        """
        Prepare text prompts for YOLO-World.

        Returns:
            List of formatted prompts for each class
        """
        prepared_prompts = []

        for class_name in self.class_names:
            if class_name in self.text_prompts:
                # Use the first prompt as the primary class name
                prompts = self.text_prompts[class_name]
                if prompts:
                    prepared_prompts.append(prompts[0])
                else:
                    prepared_prompts.append(class_name)
            else:
                prepared_prompts.append(class_name)

        logger.debug(f"Prepared prompts: {prepared_prompts}")
        return prepared_prompts

    def _extract_detections(self, result, img_width: int, img_height: int) -> List[Dict]:
        """
        Extract detections from YOLO-World result.

        Args:
            result: YOLO-World detection result
            img_width: Image width
            img_height: Image height

        Returns:
            List of detections in standardized format
        """
        detections = []

        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy()  # xyxy format
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)

        for i, (box, confidence, class_id) in enumerate(zip(boxes, confidences, class_ids)):
            # Map class_id to class name
            if class_id < len(self.class_names):
                class_name = self.class_names[class_id]
            else:
                logger.warning(f"Unknown class_id: {class_id}, skipping detection")
                continue

            # Skip if not in our target classes
            if class_name not in self.output_class_mapping:
                continue

            # Convert xyxy to YOLO format (normalized)
            x1, y1, x2, y2 = box
            x_center = ((x1 + x2) / 2) / img_width
            y_center = ((y1 + y2) / 2) / img_height
            width = (x2 - x1) / img_width
            height = (y2 - y1) / img_height

            detection = {
                'class_id': self.output_class_mapping[class_name],
                'class_name': class_name,
                'confidence': float(confidence),
                'x_center': float(x_center),
                'y_center': float(y_center),
                'width': float(width),
                'height': float(height),
                'source': f'yolo_world_{class_name}',
                'bbox_xyxy': [float(x1), float(y1), float(x2), float(y2)],
                'text_prompts_used': self.text_prompts.get(class_name, [class_name])
            }

            detections.append(detection)

        return detections

    def _apply_confidence_filtering(self, detections: List[Dict]) -> List[Dict]:
        """
        Apply class-specific confidence thresholds.

        Args:
            detections: List of raw detections

        Returns:
            List of filtered detections
        """
        filtered_detections = []

        for detection in detections:
            class_name = detection['class_name']
            confidence = detection['confidence']

            # Get class-specific threshold or use default
            threshold = self.confidence_thresholds.get(
                class_name, self.stage_config.confidence_threshold
            )

            if confidence >= threshold:
                filtered_detections.append(detection)
            else:
                logger.debug(
                    f"Filtered {class_name} detection with confidence "
                    f"{confidence:.3f} < {threshold:.3f}"
                )

        return filtered_detections

    def predict_batch(self,
                     images: List[Union[np.ndarray, Image.Image, str, Path]],
                     confidence_threshold: Optional[float] = None) -> List[List[Dict]]:
        """
        Run batch prediction on multiple images.

        Args:
            images: List of input images
            confidence_threshold: Override default confidence threshold

        Returns:
            List of detection lists, one per image
        """
        if not self.is_initialized():
            logger.error("Model not initialized. Call initialize() first.")
            return [[] for _ in images]

        confidence = confidence_threshold or self.stage_config.confidence_threshold

        try:
            # Run batch inference
            results = self.model(images, conf=confidence, verbose=False)

            batch_detections = []
            for result in results:
                if result.orig_shape is None:
                    batch_detections.append([])
                    continue

                img_height, img_width = result.orig_shape

                # Extract and filter detections for this image
                raw_detections = self._extract_detections(result, img_width, img_height)
                filtered_detections = self._apply_confidence_filtering(raw_detections)

                batch_detections.append(filtered_detections)

            return batch_detections

        except Exception as e:
            logger.error(f"Error during batch YOLO-World detection: {e}")
            return [[] for _ in images]

    def get_supported_classes(self) -> Dict[int, str]:
        """Get mapping of supported output class IDs to names."""
        return {
            6: 'e-scooter',
            7: 'SUV',
            8: 'delivery_van'
        }

    def update_text_prompts(self, new_prompts: Dict[str, List[str]]) -> bool:
        """
        Update text prompts for classes.

        Args:
            new_prompts: New text prompts dictionary

        Returns:
            True if update successful
        """
        try:
            self.text_prompts.update(new_prompts)
            self.prepared_prompts = self._prepare_prompts()

            # Update model with new prompts if available
            if self.model and hasattr(self.model.model, 'set_classes'):
                self.model.model.set_classes(self.prepared_prompts)
                logger.info("Updated YOLO-World text prompts")

            return True

        except Exception as e:
            logger.error(f"Failed to update text prompts: {e}")
            return False

    def get_class_statistics(self, detections: List[Dict]) -> Dict[str, Dict[str, float]]:
        """
        Get detection statistics per class.

        Args:
            detections: List of detections

        Returns:
            Dictionary with statistics per class
        """
        stats = {}

        for class_name in self.class_names:
            class_detections = [d for d in detections if d['class_name'] == class_name]

            if class_detections:
                confidences = [d['confidence'] for d in class_detections]
                stats[class_name] = {
                    'count': len(class_detections),
                    'mean_confidence': np.mean(confidences),
                    'max_confidence': np.max(confidences),
                    'min_confidence': np.min(confidences)
                }
            else:
                stats[class_name] = {
                    'count': 0,
                    'mean_confidence': 0.0,
                    'max_confidence': 0.0,
                    'min_confidence': 0.0
                }

        return stats