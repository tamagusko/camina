#!/usr/bin/env python3
"""
CAMINA Stage A Detector - YOLO11n with Cyclist Logic

Implements the first stage of the two-stage detection pipeline using YOLO11n
for COCO classes and applying cyclist detection logic.
"""

import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
import numpy as np
import torch
from PIL import Image

from .cyclist_logic import CyclistDetector
from .config import StageConfig, CyclistDetectionConfig

logger = logging.getLogger(__name__)


class YOLO11nDetector:
    """
    Stage A detector using YOLO11n for COCO classes with cyclist logic.

    This detector:
    1. Runs YOLO11n inference for COCO classes (person, bicycle, car, motorcycle, bus, truck)
    2. Applies cyclist detection logic to create cyclist detections from person+bicycle pairs
    3. Returns consolidated detections for Stage A classes
    """

    def __init__(self,
                 stage_config: StageConfig,
                 cyclist_config: CyclistDetectionConfig):
        """
        Initialize YOLO11n detector with cyclist logic.

        Args:
            stage_config: Stage A configuration
            cyclist_config: Cyclist detection configuration
        """
        self.stage_config = stage_config
        self.cyclist_config = cyclist_config
        self.model = None
        self.device = stage_config.device
        self.model_path = Path(stage_config.model_path)

        # Initialize cyclist detector
        self.cyclist_detector = CyclistDetector(
            iou_threshold=cyclist_config.iou_threshold,
            lower_margin_px=cyclist_config.lower_margin_px,
            spatial_margin_px=cyclist_config.spatial_margin_px,
            min_bbox_area=cyclist_config.min_bbox_area,
            confidence_threshold=cyclist_config.confidence_threshold
        )

        # COCO class mapping for YOLO11n
        self.coco_class_mapping = {
            0: 'person',        # COCO person -> person
            1: 'bicycle',       # COCO bicycle -> bicycle (used for cyclist logic)
            2: 'car',           # COCO car -> car
            3: 'motorcycle',    # COCO motorcycle -> motorcycle
            5: 'bus',           # COCO bus -> bus
            7: 'truck'          # COCO truck -> truck
        }

        # Target class mapping for output
        self.output_class_mapping = {
            'person': 0,
            'cyclist': 1,
            'car': 2,
            'motorcycle': 3,
            'bus': 4,
            'truck': 5
        }

        logger.info(f"Initialized YOLO11n detector with model: {self.model_path}")

    def initialize(self) -> bool:
        """
        Initialize the YOLO11n model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Import YOLO here to avoid dependency issues if not available
            from ultralytics import YOLO

            if not self.model_path.exists():
                logger.warning(f"Model file not found: {self.model_path}, will download")

            self.model = YOLO(str(self.model_path))

            # Set device
            if torch.cuda.is_available() and 'cuda' in self.device:
                self.model.to(self.device)
                logger.info(f"YOLO11n model loaded on device: {self.device}")
            else:
                logger.warning(f"CUDA not available, using CPU")
                self.device = 'cpu'

            return True

        except ImportError as e:
            logger.error(f"Failed to import ultralytics: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize YOLO11n model: {e}")
            return False

    def is_initialized(self) -> bool:
        """Check if model is properly initialized."""
        return self.model is not None

    def detect(self,
               image: Union[np.ndarray, Image.Image, str, Path],
               confidence_threshold: Optional[float] = None) -> List[Dict]:
        """
        Run Stage A detection with cyclist logic.

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
            # Run YOLO11n inference
            results = self.model(image, conf=confidence, verbose=False)

            if not results or len(results) == 0:
                return []

            result = results[0]  # Single image
            image_shape = result.orig_shape  # (height, width)
            img_height, img_width = image_shape

            # Extract raw detections
            raw_detections = self._extract_raw_detections(result, img_width, img_height)

            # Separate person and bicycle detections for cyclist logic
            person_detections = [det for det in raw_detections if det['class_name'] == 'person']
            bicycle_detections = [det for det in raw_detections if det['class_name'] == 'bicycle']
            other_detections = [det for det in raw_detections
                              if det['class_name'] not in ['person', 'bicycle']]

            # Apply cyclist detection logic if enabled
            if self.cyclist_config.enabled:
                cyclist_detections, unmatched_person_indices = self.cyclist_detector.detect_cyclists(
                    person_detections, bicycle_detections, img_width, img_height
                )

                # Keep unmatched persons as person detections
                unmatched_persons = [
                    person_detections[i] for i in unmatched_person_indices
                    if i < len(person_detections)
                ]
            else:
                cyclist_detections = []
                unmatched_persons = person_detections

            # Combine all Stage A detections
            stage_a_detections = []

            # Add unmatched persons
            for person_det in unmatched_persons:
                person_det['class_id'] = self.output_class_mapping['person']
                person_det['source'] = 'yolo11n_person'
                stage_a_detections.append(person_det)

            # Add cyclist detections
            for cyclist_det in cyclist_detections:
                cyclist_det['class_id'] = self.output_class_mapping['cyclist']
                cyclist_det['source'] = 'yolo11n_cyclist'
                stage_a_detections.append(cyclist_det)

            # Add other detections (car, motorcycle, bus, truck)
            for other_det in other_detections:
                if other_det['class_name'] in self.output_class_mapping:
                    other_det['class_id'] = self.output_class_mapping[other_det['class_name']]
                    other_det['source'] = f"yolo11n_{other_det['class_name']}"
                    stage_a_detections.append(other_det)

            logger.debug(
                f"Stage A detection: {len(person_detections)} persons, "
                f"{len(bicycle_detections)} bicycles -> "
                f"{len(cyclist_detections)} cyclists, "
                f"{len(unmatched_persons)} unmatched persons, "
                f"{len(other_detections)} other objects"
            )

            return stage_a_detections

        except Exception as e:
            logger.error(f"Error during YOLO11n detection: {e}")
            return []

    def _extract_raw_detections(self, result, img_width: int, img_height: int) -> List[Dict]:
        """
        Extract raw detections from YOLO result.

        Args:
            result: YOLO detection result
            img_width: Image width
            img_height: Image height

        Returns:
            List of raw detections in YOLO format
        """
        detections = []

        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy()  # xyxy format
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)

        for i, (box, confidence, class_id) in enumerate(zip(boxes, confidences, class_ids)):
            # Filter by COCO classes we care about
            if class_id not in self.coco_class_mapping:
                continue

            class_name = self.coco_class_mapping[class_id]

            # Convert xyxy to YOLO format (normalized)
            x1, y1, x2, y2 = box
            x_center = ((x1 + x2) / 2) / img_width
            y_center = ((y1 + y2) / 2) / img_height
            width = (x2 - x1) / img_width
            height = (y2 - y1) / img_height

            detection = {
                'class_id': class_id,  # Original COCO class ID
                'class_name': class_name,
                'confidence': float(confidence),
                'x_center': float(x_center),
                'y_center': float(y_center),
                'width': float(width),
                'height': float(height),
                'source': 'yolo11n_raw',
                'bbox_xyxy': [float(x1), float(y1), float(x2), float(y2)]
            }

            detections.append(detection)

        return detections

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

                # Extract and process detections for this image
                raw_detections = self._extract_raw_detections(result, img_width, img_height)

                # Process through cyclist logic
                person_detections = [det for det in raw_detections if det['class_name'] == 'person']
                bicycle_detections = [det for det in raw_detections if det['class_name'] == 'bicycle']
                other_detections = [det for det in raw_detections
                                  if det['class_name'] not in ['person', 'bicycle']]

                if self.cyclist_config.enabled:
                    cyclist_detections, unmatched_person_indices = self.cyclist_detector.detect_cyclists(
                        person_detections, bicycle_detections, img_width, img_height
                    )

                    unmatched_persons = [
                        person_detections[i] for i in unmatched_person_indices
                        if i < len(person_detections)
                    ]
                else:
                    cyclist_detections = []
                    unmatched_persons = person_detections

                # Combine detections
                image_detections = []

                # Add unmatched persons
                for person_det in unmatched_persons:
                    person_det['class_id'] = self.output_class_mapping['person']
                    person_det['source'] = 'yolo11n_person'
                    image_detections.append(person_det)

                # Add cyclists
                for cyclist_det in cyclist_detections:
                    cyclist_det['class_id'] = self.output_class_mapping['cyclist']
                    cyclist_det['source'] = 'yolo11n_cyclist'
                    image_detections.append(cyclist_det)

                # Add other objects
                for other_det in other_detections:
                    if other_det['class_name'] in self.output_class_mapping:
                        other_det['class_id'] = self.output_class_mapping[other_det['class_name']]
                        other_det['source'] = f"yolo11n_{other_det['class_name']}"
                        image_detections.append(other_det)

                batch_detections.append(image_detections)

            return batch_detections

        except Exception as e:
            logger.error(f"Error during batch YOLO11n detection: {e}")
            return [[] for _ in images]

    def get_supported_classes(self) -> Dict[int, str]:
        """Get mapping of supported output class IDs to names."""
        return {
            0: 'person',
            1: 'cyclist',
            2: 'car',
            3: 'motorcycle',
            4: 'bus',
            5: 'truck'
        }