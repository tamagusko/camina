#!/usr/bin/env python3
"""
CAMINA Dataset Creator - Grounding DINO Implementation for Urban Mobility Object Detection

This script implements a complete auto-labeling pipeline using Grounding DINO for 9-class
urban mobility object detection. Optimized for RTX 3060 (12GB VRAM) with dynamic
batch sizing and memory management.

Configuration is loaded from dataset_creator_config.json
Classes: pedestrian, cyclist, car, motorcycle, bus, truck, e-scooter, SUV, delivery_van

Author: CAMINA Team
Date: 2025-09-16
"""

import os
import sys
import gc
import json
import logging
import argparse
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, asdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp

# Third-party imports
import cv2
import numpy as np
import torch
import psutil
from tqdm import tqdm
import yaml
from PIL import Image
import torchvision.transforms as transforms

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dataset_creator_groundingDino.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "dataset_creator_config.json") -> Dict:
    """Load configuration from JSON file with error handling"""
    try:
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Validate required sections
        required_sections = ['classes', 'confidence_thresholds', 'text_prompts', 'memory_config', 'grounding_dino_config']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        logger.info(f"Configuration loaded successfully from {config_path}")
        return config

    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        raise


@dataclass
class ClassConfig:
    """9-class urban mobility detection configuration loaded from JSON"""
    # Class definitions with IDs
    CLASSES: Dict[int, str]

    # Class-specific confidence thresholds for better precision
    CONFIDENCE_THRESHOLDS: Dict[str, float]

    # Grounding DINO text prompts for each class
    TEXT_PROMPTS: Dict[str, List[str]]

    @classmethod
    def from_config(cls, config: Dict) -> 'ClassConfig':
        """Create ClassConfig from loaded configuration"""
        # Convert string keys to int for classes
        classes = {int(k): v for k, v in config['classes'].items()}

        return cls(
            CLASSES=classes,
            CONFIDENCE_THRESHOLDS=config['confidence_thresholds'],
            TEXT_PROMPTS=config['text_prompts']
        )

    @property
    def class_names(self) -> List[str]:
        """Get ordered list of class names"""
        return [self.CLASSES[i] for i in sorted(self.CLASSES.keys())]

    @property
    def num_classes(self) -> int:
        """Get total number of classes"""
        return len(self.CLASSES)

    def get_grounding_dino_prompt(self) -> str:
        """Create combined prompt for Grounding DINO"""
        # Use primary prompts for each class
        prompts = []
        for class_name in self.class_names:
            primary_prompt = self.TEXT_PROMPTS[class_name][0]
            prompts.append(primary_prompt)

        return ". ".join(prompts) + "."


@dataclass
class MemoryConfig:
    """Memory management configuration for RTX 3060 optimization"""
    max_vram_gb: float
    batch_size_base: int
    max_batch_size: int
    min_batch_size: int
    memory_threshold: float
    cleanup_interval: int

    @classmethod
    def from_config(cls, config: Dict) -> 'MemoryConfig':
        """Create MemoryConfig from loaded configuration"""
        memory_config = config['memory_config']
        return cls(
            max_vram_gb=memory_config['max_vram_gb'],
            batch_size_base=memory_config['batch_size_base'],
            max_batch_size=memory_config['max_batch_size'],
            min_batch_size=memory_config['min_batch_size'],
            memory_threshold=memory_config['memory_threshold'],
            cleanup_interval=memory_config['cleanup_interval']
        )

    def get_optimal_batch_size(self, image_size: Tuple[int, int]) -> int:
        """Calculate optimal batch size based on image dimensions and available VRAM"""
        # Estimate memory usage per image (empirical formula)
        pixels = image_size[0] * image_size[1]
        memory_per_image_mb = (pixels * 3 * 4) / (1024 * 1024)  # RGB float32

        # Add model overhead (Grounding DINO is memory-intensive)
        model_overhead_mb = 3000  # Higher than YOLO-World
        memory_per_image_mb += model_overhead_mb / self.batch_size_base

        # Calculate batch size
        available_memory_mb = self.max_vram_gb * 1024 * self.memory_threshold
        optimal_batch_size = int(available_memory_mb / memory_per_image_mb)

        return max(self.min_batch_size, min(optimal_batch_size, self.max_batch_size))


@dataclass
class Detection:
    """Object detection result with YOLO format compatibility"""
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]  # [center_x, center_y, width, height] normalized
    image_path: Optional[str] = None

    def to_yolo_format(self) -> str:
        """Convert to YOLO label format"""
        return f"{self.class_id} {self.bbox[0]:.6f} {self.bbox[1]:.6f} {self.bbox[2]:.6f} {self.bbox[3]:.6f}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'class_id': self.class_id,
            'class_name': self.class_name,
            'confidence': self.confidence,
            'bbox': self.bbox,
            'image_path': self.image_path
        }


class MemoryManager:
    """Advanced memory management for RTX 3060 optimization"""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.cleanup_counter = 0

    def get_gpu_memory_info(self) -> Dict[str, float]:
        """Get current GPU memory usage information"""
        if not torch.cuda.is_available():
            return {'used': 0, 'free': 0, 'total': 0}

        torch.cuda.synchronize()
        used = torch.cuda.memory_allocated() / (1024**3)  # GB
        cached = torch.cuda.memory_reserved() / (1024**3)  # GB
        total = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
        free = total - used

        return {
            'used': used,
            'free': free,
            'total': total,
            'cached': cached
        }

    def cleanup_memory(self, force: bool = False):
        """Clean up GPU and system memory"""
        self.cleanup_counter += 1

        if force or self.cleanup_counter >= self.config.cleanup_interval:
            # Clean GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            # Clean system memory
            gc.collect()

            self.cleanup_counter = 0
            logger.debug("Memory cleanup performed")

    def check_memory_pressure(self) -> bool:
        """Check if system is under memory pressure"""
        gpu_info = self.get_gpu_memory_info()
        memory_usage = gpu_info['used'] / gpu_info['total'] if gpu_info['total'] > 0 else 0

        return memory_usage > self.config.memory_threshold


class GroundingDINODetector:
    """Production-ready Grounding DINO detector with RTX 3060 optimizations"""

    def __init__(self, class_config: ClassConfig, memory_config: MemoryConfig,
                 grounding_dino_config: Dict, detection_settings: Dict = None):
        self.class_config = class_config
        self.memory_config = memory_config
        self.grounding_dino_config = grounding_dino_config
        self.memory_manager = MemoryManager(memory_config)
        self.detection_settings = detection_settings or {
            'initial_confidence': 0.1,
            'iou_threshold': 0.4,
            'min_bbox_area': 0.01,
            'supported_formats': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        }
        self.min_bbox_area = self.detection_settings.get('min_bbox_area', 0.01)

        # Model initialization
        self.model = None
        self.device = self._setup_device()
        self.current_batch_size = memory_config.batch_size_base

        # Grounding DINO specific components
        self.text_prompt = class_config.get_grounding_dino_prompt()

        # Statistics tracking
        self.stats = {
            'total_images': 0,
            'successful_detections': 0,
            'failed_images': 0,
            'total_detections': 0,
            'class_counts': {name: 0 for name in class_config.class_names},
            'processing_times': []
        }

        logger.info(f"GroundingDINODetector initialized on device: {self.device}")
        logger.info(f"Text prompt: {self.text_prompt}")

    def _setup_device(self) -> torch.device:
        """Setup optimal computing device"""
        if torch.cuda.is_available():
            device = torch.device('cuda')
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"Using GPU: {gpu_name} ({gpu_memory:.1f}GB)")
            return device
        elif torch.backends.mps.is_available():
            logger.info("Using Apple Metal Performance Shaders")
            return torch.device('mps')
        else:
            logger.warning("GPU not available, falling back to CPU")
            return torch.device('cpu')

    def initialize_model(self) -> bool:
        """Initialize Grounding DINO model with error handling"""
        try:
            # Import Grounding DINO components
            try:
                from groundingdino.util.inference import Model
                self.Model = Model
            except ImportError:
                logger.error("Grounding DINO not installed. Please install: pip install groundingdino-py")
                return False

            # Use groundingdino-py Model class (handles download automatically)
            logger.info("Loading Grounding DINO model (auto-download on first use)...")

            # Initialize model using groundingdino-py Model class
            import groundingdino
            import os
            package_path = os.path.dirname(groundingdino.__file__)
            config_path = os.path.join(package_path, "config", "GroundingDINO_SwinT_OGC.py")

            self.model = Model(
                model_config_path=config_path,
                model_checkpoint_path="groundingdino_swint_ogc.pth",
                device=str(self.device)
            )

            logger.info("Grounding DINO model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Grounding DINO model: {str(e)}")
            logger.error("This may be normal on first run - model will be downloaded")

            # Try fallback approach
            try:
                logger.info("Trying fallback model loading...")
                from groundingdino.util.inference import load_model

                # Try to download and cache the model locally
                import os
                cache_dir = os.path.expanduser("~/.cache/groundingdino")
                os.makedirs(cache_dir, exist_ok=True)

                weights_path = os.path.join(cache_dir, "groundingdino_swint_ogc.pth")

                if not os.path.exists(weights_path):
                    logger.info("Downloading model weights (this may take a few minutes)...")
                    import urllib.request
                    urllib.request.urlretrieve(
                        "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth",
                        weights_path
                    )

                import groundingdino
                package_path = os.path.dirname(groundingdino.__file__)
                config_path = os.path.join(package_path, "config", "GroundingDINO_SwinT_OGC.py")

                self.model = load_model(config_path, weights_path)
                self.model.to(self.device)
                self.model.eval()

                logger.info("Grounding DINO model loaded with fallback method")
                return True

            except Exception as fallback_e:
                logger.error(f"Fallback loading also failed: {str(fallback_e)}")
                return False

    def _preprocess_image(self, image: np.ndarray) -> torch.Tensor:
        """Preprocess image for Grounding DINO"""
        try:
            # Convert to PIL Image
            if len(image.shape) == 3 and image.shape[2] == 3:
                # RGB image
                pil_image = Image.fromarray(image)
            else:
                raise ValueError("Invalid image format")

            # Standard Grounding DINO preprocessing
            transform = transforms.Compose([
                transforms.Resize((800, 1333)),  # Grounding DINO standard input size
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])

            tensor_image = transform(pil_image).unsqueeze(0)
            return tensor_image.to(self.device)

        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            raise

    def _adaptive_batch_sizing(self, image_paths: List[Path]) -> int:
        """Determine optimal batch size based on image characteristics"""
        if not image_paths:
            return self.memory_config.min_batch_size

        # For Grounding DINO, we typically process one image at a time due to memory constraints
        # and the nature of the text-guided detection
        return 1

    def detect_batch(self, image_paths: List[Path]) -> List[List[Detection]]:
        """Process batch of images with memory optimization"""
        if not self.model:
            logger.error("Model not initialized")
            return [[] for _ in image_paths]

        batch_results = []
        start_time = time.time()

        try:
            # Import required utilities
            try:
                from groundingdino.util.utils import get_phrases_from_posmap
                from groundingdino.util.inference import annotate, predict
            except ImportError as e:
                logger.error(f"Failed to import Grounding DINO utilities: {str(e)}")
                raise RuntimeError("Grounding DINO installation incomplete or incorrect")

            # Process images one by one (Grounding DINO limitation)
            for img_path in image_paths:
                try:
                    # Load image using groundingdino's load_image function
                    from groundingdino.util.inference import load_image, predict

                    # Load image properly for Grounding DINO
                    image_source, image_tensor = load_image(str(img_path))

                    # Get image dimensions for bbox conversion
                    img_height, img_width = image_source.shape[:2]

                    # Run inference
                    box_threshold = self.grounding_dino_config.get('box_threshold', 0.25)
                    text_threshold = self.grounding_dino_config.get('text_threshold', 0.2)

                    try:
                        # Use predict function with properly loaded image
                        boxes, logits, phrases = predict(
                            model=self.model,
                            image=image_tensor,
                            caption=self.text_prompt,
                            box_threshold=box_threshold,
                            text_threshold=text_threshold,
                            device=self.device
                        )
                    except torch.cuda.OutOfMemoryError:
                        logger.error(f"GPU out of memory processing {img_path}. Skipping.")
                        batch_results.append([])
                        self.memory_manager.cleanup_memory(force=True)
                        continue
                    except Exception as inference_e:
                        logger.error(f"Inference failed for {img_path}: {str(inference_e)}")
                        batch_results.append([])
                        continue

                    # Process results
                    img_shape = (img_height, img_width, 3)  # H, W, C format
                    detections = self._process_grounding_dino_result(
                        boxes, logits, phrases, img_path, img_shape
                    )
                    batch_results.append(detections)

                    # Update statistics
                    self.stats['total_detections'] += len(detections)
                    for det in detections:
                        self.stats['class_counts'][det.class_name] += 1

                except Exception as e:
                    logger.error(f"Error processing {img_path}: {str(e)}")
                    batch_results.append([])
                    continue

            # Update processing time
            processing_time = time.time() - start_time
            self.stats['processing_times'].append(processing_time)

            # Memory management
            self.memory_manager.cleanup_memory()

            return batch_results

        except torch.cuda.OutOfMemoryError:
            logger.error("GPU out of memory during batch processing")
            self.memory_manager.cleanup_memory(force=True)
            return [[] for _ in image_paths]
        except ImportError as e:
            logger.error(f"Missing required dependencies: {str(e)}")
            return [[] for _ in image_paths]
        except Exception as e:
            logger.error(f"Batch detection failed: {str(e)}", exc_info=True)
            return [[] for _ in image_paths]

    def _process_grounding_dino_result(self, boxes: torch.Tensor, logits: torch.Tensor,
                                     phrases: List[str], img_path: Path,
                                     img_shape: Tuple[int, int, int]) -> List[Detection]:
        """Process Grounding DINO result into Detection objects"""
        detections = []

        try:
            if len(boxes) == 0:
                return detections

            img_height, img_width = img_shape[:2]

            for i, (box, logit, phrase) in enumerate(zip(boxes, logits, phrases)):
                # Extract box coordinates (in format [cx, cy, w, h] normalized)
                cx, cy, w, h = box.cpu().numpy()

                # Convert to confidence score
                confidence = float(torch.sigmoid(logit).cpu())

                # Map phrase to class
                class_name, class_id = self._map_phrase_to_class(phrase)
                if class_name is None:
                    continue

                # Apply class-specific confidence threshold
                threshold = self.class_config.CONFIDENCE_THRESHOLDS[class_name]
                if confidence < threshold:
                    continue

                # Validate bbox (already in normalized YOLO format)
                bbox_norm = [cx, cy, w, h]
                if not self._is_valid_bbox(bbox_norm):
                    continue

                # Create detection
                detection = Detection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=confidence,
                    bbox=bbox_norm,
                    image_path=str(img_path)
                )

                detections.append(detection)

        except Exception as e:
            logger.error(f"Error processing Grounding DINO result for {img_path}: {str(e)}")

        return detections

    def _map_phrase_to_class(self, phrase: str) -> Tuple[Optional[str], Optional[int]]:
        """Map detected phrase to our class system"""
        phrase = phrase.lower().strip()

        # Direct mapping attempts
        for class_id, class_name in self.class_config.CLASSES.items():
            prompts = self.class_config.TEXT_PROMPTS[class_name]

            # Check if phrase matches any of our prompts
            for prompt in prompts:
                if phrase in prompt.lower() or prompt.lower() in phrase:
                    return class_name, class_id

        # Fuzzy matching for common variations
        class_mappings = {
            'person': 'pedestrian',
            'people': 'pedestrian',
            'human': 'pedestrian',
            'bicycle': 'cyclist',
            'bike': 'cyclist',
            'cycle': 'cyclist',
            'vehicle': 'car',  # Default vehicle mapping
            'automobile': 'car',
            'sedan': 'car',
            'motor': 'motorcycle',  # Could be motorcycle
            'van': 'delivery_van',  # Default van mapping
        }

        for key, mapped_class in class_mappings.items():
            if key in phrase:
                if mapped_class in self.class_config.CLASSES.values():
                    class_id = next(k for k, v in self.class_config.CLASSES.items() if v == mapped_class)
                    return mapped_class, class_id

        return None, None

    def _is_valid_bbox(self, bbox: List[float]) -> bool:
        """Validate bbox coordinates"""
        center_x, center_y, width, height = bbox

        # Check bounds
        if not (0 <= center_x <= 1 and 0 <= center_y <= 1):
            return False
        if not (0 < width <= 1 and 0 < height <= 1):
            return False

        # Check minimum size (configurable)
        if width * height < self.min_bbox_area:
            return False

        return True

    def process_directory(self,
                         input_dir: Path,
                         output_dir: Path,
                         batch_size: Optional[int] = None,
                         max_workers: int = 1) -> Dict:
        """Process entire directory with optimized batching"""
        logger.info(f"Processing directory: {input_dir}")

        # Find all image files (using config)
        image_extensions = set(self.detection_settings['supported_formats'])
        image_paths = []
        for ext in image_extensions:
            image_paths.extend(input_dir.glob(f'**/*{ext}'))
            image_paths.extend(input_dir.glob(f'**/*{ext.upper()}'))

        if not image_paths:
            logger.error(f"No images found in {input_dir}")
            return {'success': False, 'error': 'No images found'}

        logger.info(f"Found {len(image_paths)} images")

        # Create output directories
        images_output_dir = output_dir / 'images'
        labels_output_dir = output_dir / 'labels'
        images_output_dir.mkdir(parents=True, exist_ok=True)
        labels_output_dir.mkdir(parents=True, exist_ok=True)

        # Determine batch size (Grounding DINO typically processes one image at a time)
        if batch_size is None:
            batch_size = self._adaptive_batch_sizing(image_paths)

        self.current_batch_size = batch_size
        logger.info(f"Using batch size: {batch_size}")

        # Process in batches
        self.stats['total_images'] = len(image_paths)

        successful_images = 0
        failed_images = 0

        with tqdm(total=len(image_paths), desc="Processing images") as pbar:
            for batch_idx in range(0, len(image_paths), batch_size):
                batch_paths = image_paths[batch_idx:batch_idx + batch_size]

                # Process batch
                batch_results = self.detect_batch(batch_paths)

                # Save results
                for img_path, detections in zip(batch_paths, batch_results):
                    try:
                        # Copy image to output directory
                        output_img_path = images_output_dir / img_path.name
                        if not output_img_path.exists():
                            import shutil
                            shutil.copy2(img_path, output_img_path)

                        # Save labels
                        if detections:
                            label_path = labels_output_dir / f"{img_path.stem}.txt"
                            with open(label_path, 'w') as f:
                                for det in detections:
                                    f.write(det.to_yolo_format() + '\n')

                        successful_images += 1

                    except Exception as e:
                        logger.error(f"Failed to save results for {img_path}: {str(e)}")
                        failed_images += 1

                    pbar.update(1)

                # Memory management
                if batch_idx % (batch_size * 10) == 0:  # Every 10 batches
                    self.memory_manager.cleanup_memory(force=True)

        # Update statistics
        self.stats['successful_detections'] = successful_images
        self.stats['failed_images'] = failed_images

        # Generate summary
        return self._generate_summary(output_dir)

    def _generate_summary(self, output_dir: Path) -> Dict:
        """Generate processing summary and statistics"""
        summary = {
            'success': True,
            'output_directory': str(output_dir),
            'statistics': dict(self.stats),
            'processing_info': {
                'device': str(self.device),
                'batch_size': self.current_batch_size,
                'avg_processing_time': np.mean(self.stats['processing_times']) if self.stats['processing_times'] else 0,
                'total_processing_time': sum(self.stats['processing_times']),
                'model_type': 'Grounding DINO'
            }
        }

        # Save summary to file
        summary_path = output_dir / 'dataset_creation_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        # Log summary
        logger.info("=== DATASET CREATION SUMMARY ===")
        logger.info(f"Total images processed: {self.stats['total_images']}")
        logger.info(f"Successful: {self.stats['successful_detections']}")
        logger.info(f"Failed: {self.stats['failed_images']}")
        logger.info(f"Total detections: {self.stats['total_detections']}")
        logger.info(f"Average processing time: {summary['processing_info']['avg_processing_time']:.2f}s per batch")

        logger.info("Class distribution:")
        for class_name, count in self.stats['class_counts'].items():
            if count > 0:
                logger.info(f"  {class_name}: {count}")

        return summary


class DatasetValidator:
    """Validate and analyze created dataset"""

    def __init__(self, class_config: ClassConfig):
        self.class_config = class_config

    def validate_dataset(self, dataset_dir: Path) -> Dict:
        """Validate dataset structure and content"""
        logger.info("Validating dataset structure...")

        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }

        # Check directory structure
        required_dirs = ['images', 'labels']
        for dir_name in required_dirs:
            dir_path = dataset_dir / dir_name
            if not dir_path.exists():
                validation_results['errors'].append(f"Missing directory: {dir_name}")
                validation_results['valid'] = False

        if not validation_results['valid']:
            return validation_results

        # Validate images and labels
        images_dir = dataset_dir / 'images'
        labels_dir = dataset_dir / 'labels'

        image_files = list(images_dir.glob('*'))
        label_files = list(labels_dir.glob('*.txt'))

        # Check for orphaned files
        image_stems = {f.stem for f in image_files}
        label_stems = {f.stem for f in label_files}

        orphaned_images = image_stems - label_stems
        orphaned_labels = label_stems - image_stems

        if orphaned_images:
            validation_results['warnings'].append(f"Images without labels: {len(orphaned_images)}")

        if orphaned_labels:
            validation_results['warnings'].append(f"Labels without images: {len(orphaned_labels)}")

        # Analyze label content
        class_distribution = {name: 0 for name in self.class_config.class_names}
        total_annotations = 0
        invalid_labels = 0

        for label_file in label_files:
            try:
                with open(label_file, 'r') as f:
                    lines = f.readlines()

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split()
                    if len(parts) != 5:
                        invalid_labels += 1
                        continue

                    try:
                        class_id = int(parts[0])
                        if class_id in self.class_config.CLASSES:
                            class_name = self.class_config.CLASSES[class_id]
                            class_distribution[class_name] += 1
                            total_annotations += 1
                        else:
                            invalid_labels += 1
                    except ValueError:
                        invalid_labels += 1

            except Exception as e:
                validation_results['errors'].append(f"Error reading {label_file}: {str(e)}")

        # Update statistics
        validation_results['statistics'] = {
            'total_images': len(image_files),
            'total_labels': len(label_files),
            'total_annotations': total_annotations,
            'invalid_labels': invalid_labels,
            'class_distribution': class_distribution,
            'orphaned_images': len(orphaned_images),
            'orphaned_labels': len(orphaned_labels)
        }

        logger.info("Dataset validation completed")
        return validation_results


def create_dataset_yaml(output_dir: Path, class_config: ClassConfig) -> Path:
    """Create YOLO dataset configuration file"""
    yaml_config = {
        'path': str(output_dir.absolute()),
        'train': 'images',
        'val': 'images',  # Will be split later
        'test': 'images',  # Will be split later
        'nc': class_config.num_classes,
        'names': {i: name for i, name in class_config.CLASSES.items()}
    }

    yaml_path = output_dir / 'dataset.yaml'
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Dataset YAML created: {yaml_path}")
    return yaml_path


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="CAMINA Dataset Creator - Grounding DINO implementation for urban mobility object detection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        'input_dir',
        type=Path,
        help='Directory containing input images'
    )

    parser.add_argument(
        'output_dir',
        type=Path,
        help='Directory to save labeled dataset'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=1,
        help='Batch size for processing (Grounding DINO typically uses 1)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=1,
        help='Maximum number of worker processes'
    )

    parser.add_argument(
        '--confidence-scale',
        type=float,
        default=1.0,
        help='Scale factor for confidence thresholds'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate dataset after creation'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='dataset_creator_config.json',
        help='Path to configuration file (default: dataset_creator_config.json)'
    )

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate input directory
    if not args.input_dir.exists():
        logger.error(f"Input directory not found: {args.input_dir}")
        return 1

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== CAMINA Dataset Creator (Grounding DINO) Started ===")
    logger.info(f"Input directory: {args.input_dir}")
    logger.info(f"Output directory: {args.output_dir}")

    # Load configuration from JSON file
    try:
        config_data = load_config(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {args.config}")
        logger.error("Please ensure the config file exists or specify a different path with --config")
        return 1
    except ValueError as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {str(e)}", exc_info=True)
        return 1

    # Initialize configurations
    class_config = ClassConfig.from_config(config_data)
    memory_config = MemoryConfig.from_config(config_data)
    grounding_dino_config = config_data.get('grounding_dino_config', {})
    detection_settings = config_data.get('detection_settings', {})

    # Apply confidence scale
    if args.confidence_scale != 1.0:
        for class_name in class_config.CONFIDENCE_THRESHOLDS:
            class_config.CONFIDENCE_THRESHOLDS[class_name] *= args.confidence_scale
        logger.info(f"Confidence thresholds scaled by {args.confidence_scale}")

    # Initialize detector
    detector = GroundingDINODetector(class_config, memory_config, grounding_dino_config, detection_settings)

    # Initialize model
    if not detector.initialize_model():
        logger.error("Failed to initialize Grounding DINO model")
        return 1

    try:
        # Process dataset
        logger.info("Starting dataset processing with Grounding DINO...")
        results = detector.process_directory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            max_workers=args.max_workers
        )

        if not results['success']:
            logger.error(f"Dataset creation failed: {results.get('error', 'Unknown error')}")
            return 1

        logger.info("Dataset processing completed successfully")

        # Create dataset YAML
        try:
            create_dataset_yaml(args.output_dir, class_config)
            logger.info("Dataset YAML configuration created")
        except Exception as e:
            logger.error(f"Failed to create dataset YAML: {str(e)}")
            return 1

        # Validate dataset if requested
        if args.validate:
            try:
                logger.info("Starting dataset validation...")
                validator = DatasetValidator(class_config)
                validation_results = validator.validate_dataset(args.output_dir)

                if validation_results['valid']:
                    logger.info("Dataset validation passed")
                else:
                    logger.warning("Dataset validation found issues")
                    for error in validation_results['errors']:
                        logger.error(f"Validation error: {error}")
                    for warning in validation_results['warnings']:
                        logger.warning(f"Validation warning: {warning}")

            except Exception as e:
                logger.error(f"Dataset validation failed: {str(e)}", exc_info=True)
                logger.warning("Continuing despite validation errors")

        logger.info("=== Dataset Creation Completed Successfully ===")
        return 0

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        detector.memory_manager.cleanup_memory(force=True)
        return 1
    except torch.cuda.OutOfMemoryError:
        logger.error("GPU out of memory. Try reducing batch size or using smaller images")
        detector.memory_manager.cleanup_memory(force=True)
        return 1
    except ImportError as e:
        logger.error(f"Missing required dependencies: {str(e)}")
        logger.error("Please install Grounding DINO following the official installation guide")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during dataset creation: {str(e)}", exc_info=True)
        if hasattr(detector, 'memory_manager'):
            detector.memory_manager.cleanup_memory(force=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())