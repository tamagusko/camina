#!/usr/bin/env python3
"""
CAMINA E-scooter Spatial Association Logic

Implements spatial association algorithm that creates combined e-scooter
detections from person and e-scooter detection pairs using spatial overlap analysis.

Similar to cyclist logic: person + bicycle → cyclist
This creates: person + e-scooter → combined e-scooter bbox
"""

import logging
from typing import List, Dict, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EscooterSpatialAssociator:
    """
    Spatial association for e-scooter detections using person + e-scooter analysis.

    This class implements spatial association that:
    1. Finds overlapping person and e-scooter detections
    2. Validates geometric constraints (e-scooter positioned near person feet)
    3. Creates union bounding boxes for valid pairs
    4. Combines confidences using geometric mean with IoU factor
    5. Returns combined e-scooter bbox that includes both person and e-scooter
    """

    def __init__(self,
                 iou_threshold: float = 0.15,
                 vertical_margin_px: int = 10,
                 spatial_margin_px: int = 5,
                 min_bbox_area: float = 0.01,
                 confidence_threshold: float = 0.1):
        """
        Initialize e-scooter spatial associator with configuration parameters.

        Args:
            iou_threshold: Minimum IoU for person-escooter pairing (lower than cyclist)
            vertical_margin_px: Vertical margin for e-scooter positioning relative to person
            spatial_margin_px: Spatial margin for geometric validation
            min_bbox_area: Minimum bounding box area (normalized)
            confidence_threshold: Minimum confidence for input detections
        """
        self.iou_threshold = iou_threshold
        self.vertical_margin_px = vertical_margin_px
        self.spatial_margin_px = spatial_margin_px
        self.min_bbox_area = min_bbox_area
        self.confidence_threshold = confidence_threshold

        logger.info(f"Initialized EscooterSpatialAssociator with IoU threshold: {iou_threshold}")

    def associate_person_escooter(self,
                                 person_detections: List[Dict],
                                 escooter_detections: List[Dict],
                                 img_width: int,
                                 img_height: int) -> Tuple[List[Dict], List[int], List[int]]:
        """
        Create combined e-scooter detections from person and e-scooter detection pairs.

        Args:
            person_detections: List of person detections in YOLO format
            escooter_detections: List of e-scooter detections in YOLO format
            img_width: Image width for coordinate conversion
            img_height: Image height for coordinate conversion

        Returns:
            Tuple of:
                - List of combined e-scooter detections created from valid pairs
                - List of person indices that were not paired
                - List of e-scooter indices that were not paired
        """
        if not person_detections or not escooter_detections:
            return [], list(range(len(person_detections))), list(range(len(escooter_detections)))

        # Filter detections by confidence
        filtered_persons = [
            (i, det) for i, det in enumerate(person_detections)
            if det.get('confidence', 0.0) >= self.confidence_threshold
        ]

        filtered_escooters = [
            (i, det) for i, det in enumerate(escooter_detections)
            if det.get('confidence', 0.0) >= self.confidence_threshold
        ]

        if not filtered_persons or not filtered_escooters:
            return [], list(range(len(person_detections))), list(range(len(escooter_detections)))

        # Convert to xyxy format for IoU calculation
        person_boxes_xyxy = []
        person_indices = []

        for orig_idx, person in filtered_persons:
            xyxy = self._yolo_to_xyxy(person, img_width, img_height)
            if self._is_valid_bbox(xyxy, img_width, img_height):
                person_boxes_xyxy.append(xyxy)
                person_indices.append(orig_idx)

        escooter_boxes_xyxy = []
        escooter_indices = []
        for orig_idx, escooter in filtered_escooters:
            xyxy = self._yolo_to_xyxy(escooter, img_width, img_height)
            if self._is_valid_bbox(xyxy, img_width, img_height):
                escooter_boxes_xyxy.append(xyxy)
                escooter_indices.append(orig_idx)

        if not person_boxes_xyxy or not escooter_boxes_xyxy:
            return [], list(range(len(person_detections))), list(range(len(escooter_detections)))

        # Perform greedy pairing algorithm
        combined_detections, matched_person_indices, matched_escooter_indices = self._pair_person_escooter(
            filtered_persons, filtered_escooters, person_boxes_xyxy,
            escooter_boxes_xyxy, person_indices, escooter_indices, img_width, img_height
        )

        # Get unmatched indices
        unmatched_person_indices = [
            i for i in range(len(person_detections))
            if i not in matched_person_indices
        ]

        unmatched_escooter_indices = [
            i for i in range(len(escooter_detections))
            if i not in matched_escooter_indices
        ]

        logger.debug(
            f"E-scooter association: {len(person_detections)} persons, "
            f"{len(escooter_detections)} e-scooters -> {len(combined_detections)} combined, "
            f"{len(unmatched_person_indices)} unmatched persons, "
            f"{len(unmatched_escooter_indices)} unmatched e-scooters"
        )

        return combined_detections, unmatched_person_indices, unmatched_escooter_indices

    def _pair_person_escooter(self,
                             filtered_persons: List[Tuple[int, Dict]],
                             filtered_escooters: List[Tuple[int, Dict]],
                             person_boxes_xyxy: List[List[float]],
                             escooter_boxes_xyxy: List[List[float]],
                             person_indices: List[int],
                             escooter_indices: List[int],
                             img_width: int,
                             img_height: int) -> Tuple[List[Dict], List[int], List[int]]:
        """
        Perform greedy pairing of person and e-scooter detections.
        """
        used_escooters = set()
        combined_detections = []
        matched_person_indices = []
        matched_escooter_indices = []

        for person_idx, (orig_person_idx, person_det) in enumerate(filtered_persons):
            if person_idx >= len(person_boxes_xyxy):
                continue

            person_box = person_boxes_xyxy[person_idx]
            best_match = None

            for escooter_idx, escooter_box in enumerate(escooter_boxes_xyxy):
                if escooter_idx in used_escooters:
                    continue

                # Check spatial proximity (e-scooters can be at various positions relative to person)
                if not self._is_spatially_compatible(person_box, escooter_box):
                    continue

                # Calculate IoU
                iou_score = self._calculate_iou_xyxy(person_box, escooter_box)
                if iou_score >= self.iou_threshold:
                    if best_match is None or iou_score > best_match['score']:
                        best_match = {
                            'person_idx': person_idx,
                            'escooter_idx': escooter_idx,
                            'score': iou_score,
                            'union_box': self._compute_union_box(person_box, escooter_box)
                        }

            if best_match is not None:
                # Create combined e-scooter detection from union box
                union_box = best_match['union_box']
                escooter_det = filtered_escooters[best_match['escooter_idx']][1]
                orig_escooter_idx = escooter_indices[best_match['escooter_idx']]

                combined_det = self._create_combined_escooter_detection(
                    person_det, escooter_det, union_box,
                    best_match['score'], img_width, img_height
                )

                combined_detections.append(combined_det)
                matched_person_indices.append(orig_person_idx)
                matched_escooter_indices.append(orig_escooter_idx)
                used_escooters.add(best_match['escooter_idx'])

        return combined_detections, matched_person_indices, matched_escooter_indices

    def _is_spatially_compatible(self, person_box: List[float], escooter_box: List[float]) -> bool:
        """
        Check if person and e-scooter are spatially compatible.
        E-scooters can be positioned at various angles relative to the person.
        """
        person_x1, person_y1, person_x2, person_y2 = person_box
        escooter_x1, escooter_y1, escooter_x2, escooter_y2 = escooter_box

        # Check for reasonable spatial overlap or proximity
        person_center_x = (person_x1 + person_x2) / 2
        person_center_y = (person_y1 + person_y2) / 2
        escooter_center_x = (escooter_x1 + escooter_x2) / 2
        escooter_center_y = (escooter_y1 + escooter_y2) / 2

        # Allow more flexible positioning for e-scooters
        horizontal_distance = abs(person_center_x - escooter_center_x)
        vertical_distance = abs(person_center_y - escooter_center_y)

        person_width = person_x2 - person_x1
        person_height = person_y2 - person_y1

        # E-scooter should be within reasonable distance of person
        max_horizontal_distance = person_width * 1.5
        max_vertical_distance = person_height * 1.2

        return (horizontal_distance <= max_horizontal_distance and
                vertical_distance <= max_vertical_distance)

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

    def _is_valid_bbox(self, xyxy: List[float], img_width: int, img_height: int) -> bool:
        """Validate bounding box coordinates and minimum area."""
        x1, y1, x2, y2 = xyxy

        if x1 >= x2 or y1 >= y2:
            return False

        if x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
            return False

        area = (x2 - x1) * (y2 - y1)
        normalized_area = area / (img_width * img_height)

        return normalized_area >= self.min_bbox_area

    def _calculate_iou_xyxy(self, box1: List[float], box2: List[float]) -> float:
        """Calculate Intersection over Union (IoU) for two boxes in xyxy format."""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        # Calculate intersection
        x1_inter = max(x1_1, x1_2)
        y1_inter = max(y1_1, y1_2)
        x2_inter = min(x2_1, x2_2)
        y2_inter = min(y2_1, y2_2)

        if x2_inter <= x1_inter or y2_inter <= y1_inter:
            return 0.0

        intersection = (x2_inter - x1_inter) * (y2_inter - y1_inter)

        # Calculate areas
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def _compute_union_box(self, box1: List[float], box2: List[float]) -> List[float]:
        """Compute union (bounding box) of two boxes."""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        return [
            min(x1_1, x1_2),  # x1
            min(y1_1, y1_2),  # y1
            max(x2_1, x2_2),  # x2
            max(y2_1, y2_2)   # y2
        ]

    def _create_combined_escooter_detection(self,
                                           person_det: Dict,
                                           escooter_det: Dict,
                                           union_box: List[float],
                                           iou_score: float,
                                           img_width: int,
                                           img_height: int) -> Dict:
        """
        Create combined e-scooter detection from person and e-scooter detections.

        The result is an e-scooter detection with bbox that encompasses both person and e-scooter.
        """
        x1, y1, x2, y2 = union_box

        # Convert back to YOLO format
        x_center = (x1 + x2) / 2 / img_width
        y_center = (y1 + y2) / 2 / img_height
        width = (x2 - x1) / img_width
        height = (y2 - y1) / img_height

        # Combine confidences using geometric mean weighted by IoU
        person_conf = person_det.get('confidence', 0.5)
        escooter_conf = escooter_det.get('confidence', 0.5)

        # Weight the geometric mean by IoU score to reward better spatial alignment
        combined_confidence = np.sqrt(person_conf * escooter_conf) * (1.0 + iou_score)
        combined_confidence = min(combined_confidence, 1.0)  # Cap at 1.0

        return {
            'class_id': 6,  # e-scooter class ID
            'class_name': 'e-scooter',
            'confidence': combined_confidence,
            'x_center': x_center,
            'y_center': y_center,
            'width': width,
            'height': height,
            'source': 'spatial_association',
            'components': {
                'person_confidence': person_conf,
                'escooter_confidence': escooter_conf,
                'iou_score': iou_score,
                'association_method': 'person_escooter_union'
            }
        }