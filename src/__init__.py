"""
CAMINA Source Package

Production-ready two-stage detection pipeline for urban mobility object detection.
"""

__version__ = "2.0.0"
__author__ = "CAMINA Team"
__description__ = "Two-stage Urban Mobility Object Detection Pipeline"

from .config import CAMINAConfig, load_config
from .detector_yolo11n import YOLO11nDetector
from .detector_yolo_world import YOLOWorldDetector
from .cyclist_logic import CyclistDetector
from .merger_nms import NMSConsolidator
from .io_utils import ImageLoader, AnnotationWriter, DatasetValidator
from .utils import MemoryManager, PerformanceMonitor, BatchProcessor

__all__ = [
    "CAMINAConfig",
    "load_config",
    "YOLO11nDetector",
    "YOLOWorldDetector",
    "CyclistDetector",
    "NMSConsolidator",
    "ImageLoader",
    "AnnotationWriter",
    "DatasetValidator",
    "MemoryManager",
    "PerformanceMonitor",
    "BatchProcessor"
]