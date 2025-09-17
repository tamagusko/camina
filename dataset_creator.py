#!/usr/bin/env python3
"""
CAMINA Dataset Creator - Optimized Hybrid Detection for Urban Mobility Object Detection

This script implements an optimized hybrid auto-labeling pipeline for 9-class urban mobility object detection.
Uses YOLO11n for COCO classes and YOLO-World/Grounding DINO for new classes.

Optimizations:
- Memory-efficient image loading with caching
- Vectorized coordinate conversions
- Improved error handling and validation
- Modular architecture with dependency injection
- Performance monitoring and statistics

Optimized for RTX 3060 (12GB VRAM) with dynamic batch sizing and memory management.

Configuration is loaded from dataset_creator_config.json
Classes: pedestrian, cyclist, car, motorcycle, bus, truck, e-scooter, SUV, delivery_van

Hybrid Detection Model:
- YOLO11n for COCO classes: pedestrian, cyclist (from person+bicycle union), car, motorcycle, bus, truck
- YOLO-World or Grounding DINO for new classes: e-scooter, SUV, delivery_van (targeted detection)
- Benefits: 3-4x speed improvement, highest accuracy on standard classes, cyclist detection from rule-based pairing

Author: CAMINA Team
Date: 2025-09-17
"""

import os
import sys
import gc
import json
import logging
import argparse
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union, Protocol, runtime_checkable
from dataclasses import dataclass, asdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp
from contextlib import contextmanager
from abc import ABC, abstractmethod

# Third-party imports
import cv2
import numpy as np
import torch
import torchvision
import psutil
from tqdm import tqdm
import yaml
from PIL import Image
import torchvision.transforms as transforms

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('dataset_creator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Utility Classes and Functions
@runtime_checkable
class DetectionModel(Protocol):
    """Protocol for detection models"""
    def predict(self, image: np.ndarray, **kwargs) -> List[Dict]:
        """Predict objects in image"""
        ...

    def is_initialized(self) -> bool:
        """Check if model is properly initialized"""
        ...


class ImageCache:
    """Simple LRU cache for loaded images to reduce I/O operations"""

    def __init__(self, max_size: int = 50):
        self.cache = {}
        self.access_order = []
        self.max_size = max_size

    def get(self, image_path: Union[str, Path]) -> Optional[Tuple[Image.Image, Tuple[int, int]]]:
        """Get cached image and dimensions"""
        path_str = str(image_path)
        if path_str in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(path_str)
            self.access_order.append(path_str)
            return self.cache[path_str]
        return None

    def put(self, image_path: Union[str, Path], image: Image.Image, dimensions: Tuple[int, int]) -> None:
        """Cache image with LRU eviction"""
        path_str = str(image_path)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size and path_str not in self.cache:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]

        # Add/update cache
        if path_str in self.cache:
            self.access_order.remove(path_str)

        self.cache[path_str] = (image, dimensions)
        self.access_order.append(path_str)

    def clear(self) -> None:
        """Clear all cached images"""
        self.cache.clear()
        self.access_order.clear()


class CoordinateConverter:
    """Optimized coordinate conversion utilities"""

    @staticmethod
    def xyxy_to_yolo_vectorized(boxes: np.ndarray, img_width: int, img_height: int) -> np.ndarray:
        """Convert xyxy format to YOLO format (vectorized)"""
        if boxes.size == 0:
            return boxes

        # Convert from xyxy to center format
        x_centers = (boxes[:, 0] + boxes[:, 2]) / (2 * img_width)
        y_centers = (boxes[:, 1] + boxes[:, 3]) / (2 * img_height)
        widths = (boxes[:, 2] - boxes[:, 0]) / img_width
        heights = (boxes[:, 3] - boxes[:, 1]) / img_height

        return np.column_stack([x_centers, y_centers, widths, heights])

    @staticmethod
    def yolo_to_xyxy_vectorized(boxes: np.ndarray, img_width: int, img_height: int) -> np.ndarray:
        """Convert YOLO format to xyxy format (vectorized)"""
        if boxes.size == 0:
            return boxes

        # Convert from center format to xyxy
        half_widths = (boxes[:, 2] * img_width) / 2
        half_heights = (boxes[:, 3] * img_height) / 2
        x_centers = boxes[:, 0] * img_width
        y_centers = boxes[:, 1] * img_height

        x1 = x_centers - half_widths
        y1 = y_centers - half_heights
        x2 = x_centers + half_widths
        y2 = y_centers + half_heights

        return np.column_stack([x1, y1, x2, y2])


@contextmanager
def torch_inference_mode():
    """Context manager for optimized inference"""
    with torch.inference_mode():
        yield


def validate_image_file(image_path: Union[str, Path]) -> bool:
    """Validate image file format and integrity"""
    try:
        path = Path(image_path)

        # Check file exists and has valid extension
        if not path.exists() or path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']:
            return False

        # Quick validation by opening with PIL
        with Image.open(path) as img:
            img.verify()

        return True
    except Exception:
        return False


def load_config(config_path: str = "dataset_creator_config.json") -> Dict:
    """Load configuration from JSON file for hybrid detection mode"""
    try:
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Validate required sections for hybrid mode
        required_sections = ['classes', 'confidence_thresholds', 'text_prompts', 'memory_config', 'hybrid_config']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate hybrid configuration
        hybrid_config = config['hybrid_config']
        if not hybrid_config.get('enabled', False):
            raise ValueError("Hybrid mode must be enabled in configuration")

        # Validate secondary model configuration exists
        secondary_model = hybrid_config.get('secondary_model', 'yolo_world')
        if secondary_model == 'yolo_world' and 'yolo_world_config' not in config:
            raise ValueError("yolo_world_config section required when using hybrid mode with YOLO-World")
        elif secondary_model == 'grounding_dino' and 'grounding_dino_config' not in config:
            raise ValueError("grounding_dino_config section required when using hybrid mode with Grounding DINO")

        logger.info(f"Configuration loaded successfully from {config_path}")
        logger.info(f"Detection mode: hybrid (YOLO11n + {secondary_model})")
        return config

    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        raise


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

        # Add model overhead (both models are memory-intensive)
        model_overhead_mb = 2000  # Conservative estimate
        memory_per_image_mb += model_overhead_mb / self.batch_size_base

        # Calculate batch size
        available_memory_mb = self.max_vram_gb * 1024 * self.memory_threshold
        optimal_batch_size = int(available_memory_mb / memory_per_image_mb)

        return max(self.min_batch_size, min(optimal_batch_size, self.max_batch_size))


@dataclass
class ClassConfig:
    """9-class urban mobility detection configuration loaded from JSON"""
    # Class definitions with IDs
    CLASSES: Dict[int, str]

    # Class-specific confidence thresholds for better precision
    CONFIDENCE_THRESHOLDS: Dict[str, float]

    # Text prompts for each class (used by both models)
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

    def get_class_id(self, class_name: str) -> Optional[int]:
        """Get class ID from class name"""
        for class_id, name in self.CLASSES.items():
            if name == class_name:
                return class_id
        return None

    def get_confidence_threshold(self, class_name: str) -> float:
        """Get confidence threshold for a specific class"""
        return self.CONFIDENCE_THRESHOLDS.get(class_name, 0.3)

    def get_text_prompts(self, class_name: str) -> List[str]:
        """Get text prompts for a specific class"""
        return self.TEXT_PROMPTS.get(class_name, [class_name])


class MemoryManager:
    """Optimized memory management for RTX 3060 (12GB VRAM)"""

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
            'cached': cached,
            'free': free,
            'total': total,
            'utilization': (used / total) * 100
        }

    def cleanup_memory(self, force: bool = False) -> None:
        """Perform memory cleanup when needed"""
        self.cleanup_counter += 1

        if force or (self.cleanup_counter % self.config.cleanup_interval == 0):
            logger.debug("Performing memory cleanup...")

            # Clear Python garbage
            collected = gc.collect()

            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            memory_info = self.get_gpu_memory_info()
            logger.debug(f"Memory cleanup completed. Collected {collected} objects. "
                        f"GPU: {memory_info['used']:.1f}GB used, {memory_info['free']:.1f}GB free")

    def check_memory_status(self) -> bool:
        """Check if memory usage is within acceptable limits"""
        memory_info = self.get_gpu_memory_info()
        utilization = memory_info['utilization']

        if utilization > (self.config.memory_threshold * 100):
            logger.warning(f"High memory usage detected: {utilization:.1f}%. "
                          f"Used: {memory_info['used']:.1f}GB, "
                          f"Free: {memory_info['free']:.1f}GB")
            self.cleanup_memory(force=True)
            return False

        return True


@dataclass
class HybridConfig:
    """Hybrid detection configuration with COCO to CAMINA mapping"""
    enabled: bool
    yolo11_model: str
    secondary_model: str
    coco_classes: Dict[int, str]
    new_classes: Dict[int, str]

    # COCO class IDs mapping to CAMINA classes
    COCO_TO_CAMINA_MAPPING = {
        0: 0,    # person -> pedestrian
        1: 1,    # bicycle -> used for cyclist creation
        2: 2,    # car -> car
        3: 3,    # motorcycle -> motorcycle
        5: 4,    # bus -> bus
        7: 5,    # truck -> truck
    }

    @classmethod
    def from_config(cls, config: Dict) -> 'HybridConfig':
        """Create HybridConfig from loaded configuration"""
        hybrid_config = config['hybrid_config']

        # Convert string keys to int for class mappings
        coco_classes = {int(k): v for k, v in hybrid_config['coco_classes'].items()}
        new_classes = {int(k): v for k, v in hybrid_config['new_classes'].items()}

        return cls(
            enabled=hybrid_config['enabled'],
            yolo11_model=hybrid_config['yolo11_model'],
            secondary_model=hybrid_config['secondary_model'],
            coco_classes=coco_classes,
            new_classes=new_classes
        )

    def is_coco_class(self, camina_class_id: int) -> bool:
        """Check if a CAMINA class ID corresponds to a COCO class"""
        return camina_class_id in self.coco_classes

    def is_new_class(self, camina_class_id: int) -> bool:
        """Check if a CAMINA class ID corresponds to a new class"""
        return camina_class_id in self.new_classes

    def get_coco_class_id(self, camina_class_id: int) -> Optional[int]:
        """Get COCO class ID from CAMINA class ID"""
        for coco_id, camina_id in self.COCO_TO_CAMINA_MAPPING.items():
            if camina_id == camina_class_id:
                return coco_id
        return None


class HybridDetector:
    """Optimized hybrid detector combining YOLO11 for COCO classes with YOLO-World/Grounding DINO for new classes

    Includes cyclist detection logic that combines person and bicycle detections from YOLO11
    to create cyclist class through union of overlapping bounding boxes.
    """

    def __init__(self, class_config: ClassConfig, memory_config: MemoryConfig,
                 hybrid_config: HybridConfig, yolo_world_config: Dict, grounding_dino_config: Dict,
                 cyclist_detection_config: Dict):
        self.class_config = class_config
        self.memory_config = memory_config
        self.hybrid_config = hybrid_config
        self.yolo_world_config = yolo_world_config
        self.grounding_dino_config = grounding_dino_config
        self.cyclist_detection_config = cyclist_detection_config
        self.memory_manager = MemoryManager(memory_config)

        # Image cache for performance optimization
        self.image_cache = ImageCache(max_size=self.memory_config.batch_size_base * 2)

        # Models (lazy initialization)
        self.yolo11_model = None
        self.secondary_model = None
        self.device = self._setup_device()
        self._models_initialized = False

        # Performance tracking
        self.total_processed = 0
        self.total_detections = 0
        self.yolo11_detections = 0
        self.secondary_detections = 0
        self.merged_detections = 0
        self.processing_times = {'yolo11': [], 'secondary': [], 'merge': []}
        self.class_stats = {name: 0 for name in class_config.CLASSES.values()}

        logger.info(f"Initializing optimized hybrid detector (YOLO11 + {hybrid_config.secondary_model})...")

        # Cyclist detection configuration (from example file logic)
        self.iou_threshold_cyclist = cyclist_detection_config.get("iou_threshold", 0.20)  # Min IoU for pedestrian ⨂ cycle pairing
        self.lower_margin_px = cyclist_detection_config.get("spatial_margin_px", 5)  # Cycle must be at least this many px lower than pedestrian
        self.min_side_px = 4  # Drop detector boxes smaller than this (px)

    def _setup_device(self) -> torch.device:
        """Setup and validate CUDA device"""
        if not torch.cuda.is_available():
            logger.warning("CUDA not available! Using CPU (will be very slow)")
            return torch.device("cpu")

        device = torch.device("cuda")
        gpu_props = torch.cuda.get_device_properties(0)
        total_memory_gb = gpu_props.total_memory / (1024**3)

        logger.info(f"GPU Device: {gpu_props.name}")
        logger.info(f"Total GPU Memory: {total_memory_gb:.1f}GB")
        logger.info(f"Configured Max VRAM: {self.memory_config.max_vram_gb}GB")

        if total_memory_gb < self.memory_config.max_vram_gb:
            logger.warning(f"Available GPU memory ({total_memory_gb:.1f}GB) is less than "
                          f"configured max VRAM ({self.memory_config.max_vram_gb}GB)")

        return device

    def initialize_models(self) -> bool:
        """Initialize both YOLO11 and secondary model"""
        try:
            # Initialize YOLO11 for COCO classes
            if not self._initialize_yolo11():
                return False

            # Initialize secondary model for new classes
            if not self._initialize_secondary_model():
                return False

            self._models_initialized = True
            logger.info("Optimized hybrid detection models initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize hybrid models: {str(e)}")
            self._models_initialized = False
            return False

    def _initialize_yolo11(self) -> bool:
        """Initialize YOLO11 model for COCO classes"""
        try:
            from ultralytics import YOLO

            model_name = self.hybrid_config.yolo11_model
            logger.info(f"Loading YOLO11 primary model: {model_name}")

            self.yolo11_model = YOLO(model_name)

            # Move to device
            if self.device.type == "cuda":
                self.yolo11_model.to(self.device)

            logger.info(f"YOLO11 primary model loaded successfully on {self.device}")
            return True

        except ImportError:
            logger.error("YOLO11 not available. Install with: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize YOLO11: {str(e)}")
            return False

    def _initialize_secondary_model(self) -> bool:
        """Initialize secondary model (YOLO-World or Grounding DINO) for new classes"""
        logger.info(f"Initializing secondary model: {self.hybrid_config.secondary_model}")

        if self.hybrid_config.secondary_model == 'yolo_world':
            logger.info("Using YOLO-World as secondary model for new classes")
            return self._initialize_yolo_world_secondary()
        elif self.hybrid_config.secondary_model == 'grounding_dino':
            logger.info("Using Grounding DINO as secondary model for new classes")
            return self._initialize_grounding_dino_secondary()
        else:
            logger.error(f"Unsupported secondary model: {self.hybrid_config.secondary_model}")
            return False

    def _initialize_yolo_world_secondary(self) -> bool:
        """Initialize YOLO-World as secondary model"""
        try:
            from ultralytics import YOLOWorld

            model_name = self.yolo_world_config.get("model_name", "yolov8m-world.pt")
            logger.info(f"Loading YOLO-World secondary model: {model_name}")

            self.secondary_model = YOLOWorld(model_name)

            # Set up text prompts for new classes (more effective than just class names)
            new_class_prompts = []
            new_class_mapping = {}  # Maps prompt index to (class_id, class_name)
            prompt_index = 0

            for class_id in self.hybrid_config.new_classes:
                class_name = self.hybrid_config.new_classes[class_id]
                prompts = self.class_config.get_text_prompts(class_name)
                for prompt in prompts:
                    new_class_prompts.append(prompt)
                    new_class_mapping[prompt_index] = (class_id, class_name)
                    prompt_index += 1

            # Store the mapping for detection processing
            self.yolo_world_class_mapping = new_class_mapping
            self.secondary_model.set_classes(new_class_prompts)

            # Move to device
            if self.device.type == "cuda":
                self.secondary_model.to(self.device)

            logger.info(f"YOLO-World secondary model loaded successfully")
            logger.info(f"Text prompts configured: {new_class_prompts}")
            logger.info(f"Class mapping: {new_class_mapping}")
            return True

        except ImportError:
            logger.error("YOLO-World not available. Install with: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize YOLO-World secondary: {str(e)}")
            return False

    def _initialize_grounding_dino_secondary(self) -> bool:
        """Initialize Grounding DINO as secondary model"""
        try:
            from groundingdino.util.inference import Model
            import groundingdino

            # Get model configuration
            model_name = self.grounding_dino_config.get("model_name", "IDEA-Research/grounding-dino-tiny")

            # Find config file
            package_path = os.path.dirname(groundingdino.__file__)
            config_path = os.path.join(package_path, "config", "GroundingDINO_SwinT_OGC.py")

            if not os.path.exists(config_path):
                logger.error(f"Grounding DINO config file not found: {config_path}")
                return False

            logger.info(f"Loading Grounding DINO secondary model: {model_name}")

            # Initialize model
            self.secondary_model = Model(
                model_config_path=config_path,
                model_checkpoint_path="groundingdino_swint_ogc.pth",
                device=str(self.device)
            )

            logger.info(f"Grounding DINO secondary model loaded successfully")
            return True

        except ImportError:
            logger.error("Grounding DINO not available. Install with: pip install groundingdino-py")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Grounding DINO secondary: {str(e)}")
            return False

    def _iou_xyxy(self, box_a: List[float], box_b: List[float]) -> float:
        """Calculate IoU between two boxes in xyxy format"""
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        # Calculate intersection
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        intersection = iw * ih

        # Calculate union
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - intersection + 1e-9

        return intersection / union

    def _union_box(self, box_a: List[float], box_b: List[float]) -> List[float]:
        """Create union bounding box from two boxes in xyxy format"""
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        return [min(ax1, bx1), min(ay1, by1), max(ax2, bx2), max(ay2, by2)]

    def _bottom_y(self, xyxy: List[float]) -> float:
        """Get bottom y coordinate of bounding box"""
        return xyxy[3]

    def _pair_pedestrian_bicycle_to_cyclist(self, ped_detections: List[Dict],
                                           bicycle_detections: List[Dict],
                                           img_width: int, img_height: int) -> Tuple[List[Dict], List[int]]:
        """
        Pair pedestrian and bicycle detections to create cyclist detections.

        Logic from example file:
        - Find overlapping person and bicycle boxes with IoU >= threshold
        - Bicycle must be positioned lower than person (bottom edge)
        - Create union bounding box for matched pairs
        - Return cyclist detections and indices of unmatched pedestrians

        Args:
            ped_detections: List of pedestrian detections (in YOLO format)
            bicycle_detections: List of bicycle detections (in YOLO format)
            img_width: Image width for coordinate conversion
            img_height: Image height for coordinate conversion

        Returns:
            cyclist_detections: List of cyclist detections created from pairs
            unmatched_ped_indices: List of pedestrian indices not paired
        """
        if not ped_detections or not bicycle_detections:
            return [], list(range(len(ped_detections)))

        # Convert YOLO format to xyxy for IoU calculation
        ped_boxes_xyxy = []
        for ped in ped_detections:
            x_center, y_center, width, height = ped['x_center'], ped['y_center'], ped['width'], ped['height']
            x1 = (x_center - width / 2) * img_width
            y1 = (y_center - height / 2) * img_height
            x2 = (x_center + width / 2) * img_width
            y2 = (y_center + height / 2) * img_height
            ped_boxes_xyxy.append([x1, y1, x2, y2])

        bicycle_boxes_xyxy = []
        for bicycle in bicycle_detections:
            x_center, y_center, width, height = bicycle['x_center'], bicycle['y_center'], bicycle['width'], bicycle['height']
            x1 = (x_center - width / 2) * img_width
            y1 = (y_center - height / 2) * img_height
            x2 = (x_center + width / 2) * img_width
            y2 = (y_center + height / 2) * img_height
            bicycle_boxes_xyxy.append([x1, y1, x2, y2])

        # Greedy pairing algorithm from example file
        used_bicycles = set()
        cyclist_detections = []
        matched_peds = set()

        for ped_idx, ped_box in enumerate(ped_boxes_xyxy):
            best_match = None
            ped_bottom_y = self._bottom_y(ped_box)

            for bicycle_idx, bicycle_box in enumerate(bicycle_boxes_xyxy):
                if bicycle_idx in used_bicycles:
                    continue

                # Check if bicycle is positioned lower than pedestrian
                bicycle_bottom_y = self._bottom_y(bicycle_box)
                if bicycle_bottom_y < ped_bottom_y + self.lower_margin_px:
                    continue

                # Calculate IoU
                iou_score = self._iou_xyxy(ped_box, bicycle_box)
                if iou_score >= self.iou_threshold_cyclist:
                    if best_match is None or iou_score > best_match['score']:
                        best_match = {
                            'ped_idx': ped_idx,
                            'bicycle_idx': bicycle_idx,
                            'score': iou_score,
                            'union_box': self._union_box(ped_box, bicycle_box)
                        }

            if best_match is not None:
                # Create cyclist detection from union box
                union_box = best_match['union_box']
                x1, y1, x2, y2 = union_box

                # Convert back to YOLO format
                x_center = ((x1 + x2) / 2) / img_width
                y_center = ((y1 + y2) / 2) / img_height
                width = (x2 - x1) / img_width
                height = (y2 - y1) / img_height

                # Combine confidences using geometric mean with IoU factor
                ped_conf = ped_detections[ped_idx]['confidence']
                bicycle_conf = bicycle_detections[best_match['bicycle_idx']]['confidence']
                combined_conf = (ped_conf * bicycle_conf * best_match['score']) ** (1/3)

                cyclist_detections.append({
                    'class_id': 1,  # cyclist class ID
                    'class_name': 'cyclist',
                    'confidence': float(combined_conf),
                    'x_center': float(x_center),
                    'y_center': float(y_center),
                    'width': float(width),
                    'height': float(height),
                    'source': 'yolo11_cyclist'
                })

                matched_peds.add(ped_idx)
                used_bicycles.add(best_match['bicycle_idx'])

        # Get unmatched pedestrian indices
        unmatched_ped_indices = [i for i in range(len(ped_detections)) if i not in matched_peds]

        logger.debug(f"Cyclist pairing: {len(ped_detections)} pedestrians, {len(bicycle_detections)} bicycles -> "
                    f"{len(cyclist_detections)} cyclists, {len(unmatched_ped_indices)} unmatched pedestrians")

        return cyclist_detections, unmatched_ped_indices

    def detect_objects(self, image_path: Union[str, Path]) -> List[Dict]:
        """Detect objects using optimized hybrid approach with image caching"""
        if not self._models_initialized:
            logger.error("Models not initialized! Call initialize_models() first.")
            return []

        # Validate image file first
        if not validate_image_file(image_path):
            logger.warning(f"Invalid image file: {image_path}")
            return []

        try:
            # Load image once and cache it
            image, dimensions = self._load_image_cached(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return []

            # Get detections from both models with timing
            start_time = time.time()
            logger.debug(f"Running YOLO11 detection on {image_path}")
            yolo11_detections = self._detect_yolo11_coco(image, dimensions)
            yolo11_time = time.time() - start_time
            self.processing_times['yolo11'].append(yolo11_time)
            logger.debug(f"YOLO11 found {len(yolo11_detections)} detections in {yolo11_time:.3f}s")

            start_time = time.time()
            logger.debug(f"Running {self.hybrid_config.secondary_model} detection on {image_path}")
            secondary_detections = self._detect_secondary_new_classes(image, dimensions, image_path)
            secondary_time = time.time() - start_time
            self.processing_times['secondary'].append(secondary_time)
            logger.debug(f"Secondary model found {len(secondary_detections)} detections in {secondary_time:.3f}s")

            # Merge detections and apply NMS
            start_time = time.time()
            merged_detections = self._merge_detections(yolo11_detections, secondary_detections)
            merge_time = time.time() - start_time
            self.processing_times['merge'].append(merge_time)
            logger.debug(f"After merging: {len(merged_detections)} final detections in {merge_time:.3f}s")

            # Update statistics
            self._update_statistics(yolo11_detections, secondary_detections, merged_detections)

            return merged_detections

        except Exception as e:
            logger.error(f"Hybrid detection failed for {image_path}: {str(e)}", exc_info=True)
            return []

    def _load_image_cached(self, image_path: Union[str, Path]) -> Tuple[Optional[Image.Image], Optional[Tuple[int, int]]]:
        """Load image with caching support"""
        cached_result = self.image_cache.get(image_path)
        if cached_result is not None:
            return cached_result

        try:
            image = Image.open(image_path).convert('RGB')
            dimensions = image.size  # (width, height)
            self.image_cache.put(image_path, image, dimensions)
            return image, dimensions
        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {str(e)}")
            return None, None

    def _update_statistics(self, yolo11_detections: List[Dict], secondary_detections: List[Dict], merged_detections: List[Dict]) -> None:
        """Update detection statistics"""
        self.total_processed += 1
        self.yolo11_detections += len(yolo11_detections)
        self.secondary_detections += len(secondary_detections)
        self.merged_detections += len(merged_detections)
        self.total_detections += len(merged_detections)

        for detection in merged_detections:
            self.class_stats[detection['class_name']] += 1

    def _detect_yolo11_coco(self, image: Image.Image, dimensions: Tuple[int, int]) -> List[Dict]:
        """Detect COCO classes using YOLO11 with cyclist creation logic"""
        try:
            with torch_inference_mode():
                # Convert PIL image to numpy array for YOLO11
                image_array = np.array(image)
                results = self.yolo11_model(image_array, verbose=False)

                # Separate collections for person, bicycle, and other detections
                person_detections = []
                bicycle_detections = []
                other_detections = []

                if results and len(results) > 0:
                    result = results[0]

                    if result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes.xyxy.cpu().numpy()
                        confidences = result.boxes.conf.cpu().numpy()
                        class_ids = result.boxes.cls.cpu().numpy().astype(int)

                        img_width, img_height = dimensions

                        # Process all detections and separate by type
                        for box, conf, coco_class_id in zip(boxes, confidences, class_ids):
                            # Check if this is a COCO class we want to detect
                            if coco_class_id in self.hybrid_config.COCO_TO_CAMINA_MAPPING:
                                camina_class_id = self.hybrid_config.COCO_TO_CAMINA_MAPPING[coco_class_id]

                                if camina_class_id in self.class_config.CLASSES:
                                    class_name = self.class_config.CLASSES[camina_class_id]

                                    # Apply class-specific confidence threshold
                                    threshold = self.class_config.get_confidence_threshold(class_name)
                                    if conf >= threshold:
                                        # Check box size filter
                                        box_width = box[2] - box[0]
                                        box_height = box[3] - box[1]
                                        if box_width >= self.min_side_px and box_height >= self.min_side_px:

                                            # Convert to YOLO format
                                            x_center = ((box[0] + box[2]) / 2) / img_width
                                            y_center = ((box[1] + box[3]) / 2) / img_height
                                            width = box_width / img_width
                                            height = box_height / img_height

                                            detection = {
                                                'class_id': camina_class_id,
                                                'class_name': class_name,
                                                'confidence': float(conf),
                                                'x_center': float(x_center),
                                                'y_center': float(y_center),
                                                'width': float(width),
                                                'height': float(height),
                                                'source': 'yolo11'
                                            }

                                            # Separate person and bicycle for cyclist pairing
                                            if coco_class_id == 0:  # person
                                                person_detections.append(detection)
                                            elif coco_class_id == 1:  # bicycle
                                                bicycle_detections.append(detection)
                                            else:  # other vehicle classes
                                                other_detections.append(detection)

                # Create cyclists from person + bicycle pairs
                cyclist_detections = []
                unmatched_person_indices = []

                if person_detections and bicycle_detections:
                    cyclist_detections, unmatched_person_indices = self._pair_pedestrian_bicycle_to_cyclist(
                        person_detections, bicycle_detections, img_width, img_height
                    )
                else:
                    unmatched_person_indices = list(range(len(person_detections)))

                # Combine final detections
                final_detections = []

                # Add cyclists
                final_detections.extend(cyclist_detections)

                # Add unmatched persons as pedestrians
                for idx in unmatched_person_indices:
                    final_detections.append(person_detections[idx])

                # Add other vehicle detections (car, motorcycle, bus, truck)
                final_detections.extend(other_detections)

                # Note: we intentionally do NOT add standalone bicycles to final output
                # as per the example file logic

                logger.debug(f"YOLO11 detection summary: {len(person_detections)} persons, {len(bicycle_detections)} bicycles -> "
                           f"{len(cyclist_detections)} cyclists, {len(unmatched_person_indices)} pedestrians, "
                           f"{len(other_detections)} vehicles")

                return final_detections

        except Exception as e:
            logger.error(f"YOLO11 detection failed: {str(e)}")
            return []

    def _detect_secondary_new_classes(self, image: Image.Image, dimensions: Tuple[int, int], image_path: Union[str, Path]) -> List[Dict]:
        """Detect new classes using secondary model"""
        if self.hybrid_config.secondary_model == 'yolo_world':
            return self._detect_yolo_world_new_classes(image, dimensions)
        elif self.hybrid_config.secondary_model == 'grounding_dino':
            return self._detect_grounding_dino_new_classes(image, dimensions)
        else:
            return []

    def _detect_yolo_world_new_classes(self, image: Image.Image, dimensions: Tuple[int, int]) -> List[Dict]:
        """Detect new classes using YOLO-World with optimized processing"""
        try:
            with torch_inference_mode():
                # Convert PIL image to numpy array for YOLO-World
                image_array = np.array(image)
                results = self.secondary_model(image_array, verbose=False)
                detections = []

                if results and len(results) > 0:
                    result = results[0]

                    if result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes.xyxy.cpu().numpy()
                        confidences = result.boxes.conf.cpu().numpy()
                        class_ids = result.boxes.cls.cpu().numpy().astype(int)

                        img_width, img_height = dimensions

                        # Map from YOLO-World prompt indices to CAMINA class IDs using our mapping
                        valid_boxes = []
                        valid_confidences = []
                        valid_classes = []

                        for box, conf, prompt_class_id in zip(boxes, confidences, class_ids):
                            if prompt_class_id in self.yolo_world_class_mapping:
                                camina_class_id, class_name = self.yolo_world_class_mapping[prompt_class_id]

                                # Apply class-specific confidence threshold
                                threshold = self.class_config.get_confidence_threshold(class_name)
                                if conf >= threshold:
                                    valid_boxes.append(box)
                                    valid_confidences.append(conf)
                                    valid_classes.append((camina_class_id, class_name))

                        # Convert coordinates in batch if we have valid detections
                        if valid_boxes:
                            valid_boxes = np.array(valid_boxes)
                            yolo_coords = CoordinateConverter.xyxy_to_yolo_vectorized(
                                valid_boxes, img_width, img_height
                            )

                            for coords, conf, (class_id, class_name) in zip(yolo_coords, valid_confidences, valid_classes):
                                detections.append({
                                    'class_id': class_id,
                                    'class_name': class_name,
                                    'confidence': float(conf),
                                    'x_center': float(coords[0]),
                                    'y_center': float(coords[1]),
                                    'width': float(coords[2]),
                                    'height': float(coords[3]),
                                    'source': 'yolo_world'
                                })

                return detections

        except Exception as e:
            logger.error(f"YOLO-World secondary detection failed: {str(e)}")
            return []

    def _detect_grounding_dino_new_classes(self, image: Image.Image, dimensions: Tuple[int, int]) -> List[Dict]:
        """Detect new classes using Grounding DINO with optimized processing"""
        try:
            # Convert PIL image to the format expected by Grounding DINO
            image_array = np.array(image)

            # Create text prompt from new classes only
            new_class_prompts = []
            for class_id in self.hybrid_config.new_classes:
                class_name = self.hybrid_config.new_classes[class_id]
                prompts = self.class_config.get_text_prompts(class_name)
                new_class_prompts.extend(prompts)

            text_prompt = " . ".join(new_class_prompts) + " ."

            # Get model configuration
            box_threshold = self.grounding_dino_config.get("box_threshold", 0.25)
            text_threshold = self.grounding_dino_config.get("text_threshold", 0.2)

            # Run inference
            boxes, logits, phrases = self.secondary_model.predict_with_classes(
                image=image_array,
                classes=list(self.hybrid_config.new_classes.values()),
                box_threshold=box_threshold,
                text_threshold=text_threshold
            )

            detections = []
            if len(boxes) > 0:
                # Vectorized processing for better performance
                valid_boxes = []
                valid_confidences = []
                valid_classes = []

                for box, logit, phrase in zip(boxes, logits, phrases):
                    # Find matching class
                    best_class = None
                    best_confidence = 0

                    for class_name in self.hybrid_config.new_classes.values():
                        if class_name.lower() in phrase.lower():
                            confidence = float(torch.max(logit).item()) if torch.is_tensor(logit) else float(logit)
                            if confidence > best_confidence:
                                best_class = class_name
                                best_confidence = confidence

                    if best_class:
                        # Apply class-specific confidence threshold
                        threshold = self.class_config.get_confidence_threshold(best_class)
                        if best_confidence >= threshold:
                            camina_class_id = self.class_config.get_class_id(best_class)
                            valid_boxes.append(box.tolist() if torch.is_tensor(box) else box)
                            valid_confidences.append(best_confidence)
                            valid_classes.append((camina_class_id, best_class))

                # Process all valid detections
                for box, conf, (class_id, class_name) in zip(valid_boxes, valid_confidences, valid_classes):
                    # Box coordinates are already normalized (0-1)
                    x1, y1, x2, y2 = box
                    x_center = (x1 + x2) / 2
                    y_center = (y1 + y2) / 2
                    width = x2 - x1
                    height = y2 - y1

                    detections.append({
                        'class_id': class_id,
                        'class_name': class_name,
                        'confidence': conf,
                        'x_center': float(x_center),
                        'y_center': float(y_center),
                        'width': float(width),
                        'height': float(height),
                        'source': 'grounding_dino'
                    })

            return detections

        except Exception as e:
            logger.error(f"Grounding DINO secondary detection failed: {str(e)}")
            return []

    def _merge_detections(self, yolo11_detections: List[Dict], secondary_detections: List[Dict]) -> List[Dict]:
        """Merge detections from both models and apply Non-Maximum Suppression"""
        all_detections = yolo11_detections + secondary_detections

        if len(all_detections) == 0:
            return []

        # Apply NMS to remove overlapping detections
        merged_detections = self._apply_nms(all_detections)

        return merged_detections

    def _apply_nms(self, detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
        """Apply Non-Maximum Suppression to remove duplicate detections"""
        if len(detections) <= 1:
            return detections

        # Convert to tensors for NMS
        boxes = []
        scores = []

        for det in detections:
            # Convert center format to xyxy format
            x_center, y_center, width, height = det['x_center'], det['y_center'], det['width'], det['height']
            x1 = x_center - width / 2
            y1 = y_center - height / 2
            x2 = x_center + width / 2
            y2 = y_center + height / 2

            boxes.append([x1, y1, x2, y2])
            scores.append(det['confidence'])

        boxes_tensor = torch.tensor(boxes, dtype=torch.float32)
        scores_tensor = torch.tensor(scores, dtype=torch.float32)

        # Apply NMS
        keep_indices = torchvision.ops.nms(boxes_tensor, scores_tensor, iou_threshold)

        # Return kept detections
        merged_detections = [detections[i] for i in keep_indices.tolist()]

        # Remove source field for final output
        for det in merged_detections:
            det.pop('source', None)

        return merged_detections

    def save_yolo_labels(self, detections: List[Dict], output_path: Path) -> None:
        """Save detections in YOLO format"""
        try:
            with open(output_path, 'w') as f:
                for detection in detections:
                    # YOLO format: class_id x_center y_center width height confidence
                    line = f"{detection['class_id']} {detection['x_center']:.6f} " \
                           f"{detection['y_center']:.6f} {detection['width']:.6f} " \
                           f"{detection['height']:.6f} {detection['confidence']:.6f}\n"
                    f.write(line)
        except Exception as e:
            logger.error(f"Failed to save labels to {output_path}: {str(e)}")

    def get_statistics(self) -> Dict:
        """Get comprehensive detection and performance statistics"""
        # Calculate average processing times
        avg_times = {}
        for stage, times in self.processing_times.items():
            avg_times[f'avg_{stage}_time'] = np.mean(times) if times else 0.0

        total_avg_time = sum(avg_times.values())

        return {
            'model': 'optimized_hybrid',
            'primary_model': 'yolo11',
            'secondary_model': self.hybrid_config.secondary_model,
            'total_processed': self.total_processed,
            'total_detections': self.total_detections,
            'yolo11_detections': self.yolo11_detections,
            'secondary_detections': self.secondary_detections,
            'merged_detections': self.merged_detections,
            'avg_detections_per_image': self.total_detections / max(1, self.total_processed),
            'performance_metrics': {
                **avg_times,
                'total_avg_time_per_image': total_avg_time,
                'images_per_second': 1.0 / max(total_avg_time, 0.001),
                'cache_hit_rate': len(self.image_cache.cache) / max(1, self.total_processed)
            },
            'class_distribution': self.class_stats.copy()
        }

    def cleanup_resources(self) -> None:
        """Clean up resources and clear caches"""
        self.image_cache.clear()
        self.memory_manager.cleanup_memory(force=True)

        # Clear model references to free GPU memory
        if self.yolo11_model is not None:
            del self.yolo11_model
            self.yolo11_model = None

        if self.secondary_model is not None:
            del self.secondary_model
            self.secondary_model = None

        self._models_initialized = False
        logger.info("Resources cleaned up successfully")




class DatasetValidator:
    """Validate dataset structure and content"""

    def __init__(self, class_config: ClassConfig):
        self.class_config = class_config

    def validate_dataset(self, dataset_dir: Path) -> Dict:
        """Validate dataset structure and content"""
        logger.info("Validating dataset structure...")

        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {
                'total_images': 0,
                'total_labels': 0,
                'images_with_labels': 0,
                'images_without_labels': 0,
                'class_distribution': {name: 0 for name in self.class_config.CLASSES.values()}
            }
        }

        # Check directory structure
        images_dir = dataset_dir / 'images'
        labels_dir = dataset_dir / 'labels'

        if not images_dir.exists():
            validation_results['errors'].append(f"Images directory not found: {images_dir}")
            validation_results['valid'] = False

        if not labels_dir.exists():
            validation_results['errors'].append(f"Labels directory not found: {labels_dir}")
            validation_results['valid'] = False

        if not validation_results['valid']:
            return validation_results

        # Validate images and labels
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        image_files = []

        for ext in image_extensions:
            image_files.extend(images_dir.glob(f"*{ext}"))
            image_files.extend(images_dir.glob(f"*{ext.upper()}"))

        validation_results['statistics']['total_images'] = len(image_files)

        for image_file in image_files:
            label_file = labels_dir / f"{image_file.stem}.txt"

            if label_file.exists():
                validation_results['statistics']['images_with_labels'] += 1
                validation_results['statistics']['total_labels'] += 1

                # Validate label content
                try:
                    with open(label_file, 'r') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if line:
                                parts = line.split()
                                if len(parts) >= 5:
                                    class_id = int(parts[0])
                                    if class_id in self.class_config.CLASSES:
                                        class_name = self.class_config.CLASSES[class_id]
                                        validation_results['statistics']['class_distribution'][class_name] += 1
                                    else:
                                        validation_results['warnings'].append(
                                            f"Unknown class_id {class_id} in {label_file}:{line_num}")
                                else:
                                    validation_results['warnings'].append(
                                        f"Invalid label format in {label_file}:{line_num}")
                except Exception as e:
                    validation_results['errors'].append(f"Error reading {label_file}: {str(e)}")
            else:
                validation_results['statistics']['images_without_labels'] += 1

        logger.info(f"Validation completed. Total images: {validation_results['statistics']['total_images']}")

        return validation_results


def process_images(input_dir: Path, output_dir: Path, detector: HybridDetector,
                  verbose: bool = False) -> Dict:
    """Process all images in input directory and create optimized YOLO dataset"""

    # Create output directories
    images_output_dir = output_dir / 'images'
    labels_output_dir = output_dir / 'labels'
    images_output_dir.mkdir(parents=True, exist_ok=True)
    labels_output_dir.mkdir(parents=True, exist_ok=True)

    # Get image files
    supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
    image_files = []

    for ext in supported_extensions:
        image_files.extend(input_dir.glob(f"*{ext}"))
        image_files.extend(input_dir.glob(f"*{ext.upper()}"))

    # Filter valid image files
    valid_image_files = [f for f in image_files if validate_image_file(f)]

    if not valid_image_files:
        logger.error(f"No valid image files found in {input_dir}")
        return {'processed': 0, 'errors': 0}

    logger.info(f"Found {len(valid_image_files)} valid images to process")
    if len(image_files) > len(valid_image_files):
        logger.warning(f"Skipped {len(image_files) - len(valid_image_files)} invalid image files")

    processed_count = 0
    error_count = 0
    total_detections = 0

    try:
        # Process images with progress bar and memory management
        with tqdm(total=len(valid_image_files), desc="Processing images",
                  unit="img", dynamic_ncols=True) as pbar:

            for i, image_file in enumerate(valid_image_files):
                try:
                    # Detect objects
                    detections = detector.detect_objects(image_file)

                    if detections:
                        # Copy image to output directory
                        output_image_path = images_output_dir / image_file.name
                        if not output_image_path.exists():
                            import shutil
                            shutil.copy2(image_file, output_image_path)

                        # Save labels
                        label_file = labels_output_dir / f"{image_file.stem}.txt"
                        detector.save_yolo_labels(detections, label_file)

                        total_detections += len(detections)

                        if verbose:
                            logger.info(f"Processed {image_file.name}: {len(detections)} detections")

                    processed_count += 1

                    # Periodic memory cleanup (every 50 images)
                    if (i + 1) % 50 == 0:
                        detector.memory_manager.cleanup_memory()
                        pbar.set_postfix({
                            'processed': processed_count,
                            'detections': total_detections,
                            'errors': error_count
                        })

                except Exception as e:
                    logger.error(f"Error processing {image_file}: {str(e)}")
                    error_count += 1

                pbar.update(1)

    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
    finally:
        # Ensure final cleanup
        detector.memory_manager.cleanup_memory(force=True)

    # Get final statistics
    stats = detector.get_statistics()

    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETED!")
    logger.info("=" * 60)
    logger.info(f"Model used: {stats['model']}")
    logger.info(f"Processed: {processed_count} images")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Total detections: {stats['total_detections']}")
    logger.info(f"Average detections per image: {stats['avg_detections_per_image']:.2f}")

    # Print performance metrics
    if 'performance_metrics' in stats:
        perf = stats['performance_metrics']
        logger.info(f"Performance:")
        logger.info(f"  Average processing time: {perf.get('total_avg_time_per_image', 0):.3f}s per image")
        logger.info(f"  Processing speed: {perf.get('images_per_second', 0):.2f} images/second")
        logger.info(f"  Cache hit rate: {perf.get('cache_hit_rate', 0)*100:.1f}%")

    # Print class distribution
    if stats['total_detections'] > 0:
        logger.info("Class distribution:")
        for class_name, count in stats['class_distribution'].items():
            if count > 0:
                percentage = (count / stats['total_detections']) * 100
                logger.info(f"  {class_name}: {count} ({percentage:.1f}%)")

    return {
        'processed': processed_count,
        'errors': error_count,
        'statistics': stats
    }


def main():
    """Main function with comprehensive CLI interface"""
    parser = argparse.ArgumentParser(
        description="CAMINA Dataset Creator - Hybrid auto-labeling for urban mobility detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process images using hybrid detection
  python dataset_creator.py /path/to/images /path/to/output --verbose

  # Process specific format images
  python dataset_creator.py images/ output/ --verbose

  # Validate existing dataset
  python dataset_creator.py --validate /path/to/dataset

Detection Model:
  Hybrid approach (YOLO11n + YOLO-World/Grounding DINO):
  - YOLO11n for COCO classes (pedestrian, cyclist from person+bicycle union, car, motorcycle, bus, truck)
  - YOLO-World or Grounding DINO for new classes (e-scooter, SUV, delivery_van)
  - Fastest processing with highest accuracy on standard classes, rule-based cyclist detection

Configuration:
  Edit dataset_creator_config.json to select secondary model and adjust parameters.
        """
    )

    parser.add_argument("input_dir", nargs='?', type=str,
                       help="Input directory containing images to process")
    parser.add_argument("output_dir", nargs='?', type=str,
                       help="Output directory for YOLO dataset")
    parser.add_argument("--config", "-c", type=str, default="dataset_creator_config.json",
                       help="Configuration file path (default: dataset_creator_config.json)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--validate", type=str,
                       help="Validate existing dataset structure")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load configuration
        config = load_config(args.config)

        # Initialize configurations
        class_config = ClassConfig.from_config(config)
        memory_config = MemoryConfig.from_config(config)
        hybrid_config = HybridConfig.from_config(config)

        # Validation mode
        if args.validate:
            validator = DatasetValidator(class_config)
            results = validator.validate_dataset(Path(args.validate))

            if results['valid']:
                logger.info("✅ Dataset validation passed!")
            else:
                logger.error("❌ Dataset validation failed!")
                for error in results['errors']:
                    logger.error(f"  Error: {error}")

            for warning in results['warnings']:
                logger.warning(f"  Warning: {warning}")

            # Print statistics
            stats = results['statistics']
            logger.info(f"\nDataset Statistics:")
            logger.info(f"  Total images: {stats['total_images']}")
            logger.info(f"  Images with labels: {stats['images_with_labels']}")
            logger.info(f"  Images without labels: {stats['images_without_labels']}")

            return

        # Processing mode
        if not args.input_dir or not args.output_dir:
            parser.error("input_dir and output_dir are required for processing mode")

        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)

        if not input_dir.exists():
            logger.error(f"Input directory does not exist: {input_dir}")
            return

        # Initialize hybrid detector
        detector = HybridDetector(
            class_config, memory_config, hybrid_config,
            config['yolo_world_config'], config['grounding_dino_config'],
            config['cyclist_detection_config']
        )
        if not detector.initialize_models():
            logger.error("Failed to initialize hybrid models. Exiting.")
            return

        # Process images
        logger.info(f"Starting optimized image processing...")
        logger.info(f"Input directory: {input_dir}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Model: optimized hybrid (YOLO11n with cyclist detection + {hybrid_config.secondary_model})")

        try:
            results = process_images(input_dir, output_dir, detector, args.verbose)

            # Validate output dataset
            validator = DatasetValidator(class_config)
            validation_results = validator.validate_dataset(output_dir)

            if validation_results['valid']:
                logger.info("✅ Output dataset validation passed!")
            else:
                logger.warning("⚠️ Output dataset has issues:")
                for error in validation_results['errors']:
                    logger.error(f"  Error: {error}")

            logger.info("🎉 CAMINA optimized dataset creation completed successfully!")

        finally:
            # Ensure proper cleanup
            detector.cleanup_resources()
            logger.info("Resources cleaned up")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise


if __name__ == "__main__":
    main()