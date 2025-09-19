"""
Utility functions for CAMINA pipeline.
Common functions used across multiple modules.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import json
import yaml
import cv2
import numpy as np
from datetime import datetime
import torch


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """
    Setup comprehensive logging for CAMINA pipeline.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file to save logs
    
    Returns:
        Configured logger
    """
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Set logging level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    logger = logging.getLogger("camina")
    logger.info(f"Logging initialized at {level} level")
    if log_file:
        logger.info(f"Logs will be saved to {log_file}")
    
    return logger


def validate_paths(*paths: Union[str, Path]) -> bool:
    """
    Validate that all provided paths exist.
    
    Args:
        *paths: Variable number of paths to validate
    
    Returns:
        True if all paths exist, False otherwise
    """
    logger = logging.getLogger("camina.utils")
    
    for path in paths:
        path = Path(path)
        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return False
    
    logger.debug(f"All paths validated: {[str(p) for p in paths]}")
    return True


def create_directory_structure(base_path: Union[str, Path], 
                             subdirs: List[str]) -> Dict[str, Path]:
    """
    Create directory structure for CAMINA pipeline.
    
    Args:
        base_path: Base directory path
        subdirs: List of subdirectories to create
    
    Returns:
        Dictionary mapping subdir names to Path objects
    """
    logger = logging.getLogger("camina.utils")
    base_path = Path(base_path)
    
    created_dirs = {}
    for subdir in subdirs:
        dir_path = base_path / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        created_dirs[subdir] = dir_path
        logger.debug(f"Created directory: {dir_path}")
    
    logger.info(f"Directory structure created at {base_path}")
    return created_dirs


def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger = logging.getLogger("camina.utils")
        logger.error(f"Failed to load JSON from {file_path}: {e}")
        return {}


def save_json(data: Dict[str, Any], file_path: Union[str, Path]):
    """Save data to JSON file with error handling"""
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger = logging.getLogger("camina.utils")
        logger.error(f"Failed to save JSON to {file_path}: {e}")


def load_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load YAML file with error handling"""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger = logging.getLogger("camina.utils")
        logger.error(f"Failed to load YAML from {file_path}: {e}")
        return {}


def save_yaml(data: Dict[str, Any], file_path: Union[str, Path]):
    """Save data to YAML file with error handling"""
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        logger = logging.getLogger("camina.utils")
        logger.error(f"Failed to save YAML to {file_path}: {e}")


def get_device(preferred: str = "auto") -> torch.device:
    """
    Get optimal compute device.
    
    Args:
        preferred: Preferred device ('auto', 'cpu', 'cuda', 'mps')
    
    Returns:
        torch.device object
    """
    logger = logging.getLogger("camina.utils")
    
    if preferred != "auto":
        device = torch.device(preferred)
        logger.info(f"Using specified device: {device}")
        return device
    
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"Using CUDA device: {gpu_name} ({gpu_memory:.1f} GB)")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Using Apple Metal Performance Shaders (MPS)")
    else:
        device = torch.device("cpu")
        logger.info("Using CPU")
    
    return device


def normalize_bbox(bbox: List[float], img_width: int, img_height: int) -> List[float]:
    """
    Normalize bounding box coordinates to YOLO format.
    
    Args:
        bbox: [x1, y1, x2, y2] in absolute coordinates
        img_width: Image width
        img_height: Image height
    
    Returns:
        [center_x, center_y, width, height] in normalized coordinates
    """
    x1, y1, x2, y2 = bbox
    
    center_x = (x1 + x2) / 2.0 / img_width
    center_y = (y1 + y2) / 2.0 / img_height
    width = (x2 - x1) / img_width
    height = (y2 - y1) / img_height
    
    return [center_x, center_y, width, height]


def denormalize_bbox(bbox: List[float], img_width: int, img_height: int) -> List[int]:
    """
    Convert normalized YOLO bbox to absolute coordinates.
    
    Args:
        bbox: [center_x, center_y, width, height] in normalized coordinates
        img_width: Image width
        img_height: Image height
    
    Returns:
        [x1, y1, x2, y2] in absolute coordinates
    """
    center_x, center_y, width, height = bbox
    
    x1 = int((center_x - width / 2) * img_width)
    y1 = int((center_y - height / 2) * img_height)
    x2 = int((center_x + width / 2) * img_width)
    y2 = int((center_y + height / 2) * img_height)
    
    return [x1, y1, x2, y2]


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        box1, box2: Bounding boxes in [x1, y1, x2, y2] format
    
    Returns:
        IoU value between 0 and 1
    """
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # Calculate intersection area
    x1_inter = max(x1_1, x1_2)
    y1_inter = max(y1_1, y1_2)
    x2_inter = min(x2_1, x2_2)
    y2_inter = min(y2_1, y2_2)
    
    if x2_inter <= x1_inter or y2_inter <= y1_inter:
        return 0.0
    
    intersection_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
    
    # Calculate union area
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = area1 + area2 - intersection_area
    
    if union_area == 0:
        return 0.0
    
    return intersection_area / union_area


def create_experiment_id(prefix: str = "camina") -> str:
    """Create unique experiment identifier"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"


def format_duration(seconds: float) -> str:
    """Format duration in human readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def get_image_info(image_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Get basic information about an image file.
    
    Args:
        image_path: Path to image file
    
    Returns:
        Dictionary with image information
    """
    image_path = Path(image_path)
    
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return {}
        
        height, width = img.shape[:2]
        file_size = image_path.stat().st_size
        
        return {
            'path': str(image_path),
            'width': width,
            'height': height,
            'channels': img.shape[2] if len(img.shape) > 2 else 1,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'format': image_path.suffix.lower()
        }
    except Exception as e:
        logger = logging.getLogger("camina.utils")
        logger.error(f"Failed to get image info for {image_path}: {e}")
        return {}


class ProgressTracker:
    """Simple progress tracker for long-running operations"""
    
    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.current = 0
        self.description = description
        self.logger = logging.getLogger("camina.progress")
        self.start_time = datetime.now()
    
    def update(self, count: int = 1):
        """Update progress"""
        self.current += count
        percentage = (self.current / self.total) * 100
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = format_duration(eta)
        else:
            eta_str = "Unknown"
        
        self.logger.info(f"{self.description}: {self.current}/{self.total} "
                        f"({percentage:.1f}%) - ETA: {eta_str}")
    
    def finish(self):
        """Mark progress as finished"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.logger.info(f"{self.description} completed in {format_duration(elapsed)}")


def validate_image_directory(directory: Union[str, Path], 
                           extensions: List[str] = None) -> Dict[str, Any]:
    """
    Validate and analyze image directory.
    
    Args:
        directory: Path to directory containing images
        extensions: Valid image extensions
    
    Returns:
        Directory analysis results
    """
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    
    directory = Path(directory)
    logger = logging.getLogger("camina.utils")
    
    if not directory.exists():
        logger.error(f"Directory does not exist: {directory}")
        return {'valid': False, 'error': 'Directory not found'}
    
    # Find image files
    image_files = []
    for ext in extensions:
        image_files.extend(directory.glob(f'*{ext}'))
        image_files.extend(directory.glob(f'*{ext.upper()}'))
    
    # Analyze images
    total_size = 0
    valid_images = 0
    invalid_images = []
    
    for img_path in image_files:
        info = get_image_info(img_path)
        if info:
            valid_images += 1
            total_size += info['file_size_bytes']
        else:
            invalid_images.append(str(img_path))
    
    return {
        'valid': True,
        'total_files': len(image_files),
        'valid_images': valid_images,
        'invalid_images': invalid_images,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'extensions_found': list(set(f.suffix.lower() for f in image_files))
    }