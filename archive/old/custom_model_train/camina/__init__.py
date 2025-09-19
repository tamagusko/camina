"""
CAMINA: Computer Vision Analytics for Micro-mobility and INnovation Assessment
A clean, maintainable pipeline for 9-class object detection training.
"""

__version__ = "2.0.0"
__author__ = "CAMINA Research Team"

from .config import CaminaConfig
from .data import VideoProcessor, DatasetManager
from .models import YOLO11nTrainer
from .labeling import AutoLabeler
from .evaluation import ResultsManager
from .utils import setup_logging, validate_paths

__all__ = [
    'CaminaConfig',
    'VideoProcessor', 
    'DatasetManager',
    'YOLO11nTrainer',
    'AutoLabeler',
    'ResultsManager',
    'setup_logging',
    'validate_paths'
]