#!/usr/bin/env python3
"""
CAMINA NMS Consolidation Module

Implements Non-Maximum Suppression (NMS) consolidation to merge detections
from Stage A (YOLO11n + cyclist logic) and Stage B (YOLO-World) with
deterministic tie-breaking and configurable confidence strategies.
"""

import logging
from typing import List, Dict, Tuple, Optional
import numpy as np

from .config import NMSConfig

logger = logging.getLogger(__name__)


class NMSConsolidator:
    """
    NMS consolidation for merging multi-stage detections.

    This class implements sophisticated NMS that:
    1. Merges detections from multiple detection stages
    2. Applies class-aware NMS with configurable IoU thresholds
    3. Uses deterministic tie-breaking based on class priority
    4. Supports multiple confidence combination strategies
    5. Handles special cases (e.g., cyclist vs e-scooter conflicts)
    """

    def __init__(self, nms_config: NMSConfig):
        """
        Initialize NMS consolidator.

        Args:
            nms_config: NMS configuration parameters
        """
        self.config = nms_config
        self.iou_threshold = nms_config.iou_threshold
        self.confidence_strategy = nms_config.confidence_strategy
        self.deterministic_tiebreaker = nms_config.deterministic_tiebreaker
        self.class_priority_order = nms_config.class_priority_order

        # Create priority mapping for deterministic tie-breaking
        self.class_priority_map = {
            class_id: priority for priority, class_id in enumerate(self.class_priority_order)
        }

        logger.info(f"Initialized NMS consolidator with IoU threshold: {self.iou_threshold}")
        logger.info(f"Confidence strategy: {self.confidence_strategy}")
        logger.info(f"Class priority order: {self.class_priority_order}")

    def consolidate(self,
                   stage_a_detections: List[Dict],
                   stage_b_detections: List[Dict],
                   img_width: int,
                   img_height: int) -> List[Dict]:
        """
        Consolidate detections from both stages using NMS.

        Args:
            stage_a_detections: Detections from Stage A (YOLO11n + cyclist logic)
            stage_b_detections: Detections from Stage B (YOLO-World)
            img_width: Image width for coordinate conversion
            img_height: Image height for coordinate conversion

        Returns:
            List of consolidated detections after NMS
        """
        if not self.config.enabled:
            # If NMS disabled, simply combine detections
            return stage_a_detections + stage_b_detections

        # Combine all detections
        all_detections = stage_a_detections + stage_b_detections

        if not all_detections:
            return []

        # Handle special case: cyclist vs e-scooter suppression
        all_detections = self._handle_cyclist_escooter_conflicts(
            all_detections, img_width, img_height
        )

        # Apply global NMS
        consolidated_detections = self._apply_global_nms(all_detections, img_width, img_height)

        logger.debug(
            f"NMS consolidation: {len(stage_a_detections)} + {len(stage_b_detections)} = "
            f"{len(all_detections)} total -> {len(consolidated_detections)} final"
        )

        return consolidated_detections

    def _apply_global_nms(self,
                         detections: List[Dict],
                         img_width: int,
                         img_height: int) -> List[Dict]:
        """
        Apply global NMS across all detections.

        Args:
            detections: All detections to process
            img_width: Image width
            img_height: Image height

        Returns:
            List of detections after NMS
        """
        if not detections:
            return []

        # Convert to xyxy format for IoU calculation
        boxes_xyxy = []
        for detection in detections:
            xyxy = self._yolo_to_xyxy(detection, img_width, img_height)
            boxes_xyxy.append(xyxy)

        # Apply NMS
        keep_indices = self._nms_with_priority(detections, boxes_xyxy)

        # Return kept detections
        return [detections[i] for i in keep_indices]

    def _nms_with_priority(self,
                          detections: List[Dict],
                          boxes_xyxy: List[List[float]]) -> List[int]:
        """
        Apply NMS with class priority-based tie-breaking.

        Args:
            detections: List of detections
            boxes_xyxy: Corresponding bounding boxes in xyxy format

        Returns:
            List of indices to keep
        """
        if not detections:
            return []

        # Create detection info for sorting
        detection_info = []
        for i, (detection, box) in enumerate(zip(detections, boxes_xyxy)):
            class_id = detection.get('class_id', -1)
            confidence = detection.get('confidence', 0.0)
            priority = self.class_priority_map.get(class_id, len(self.class_priority_order))

            detection_info.append({
                'index': i,
                'confidence': confidence,
                'class_id': class_id,
                'priority': priority,
                'box': box,
                'detection': detection
            })

        # Sort by confidence (descending), then by priority (ascending)
        detection_info.sort(key=lambda x: (-x['confidence'], x['priority']))

        # Apply NMS
        keep_indices = []
        suppressed = set()

        for info in detection_info:
            idx = info['index']

            if idx in suppressed:
                continue

            keep_indices.append(idx)

            # Suppress overlapping detections
            current_box = info['box']
            current_class = info['class_id']

            for other_info in detection_info:
                other_idx = other_info['index']

                if other_idx == idx or other_idx in suppressed:
                    continue

                other_box = other_info['box']
                other_class = other_info['class_id']

                # Calculate IoU
                iou = self._calculate_iou_xyxy(current_box, other_box)

                if iou >= self.iou_threshold:
                    # Apply suppression rules
                    should_suppress = self._should_suppress(
                        info, other_info, iou
                    )

                    if should_suppress:
                        suppressed.add(other_idx)

        return sorted(keep_indices)

    def _should_suppress(self,
                        current_info: Dict,
                        other_info: Dict,
                        iou: float) -> bool:
        """
        Determine if other detection should be suppressed by current detection.

        Args:
            current_info: Current detection info (higher priority)
            other_info: Other detection info
            iou: IoU between the two detections

        Returns:
            True if other detection should be suppressed
        """
        current_class = current_info['class_id']
        other_class = other_info['class_id']

        # Same class: always suppress lower confidence
        if current_class == other_class:
            return True

        # Different classes: apply class-specific suppression rules

        # Special rule: YOLO-World classes (6, 7, 8) always suppress overlapping YOLO11n classes
        yolo_world_classes = {6, 7, 8}  # e-scooter, SUV, delivery_van
        yolo11n_vehicle_classes = {2, 4, 5}  # car, bus, truck

        if (current_class in yolo_world_classes and
            other_class in yolo11n_vehicle_classes):
            logger.debug(f"YOLO-World class {current_class} suppressing YOLO11n class {other_class}")
            return True

        # Special rule: delivery_van (8) suppresses truck (5) when overlapping
        if current_class == 8 and other_class == 5:  # delivery_van vs truck
            logger.debug("Delivery van suppressing truck detection")
            return True

        # Special rule: SUV (7) suppresses car (2) when overlapping
        if current_class == 7 and other_class == 2:  # SUV vs car
            logger.debug("SUV suppressing car detection")
            return True

        if self.deterministic_tiebreaker:
            current_priority = current_info['priority']
            other_priority = other_info['priority']

            # Higher priority class (lower number) suppresses lower priority
            if current_priority < other_priority:
                return True
            elif current_priority > other_priority:
                return False
            else:
                # Same priority: suppress lower confidence
                return current_info['confidence'] > other_info['confidence']

        # Default: suppress if significantly higher confidence
        confidence_ratio = current_info['confidence'] / max(other_info['confidence'], 1e-6)
        return confidence_ratio > 1.2  # 20% confidence advantage required

    def _handle_cyclist_escooter_conflicts(self,
                                         detections: List[Dict],
                                         img_width: int,
                                         img_height: int) -> List[Dict]:
        """
        Handle special case conflicts between cyclist and e-scooter detections.

        E-scooter detections should take priority over cyclist detections when
        they significantly overlap, as the cyclist logic may incorrectly pair
        a person on an e-scooter with a nearby bicycle.

        Args:
            detections: All detections
            img_width: Image width
            img_height: Image height

        Returns:
            Filtered detections with cyclist-escooter conflicts resolved
        """
        cyclist_detections = [
            (i, det) for i, det in enumerate(detections)
            if det.get('class_name') == 'cyclist' or det.get('class_id') == 1
        ]

        escooter_detections = [
            (i, det) for i, det in enumerate(detections)
            if det.get('class_name') == 'e-scooter' or det.get('class_id') == 6
        ]

        if not cyclist_detections or not escooter_detections:
            return detections

        # Find cyclists to suppress
        suppressed_indices = set()

        for cyclist_idx, cyclist_det in cyclist_detections:
            cyclist_box = self._yolo_to_xyxy(cyclist_det, img_width, img_height)

            for escooter_idx, escooter_det in escooter_detections:
                escooter_box = self._yolo_to_xyxy(escooter_det, img_width, img_height)

                iou = self._calculate_iou_xyxy(cyclist_box, escooter_box)

                # Use stricter threshold for cyclist-escooter conflicts
                if iou >= 0.35:  # Configurable threshold
                    suppressed_indices.add(cyclist_idx)
                    logger.debug(
                        f"Suppressing cyclist detection {cyclist_idx} due to "
                        f"e-scooter overlap (IoU: {iou:.3f})"
                    )
                    break

        # Return detections without suppressed cyclists
        filtered_detections = [
            det for i, det in enumerate(detections)
            if i not in suppressed_indices
        ]

        if suppressed_indices:
            logger.info(
                f"Suppressed {len(suppressed_indices)} cyclist detections "
                f"due to e-scooter conflicts"
            )

        return filtered_detections

    def _yolo_to_xyxy(self, detection: Dict, img_width: int, img_height: int) -> List[float]:
        """Convert YOLO format to xyxy format."""
        x_center = detection['x_center']
        y_center = detection['y_center']
        width = detection['width']
        height = detection['height']

        x1 = (x_center - width / 2) * img_width
        y1 = (y_center - height / 2) * img_height
        x2 = (x_center + width / 2) * img_width
        y2 = (y_center + height / 2) * img_height

        return [x1, y1, x2, y2]

    def _calculate_iou_xyxy(self, box1: List[float], box2: List[float]) -> float:
        """
        Calculate IoU between two bounding boxes in xyxy format.

        Args:
            box1: First bounding box [x1, y1, x2, y2]
            box2: Second bounding box [x1, y1, x2, y2]

        Returns:
            IoU score between 0.0 and 1.0
        """
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        # Calculate intersection
        x1_int = max(x1_1, x1_2)
        y1_int = max(y1_1, y1_2)
        x2_int = min(x2_1, x2_2)
        y2_int = min(y2_1, y2_2)

        if x2_int <= x1_int or y2_int <= y1_int:
            return 0.0

        intersection_area = (x2_int - x1_int) * (y2_int - y1_int)

        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - intersection_area

        if union_area <= 0:
            return 0.0

        return intersection_area / union_area

    def merge_overlapping_detections(self,
                                   detections: List[Dict],
                                   iou_threshold: float = 0.5) -> List[Dict]:
        """
        Merge highly overlapping detections of the same class.

        Args:
            detections: List of detections
            iou_threshold: IoU threshold for merging

        Returns:
            List of merged detections
        """
        if not detections:
            return []

        # Group by class
        class_groups = {}
        for detection in detections:
            class_id = detection.get('class_id', -1)
            if class_id not in class_groups:
                class_groups[class_id] = []
            class_groups[class_id].append(detection)

        merged_detections = []

        # Process each class separately
        for class_id, class_detections in class_groups.items():
            if len(class_detections) == 1:
                merged_detections.extend(class_detections)
                continue

            # Apply merging within class
            class_merged = self._merge_class_detections(
                class_detections, iou_threshold
            )
            merged_detections.extend(class_merged)

        return merged_detections

    def _merge_class_detections(self,
                              detections: List[Dict],
                              iou_threshold: float) -> List[Dict]:
        """
        Merge detections within the same class.

        Args:
            detections: Detections of the same class
            iou_threshold: IoU threshold for merging

        Returns:
            List of merged detections
        """
        if len(detections) <= 1:
            return detections

        # Simple clustering approach
        clusters = []
        used = set()

        for i, detection in enumerate(detections):
            if i in used:
                continue

            cluster = [detection]
            used.add(i)

            # Find similar detections to merge
            for j, other_detection in enumerate(detections):
                if j in used or i == j:
                    continue

                # Check if they should be merged
                should_merge = self._should_merge_detections(
                    detection, other_detection, iou_threshold
                )

                if should_merge:
                    cluster.append(other_detection)
                    used.add(j)

            clusters.append(cluster)

        # Merge each cluster into a single detection
        merged_detections = []
        for cluster in clusters:
            if len(cluster) == 1:
                merged_detections.append(cluster[0])
            else:
                merged_detection = self._merge_detection_cluster(cluster)
                merged_detections.append(merged_detection)

        return merged_detections

    def _should_merge_detections(self,
                               det1: Dict,
                               det2: Dict,
                               iou_threshold: float) -> bool:
        """Check if two detections should be merged."""
        # For now, only merge if same source and high IoU
        if det1.get('source', '') != det2.get('source', ''):
            return False

        # Would need image dimensions to calculate IoU properly
        # This is a simplified version
        return False

    def _merge_detection_cluster(self, cluster: List[Dict]) -> Dict:
        """
        Merge a cluster of detections into a single detection.

        Args:
            cluster: List of detections to merge

        Returns:
            Single merged detection
        """
        if len(cluster) == 1:
            return cluster[0]

        # Weighted average based on confidence
        total_confidence = sum(det['confidence'] for det in cluster)
        weights = [det['confidence'] / total_confidence for det in cluster]

        # Weighted average of coordinates
        x_center = sum(w * det['x_center'] for w, det in zip(weights, cluster))
        y_center = sum(w * det['y_center'] for w, det in zip(weights, cluster))
        width = sum(w * det['width'] for w, det in zip(weights, cluster))
        height = sum(w * det['height'] for w, det in zip(weights, cluster))

        # Use highest confidence
        max_confidence = max(det['confidence'] for det in cluster)

        # Use properties from highest confidence detection
        best_detection = max(cluster, key=lambda x: x['confidence'])

        merged_detection = {
            'class_id': best_detection['class_id'],
            'class_name': best_detection['class_name'],
            'confidence': float(max_confidence),
            'x_center': float(x_center),
            'y_center': float(y_center),
            'width': float(width),
            'height': float(height),
            'source': f"merged_{best_detection.get('source', 'unknown')}",
            'merged_count': len(cluster),
            'merged_sources': [det.get('source', 'unknown') for det in cluster]
        }

        return merged_detection