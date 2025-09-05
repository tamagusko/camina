"""
Auto-labeling module for CAMINA dataset expansion.
Simplified, research-focused implementation for 9-class object detection.
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
import json
import torch
from dataclasses import dataclass
from PIL import Image
import torchvision.transforms as transforms

from .config import CaminaConfig
from .utils import ProgressTracker, normalize_bbox, calculate_iou

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Object detection result"""
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]  # [center_x, center_y, width, height] normalized
    
    def to_yolo_format(self) -> str:
        """Convert to YOLO label format"""
        return f"{self.class_id} {self.bbox[0]:.6f} {self.bbox[1]:.6f} {self.bbox[2]:.6f} {self.bbox[3]:.6f}"


class AutoLabeler:
    """
    Simplified auto-labeling pipeline for research reproducibility.
    Focuses on the three new classes: e-scooter, SUV, delivery_van.
    """
    
    def __init__(self, config: CaminaConfig):
        self.config = config
        self.class_schema = config.class_schema
        self.labeling_config = config.auto_labeling
        
        # Initialize models
        self.yolo_model = None
        self.clip_model = None
        self.device = torch.device('cpu')  # Default to CPU for stability
        
        # Detection parameters
        self.confidence_threshold = self.labeling_config.confidence_threshold
        self.nms_threshold = self.labeling_config.nms_threshold
        self.min_box_size = self.labeling_config.min_box_size
        
        logger.info("AutoLabeler initialized for 3 new classes")
    
    def initialize_models(self, 
                         yolo_model_path: Optional[str] = None,
                         device: str = 'auto') -> bool:
        """
        Initialize detection models.
        
        Args:
            yolo_model_path: Path to pre-trained YOLO model
            device: Computing device
        
        Returns:
            True if models initialized successfully
        """
        try:
            # Setup device
            if device == 'auto':
                if torch.cuda.is_available():
                    self.device = torch.device('cuda')
                elif torch.backends.mps.is_available():
                    self.device = torch.device('mps')
                else:
                    self.device = torch.device('cpu')
            else:
                self.device = torch.device(device)
            
            logger.info(f"Using device: {self.device}")
            
            # Initialize YOLO model for general object detection
            if yolo_model_path:
                self._initialize_yolo(yolo_model_path)
            
            # Initialize CLIP for semantic classification
            self._initialize_clip()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            return False
    
    def _initialize_yolo(self, model_path: str):
        """Initialize YOLO model"""
        try:
            from ultralytics import YOLO
            self.yolo_model = YOLO(model_path)
            logger.info(f"YOLO model loaded: {model_path}")
        except ImportError:
            logger.warning("Ultralytics not available, YOLO detection disabled")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
    
    def _initialize_clip(self):
        """Initialize CLIP model for semantic classification"""
        try:
            import clip
            self.clip_model, self.clip_preprocess = clip.load("ViT-B/32", device=self.device)
            logger.info("CLIP model loaded successfully")
        except ImportError:
            logger.warning("CLIP not available, semantic classification disabled")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
    
    def detect_objects(self, image_path: Union[str, Path]) -> List[Detection]:
        """
        Detect objects in image using YOLO + CLIP pipeline.
        
        Args:
            image_path: Path to input image
        
        Returns:
            List of detected objects
        """
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Image not found: {image_path}")
            return []
        
        detections = []
        
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return []
            
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width = image.shape[:2]
            
            # YOLO detection for general objects
            if self.yolo_model is not None:
                yolo_detections = self._yolo_detect(image_rgb, width, height)
                detections.extend(yolo_detections)
            
            # CLIP-based classification for new classes
            if self.clip_model is not None:
                clip_detections = self._clip_classify(image_rgb, width, height)
                detections.extend(clip_detections)
            
            # Apply NMS to remove overlapping detections
            detections = self._apply_nms(detections)
            
            # Filter by confidence and size
            detections = self._filter_detections(detections)
            
        except Exception as e:
            logger.error(f"Detection failed for {image_path}: {e}")
            return []
        
        return detections
    
    def _yolo_detect(self, image: np.ndarray, width: int, height: int) -> List[Detection]:
        """Use YOLO for general object detection"""
        detections = []
        
        try:
            results = self.yolo_model(image, verbose=False)
            
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                
                for box in boxes:
                    # Get box coordinates and confidence
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    
                    if conf < self.confidence_threshold:
                        continue
                    
                    # Convert to normalized YOLO format
                    bbox_norm = normalize_bbox(xyxy, width, height)
                    
                    # Map YOLO class to CAMINA class if applicable
                    camina_class_id = self._map_yolo_class(cls)
                    if camina_class_id is not None:
                        detection = Detection(
                            class_id=camina_class_id,
                            class_name=self.class_schema.CLASSES[camina_class_id],
                            confidence=conf,
                            bbox=bbox_norm
                        )
                        detections.append(detection)
        
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
        
        return detections
    
    def _clip_classify(self, image: np.ndarray, width: int, height: int) -> List[Detection]:
        """Use CLIP for semantic classification of new classes"""
        detections = []
        
        if self.clip_model is None:
            return detections
        
        try:
            # Convert to PIL Image
            pil_image = Image.fromarray(image)
            
            # Preprocess image for CLIP
            image_tensor = self.clip_preprocess(pil_image).unsqueeze(0).to(self.device)
            
            # Create text prompts for new classes
            text_prompts = []
            class_mapping = []
            
            for class_id, prompts in self.labeling_config.clip_prompts.items():
                for prompt in prompts:
                    text_prompts.append(prompt)
                    class_mapping.append(class_id)
            
            # Tokenize text prompts
            text_tokens = clip.tokenize(text_prompts).to(self.device)
            
            # Get embeddings
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_tensor)
                text_features = self.clip_model.encode_text(text_tokens)
                
                # Calculate similarities
                similarities = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                similarities = similarities.cpu().numpy()[0]
            
            # Find best matches above threshold
            for i, similarity in enumerate(similarities):
                if similarity > self.confidence_threshold:
                    class_id = class_mapping[i]
                    
                    # Create full-image detection for now
                    # In practice, you might want to use object proposals or sliding windows
                    bbox_norm = [0.5, 0.5, 0.8, 0.8]  # Center detection covering most of image
                    
                    detection = Detection(
                        class_id=class_id,
                        class_name=self.class_schema.CLASSES[class_id],
                        confidence=float(similarity),
                        bbox=bbox_norm
                    )
                    detections.append(detection)
        
        except Exception as e:
            logger.error(f"CLIP classification failed: {e}")
        
        return detections
    
    def _map_yolo_class(self, yolo_class: int) -> Optional[int]:
        """
        Map YOLO class ID to CAMINA class ID.
        This is a simplified mapping for common COCO classes.
        """
        # COCO to CAMINA mapping (simplified)
        coco_to_camina = {
            0: 0,   # person -> pedestrian
            2: 2,   # car -> car
            3: 3,   # motorcycle -> motorcycle
            5: 4,   # bus -> bus
            7: 5,   # truck -> truck
            1: 1,   # bicycle -> cyclist (approximate)
        }
        
        return coco_to_camina.get(yolo_class)
    
    def _apply_nms(self, detections: List[Detection]) -> List[Detection]:
        """Apply Non-Maximum Suppression to remove overlapping detections"""
        if len(detections) <= 1:
            return detections
        
        # Group by class
        class_detections = {}
        for det in detections:
            if det.class_id not in class_detections:
                class_detections[det.class_id] = []
            class_detections[det.class_id].append(det)
        
        # Apply NMS per class
        filtered_detections = []
        for class_id, dets in class_detections.items():
            if len(dets) <= 1:
                filtered_detections.extend(dets)
                continue
            
            # Sort by confidence
            dets.sort(key=lambda x: x.confidence, reverse=True)
            
            # Apply NMS
            keep = []
            while dets:
                best = dets.pop(0)
                keep.append(best)
                
                # Remove overlapping detections
                remaining = []
                for det in dets:
                    iou = self._calculate_detection_iou(best, det)
                    if iou < self.nms_threshold:
                        remaining.append(det)
                dets = remaining
            
            filtered_detections.extend(keep)
        
        return filtered_detections
    
    def _calculate_detection_iou(self, det1: Detection, det2: Detection) -> float:
        """Calculate IoU between two detections"""
        # Convert normalized bbox to absolute coordinates (assuming 640x640)
        def to_absolute(bbox, size=640):
            cx, cy, w, h = bbox
            x1 = (cx - w/2) * size
            y1 = (cy - h/2) * size
            x2 = (cx + w/2) * size
            y2 = (cy + h/2) * size
            return [x1, y1, x2, y2]
        
        box1 = to_absolute(det1.bbox)
        box2 = to_absolute(det2.bbox)
        
        return calculate_iou(box1, box2)
    
    def _filter_detections(self, detections: List[Detection]) -> List[Detection]:
        """Filter detections by confidence and size"""
        filtered = []
        
        for det in detections:
            # Check minimum confidence
            if det.confidence < self.confidence_threshold:
                continue
            
            # Check minimum box size
            box_area = det.bbox[2] * det.bbox[3]  # width * height
            if box_area < self.min_box_size:
                continue
            
            filtered.append(det)
        
        return filtered
    
    def label_image(self, 
                   image_path: Union[str, Path], 
                   output_path: Optional[Union[str, Path]] = None) -> List[Detection]:
        """
        Label single image and optionally save results.
        
        Args:
            image_path: Path to input image
            output_path: Optional path to save label file
        
        Returns:
            List of detections
        """
        detections = self.detect_objects(image_path)
        
        if output_path and detections:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                for det in detections:
                    f.write(det.to_yolo_format() + '\n')
            
            logger.debug(f"Labels saved to {output_path}")
        
        return detections
    
    def label_directory(self, 
                       images_dir: Union[str, Path], 
                       labels_dir: Union[str, Path],
                       overwrite: bool = False) -> Dict[str, any]:
        """
        Label all images in directory.
        
        Args:
            images_dir: Directory containing images
            labels_dir: Directory to save label files
            overwrite: Whether to overwrite existing labels
        
        Returns:
            Labeling results summary
        """
        images_dir = Path(images_dir)
        labels_dir = Path(labels_dir)
        
        if not images_dir.exists():
            logger.error(f"Images directory not found: {images_dir}")
            return {'success': False, 'error': 'Images directory not found'}
        
        # Create labels directory
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        # Find image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        image_files = []
        for ext in image_extensions:
            image_files.extend(images_dir.glob(f'*{ext}'))
            image_files.extend(images_dir.glob(f'*{ext.upper()}'))
        
        if not image_files:
            logger.error(f"No images found in {images_dir}")
            return {'success': False, 'error': 'No images found'}
        
        logger.info(f"Labeling {len(image_files)} images...")
        
        # Initialize statistics
        stats = {
            'total_images': len(image_files),
            'processed_images': 0,
            'skipped_images': 0,
            'total_detections': 0,
            'class_counts': {name: 0 for name in self.class_schema.class_names}
        }
        
        progress = ProgressTracker(
            total=len(image_files),
            description="Auto-labeling images"
        )
        
        # Process each image
        for image_path in image_files:
            label_path = labels_dir / f"{image_path.stem}.txt"
            
            # Skip if label exists and not overwriting
            if label_path.exists() and not overwrite:
                stats['skipped_images'] += 1
                progress.update()
                continue
            
            # Detect and label
            detections = self.label_image(image_path, label_path)
            
            # Update statistics
            stats['processed_images'] += 1
            stats['total_detections'] += len(detections)
            
            for det in detections:
                stats['class_counts'][det.class_name] += 1
            
            progress.update()
        
        progress.finish()
        
        # Print summary
        logger.info("=== Auto-labeling Summary ===")
        logger.info(f"Total images: {stats['total_images']}")
        logger.info(f"Processed: {stats['processed_images']}")
        logger.info(f"Skipped: {stats['skipped_images']}")
        logger.info(f"Total detections: {stats['total_detections']}")
        
        logger.info("Class distribution:")
        for class_name, count in stats['class_counts'].items():
            if count > 0:
                logger.info(f"  {class_name}: {count}")
        
        return {
            'success': True,
            'statistics': stats,
            'images_dir': str(images_dir),
            'labels_dir': str(labels_dir)
        }
    
    def create_visualization(self, 
                           image_path: Union[str, Path], 
                           detections: List[Detection], 
                           output_path: Union[str, Path]):
        """
        Create visualization of detections.
        
        Args:
            image_path: Path to original image
            detections: List of detections to visualize
            output_path: Path to save visualization
        """
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return
            
            height, width = image.shape[:2]
            
            # Define colors for each class
            colors = [
                (255, 0, 0),    # pedestrian - red
                (0, 255, 0),    # cyclist - green
                (0, 0, 255),    # car - blue
                (255, 255, 0),  # motorcycle - cyan
                (255, 0, 255),  # bus - magenta
                (0, 255, 255),  # truck - yellow
                (128, 0, 128),  # e-scooter - purple
                (255, 165, 0),  # SUV - orange
                (0, 128, 0),    # delivery_van - dark green
            ]
            
            # Draw detections
            for det in detections:
                # Convert normalized bbox to pixel coordinates
                cx, cy, w, h = det.bbox
                x1 = int((cx - w/2) * width)
                y1 = int((cy - h/2) * height)
                x2 = int((cx + w/2) * width)
                y2 = int((cy + h/2) * height)
                
                # Get color
                color = colors[det.class_id % len(colors)]
                
                # Draw bounding box
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{det.class_name}: {det.confidence:.2f}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                cv2.rectangle(image, (x1, y1 - label_size[1] - 10), 
                            (x1 + label_size[0], y1), color, -1)
                cv2.putText(image, label, (x1, y1 - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Save visualization
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), image)
            
            logger.debug(f"Visualization saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to create visualization: {e}")


def create_simple_labeler(config: CaminaConfig) -> AutoLabeler:
    """Create a simplified auto-labeler for research use"""
    labeler = AutoLabeler(config)
    
    # Initialize with basic models
    try:
        labeler.initialize_models()
        logger.info("Simple auto-labeler created successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize models: {e}")
        logger.info("Auto-labeler created in CPU-only mode")
    
    return labeler