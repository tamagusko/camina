"""
Centralized configuration management for CAMINA pipeline.
All paths, parameters, and class definitions are managed here.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClassSchema:
    """9-class detection schema for CAMINA"""
    
    # Class definitions
    CLASSES: Dict[int, str] = field(default_factory=lambda: {
        0: 'pedestrian',
        1: 'cyclist', 
        2: 'car',
        3: 'motorcycle',
        4: 'bus',
        5: 'truck',
        6: 'e-scooter',
        7: 'SUV', 
        8: 'delivery_van'
    })
    
    # SDL dataset class mapping to new schema
    SDL_MAPPING: Dict[int, int] = field(default_factory=lambda: {
        0: 4,  # bus -> bus
        1: 2,  # car -> car
        2: 1,  # cyclist -> cyclist
        3: 3,  # motorcycle -> motorcycle
        4: 0,  # person -> pedestrian
        5: 5   # truck -> truck
    })
    
    # New classes that need auto-labeling
    NEW_CLASSES: List[int] = field(default_factory=lambda: [6, 7, 8])
    
    @property
    def class_names(self) -> List[str]:
        """Get ordered list of class names"""
        return [self.CLASSES[i] for i in sorted(self.CLASSES.keys())]
    
    @property
    def num_classes(self) -> int:
        """Get total number of classes"""
        return len(self.CLASSES)


@dataclass 
class DatasetConfig:
    """Dataset configuration"""
    sdl_dataset_path: str = "datasets/SDL fine-tuned_v3-cyclist_cleaned"
    output_dataset_path: str = "datasets/camina_9class"
    train_split: float = 0.8
    val_split: float = 0.15
    test_split: float = 0.05
    min_samples_per_class: int = 100


@dataclass
class VideoProcessingConfig:
    """Video processing configuration"""
    extraction_fps: float = 0.5
    output_format: str = "jpg"
    quality: int = 95
    max_frames_per_video: Optional[int] = 1000
    frame_size: Optional[tuple] = (640, 640)


@dataclass
class TrainingConfig:
    """YOLO11n training configuration"""
    model_name: str = "yolo11n.pt"
    epochs: int = 100
    batch_size: int = 16
    image_size: int = 640
    device: str = "auto"
    workers: int = 4
    patience: int = 10
    learning_rate: float = 0.001
    weight_decay: float = 0.0005
    optimizer: str = "AdamW"
    
    # Augmentation parameters
    mosaic: float = 1.0
    mixup: float = 0.15
    copy_paste: float = 0.3
    flipud: float = 0.0
    fliplr: float = 0.5
    degrees: float = 0.0
    translate: float = 0.1
    scale: float = 0.9
    perspective: float = 0.0
    hsv_h: float = 0.015
    hsv_s: float = 0.7
    hsv_v: float = 0.4


@dataclass
class AutoLabelingConfig:
    """Auto-labeling configuration"""
    confidence_threshold: float = 0.3
    nms_threshold: float = 0.4
    min_box_size: float = 0.01
    max_detections: int = 100
    
    # CLIP prompts for new classes
    clip_prompts: Dict[int, List[str]] = field(default_factory=lambda: {
        6: ['electric scooter', 'e-scooter', 'kick scooter'],
        7: ['SUV', 'sport utility vehicle', 'large car'],
        8: ['delivery van', 'cargo van', 'commercial van']
    })


@dataclass
class DeploymentConfig:
    """Raspberry Pi deployment configuration"""
    target_device: str = "raspberry_pi_5"
    export_formats: List[str] = field(default_factory=lambda: ["onnx", "ncnn"])
    quantization: bool = True
    optimization: bool = True
    max_memory_mb: int = 1000
    target_fps: int = 15


class CaminaConfig:
    """Main configuration manager for CAMINA pipeline"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.class_schema = ClassSchema()
        self.dataset = DatasetConfig()
        self.video_processing = VideoProcessingConfig()
        self.training = TrainingConfig()
        self.auto_labeling = AutoLabelingConfig()
        self.deployment = DeploymentConfig()
        
        # Load custom configuration if provided
        if config_path:
            self.load_from_file(config_path)
    
    def load_from_file(self, config_path: Union[str, Path]):
        """Load configuration from YAML file"""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Update configuration sections
        for section_name, section_data in config_data.items():
            if hasattr(self, section_name) and isinstance(section_data, dict):
                section = getattr(self, section_name)
                for key, value in section_data.items():
                    if hasattr(section, key):
                        setattr(section, key, value)
                    else:
                        logger.warning(f"Unknown config key: {section_name}.{key}")
        
        logger.info(f"Configuration loaded from {config_path}")
    
    def save_to_file(self, config_path: Union[str, Path]):
        """Save configuration to YAML file"""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = {
            'dataset': self.dataset.__dict__,
            'video_processing': self.video_processing.__dict__,
            'training': self.training.__dict__,
            'auto_labeling': self.auto_labeling.__dict__,
            'deployment': self.deployment.__dict__
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Configuration saved to {config_path}")
    
    def create_dataset_yaml(self, output_path: Union[str, Path]):
        """Create YOLO dataset configuration file"""
        output_path = Path(output_path)
        
        dataset_config = {
            'path': str(Path(self.dataset.output_dataset_path).absolute()),
            'train': 'images/train',
            'val': 'images/val',
            'test': 'images/test',
            'nc': self.class_schema.num_classes,
            'names': self.class_schema.CLASSES
        }
        
        with open(output_path, 'w') as f:
            yaml.dump(dataset_config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Dataset YAML created at {output_path}")
        return dataset_config
    
    def validate(self) -> bool:
        """Validate configuration parameters"""
        errors = []
        
        # Check dataset paths
        sdl_path = Path(self.dataset.sdl_dataset_path)
        if not sdl_path.exists():
            errors.append(f"SDL dataset path not found: {sdl_path}")
        
        # Check split ratios sum to 1.0
        total_split = (self.dataset.train_split + 
                      self.dataset.val_split + 
                      self.dataset.test_split)
        if abs(total_split - 1.0) > 0.01:
            errors.append(f"Dataset splits must sum to 1.0, got {total_split}")
        
        # Check training parameters
        if self.training.epochs <= 0:
            errors.append("Training epochs must be positive")
        
        if self.training.batch_size <= 0:
            errors.append("Batch size must be positive")
        
        # Check video processing parameters
        if self.video_processing.extraction_fps <= 0:
            errors.append("Extraction FPS must be positive")
        
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False
        
        logger.info("Configuration validation passed")
        return True


def load_config(config_path: Optional[Union[str, Path]] = None) -> CaminaConfig:
    """Load CAMINA configuration"""
    return CaminaConfig(config_path)