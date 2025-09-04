#!/usr/bin/env python3
"""
DINOv3 Semi-Automated Labeling Pipeline for CAMINA Dataset Expansion
Uses DINOv3 for feature extraction and object localization to suggest labels for new classes
"""

import os
import cv2
import torch
import numpy as np
import logging
from pathlib import Path
import json
import argparse
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Dict, Tuple
from dataclasses import dataclass
import torchvision.transforms as transforms

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BoundingBox:
    """Bounding box in YOLO format (normalized coordinates)"""
    class_id: int
    center_x: float
    center_y: float 
    width: float
    height: float
    confidence: float = 0.0

class DINOv3SemiAutoLabeler:
    def __init__(self, model_name='dinov2_vits14', device='auto'):
        """
        Initialize DINOv3 semi-automated labeling pipeline
        
        Args:
            model_name: DINOv3 model variant
            device: compute device ('auto', 'cpu', 'cuda', 'mps')
        """
        self.device = self._setup_device(device)
        self.model = self._load_dinov3_model(model_name)
        self.transform = self._setup_transforms()
        
        # Target classes for new object detection
        self.target_classes = {
            6: 'e-scooter',
            7: 'SUV', 
            8: 'delivery_van'
        }
        
        # Detection thresholds and parameters
        self.confidence_threshold = 0.5
        self.nms_threshold = 0.4
        self.min_box_size = 0.01  # Minimum box size (normalized)
        
        logger.info(f"Initialized DINOv3 labeler on {self.device}")
        
    def _setup_device(self, device):
        """Setup computation device"""
        if device == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            elif torch.backends.mps.is_available():
                return torch.device('mps')
            else:
                return torch.device('cpu')
        return torch.device(device)
    
    def _load_dinov3_model(self, model_name):
        """Load DINOv3 model"""
        try:
            # Try to load from torch hub
            model = torch.hub.load('facebookresearch/dinov2', model_name, pretrained=True)
            model.eval()
            model.to(self.device)
            return model
        except Exception as e:
            logger.error(f"Failed to load DINOv3 model: {e}")
            # Fallback: create a dummy model for testing
            logger.warning("Using dummy model for testing purposes")
            return self._create_dummy_model()
    
    def _create_dummy_model(self):
        """Create dummy model for testing when DINOv3 not available"""
        class DummyDINOv3(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.feature_dim = 384
                
            def forward(self, x):
                # Return random features for testing
                batch_size = x.shape[0]
                return torch.randn(batch_size, self.feature_dim, device=x.device)
        
        return DummyDINOv3().to(self.device)
    
    def _setup_transforms(self):
        """Setup image transforms for DINOv3"""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
    
    def extract_features(self, image: np.ndarray) -> torch.Tensor:
        """
        Extract DINOv3 features from image
        
        Args:
            image: Input image as numpy array (H, W, 3)
            
        Returns:
            Feature tensor
        """
        # Convert to PIL Image
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
        pil_image = Image.fromarray(image)
        
        # Apply transforms
        tensor_image = self.transform(pil_image).unsqueeze(0).to(self.device)
        
        # Extract features
        with torch.no_grad():
            features = self.model(tensor_image)
            
        return features
    
    def detect_objects_sliding_window(self, image: np.ndarray, window_sizes: List[Tuple[int, int]], 
                                    stride_ratio: float = 0.5) -> List[BoundingBox]:
        """
        Use sliding window approach with DINOv3 features for object detection
        
        Args:
            image: Input image
            window_sizes: List of (width, height) window sizes
            stride_ratio: Stride as ratio of window size
            
        Returns:
            List of detected bounding boxes
        """
        detections = []
        height, width = image.shape[:2]
        
        for win_w, win_h in window_sizes:
            stride_x = max(1, int(win_w * stride_ratio))
            stride_y = max(1, int(win_h * stride_ratio))
            
            for y in range(0, height - win_h + 1, stride_y):
                for x in range(0, width - win_w + 1, stride_x):
                    # Extract window
                    window = image[y:y+win_h, x:x+win_w]
                    
                    # Extract features
                    features = self.extract_features(window)
                    
                    # Classify window (simplified approach)
                    confidence = self._classify_window_features(features)
                    
                    if confidence > self.confidence_threshold:
                        # Convert to normalized YOLO format
                        center_x = (x + win_w / 2) / width
                        center_y = (y + win_h / 2) / height
                        norm_width = win_w / width
                        norm_height = win_h / height
                        
                        # Determine class (simplified logic)
                        class_id = self._determine_class_from_features(features, window)
                        
                        bbox = BoundingBox(
                            class_id=class_id,
                            center_x=center_x,
                            center_y=center_y,
                            width=norm_width,
                            height=norm_height,
                            confidence=confidence
                        )
                        detections.append(bbox)
        
        return detections
    
    def _classify_window_features(self, features: torch.Tensor) -> float:
        """
        Classify window based on DINOv3 features
        This is a simplified approach - in practice, you'd train a classifier
        
        Args:
            features: DINOv3 feature tensor
            
        Returns:
            Classification confidence
        """
        # Simplified feature-based classification
        # In practice, you'd have trained classifiers for each target class
        
        # Use feature magnitude and variance as proxy for object presence
        feature_magnitude = torch.norm(features).item()
        feature_variance = torch.var(features).item()
        
        # Simple heuristic (replace with trained classifier)
        confidence = min(1.0, (feature_magnitude * feature_variance) / 100.0)
        
        return confidence
    
    def _determine_class_from_features(self, features: torch.Tensor, window: np.ndarray) -> int:
        """
        Determine object class based on features and visual cues
        
        Args:
            features: DINOv3 features
            window: Image window
            
        Returns:
            Predicted class ID
        """
        # Simplified class determination based on window properties
        h, w = window.shape[:2]
        aspect_ratio = w / h
        
        # Basic heuristics (replace with proper classification)
        if aspect_ratio > 1.5 and h < w:  # Wide, low objects
            if np.mean(window) > 100:  # Brighter objects tend to be vehicles
                return 7  # SUV
            else:
                return 8  # delivery_van
        else:  # More compact objects
            return 6  # e-scooter
    
    def apply_nms(self, detections: List[BoundingBox]) -> List[BoundingBox]:
        """Apply Non-Maximum Suppression to remove overlapping detections"""
        if not detections:
            return []
        
        # Convert to format suitable for NMS
        boxes = []
        scores = []
        
        for det in detections:
            # Convert YOLO format to (x1, y1, x2, y2)
            x1 = det.center_x - det.width / 2
            y1 = det.center_y - det.height / 2
            x2 = det.center_x + det.width / 2
            y2 = det.center_y + det.height / 2
            
            boxes.append([x1, y1, x2, y2])
            scores.append(det.confidence)
        
        boxes = torch.tensor(boxes, dtype=torch.float32)
        scores = torch.tensor(scores, dtype=torch.float32)
        
        # Apply NMS
        keep_indices = torch.ops.torchvision.nms(boxes, scores, self.nms_threshold)
        
        # Return filtered detections
        filtered_detections = [detections[i] for i in keep_indices]
        
        return filtered_detections
    
    def process_image(self, image_path: str, output_dir: str = None) -> List[BoundingBox]:
        """
        Process single image and generate label suggestions
        
        Args:
            image_path: Path to input image
            output_dir: Directory to save visualization (optional)
            
        Returns:
            List of detected bounding boxes
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not load image: {image_path}")
            return []
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Define sliding window sizes (in pixels)
        # Adjust based on expected object sizes
        window_sizes = [
            (80, 120),   # Small objects (e-scooter)
            (120, 80),   # Wide objects (SUV)
            (100, 100),  # Square objects (delivery van)
            (160, 120),  # Large objects
        ]
        
        # Detect objects
        detections = self.detect_objects_sliding_window(image_rgb, window_sizes)
        
        # Apply NMS
        detections = self.apply_nms(detections)
        
        # Filter by minimum size
        detections = [d for d in detections if d.width >= self.min_box_size and d.height >= self.min_box_size]
        
        logger.info(f"Found {len(detections)} potential objects in {Path(image_path).name}")
        
        # Save visualization if requested
        if output_dir:
            self.visualize_detections(image_rgb, detections, 
                                    output_path=Path(output_dir) / f"{Path(image_path).stem}_detections.jpg")
        
        return detections
    
    def visualize_detections(self, image: np.ndarray, detections: List[BoundingBox], 
                           output_path: str = None):
        """
        Visualize detected bounding boxes on image
        
        Args:
            image: Input image (RGB)
            detections: List of bounding boxes
            output_path: Path to save visualization
        """
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        ax.imshow(image)
        
        colors = {6: 'red', 7: 'blue', 8: 'green'}  # Colors for different classes
        
        for det in detections:
            # Convert normalized coordinates to pixel coordinates
            h, w = image.shape[:2]
            x1 = (det.center_x - det.width / 2) * w
            y1 = (det.center_y - det.height / 2) * h
            width = det.width * w
            height = det.height * h
            
            color = colors.get(det.class_id, 'yellow')
            class_name = self.target_classes.get(det.class_id, f'class_{det.class_id}')
            
            # Draw bounding box
            rect = patches.Rectangle((x1, y1), width, height, 
                                   linewidth=2, edgecolor=color, facecolor='none')
            ax.add_patch(rect)
            
            # Add label
            ax.text(x1, y1 - 5, f'{class_name} ({det.confidence:.2f})', 
                   color=color, fontsize=10, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.7))
        
        ax.set_title(f'DINOv3 Semi-Automated Detections ({len(detections)} objects)')
        ax.axis('off')
        
        if output_path:
            plt.savefig(output_path, bbox_inches='tight', dpi=300)
            logger.info(f"Visualization saved to {output_path}")
        
        plt.close()
    
    def generate_yolo_labels(self, detections: List[BoundingBox], output_file: str):
        """
        Generate YOLO format label file from detections
        
        Args:
            detections: List of bounding boxes
            output_file: Path to output label file
        """
        with open(output_file, 'w') as f:
            for det in detections:
                line = f"{det.class_id} {det.center_x:.6f} {det.center_y:.6f} {det.width:.6f} {det.height:.6f}"
                f.write(line + '\n')
        
        logger.info(f"Generated YOLO labels: {output_file}")
    
    def process_dataset(self, image_dir: str, output_dir: str, visualize: bool = True):
        """
        Process entire dataset directory
        
        Args:
            image_dir: Directory containing images to process
            output_dir: Directory to save labels and visualizations
            visualize: Whether to save visualizations
        """
        image_path = Path(image_dir)
        output_path = Path(output_dir)
        
        # Create output directories
        labels_dir = output_path / 'labels'
        viz_dir = output_path / 'visualizations'
        labels_dir.mkdir(parents=True, exist_ok=True)
        if visualize:
            viz_dir.mkdir(parents=True, exist_ok=True)
        
        # Process all images
        image_files = list(image_path.glob('*.jpg')) + list(image_path.glob('*.png'))
        
        total_detections = 0
        for img_file in image_files:
            logger.info(f"Processing {img_file.name}...")
            
            # Process image
            viz_output = str(viz_dir) if visualize else None
            detections = self.process_image(str(img_file), viz_output)
            
            # Generate labels
            label_file = labels_dir / f"{img_file.stem}.txt"
            self.generate_yolo_labels(detections, str(label_file))
            
            total_detections += len(detections)
        
        logger.info(f"Processed {len(image_files)} images, found {total_detections} potential objects")

def main():
    parser = argparse.ArgumentParser(description='DINOv3 Semi-Automated Labeling Pipeline')
    parser.add_argument('--image-dir', required=True, help='Directory containing images to process')
    parser.add_argument('--output-dir', required=True, help='Output directory for labels and visualizations')
    parser.add_argument('--device', default='auto', help='Compute device (auto, cpu, cuda, mps)')
    parser.add_argument('--model', default='dinov2_vits14', help='DINOv3 model variant')
    parser.add_argument('--confidence', type=float, default=0.5, help='Detection confidence threshold')
    parser.add_argument('--visualize', action='store_true', help='Save detection visualizations')
    
    args = parser.parse_args()
    
    # Initialize labeler
    labeler = DINOv3SemiAutoLabeler(model_name=args.model, device=args.device)
    labeler.confidence_threshold = args.confidence
    
    # Process dataset
    labeler.process_dataset(args.image_dir, args.output_dir, args.visualize)

if __name__ == '__main__':
    main()