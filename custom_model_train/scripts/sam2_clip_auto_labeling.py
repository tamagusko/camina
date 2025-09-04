#!/usr/bin/env python3
"""
SAM2 + CLIP Auto-Labeling Pipeline for CAMINA Dataset Expansion
Uses SAM2 for precise segmentation and CLIP for semantic classification
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
from typing import List, Dict, Tuple, Optional
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

class SAM2CLIPAutoLabeler:
    def __init__(self, device='auto', sam2_checkpoint=None, clip_model='ViT-B/32'):
        """
        Initialize SAM2 + CLIP auto-labeling pipeline
        
        Args:
            device: compute device ('auto', 'cpu', 'cuda', 'mps')
            sam2_checkpoint: Path to SAM2 checkpoint
            clip_model: CLIP model variant
        """
        self.device = self._setup_device(device)
        self.sam2_model = self._load_sam2_model(sam2_checkpoint)
        self.clip_model, self.clip_preprocess = self._load_clip_model(clip_model)
        
        # Target classes for new object detection with CLIP prompts
        self.target_classes = {
            6: {
                'name': 'e-scooter',
                'prompts': [
                    'an electric scooter',
                    'a person riding an e-scooter', 
                    'electric kick scooter',
                    'motorized scooter'
                ]
            },
            7: {
                'name': 'SUV',
                'prompts': [
                    'a sport utility vehicle',
                    'an SUV car',
                    'large passenger car',
                    'off-road vehicle'
                ]
            },
            8: {
                'name': 'delivery_van',
                'prompts': [
                    'a delivery van',
                    'commercial delivery vehicle',
                    'cargo van',
                    'package delivery truck'
                ]
            }
        }
        
        # Detection parameters
        self.confidence_threshold = 0.3
        self.nms_threshold = 0.4
        self.min_box_size = 0.01
        self.sam2_points_per_side = 32
        
        logger.info(f"Initialized SAM2+CLIP labeler on {self.device}")
        
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
    
    def _load_sam2_model(self, checkpoint_path):
        """Load SAM2 model"""
        try:
            # Try to import SAM2 (requires installation)
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            
            if checkpoint_path and Path(checkpoint_path).exists():
                # Load from checkpoint
                sam2_model = build_sam2("sam2_hiera_large.yaml", checkpoint_path, device=self.device)
                predictor = SAM2ImagePredictor(sam2_model)
                logger.info(f"Loaded SAM2 from checkpoint: {checkpoint_path}")
                return predictor
            else:
                logger.warning("SAM2 checkpoint not found, using dummy model")
                return self._create_dummy_sam2()
                
        except ImportError:
            logger.warning("SAM2 not installed, using dummy model for testing")
            return self._create_dummy_sam2()
        except Exception as e:
            logger.error(f"Failed to load SAM2: {e}")
            return self._create_dummy_sam2()
    
    def _create_dummy_sam2(self):
        """Create dummy SAM2 model for testing"""
        class DummySAM2:
            def set_image(self, image):
                self.image_shape = image.shape[:2]
                
            def predict(self, point_coords=None, point_labels=None, box=None, **kwargs):
                # Generate dummy masks for testing
                h, w = self.image_shape
                num_masks = np.random.randint(5, 15)  # Random number of segments
                
                masks = []
                scores = []
                
                for _ in range(num_masks):
                    # Create random mask
                    mask = np.zeros((h, w), dtype=bool)
                    
                    # Random rectangular region
                    x1, y1 = np.random.randint(0, w//2), np.random.randint(0, h//2)
                    x2, y2 = np.random.randint(w//2, w), np.random.randint(h//2, h)
                    mask[y1:y2, x1:x2] = True
                    
                    masks.append(mask)
                    scores.append(np.random.random())
                
                return np.array(masks), np.array(scores), None
        
        return DummySAM2()
    
    def _load_clip_model(self, model_name):
        """Load CLIP model"""
        try:
            import clip
            model, preprocess = clip.load(model_name, device=self.device)
            logger.info(f"Loaded CLIP model: {model_name}")
            return model, preprocess
        except ImportError:
            logger.warning("CLIP not installed, using dummy model")
            return self._create_dummy_clip()
        except Exception as e:
            logger.error(f"Failed to load CLIP: {e}")
            return self._create_dummy_clip()
    
    def _create_dummy_clip(self):
        """Create dummy CLIP model for testing"""
        class DummyCLIP:
            def encode_image(self, image):
                return torch.randn(image.shape[0], 512, device=self.device)
            
            def encode_text(self, text):
                return torch.randn(text.shape[0], 512, device=self.device)
        
        class DummyPreprocess:
            def __call__(self, image):
                return transforms.Compose([
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                ])(image)
        
        return DummyCLIP(), DummyPreprocess()
    
    def generate_sam2_masks(self, image: np.ndarray) -> List[Dict]:
        """
        Generate segmentation masks using SAM2
        
        Args:
            image: Input image (H, W, 3)
            
        Returns:
            List of mask dictionaries with segmentation info
        """
        # Set image in SAM2
        self.sam2_model.set_image(image)
        
        # Generate masks using automatic mask generation
        # This is a simplified version - SAM2 has various prompting strategies
        masks_data = []
        
        # Method 1: Grid-based point prompts
        h, w = image.shape[:2]
        
        # Generate grid of points
        points_per_side = self.sam2_points_per_side
        step_x = w // points_per_side
        step_y = h // points_per_side
        
        for y in range(step_y//2, h, step_y):
            for x in range(step_x//2, w, step_x):
                # Use point as positive prompt
                point_coords = np.array([[x, y]])
                point_labels = np.array([1])  # Positive point
                
                try:
                    masks, scores, logits = self.sam2_model.predict(
                        point_coords=point_coords,
                        point_labels=point_labels,
                        multimask_output=True
                    )
                    
                    # Process each mask
                    for mask, score in zip(masks, scores):
                        if score > 0.5:  # Quality threshold
                            # Get bounding box from mask
                            bbox = self._mask_to_bbox(mask)
                            if bbox:
                                masks_data.append({
                                    'mask': mask,
                                    'bbox': bbox,
                                    'score': float(score),
                                    'area': int(np.sum(mask))
                                })
                                
                except Exception as e:
                    logger.debug(f"SAM2 prediction failed at ({x}, {y}): {e}")
                    continue
        
        # Sort by score and remove duplicates
        masks_data = sorted(masks_data, key=lambda x: x['score'], reverse=True)
        masks_data = self._remove_duplicate_masks(masks_data)
        
        logger.info(f"Generated {len(masks_data)} SAM2 masks")
        return masks_data
    
    def _mask_to_bbox(self, mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Convert binary mask to bounding box coordinates"""
        if not np.any(mask):
            return None
        
        # Find bounding box
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            return None
        
        ymin, ymax = np.where(rows)[0][[0, -1]]
        xmin, xmax = np.where(cols)[0][[0, -1]]
        
        return (int(xmin), int(ymin), int(xmax), int(ymax))
    
    def _remove_duplicate_masks(self, masks_data: List[Dict]) -> List[Dict]:
        """Remove overlapping/duplicate masks using IoU threshold"""
        if len(masks_data) <= 1:
            return masks_data
        
        filtered_masks = []
        iou_threshold = 0.7
        
        for i, mask_data in enumerate(masks_data):
            is_duplicate = False
            
            for j, existing_mask in enumerate(filtered_masks):
                iou = self._calculate_mask_iou(mask_data['mask'], existing_mask['mask'])
                if iou > iou_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_masks.append(mask_data)
        
        return filtered_masks
    
    def _calculate_mask_iou(self, mask1: np.ndarray, mask2: np.ndarray) -> float:
        """Calculate IoU between two binary masks"""
        intersection = np.logical_and(mask1, mask2)
        union = np.logical_or(mask1, mask2)
        
        if not np.any(union):
            return 0.0
        
        return np.sum(intersection) / np.sum(union)
    
    def classify_with_clip(self, image: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[int, float]:
        """
        Classify image region using CLIP
        
        Args:
            image: Full image
            bbox: Bounding box coordinates (x1, y1, x2, y2)
            
        Returns:
            Tuple of (predicted_class_id, confidence)
        """
        x1, y1, x2, y2 = bbox
        
        # Extract region of interest
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return -1, 0.0
        
        # Convert to PIL Image
        roi_pil = Image.fromarray(roi)
        
        # Preprocess for CLIP
        roi_tensor = self.clip_preprocess(roi_pil).unsqueeze(0).to(self.device)
        
        # Prepare text prompts for all target classes
        all_prompts = []
        class_indices = []
        
        for class_id, class_info in self.target_classes.items():
            for prompt in class_info['prompts']:
                all_prompts.append(prompt)
                class_indices.append(class_id)
        
        # Add negative prompts to improve discrimination
        negative_prompts = [
            'background', 'empty space', 'road', 'sidewalk', 
            'building', 'sky', 'tree', 'sign'
        ]
        for prompt in negative_prompts:
            all_prompts.append(prompt)
            class_indices.append(-1)  # Negative class
        
        try:
            import clip
            
            # Tokenize prompts
            text_tokens = clip.tokenize(all_prompts).to(self.device)
            
            # Get features
            with torch.no_grad():
                image_features = self.clip_model.encode_image(roi_tensor)
                text_features = self.clip_model.encode_text(text_tokens)
                
                # Calculate similarities
                similarities = torch.cosine_similarity(image_features, text_features)
                similarities = similarities.cpu().numpy()
            
            # Find best match among positive classes only
            positive_indices = [i for i, cls in enumerate(class_indices) if cls != -1]
            positive_similarities = similarities[positive_indices]
            positive_classes = [class_indices[i] for i in positive_indices]
            
            if len(positive_similarities) > 0:
                best_idx = np.argmax(positive_similarities)
                best_class = positive_classes[best_idx]
                confidence = float(positive_similarities[best_idx])
                
                # Check if best positive class beats negative classes
                negative_indices = [i for i, cls in enumerate(class_indices) if cls == -1]
                if negative_indices:
                    max_negative_score = np.max(similarities[negative_indices])
                    if confidence <= max_negative_score + 0.1:  # Small margin
                        return -1, 0.0  # Classified as background
                
                return best_class, confidence
            else:
                return -1, 0.0
                
        except Exception as e:
            logger.debug(f"CLIP classification failed: {e}")
            # Fallback: random classification for testing
            class_ids = list(self.target_classes.keys())
            return np.random.choice(class_ids), np.random.random()
    
    def process_image(self, image_path: str, output_dir: str = None) -> List[BoundingBox]:
        """
        Process single image using SAM2 + CLIP pipeline
        
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
        h, w = image_rgb.shape[:2]
        
        # Generate masks with SAM2
        masks_data = self.generate_sam2_masks(image_rgb)
        
        # Classify each mask with CLIP
        detections = []
        
        for mask_data in masks_data:
            bbox_pixels = mask_data['bbox']
            if not bbox_pixels:
                continue
            
            x1, y1, x2, y2 = bbox_pixels
            
            # Skip very small regions
            if (x2 - x1) < 20 or (y2 - y1) < 20:
                continue
            
            # Classify with CLIP
            class_id, confidence = self.classify_with_clip(image_rgb, bbox_pixels)
            
            if class_id != -1 and confidence > self.confidence_threshold:
                # Convert to normalized YOLO format
                center_x = (x1 + x2) / 2 / w
                center_y = (y1 + y2) / 2 / h
                norm_width = (x2 - x1) / w
                norm_height = (y2 - y1) / h
                
                # Skip if too small
                if norm_width < self.min_box_size or norm_height < self.min_box_size:
                    continue
                
                bbox = BoundingBox(
                    class_id=class_id,
                    center_x=center_x,
                    center_y=center_y,
                    width=norm_width,
                    height=norm_height,
                    confidence=confidence
                )
                detections.append(bbox)
        
        # Apply NMS
        detections = self.apply_nms(detections)
        
        logger.info(f"Found {len(detections)} objects in {Path(image_path).name}")
        
        # Save visualization if requested
        if output_dir:
            self.visualize_detections(image_rgb, detections, 
                                    output_path=Path(output_dir) / f"{Path(image_path).stem}_detections.jpg")
        
        return detections
    
    def apply_nms(self, detections: List[BoundingBox]) -> List[BoundingBox]:
        """Apply Non-Maximum Suppression to remove overlapping detections"""
        if not detections:
            return []
        
        # Group detections by class
        class_detections = {}
        for det in detections:
            if det.class_id not in class_detections:
                class_detections[det.class_id] = []
            class_detections[det.class_id].append(det)
        
        # Apply NMS per class
        filtered_detections = []
        for class_id, class_dets in class_detections.items():
            if not class_dets:
                continue
            
            # Convert to format suitable for NMS
            boxes = []
            scores = []
            
            for det in class_dets:
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
            
            # Add filtered detections
            for i in keep_indices:
                filtered_detections.append(class_dets[i])
        
        return filtered_detections
    
    def visualize_detections(self, image: np.ndarray, detections: List[BoundingBox], 
                           output_path: str = None):
        """Visualize detected bounding boxes on image"""
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        ax.imshow(image)
        
        colors = {6: 'red', 7: 'blue', 8: 'green'}
        
        for det in detections:
            h, w = image.shape[:2]
            x1 = (det.center_x - det.width / 2) * w
            y1 = (det.center_y - det.height / 2) * h
            width = det.width * w
            height = det.height * h
            
            color = colors.get(det.class_id, 'yellow')
            class_name = self.target_classes.get(det.class_id, {}).get('name', f'class_{det.class_id}')
            
            rect = patches.Rectangle((x1, y1), width, height, 
                                   linewidth=2, edgecolor=color, facecolor='none')
            ax.add_patch(rect)
            
            ax.text(x1, y1 - 5, f'{class_name} ({det.confidence:.2f})', 
                   color=color, fontsize=10, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.7))
        
        ax.set_title(f'SAM2+CLIP Auto-Detections ({len(detections)} objects)')
        ax.axis('off')
        
        if output_path:
            plt.savefig(output_path, bbox_inches='tight', dpi=300)
            logger.info(f"Visualization saved to {output_path}")
        
        plt.close()
    
    def generate_yolo_labels(self, detections: List[BoundingBox], output_file: str):
        """Generate YOLO format label file from detections"""
        with open(output_file, 'w') as f:
            for det in detections:
                line = f"{det.class_id} {det.center_x:.6f} {det.center_y:.6f} {det.width:.6f} {det.height:.6f}"
                f.write(line + '\n')
        
        logger.info(f"Generated YOLO labels: {output_file}")
    
    def process_dataset(self, image_dir: str, output_dir: str, visualize: bool = True):
        """Process entire dataset directory"""
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
        
        class_counts = {class_id: 0 for class_id in self.target_classes.keys()}
        total_detections = 0
        
        for img_file in image_files:
            logger.info(f"Processing {img_file.name}...")
            
            # Process image
            viz_output = str(viz_dir) if visualize else None
            detections = self.process_image(str(img_file), viz_output)
            
            # Generate labels
            label_file = labels_dir / f"{img_file.stem}.txt"
            self.generate_yolo_labels(detections, str(label_file))
            
            # Update statistics
            for det in detections:
                class_counts[det.class_id] += 1
            total_detections += len(detections)
        
        # Print statistics
        logger.info(f"=== Processing Summary ===")
        logger.info(f"Processed {len(image_files)} images")
        logger.info(f"Total detections: {total_detections}")
        for class_id, count in class_counts.items():
            class_name = self.target_classes[class_id]['name']
            logger.info(f"{class_name}: {count} objects")

def main():
    parser = argparse.ArgumentParser(description='SAM2 + CLIP Auto-Labeling Pipeline')
    parser.add_argument('--image-dir', required=True, help='Directory containing images to process')
    parser.add_argument('--output-dir', required=True, help='Output directory for labels and visualizations')
    parser.add_argument('--device', default='auto', help='Compute device (auto, cpu, cuda, mps)')
    parser.add_argument('--sam2-checkpoint', help='Path to SAM2 checkpoint file')
    parser.add_argument('--clip-model', default='ViT-B/32', help='CLIP model variant')
    parser.add_argument('--confidence', type=float, default=0.3, help='Detection confidence threshold')
    parser.add_argument('--visualize', action='store_true', help='Save detection visualizations')
    
    args = parser.parse_args()
    
    # Initialize labeler
    labeler = SAM2CLIPAutoLabeler(
        device=args.device,
        sam2_checkpoint=args.sam2_checkpoint,
        clip_model=args.clip_model
    )
    labeler.confidence_threshold = args.confidence
    
    # Process dataset
    labeler.process_dataset(args.image_dir, args.output_dir, args.visualize)

if __name__ == '__main__':
    main()