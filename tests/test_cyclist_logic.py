#!/usr/bin/env python3
"""
Tests for CAMINA cyclist detection logic.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.cyclist_logic import CyclistDetector


class TestCyclistDetector:
    """Test cyclist detection logic."""

    def setup_method(self):
        """Setup test detector."""
        self.detector = CyclistDetector(
            iou_threshold=0.20,
            lower_margin_px=5,
            spatial_margin_px=5,
            min_bbox_area=0.01,
            confidence_threshold=0.1
        )

    def test_detect_cyclists_simple_case(self):
        """Test basic cyclist detection with one person and one bicycle."""
        # Person detection (center of image)
        person_detections = [{
            'x_center': 0.5,
            'y_center': 0.4,
            'width': 0.2,
            'height': 0.4,
            'confidence': 0.8,
            'class_name': 'person'
        }]

        # Bicycle detection (slightly below and overlapping)
        bicycle_detections = [{
            'x_center': 0.5,
            'y_center': 0.6,
            'width': 0.3,
            'height': 0.2,
            'confidence': 0.7,
            'class_name': 'bicycle'
        }]

        img_width, img_height = 640, 480

        cyclists, unmatched_persons = self.detector.detect_cyclists(
            person_detections, bicycle_detections, img_width, img_height
        )

        # Should create one cyclist
        assert len(cyclists) == 1
        assert len(unmatched_persons) == 0

        cyclist = cyclists[0]
        assert cyclist['class_id'] == 1
        assert cyclist['class_name'] == 'cyclist'
        assert cyclist['source'] == 'cyclist_logic'
        assert 'components' in cyclist

    def test_no_overlap_no_cyclist(self):
        """Test that non-overlapping person and bicycle don't create cyclist."""
        # Person on left
        person_detections = [{
            'x_center': 0.2,
            'y_center': 0.5,
            'width': 0.2,
            'height': 0.4,
            'confidence': 0.8,
            'class_name': 'person'
        }]

        # Bicycle on right (no overlap)
        bicycle_detections = [{
            'x_center': 0.8,
            'y_center': 0.5,
            'width': 0.2,
            'height': 0.2,
            'confidence': 0.7,
            'class_name': 'bicycle'
        }]

        img_width, img_height = 640, 480

        cyclists, unmatched_persons = self.detector.detect_cyclists(
            person_detections, bicycle_detections, img_width, img_height
        )

        # Should not create cyclist
        assert len(cyclists) == 0
        assert len(unmatched_persons) == 1

    def test_bicycle_not_below_person(self):
        """Test that bicycle above person doesn't create cyclist."""
        # Person detection (lower)
        person_detections = [{
            'x_center': 0.5,
            'y_center': 0.6,
            'width': 0.2,
            'height': 0.4,
            'confidence': 0.8,
            'class_name': 'person'
        }]

        # Bicycle detection (above person)
        bicycle_detections = [{
            'x_center': 0.5,
            'y_center': 0.3,
            'width': 0.3,
            'height': 0.2,
            'confidence': 0.7,
            'class_name': 'bicycle'
        }]

        img_width, img_height = 640, 480

        cyclists, unmatched_persons = self.detector.detect_cyclists(
            person_detections, bicycle_detections, img_width, img_height
        )

        # Should not create cyclist (bicycle not below person)
        assert len(cyclists) == 0
        assert len(unmatched_persons) == 1

    def test_low_confidence_filtering(self):
        """Test that low confidence detections are filtered out."""
        # Low confidence person
        person_detections = [{
            'x_center': 0.5,
            'y_center': 0.4,
            'width': 0.2,
            'height': 0.4,
            'confidence': 0.05,  # Below threshold
            'class_name': 'person'
        }]

        # High confidence bicycle
        bicycle_detections = [{
            'x_center': 0.5,
            'y_center': 0.6,
            'width': 0.3,
            'height': 0.2,
            'confidence': 0.7,
            'class_name': 'bicycle'
        }]

        img_width, img_height = 640, 480

        cyclists, unmatched_persons = self.detector.detect_cyclists(
            person_detections, bicycle_detections, img_width, img_height
        )

        # Should not create cyclist due to low confidence person
        assert len(cyclists) == 0
        assert len(unmatched_persons) == 1

    def test_multiple_persons_one_bicycle(self):
        """Test multiple persons with one bicycle - best match wins."""
        # Two persons
        person_detections = [
            {
                'x_center': 0.4,
                'y_center': 0.4,
                'width': 0.2,
                'height': 0.4,
                'confidence': 0.6,
                'class_name': 'person'
            },
            {
                'x_center': 0.6,
                'y_center': 0.4,
                'width': 0.2,
                'height': 0.4,
                'confidence': 0.8,
                'class_name': 'person'
            }
        ]

        # One bicycle (closer to second person)
        bicycle_detections = [{
            'x_center': 0.6,
            'y_center': 0.6,
            'width': 0.3,
            'height': 0.2,
            'confidence': 0.7,
            'class_name': 'bicycle'
        }]

        img_width, img_height = 640, 480

        cyclists, unmatched_persons = self.detector.detect_cyclists(
            person_detections, bicycle_detections, img_width, img_height
        )

        # Should create one cyclist (best IoU match)
        assert len(cyclists) == 1
        assert len(unmatched_persons) == 1

    def test_iou_calculation(self):
        """Test IoU calculation accuracy."""
        # Create perfectly overlapping boxes
        box1 = [100, 100, 200, 200]  # xyxy format
        box2 = [100, 100, 200, 200]

        iou = self.detector._calculate_iou_xyxy(box1, box2)
        assert iou == 1.0

        # Non-overlapping boxes
        box3 = [300, 300, 400, 400]
        iou = self.detector._calculate_iou_xyxy(box1, box3)
        assert iou == 0.0

        # Partially overlapping boxes
        box4 = [150, 150, 250, 250]  # 50% overlap
        iou = self.detector._calculate_iou_xyxy(box1, box4)
        assert 0.2 < iou < 0.4  # Approximate IoU for this case

    def test_coordinate_conversion(self):
        """Test YOLO to xyxy coordinate conversion."""
        detection = {
            'x_center': 0.5,
            'y_center': 0.5,
            'width': 0.4,
            'height': 0.6
        }

        img_width, img_height = 640, 480

        xyxy = self.detector._yolo_to_xyxy(detection, img_width, img_height)

        # Expected: x1=192, y1=96, x2=448, y2=384
        expected = [192.0, 96.0, 448.0, 384.0]
        assert xyxy == expected

    def test_union_box_calculation(self):
        """Test union bounding box calculation."""
        box1 = [100, 100, 200, 200]
        box2 = [150, 150, 250, 250]

        union_box = self.detector._compute_union_box(box1, box2)

        # Union should be [100, 100, 250, 250]
        expected = [100, 100, 250, 250]
        assert union_box == expected

    def test_suppress_cyclists_near_escooters(self):
        """Test cyclist suppression near e-scooters."""
        # Cyclist detection
        cyclist_detections = [{
            'x_center': 0.5,
            'y_center': 0.5,
            'width': 0.3,
            'height': 0.4,
            'confidence': 0.7,
            'class_name': 'cyclist',
            'class_id': 1
        }]

        # Overlapping e-scooter detection
        escooter_detections = [{
            'x_center': 0.52,
            'y_center': 0.52,
            'width': 0.25,
            'height': 0.3,
            'confidence': 0.8,
            'class_name': 'e-scooter',
            'class_id': 6
        }]

        img_width, img_height = 640, 480

        filtered_cyclists = self.detector.suppress_cyclists_near_escooters(
            cyclist_detections, escooter_detections, img_width, img_height
        )

        # Cyclist should be suppressed due to e-scooter overlap
        assert len(filtered_cyclists) == 0

    def test_empty_inputs(self):
        """Test behavior with empty inputs."""
        img_width, img_height = 640, 480

        # Empty persons
        cyclists, unmatched = self.detector.detect_cyclists(
            [], [{'x_center': 0.5, 'y_center': 0.5, 'width': 0.2, 'height': 0.2, 'confidence': 0.7}],
            img_width, img_height
        )
        assert len(cyclists) == 0
        assert len(unmatched) == 0

        # Empty bicycles
        cyclists, unmatched = self.detector.detect_cyclists(
            [{'x_center': 0.5, 'y_center': 0.5, 'width': 0.2, 'height': 0.4, 'confidence': 0.7}], [],
            img_width, img_height
        )
        assert len(cyclists) == 0
        assert len(unmatched) == 1

        # Both empty
        cyclists, unmatched = self.detector.detect_cyclists([], [], img_width, img_height)
        assert len(cyclists) == 0
        assert len(unmatched) == 0


if __name__ == '__main__':
    pytest.main([__file__])