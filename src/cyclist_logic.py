#!/usr/bin/env python3
"""
CAMINA Cyclist Detection Logic

Implements the rule-based cyclist detection algorithm that creates cyclist
detections from person and bicycle detection pairs using spatial overlap analysis.

This preserves the working logic from the original dataset_creator.py.
"""

import logging
from typing import List, Dict, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class CyclistDetector:
    """
    Rule-based cyclist detection using person + bicycle spatial analysis.

    This class implements the proven cyclist detection algorithm that:
    1. Finds overlapping person and bicycle detections
    2. Validates geometric constraints (bicycle positioned lower than person)
    3. Creates union bounding boxes for valid pairs
    4. Combines confidences using geometric mean with IoU factor
    """

    def __init__(self,
                 iou_threshold: float = 0.20,
                 lower_margin_px: int = 5,
                 spatial_margin_px: int = 5,
                 min_bbox_area: float = 0.01,
                 confidence_threshold: float = 0.1):
        """
        Initialize cyclist detector with configuration parameters.

        Args:
            iou_threshold: Minimum IoU for person-bicycle pairing
            lower_margin_px: Minimum pixels bicycle must be below person
            spatial_margin_px: Spatial margin for geometric validation
            min_bbox_area: Minimum bounding box area (normalized)
            confidence_threshold: Minimum confidence for input detections
        """
        self.iou_threshold = iou_threshold
        self.lower_margin_px = lower_margin_px
        self.spatial_margin_px = spatial_margin_px
        self.min_bbox_area = min_bbox_area
        self.confidence_threshold = confidence_threshold

        logger.info(f"Initialized CyclistDetector with IoU threshold: {iou_threshold}")

    def detect_cyclists(self,
                       person_detections: List[Dict],
                       bicycle_detections: List[Dict],
                       img_width: int,
                       img_height: int) -> Tuple[List[Dict], List[int]]:
        """
        Create cyclist detections from person and bicycle detection pairs.

        Args:
            person_detections: List of person detections in YOLO format
            bicycle_detections: List of bicycle detections in YOLO format
            img_width: Image width for coordinate conversion
            img_height: Image height for coordinate conversion

        Returns:
            Tuple of:
                - List of cyclist detections created from valid pairs
                - List of person indices that were not paired
        """
        if not person_detections or not bicycle_detections:
            return [], list(range(len(person_detections)))

        # Filter detections by confidence
        filtered_persons = [
            (i, det) for i, det in enumerate(person_detections)
            if det.get('confidence', 0.0) >= self.confidence_threshold
        ]

        filtered_bicycles = [
            det for det in bicycle_detections
            if det.get('confidence', 0.0) >= self.confidence_threshold
        ]

        if not filtered_persons or not filtered_bicycles:
            return [], list(range(len(person_detections)))

        # Convert to xyxy format for IoU calculation
        person_boxes_xyxy = []
        person_indices = []

        for orig_idx, person in filtered_persons:
            xyxy = self._yolo_to_xyxy(person, img_width, img_height)
            if self._is_valid_bbox(xyxy, img_width, img_height):
                person_boxes_xyxy.append(xyxy)
                person_indices.append(orig_idx)

        bicycle_boxes_xyxy = []
        for bicycle in filtered_bicycles:
            xyxy = self._yolo_to_xyxy(bicycle, img_width, img_height)
            if self._is_valid_bbox(xyxy, img_width, img_height):
                bicycle_boxes_xyxy.append(xyxy)

        if not person_boxes_xyxy or not bicycle_boxes_xyxy:
            return [], list(range(len(person_detections)))

        # Perform greedy pairing algorithm
        cyclist_detections, matched_person_indices = self._pair_person_bicycle(
            filtered_persons, filtered_bicycles, person_boxes_xyxy,
            bicycle_boxes_xyxy, person_indices, img_width, img_height
        )

        # Get unmatched person indices
        unmatched_person_indices = [
            i for i in range(len(person_detections))
            if i not in matched_person_indices
        ]

        logger.debug(
            f"Cyclist pairing: {len(person_detections)} persons, "
            f"{len(bicycle_detections)} bicycles -> {len(cyclist_detections)} cyclists, "
            f"{len(unmatched_person_indices)} unmatched persons"
        )

        return cyclist_detections, unmatched_person_indices

    def _pair_person_bicycle(self,
                            filtered_persons: List[Tuple[int, Dict]],
                            filtered_bicycles: List[Dict],
                            person_boxes_xyxy: List[List[float]],
                            bicycle_boxes_xyxy: List[List[float]],
                            person_indices: List[int],
                            img_width: int,
                            img_height: int) -> Tuple[List[Dict], List[int]]:
        """
        Perform greedy pairing of person and bicycle detections.

        This implements the exact algorithm from the working dataset_creator.py.
        """
        used_bicycles = set()
        cyclist_detections = []
        matched_person_indices = []

        for person_idx, (orig_person_idx, person_det) in enumerate(filtered_persons):
            if person_idx >= len(person_boxes_xyxy):
                continue

            person_box = person_boxes_xyxy[person_idx]
            best_match = None
            person_bottom_y = self._get_bottom_y(person_box)

            for bicycle_idx, bicycle_box in enumerate(bicycle_boxes_xyxy):
                if bicycle_idx in used_bicycles:
                    continue

                # Check geometric constraint: bicycle must be positioned lower than person
                bicycle_bottom_y = self._get_bottom_y(bicycle_box)
                if bicycle_bottom_y < person_bottom_y + self.lower_margin_px:
                    continue

                # Calculate IoU
                iou_score = self._calculate_iou_xyxy(person_box, bicycle_box)
                if iou_score >= self.iou_threshold:
                    if best_match is None or iou_score > best_match['score']:
                        best_match = {
                            'person_idx': person_idx,
                            'bicycle_idx': bicycle_idx,
                            'score': iou_score,
                            'union_box': self._compute_union_box(person_box, bicycle_box)
                        }

            if best_match is not None:
                # Create cyclist detection from union box
                union_box = best_match['union_box']
                bicycle_det = filtered_bicycles[best_match['bicycle_idx']]

                cyclist_det = self._create_cyclist_detection(
                    person_det, bicycle_det, union_box,
                    best_match['score'], img_width, img_height
                )

                cyclist_detections.append(cyclist_det)
                matched_person_indices.append(orig_person_idx)
                used_bicycles.add(best_match['bicycle_idx'])

        return cyclist_detections, matched_person_indices

    def _yolo_to_xyxy(self, detection: Dict, img_width: int, img_height: int) -> List[float]:
        """Convert YOLO format (x_center, y_center, width, height) to xyxy format."""
        x_center = detection['x_center']
        y_center = detection['y_center']
        width = detection['width']
        height = detection['height']

        x1 = (x_center - width / 2) * img_width
        y1 = (y_center - height / 2) * img_height
        x2 = (x_center + width / 2) * img_width
        y2 = (y_center + height / 2) * img_height

        return [x1, y1, x2, y2]

    def _xyxy_to_yolo(self, xyxy: List[float], img_width: int, img_height: int) -> Tuple[float, float, float, float]:
        """Convert xyxy format to YOLO format (normalized)."""
        x1, y1, x2, y2 = xyxy

        x_center = ((x1 + x2) / 2) / img_width
        y_center = ((y1 + y2) / 2) / img_height
        width = (x2 - x1) / img_width
        height = (y2 - y1) / img_height

        return x_center, y_center, width, height

    def _is_valid_bbox(self, xyxy: List[float], img_width: int, img_height: int) -> bool:
        """Validate bounding box dimensions and area."""
        x1, y1, x2, y2 = xyxy

        # Check bounds
        if x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
            return False

        # Check minimum area
        width = x2 - x1
        height = y2 - y1
        area = (width * height) / (img_width * img_height)

        return area >= self.min_bbox_area and width > 0 and height > 0

    def _get_bottom_y(self, xyxy: List[float]) -> float:
        """Get bottom y coordinate of bounding box."""
        return xyxy[3]

    def _calculate_iou_xyxy(self, box1: List[float], box2: List[float]) -> float:
        """
        Calculate Intersection over Union (IoU) for two bounding boxes in xyxy format.

        Args:
            box1: First bounding box [x1, y1, x2, y2]
            box2: Second bounding box [x1, y1, x2, y2]

        Returns:
            IoU score between 0.0 and 1.0
        """
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        # Calculate intersection area
        x1_int = max(x1_1, x1_2)
        y1_int = max(y1_1, y1_2)
        x2_int = min(x2_1, x2_2)
        y2_int = min(y2_1, y2_2)

        if x2_int <= x1_int or y2_int <= y1_int:
            return 0.0

        intersection_area = (x2_int - x1_int) * (y2_int - y1_int)

        # Calculate union area
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - intersection_area

        if union_area <= 0:
            return 0.0

        return intersection_area / union_area

    def _compute_union_box(self, box1: List[float], box2: List[float]) -> List[float]:
        """Compute union bounding box of two boxes."""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        x1_union = min(x1_1, x1_2)
        y1_union = min(y1_1, y1_2)
        x2_union = max(x2_1, x2_2)
        y2_union = max(y2_1, y2_2)

        return [x1_union, y1_union, x2_union, y2_union]

    def _create_cyclist_detection(self,
                                 person_det: Dict,
                                 bicycle_det: Dict,
                                 union_box: List[float],
                                 iou_score: float,
                                 img_width: int,
                                 img_height: int) -> Dict:
        """Create cyclist detection from person and bicycle pair."""
        # Convert union box back to YOLO format
        x_center, y_center, width, height = self._xyxy_to_yolo(
            union_box, img_width, img_height
        )

        # Combine confidences using geometric mean with IoU factor
        person_conf = person_det['confidence']
        bicycle_conf = bicycle_det['confidence']
        combined_conf = (person_conf * bicycle_conf * iou_score) ** (1/3)

        return {
            'class_id': 1,  # cyclist class ID
            'class_name': 'cyclist',
            'confidence': float(combined_conf),
            'x_center': float(x_center),
            'y_center': float(y_center),
            'width': float(width),
            'height': float(height),
            'source': 'cyclist_logic',
            'components': {
                'person_confidence': float(person_conf),
                'bicycle_confidence': float(bicycle_conf),
                'iou_score': float(iou_score)
            }
        }

    def suppress_cyclists_near_escooters(self,
                                       cyclist_detections: List[Dict],
                                       escooter_detections: List[Dict],
                                       img_width: int,
                                       img_height: int,
                                       suppress_iou: float = 0.35) -> List[Dict]:
        """
        Suppress cyclist detections that significantly overlap with e-scooter detections.

        This prevents misclassification when the cyclist logic incorrectly pairs
        a person on an e-scooter with a nearby bicycle.
        """
        if not cyclist_detections or not escooter_detections:
            return cyclist_detections

        # Convert detections to xyxy format
        cyclist_boxes = [
            self._yolo_to_xyxy(det, img_width, img_height)
            for det in cyclist_detections
        ]

        escooter_boxes = [
            self._yolo_to_xyxy(det, img_width, img_height)
            for det in escooter_detections
        ]

        # Find cyclists to suppress
        suppressed_indices = set()

        for cyclist_idx, cyclist_box in enumerate(cyclist_boxes):
            for escooter_box in escooter_boxes:
                iou = self._calculate_iou_xyxy(cyclist_box, escooter_box)
                if iou >= suppress_iou:
                    suppressed_indices.add(cyclist_idx)
                    logger.debug(
                        f"Suppressing cyclist {cyclist_idx} due to overlap "
                        f"with e-scooter (IoU: {iou:.3f})"
                    )
                    break

        # Return non-suppressed cyclist detections
        filtered_cyclists = [
            det for idx, det in enumerate(cyclist_detections)
            if idx not in suppressed_indices
        ]

        if suppressed_indices:
            logger.info(
                f"Suppressed {len(suppressed_indices)} cyclist detections "
                f"due to e-scooter overlap"
            )

        return filtered_cyclists