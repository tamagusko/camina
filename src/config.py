#!/usr/bin/env python3
"""
CAMINA Configuration Management

Handles loading and validation of YAML configuration files with
CLI argument overrides and environment variable support.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
import yaml

logger = logging.getLogger(__name__)


@dataclass
class MetadataConfig:
    """Metadata configuration."""
    version: str
    description: str
    created_date: str
    author: str
    target_hardware: str
    optimization_level: Optional[str] = None


@dataclass
class StageConfig:
    """Detection stage configuration."""
    name: str
    enabled: bool
    model_path: str
    device: str
    classes: Dict[int, str]
    confidence_threshold: float = 0.1
    confidence_thresholds: Optional[Dict[str, float]] = None


@dataclass
class CyclistDetectionConfig:
    """Cyclist detection algorithm configuration."""
    enabled: bool = True
    iou_threshold: float = 0.20
    spatial_margin_px: int = 5
    lower_margin_px: int = 5
    min_bbox_area: float = 0.01
    confidence_threshold: float = 0.1


@dataclass
class EscooterAssociationConfig:
    """E-scooter spatial association configuration."""
    enabled: bool = True
    iou_threshold: float = 0.15
    vertical_margin_px: int = 10
    spatial_margin_px: int = 5
    min_bbox_area: float = 0.01
    confidence_threshold: float = 0.1


@dataclass
class NMSConfig:
    """NMS consolidation configuration."""
    enabled: bool = True
    iou_threshold: float = 0.4
    confidence_strategy: str = "weighted_average"
    deterministic_tiebreaker: bool = True
    class_priority_order: List[int] = field(default_factory=lambda: [1, 6, 0, 2, 3, 4, 5, 7, 8])


@dataclass
class PerformanceConfig:
    """Performance and memory configuration."""
    max_vram_gb: float = 12.0
    batch_size_base: int = 32
    max_batch_size: int = 128
    min_batch_size: int = 8
    memory_threshold: float = 0.85
    cleanup_interval: int = 50
    num_workers: int = 8
    prefetch_factor: int = 4
    pin_memory: bool = True
    mixed_precision: bool = True


@dataclass
class DetectionConfig:
    """General detection settings."""
    min_bbox_area: float = 0.01
    supported_formats: List[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
    )
    max_image_size: List[int] = field(default_factory=lambda: [1920, 1080])


@dataclass
class OutputConfig:
    """Output format configuration."""
    format: str = "coco"
    include_summary: bool = True
    summary_format: str = "ndjson"
    save_visualizations: bool = False
    visualization_confidence_threshold: float = 0.3


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/camina.log"
    max_file_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


@dataclass
class ReproducibilityConfig:
    """Reproducibility settings."""
    random_seed: int = 42
    torch_seed: int = 42
    deterministic: bool = True
    benchmark: bool = False


@dataclass
class CLIConfig:
    """CLI default configuration."""
    default_images_dir: str = "data/images"
    default_output_dir: str = "outputs"
    default_device: str = "cuda"
    default_batch_size: int = 32
    clean_on_start: bool = False
    aggressive_memory_management: bool = True
    gpu_memory_fraction: float = 0.85


@dataclass
class CAMINAConfig:
    """Main CAMINA configuration class."""
    metadata: MetadataConfig
    stage_a: StageConfig
    stage_b: StageConfig
    text_prompts: Dict[str, List[str]]
    cyclist_detection: CyclistDetectionConfig
    escooter_association: EscooterAssociationConfig
    nms_consolidation: NMSConfig
    performance: PerformanceConfig
    detection: DetectionConfig
    output: OutputConfig
    logging: LoggingConfig
    reproducibility: ReproducibilityConfig
    cli: CLIConfig

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> "CAMINAConfig":
        """Load configuration from YAML file."""
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")

        # Validate required sections
        required_sections = [
            'metadata', 'detection_stages', 'text_prompts',
            'cyclist_detection', 'escooter_association', 'nms_consolidation'
        ]

        for section in required_sections:
            if section not in config_data:
                raise ValueError(f"Missing required configuration section: {section}")

        # Extract detection stages
        stages = config_data['detection_stages']
        if 'stage_a' not in stages or 'stage_b' not in stages:
            raise ValueError("Both stage_a and stage_b must be defined in detection_stages")

        # Create configuration objects
        metadata = MetadataConfig(**config_data['metadata'])

        stage_a = StageConfig(**stages['stage_a'])
        stage_b = StageConfig(**stages['stage_b'])

        cyclist_detection = CyclistDetectionConfig(**config_data['cyclist_detection'])
        escooter_association = EscooterAssociationConfig(**config_data['escooter_association'])
        nms_consolidation = NMSConfig(**config_data['nms_consolidation'])

        # Optional sections with defaults
        performance = PerformanceConfig(**config_data.get('performance', {}))
        detection = DetectionConfig(**config_data.get('detection', {}))
        output = OutputConfig(**config_data.get('output', {}))
        logging_config = LoggingConfig(**config_data.get('logging', {}))
        reproducibility = ReproducibilityConfig(**config_data.get('reproducibility', {}))
        cli = CLIConfig(**config_data.get('cli', {}))

        return cls(
            metadata=metadata,
            stage_a=stage_a,
            stage_b=stage_b,
            text_prompts=config_data['text_prompts'],
            cyclist_detection=cyclist_detection,
            escooter_association=escooter_association,
            nms_consolidation=nms_consolidation,
            performance=performance,
            detection=detection,
            output=output,
            logging=logging_config,
            reproducibility=reproducibility,
            cli=cli,
        )

    def validate(self) -> bool:
        """Validate configuration parameters."""
        errors = []

        # Validate confidence thresholds
        if not (0.0 <= self.stage_a.confidence_threshold <= 1.0):
            errors.append(f"stage_a confidence_threshold must be between 0.0 and 1.0")

        if not (0.0 <= self.stage_b.confidence_threshold <= 1.0):
            errors.append(f"stage_b confidence_threshold must be between 0.0 and 1.0")

        # Validate IoU thresholds
        if not (0.0 <= self.cyclist_detection.iou_threshold <= 1.0):
            errors.append(f"cyclist_detection iou_threshold must be between 0.0 and 1.0")

        if not (0.0 <= self.nms_consolidation.iou_threshold <= 1.0):
            errors.append(f"nms_consolidation iou_threshold must be between 0.0 and 1.0")

        # Validate performance settings
        if self.performance.min_batch_size > self.performance.max_batch_size:
            errors.append("min_batch_size cannot be greater than max_batch_size")

        # Validate text prompts
        required_classes = ['e-scooter', 'SUV', 'delivery_van']
        for class_name in required_classes:
            if class_name not in self.text_prompts:
                errors.append(f"Missing text prompts for class: {class_name}")
            elif not self.text_prompts[class_name]:
                errors.append(f"Empty text prompts for class: {class_name}")

        # Validate model paths
        stage_a_path = Path(self.stage_a.model_path)
        if not stage_a_path.exists() and not stage_a_path.name.endswith('.pt'):
            logger.warning(f"Stage A model path may not exist: {stage_a_path}")

        stage_b_path = Path(self.stage_b.model_path)
        if not stage_b_path.exists() and not stage_b_path.name.endswith('.pt'):
            logger.warning(f"Stage B model path may not exist: {stage_b_path}")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)

        return True

    def override_from_args(self, args: Dict[str, Any]) -> "CAMINAConfig":
        """Override configuration with command line arguments."""
        # Create a copy to avoid modifying the original
        config_dict = {
            'metadata': self.metadata,
            'stage_a': self.stage_a,
            'stage_b': self.stage_b,
            'text_prompts': self.text_prompts,
            'cyclist_detection': self.cyclist_detection,
            'escooter_association': self.escooter_association,
            'nms_consolidation': self.nms_consolidation,
            'performance': self.performance,
            'detection': self.detection,
            'output': self.output,
            'logging': self.logging,
            'reproducibility': self.reproducibility,
            'cli': self.cli,
        }

        # Override device settings
        if 'device' in args and args['device']:
            config_dict['stage_a'].device = args['device']
            config_dict['stage_b'].device = args['device']

        # Override batch size
        if 'batch_size' in args and args['batch_size']:
            config_dict['performance'].batch_size_base = args['batch_size']

        # Override output directory
        if 'output_dir' in args and args['output_dir']:
            config_dict['cli'].default_output_dir = args['output_dir']

        # Override clean flag
        if 'clean' in args and args['clean'] is not None:
            config_dict['cli'].clean_on_start = args['clean']

        return CAMINAConfig(**config_dict)

    def get_all_classes(self) -> Dict[int, str]:
        """Get combined class mapping from both stages."""
        all_classes = {}
        all_classes.update(self.stage_a.classes)
        all_classes.update(self.stage_b.classes)
        return all_classes


def load_config(config_path: Union[str, Path], cli_args: Optional[Dict[str, Any]] = None) -> CAMINAConfig:
    """
    Load and validate CAMINA configuration.

    Args:
        config_path: Path to YAML configuration file
        cli_args: Optional CLI arguments to override config values

    Returns:
        Validated CAMINAConfig instance
    """
    config = CAMINAConfig.from_yaml(config_path)

    if cli_args:
        config = config.override_from_args(cli_args)

    config.validate()

    logger.info(f"Loaded configuration from: {config_path}")
    logger.info(f"Configuration version: {config.metadata.version}")

    return config


def setup_environment_from_config(config: CAMINAConfig) -> None:
    """
    Setup environment variables and random seeds from configuration.

    Args:
        config: CAMINA configuration instance
    """
    import random
    import numpy as np
    import torch

    # Set random seeds for reproducibility
    if config.reproducibility.random_seed is not None:
        random.seed(config.reproducibility.random_seed)
        np.random.seed(config.reproducibility.random_seed)

    if config.reproducibility.torch_seed is not None:
        torch.manual_seed(config.reproducibility.torch_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(config.reproducibility.torch_seed)
            torch.cuda.manual_seed_all(config.reproducibility.torch_seed)

    # Set PyTorch deterministic behavior
    if config.reproducibility.deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    elif config.reproducibility.benchmark:
        torch.backends.cudnn.benchmark = True

    logger.info("Environment setup completed for reproducibility")