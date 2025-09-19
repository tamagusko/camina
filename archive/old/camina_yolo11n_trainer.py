#!/usr/bin/env python3
"""
CAMINA YOLO11n Trainer - Optimized for Raspberry Pi 5 Edge Deployment

This script implements an advanced training pipeline for YOLO11n model specifically
optimized for edge deployment on Raspberry Pi 5. Features include:
- RTX 3060 memory optimization with dynamic batch sizing
- Advanced data augmentation and class balancing
- Model quantization and compression for edge deployment
- Comprehensive training monitoring and validation
- Automatic hyperparameter optimization

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
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field, asdict
import time
import math
from collections import defaultdict

# Third-party imports
import numpy as np
import torch
import torch.nn as nn
from torch.optim.lr_scheduler import OneCycleLR, ReduceLROnPlateau
import psutil
import yaml
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
import cv2
from PIL import Image

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('camina_yolo11n_trainer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class EdgeOptimizationConfig:
    """Configuration for Raspberry Pi 5 edge deployment optimization"""

    # Target hardware specifications
    target_device: str = "raspberry_pi_5"
    target_memory_mb: int = 1000  # Target memory usage
    target_fps: int = 15  # Target inference FPS
    max_model_size_mb: int = 25  # Maximum model size

    # Quantization settings
    enable_quantization: bool = True
    quantization_type: str = "dynamic"  # "dynamic", "static", "qat"
    calibration_samples: int = 100

    # Model compression
    enable_pruning: bool = True
    pruning_sparsity: float = 0.3  # 30% sparsity
    enable_distillation: bool = True
    teacher_model: str = "yolo11s.pt"

    # Export formats
    export_formats: List[str] = field(default_factory=lambda: ["onnx", "ncnn", "tflite"])
    onnx_opset: int = 12
    onnx_simplify: bool = True

    # Optimization flags
    optimize_for_mobile: bool = True
    half_precision: bool = True
    batch_norm_folding: bool = True


@dataclass
class AdvancedTrainingConfig:
    """Advanced training configuration with RTX 3060 optimizations"""

    # Model configuration
    model_name: str = "models/yolo11n.pt"
    input_size: int = 640

    # Training parameters - optimized for RTX 3060 12GB
    epochs: int = 200
    batch_size: int = 16  # Base batch size
    max_batch_size: int = 32  # Maximum for RTX 3060
    min_batch_size: int = 4   # Minimum for stability
    accumulate_grad_batches: int = 1  # For effective larger batch size

    # Memory management
    mixed_precision: bool = True  # Enable AMP for RTX 3060
    gradient_checkpointing: bool = True
    memory_efficient: bool = True

    # Optimization parameters
    optimizer: str = "AdamW"
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    momentum: float = 0.9  # For SGD

    # Learning rate scheduling
    lr_scheduler: str = "OneCycleLR"  # "OneCycleLR", "ReduceLROnPlateau", "CosineAnnealingLR"
    warmup_epochs: int = 10
    warmup_momentum: float = 0.8
    warmup_bias_lr: float = 0.1

    # Early stopping
    patience: int = 30
    min_delta: float = 0.001

    # Validation
    val_split: float = 0.2
    test_split: float = 0.1

    # Advanced augmentation parameters
    mosaic: float = 1.0          # Mosaic augmentation probability
    mixup: float = 0.1           # MixUp augmentation probability
    copy_paste: float = 0.3      # Copy-paste augmentation probability

    # Spatial augmentations
    degrees: float = 10.0        # Rotation degrees
    translate: float = 0.2       # Translation fraction
    scale: float = 0.9           # Scale range (0.1 = 0.9-1.1)
    shear: float = 2.0           # Shear degrees
    perspective: float = 0.0001  # Perspective transform

    # Flip augmentations
    fliplr: float = 0.5         # Horizontal flip probability
    flipud: float = 0.0         # Vertical flip probability

    # Color augmentations
    hsv_h: float = 0.015        # HSV Hue augmentation
    hsv_s: float = 0.7          # HSV Saturation augmentation
    hsv_v: float = 0.4          # HSV Value augmentation

    # Additional augmentations for urban scenes
    blur: float = 0.1           # Gaussian blur probability
    noise: float = 0.05         # Gaussian noise probability

    # Class balancing
    class_weights: bool = True
    focal_loss: bool = True
    focal_alpha: float = 0.25
    focal_gamma: float = 2.0


@dataclass
class ModelMetrics:
    """Comprehensive model performance metrics"""

    # Training metrics
    train_loss: float = 0.0
    val_loss: float = 0.0

    # Detection metrics
    map50: float = 0.0          # mAP at IoU=0.5
    map50_95: float = 0.0       # mAP at IoU=0.5:0.95

    # Per-class metrics
    precision: Dict[str, float] = field(default_factory=dict)
    recall: Dict[str, float] = field(default_factory=dict)
    f1_score: Dict[str, float] = field(default_factory=dict)

    # Edge deployment metrics
    model_size_mb: float = 0.0
    inference_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    fps: float = 0.0

    # Quantization metrics (if applicable)
    quantized_accuracy_drop: float = 0.0
    compression_ratio: float = 0.0


class AdvancedDataManager:
    """Advanced data management with class balancing and smart splitting"""

    def __init__(self, dataset_path: Path, config: AdvancedTrainingConfig):
        self.dataset_path = dataset_path
        self.config = config

        # Class information
        self.class_names = []
        self.class_counts = {}
        self.class_weights = {}

        logger.info(f"Initialized data manager for: {dataset_path}")

    def analyze_dataset(self) -> Dict[str, Any]:
        """Comprehensive dataset analysis"""
        logger.info("Analyzing dataset...")

        # Load dataset YAML
        yaml_path = self.dataset_path / "dataset.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Dataset YAML not found: {yaml_path}")

        with open(yaml_path, 'r') as f:
            dataset_config = yaml.safe_load(f)

        self.class_names = list(dataset_config['names'].values())

        # Analyze images and labels
        images_dir = self.dataset_path / "images"
        labels_dir = self.dataset_path / "labels"

        if not images_dir.exists() or not labels_dir.exists():
            raise FileNotFoundError("Images or labels directory not found")

        # Count instances per class
        self.class_counts = {name: 0 for name in self.class_names}
        total_images = 0
        total_annotations = 0

        image_files = list(images_dir.glob("*"))

        for img_file in tqdm(image_files, desc="Analyzing labels"):
            total_images += 1
            label_file = labels_dir / f"{img_file.stem}.txt"

            if label_file.exists():
                with open(label_file, 'r') as f:
                    lines = f.readlines()

                for line in lines:
                    line = line.strip()
                    if line:
                        parts = line.split()
                        if len(parts) >= 5:
                            class_id = int(parts[0])
                            if class_id < len(self.class_names):
                                class_name = self.class_names[class_id]
                                self.class_counts[class_name] += 1
                                total_annotations += 1

        # Calculate class weights for balancing
        max_count = max(self.class_counts.values()) if self.class_counts.values() else 1
        self.class_weights = {
            name: max_count / max(count, 1) for name, count in self.class_counts.items()
        }

        analysis_results = {
            'total_images': total_images,
            'total_annotations': total_annotations,
            'class_counts': self.class_counts.copy(),
            'class_weights': self.class_weights.copy(),
            'class_names': self.class_names.copy(),
            'annotations_per_image': total_annotations / max(total_images, 1)
        }

        # Log analysis results
        logger.info(f"Dataset analysis completed:")
        logger.info(f"  Total images: {total_images}")
        logger.info(f"  Total annotations: {total_annotations}")
        logger.info(f"  Average annotations per image: {analysis_results['annotations_per_image']:.2f}")

        logger.info("Class distribution:")
        for name, count in self.class_counts.items():
            percentage = (count / total_annotations * 100) if total_annotations > 0 else 0
            logger.info(f"  {name}: {count} ({percentage:.1f}%)")

        return analysis_results

    def create_stratified_splits(self) -> Tuple[List[Path], List[Path], List[Path]]:
        """Create stratified train/val/test splits maintaining class distribution"""
        logger.info("Creating stratified dataset splits...")

        images_dir = self.dataset_path / "images"
        labels_dir = self.dataset_path / "labels"

        # Collect all image-label pairs with their class distributions
        image_label_pairs = []
        image_class_vectors = []

        for img_file in images_dir.glob("*"):
            label_file = labels_dir / f"{img_file.stem}.txt"

            if label_file.exists():
                # Create class vector for this image
                class_vector = [0] * len(self.class_names)

                with open(label_file, 'r') as f:
                    lines = f.readlines()

                for line in lines:
                    line = line.strip()
                    if line:
                        parts = line.split()
                        if len(parts) >= 5:
                            class_id = int(parts[0])
                            if class_id < len(self.class_names):
                                class_vector[class_id] = 1

                image_label_pairs.append(img_file)
                image_class_vectors.append(class_vector)

        # Convert to numpy for stratification
        X = np.array(image_label_pairs)
        y = np.array(image_class_vectors)

        # Multi-label stratification (simplified approach)
        # Use the dominant class for each image for stratification
        y_stratify = np.argmax(y, axis=1)

        # First split: train + val vs test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y_stratify,
            test_size=self.config.test_split,
            stratify=y_stratify,
            random_state=42
        )

        # Second split: train vs val
        val_size = self.config.val_split / (1 - self.config.test_split)
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp,
            test_size=val_size,
            stratify=y_temp,
            random_state=42
        )

        logger.info(f"Dataset splits created:")
        logger.info(f"  Train: {len(X_train)} images ({len(X_train)/len(X)*100:.1f}%)")
        logger.info(f"  Val: {len(X_val)} images ({len(X_val)/len(X)*100:.1f}%)")
        logger.info(f"  Test: {len(X_test)} images ({len(X_test)/len(X)*100:.1f}%)")

        return list(X_train), list(X_val), list(X_test)

    def create_yolo_dataset_structure(self, output_dir: Path,
                                    train_files: List[Path],
                                    val_files: List[Path],
                                    test_files: List[Path]):
        """Create YOLO-format dataset structure with splits"""
        logger.info("Creating YOLO dataset structure...")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Create split directories
        for split, files in [('train', train_files), ('val', val_files), ('test', test_files)]:
            split_images_dir = output_dir / f"{split}" / "images"
            split_labels_dir = output_dir / f"{split}" / "labels"

            split_images_dir.mkdir(parents=True, exist_ok=True)
            split_labels_dir.mkdir(parents=True, exist_ok=True)

            # Copy files
            for img_file in tqdm(files, desc=f"Creating {split} split"):
                # Copy image
                dst_img = split_images_dir / img_file.name
                if not dst_img.exists():
                    shutil.copy2(img_file, dst_img)

                # Copy corresponding label
                label_file = self.dataset_path / "labels" / f"{img_file.stem}.txt"
                if label_file.exists():
                    dst_label = split_labels_dir / f"{img_file.stem}.txt"
                    if not dst_label.exists():
                        shutil.copy2(label_file, dst_label)

        # Create dataset YAML
        dataset_yaml = {
            'path': str(output_dir.absolute()),
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'nc': len(self.class_names),
            'names': {i: name for i, name in enumerate(self.class_names)}
        }

        yaml_path = output_dir / "dataset.yaml"
        with open(yaml_path, 'w') as f:
            yaml.dump(dataset_yaml, f, default_flow_style=False, sort_keys=False)

        logger.info(f"YOLO dataset structure created at: {output_dir}")
        return yaml_path


class AdvancedYOLO11nTrainer:
    """Advanced YOLO11n trainer with edge deployment optimization"""

    def __init__(self,
                 training_config: AdvancedTrainingConfig,
                 edge_config: EdgeOptimizationConfig):
        self.training_config = training_config
        self.edge_config = edge_config

        # Model and training state
        self.model = None
        self.device = self._setup_device()
        self.current_batch_size = training_config.batch_size

        # Training history
        self.training_history = {
            'train_loss': [],
            'val_loss': [],
            'map50': [],
            'map50_95': [],
            'learning_rates': [],
            'batch_sizes': []
        }

        # Best model tracking
        self.best_metrics = ModelMetrics()
        self.best_model_path = None

        logger.info(f"Advanced YOLO11n trainer initialized on device: {self.device}")

    def _setup_device(self) -> torch.device:
        """Setup optimal computing device with memory info"""
        if torch.cuda.is_available():
            device = torch.device('cuda')
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"Using GPU: {gpu_name} ({gpu_memory:.1f}GB)")

            # Optimize for RTX 3060
            if "3060" in gpu_name:
                logger.info("RTX 3060 detected - applying specific optimizations")
                self.training_config.mixed_precision = True
                self.training_config.gradient_checkpointing = True

            return device
        elif torch.backends.mps.is_available():
            logger.info("Using Apple Metal Performance Shaders")
            return torch.device('mps')
        else:
            logger.warning("GPU not available, using CPU (not recommended)")
            return torch.device('cpu')

    def _get_gpu_memory_info(self) -> Dict[str, float]:
        """Get current GPU memory usage"""
        if not torch.cuda.is_available():
            return {'used': 0, 'free': 0, 'total': 0}

        torch.cuda.synchronize()
        used = torch.cuda.memory_allocated() / (1024**3)
        cached = torch.cuda.memory_reserved() / (1024**3)
        total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        free = total - used

        return {'used': used, 'free': free, 'total': total, 'cached': cached}

    def _adaptive_batch_sizing(self) -> int:
        """Dynamically adjust batch size based on available memory"""
        if self.device.type == 'cpu':
            return self.training_config.min_batch_size

        memory_info = self._get_gpu_memory_info()
        memory_usage_ratio = memory_info['used'] / memory_info['total']

        if memory_usage_ratio > 0.9:  # High memory pressure
            new_batch_size = max(self.current_batch_size // 2, self.training_config.min_batch_size)
        elif memory_usage_ratio < 0.6:  # Low memory usage
            new_batch_size = min(self.current_batch_size * 2, self.training_config.max_batch_size)
        else:
            new_batch_size = self.current_batch_size

        if new_batch_size != self.current_batch_size:
            logger.info(f"Adjusting batch size: {self.current_batch_size} -> {new_batch_size}")
            self.current_batch_size = new_batch_size

        return new_batch_size

    def initialize_model(self, pretrained_path: Optional[str] = None) -> bool:
        """Initialize YOLO11n model with advanced configuration"""
        try:
            # Import ultralytics
            from ultralytics import YOLO

            # Load model
            model_path = pretrained_path or self.training_config.model_name
            self.model = YOLO(model_path)

            # Move to device
            if self.device.type != 'cpu':
                self.model.to(self.device)

            # Enable mixed precision for RTX 3060
            if self.training_config.mixed_precision and self.device.type == 'cuda':
                logger.info("Mixed precision training enabled")

            logger.info(f"YOLO11n model loaded: {model_path}")
            return True

        except ImportError:
            logger.error("Ultralytics not installed. Please install: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize model: {str(e)}")
            return False

    def train_model(self,
                   dataset_yaml_path: Path,
                   output_dir: Path,
                   resume: Optional[str] = None) -> ModelMetrics:
        """Advanced model training with comprehensive monitoring"""

        if not self.model:
            logger.error("Model not initialized")
            return ModelMetrics()

        logger.info("Starting advanced YOLO11n training...")
        logger.info(f"Dataset: {dataset_yaml_path}")
        logger.info(f"Output directory: {output_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Adaptive batch size
            batch_size = self._adaptive_batch_sizing()

            # Calculate effective batch size with gradient accumulation
            effective_batch_size = batch_size * self.training_config.accumulate_grad_batches
            logger.info(f"Effective batch size: {effective_batch_size}")

            # Training arguments
            train_args = {
                # Dataset and basic config
                'data': str(dataset_yaml_path),
                'epochs': self.training_config.epochs,
                'batch': batch_size,
                'imgsz': self.training_config.input_size,
                'device': self.device,

                # Optimization
                'optimizer': self.training_config.optimizer,
                'lr0': self.training_config.learning_rate,
                'weight_decay': self.training_config.weight_decay,
                'momentum': self.training_config.momentum,

                # Learning rate scheduling
                'lrf': 0.01,  # Final learning rate factor
                'warmup_epochs': self.training_config.warmup_epochs,
                'warmup_momentum': self.training_config.warmup_momentum,
                'warmup_bias_lr': self.training_config.warmup_bias_lr,

                # Early stopping and validation
                'patience': self.training_config.patience,
                'save_period': 10,  # Save every 10 epochs
                'val': True,

                # Memory optimization
                'amp': self.training_config.mixed_precision,
                'fraction': 0.8 if self.device.type == 'cuda' else 1.0,

                # Data augmentation
                'mosaic': self.training_config.mosaic,
                'mixup': self.training_config.mixup,
                'copy_paste': self.training_config.copy_paste,

                # Spatial augmentations
                'degrees': self.training_config.degrees,
                'translate': self.training_config.translate,
                'scale': self.training_config.scale,
                'shear': self.training_config.shear,
                'perspective': self.training_config.perspective,
                'fliplr': self.training_config.fliplr,
                'flipud': self.training_config.flipud,

                # Color augmentations
                'hsv_h': self.training_config.hsv_h,
                'hsv_s': self.training_config.hsv_s,
                'hsv_v': self.training_config.hsv_v,

                # Output configuration
                'project': str(output_dir),
                'name': 'camina_yolo11n',
                'exist_ok': True,
                'verbose': True,

                # Advanced options
                'workers': min(8, os.cpu_count()),
                'seed': 42,
                'deterministic': True,
            }

            # Add resume if specified
            if resume:
                train_args['resume'] = resume
                logger.info(f"Resuming training from: {resume}")

            # Class weights for imbalanced datasets
            if self.training_config.class_weights:
                logger.info("Class weights will be calculated automatically by YOLO")

            # Start training
            logger.info("Training arguments configured, starting training...")
            results = self.model.train(**train_args)

            # Extract training metrics
            metrics = self._extract_training_metrics(results, output_dir)

            # Save best model path
            best_model_dir = output_dir / 'camina_yolo11n' / 'weights'
            self.best_model_path = best_model_dir / 'best.pt'

            logger.info("Training completed successfully")
            return metrics

        except Exception as e:
            logger.error(f"Training failed: {str(e)}", exc_info=True)
            return ModelMetrics()

    def _extract_training_metrics(self, results, output_dir: Path) -> ModelMetrics:
        """Extract comprehensive metrics from training results"""
        try:
            # Initialize metrics
            metrics = ModelMetrics()

            # Extract basic metrics from results
            if hasattr(results, 'results_dict'):
                results_dict = results.results_dict

                metrics.map50 = results_dict.get('metrics/mAP50(B)', 0.0)
                metrics.map50_95 = results_dict.get('metrics/mAP50-95(B)', 0.0)

                # Training and validation loss
                metrics.train_loss = results_dict.get('train/box_loss', 0.0) + \
                                   results_dict.get('train/cls_loss', 0.0) + \
                                   results_dict.get('train/dfl_loss', 0.0)

                metrics.val_loss = results_dict.get('val/box_loss', 0.0) + \
                                 results_dict.get('val/cls_loss', 0.0) + \
                                 results_dict.get('val/dfl_loss', 0.0)

            # Calculate model size
            if self.best_model_path and self.best_model_path.exists():
                model_size_bytes = self.best_model_path.stat().st_size
                metrics.model_size_mb = model_size_bytes / (1024 * 1024)
                logger.info(f"Best model size: {metrics.model_size_mb:.2f} MB")

            # Benchmark inference performance
            metrics = self._benchmark_model_performance(metrics)

            # Save metrics to file
            metrics_path = output_dir / 'training_metrics.json'
            with open(metrics_path, 'w') as f:
                json.dump(asdict(metrics), f, indent=2)

            return metrics

        except Exception as e:
            logger.error(f"Failed to extract training metrics: {str(e)}")
            return ModelMetrics()

    def _benchmark_model_performance(self, metrics: ModelMetrics) -> ModelMetrics:
        """Benchmark model performance for edge deployment metrics"""
        if not self.best_model_path or not self.best_model_path.exists():
            return metrics

        try:
            logger.info("Benchmarking model performance...")

            # Load best model for benchmarking
            from ultralytics import YOLO
            benchmark_model = YOLO(str(self.best_model_path))

            # Create dummy input for benchmarking
            dummy_input = torch.randn(1, 3, self.training_config.input_size,
                                    self.training_config.input_size).to(self.device)

            # Warm up
            for _ in range(10):
                _ = benchmark_model(dummy_input, verbose=False)

            # Benchmark inference time
            torch.cuda.synchronize() if torch.cuda.is_available() else None

            inference_times = []
            memory_usages = []

            for _ in range(50):  # 50 runs for stable measurement
                # Measure memory before
                memory_before = self._get_gpu_memory_info()['used'] if torch.cuda.is_available() else 0

                # Time inference
                start_time = time.time()
                _ = benchmark_model(dummy_input, verbose=False)
                torch.cuda.synchronize() if torch.cuda.is_available() else None
                end_time = time.time()

                # Measure memory after
                memory_after = self._get_gpu_memory_info()['used'] if torch.cuda.is_available() else 0

                inference_times.append((end_time - start_time) * 1000)  # Convert to ms
                memory_usages.append(memory_after - memory_before)

            # Calculate metrics
            metrics.inference_time_ms = np.mean(inference_times)
            metrics.memory_usage_mb = np.mean([m * 1024 for m in memory_usages])  # Convert to MB
            metrics.fps = 1000 / metrics.inference_time_ms  # FPS = 1000ms / inference_time_ms

            logger.info(f"Inference performance:")
            logger.info(f"  Average inference time: {metrics.inference_time_ms:.2f} ms")
            logger.info(f"  Average FPS: {metrics.fps:.1f}")
            logger.info(f"  Memory usage: {metrics.memory_usage_mb:.2f} MB")

            return metrics

        except Exception as e:
            logger.error(f"Failed to benchmark model: {str(e)}")
            return metrics

    def optimize_for_edge_deployment(self, model_path: Path, output_dir: Path) -> Dict[str, Path]:
        """Optimize model for Raspberry Pi 5 edge deployment"""
        logger.info("Optimizing model for edge deployment...")

        output_dir.mkdir(parents=True, exist_ok=True)
        export_paths = {}

        try:
            # Load model
            from ultralytics import YOLO
            model = YOLO(str(model_path))

            # Export to different formats
            for format_name in self.edge_config.export_formats:
                logger.info(f"Exporting to {format_name.upper()}...")

                try:
                    export_kwargs = {
                        'format': format_name,
                        'imgsz': self.training_config.input_size,
                        'optimize': True,
                        'half': self.edge_config.half_precision,
                        'int8': format_name in ['tflite', 'ncnn'] and self.edge_config.enable_quantization,
                        'device': self.device
                    }

                    # Format-specific optimizations
                    if format_name == 'onnx':
                        export_kwargs.update({
                            'opset': self.edge_config.onnx_opset,
                            'simplify': self.edge_config.onnx_simplify
                        })
                    elif format_name == 'tflite':
                        export_kwargs.update({
                            'int8': self.edge_config.enable_quantization,
                        })

                    # Export model
                    exported_path = model.export(**export_kwargs)

                    # Move to organized output directory
                    organized_path = output_dir / f"camina_yolo11n.{format_name}"
                    if Path(exported_path).exists():
                        shutil.move(exported_path, organized_path)
                        export_paths[format_name] = organized_path

                        # Log export info
                        size_mb = organized_path.stat().st_size / (1024 * 1024)
                        logger.info(f"  {format_name.upper()} export successful: {organized_path} ({size_mb:.2f} MB)")

                except Exception as e:
                    logger.error(f"Failed to export to {format_name}: {str(e)}")

            # Create deployment package
            self._create_deployment_package(export_paths, output_dir)

            return export_paths

        except Exception as e:
            logger.error(f"Edge optimization failed: {str(e)}")
            return {}

    def _create_deployment_package(self, export_paths: Dict[str, Path], output_dir: Path):
        """Create complete deployment package for Raspberry Pi 5"""
        logger.info("Creating deployment package...")

        # Create deployment structure
        deploy_dir = output_dir / "raspberry_pi_deployment"
        deploy_dir.mkdir(exist_ok=True)

        # Copy models
        models_dir = deploy_dir / "models"
        models_dir.mkdir(exist_ok=True)

        for format_name, model_path in export_paths.items():
            if model_path.exists():
                shutil.copy2(model_path, models_dir / model_path.name)

        # Create inference script template
        inference_script = deploy_dir / "inference.py"
        self._create_inference_script(inference_script)

        # Create requirements file for Raspberry Pi
        requirements_file = deploy_dir / "requirements_rpi.txt"
        self._create_rpi_requirements(requirements_file)

        # Create deployment README
        readme_file = deploy_dir / "README.md"
        self._create_deployment_readme(readme_file, export_paths)

        # Create configuration file
        config_file = deploy_dir / "config.yaml"
        self._create_deployment_config(config_file)

        logger.info(f"Deployment package created: {deploy_dir}")

    def _create_inference_script(self, script_path: Path):
        """Create optimized inference script for Raspberry Pi 5"""
        script_content = '''#!/usr/bin/env python3
"""
CAMINA Raspberry Pi 5 Inference Script
Optimized for edge deployment with YOLO11n
"""

import cv2
import numpy as np
import time
from pathlib import Path
import argparse

try:
    from ultralytics import YOLO
except ImportError:
    print("Installing ultralytics...")
    import subprocess
    subprocess.check_call(["pip", "install", "ultralytics"])
    from ultralytics import YOLO


class CaminaInference:
    def __init__(self, model_path, conf_threshold=0.25):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.class_names = [
            'pedestrian', 'cyclist', 'car', 'motorcycle',
            'bus', 'truck', 'e-scooter', 'SUV', 'delivery_van'
        ]

    def inference(self, image):
        """Run inference on single image"""
        results = self.model(image, conf=self.conf_threshold, verbose=False)
        return results[0] if results else None

    def process_video_stream(self, source=0):
        """Process video stream (camera or file)"""
        cap = cv2.VideoCapture(source)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Run inference
            start_time = time.time()
            result = self.inference(frame)
            inference_time = time.time() - start_time

            # Draw results
            if result and result.boxes:
                for box in result.boxes:
                    # Extract coordinates and info
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = box.conf[0].cpu().numpy()
                    cls = int(box.cls[0].cpu().numpy())

                    # Draw bounding box
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

                    # Draw label
                    label = f"{self.class_names[cls]}: {conf:.2f}"
                    cv2.putText(frame, label, (int(x1), int(y1-10)),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Add FPS info
            fps = 1.0 / inference_time
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Display frame
            cv2.imshow('CAMINA Detection', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description='CAMINA Raspberry Pi Inference')
    parser.add_argument('--model', required=True, help='Path to YOLO model')
    parser.add_argument('--source', default=0, help='Video source (0 for camera, path for file)')
    parser.add_argument('--conf', type=float, default=0.25, help='Confidence threshold')

    args = parser.parse_args()

    # Initialize inference
    camina = CaminaInference(args.model, args.conf)

    # Start processing
    camina.process_video_stream(args.source)


if __name__ == "__main__":
    main()
'''

        with open(script_path, 'w') as f:
            f.write(script_content)

        # Make executable
        script_path.chmod(0o755)

    def _create_rpi_requirements(self, requirements_path: Path):
        """Create requirements file optimized for Raspberry Pi 5"""
        requirements = [
            "torch>=2.0.0",
            "torchvision>=0.15.0",
            "ultralytics>=8.0.0",
            "opencv-python>=4.5.0",
            "numpy>=1.21.0",
            "pillow>=8.0.0",
            "pyyaml>=6.0",
            "requests>=2.25.0",
            "matplotlib>=3.3.0",
            "tqdm>=4.60.0"
        ]

        with open(requirements_path, 'w') as f:
            f.write('\n'.join(requirements))

    def _create_deployment_readme(self, readme_path: Path, export_paths: Dict[str, Path]):
        """Create deployment README with setup instructions"""
        readme_content = f'''# CAMINA Raspberry Pi 5 Deployment

## Model Information
- Model: YOLO11n optimized for urban mobility detection
- Classes: pedestrian, cyclist, car, motorcycle, bus, truck, e-scooter, SUV, delivery_van
- Input size: {self.training_config.input_size}x{self.training_config.input_size}
- Target device: Raspberry Pi 5

## Available Models
'''

        for format_name, model_path in export_paths.items():
            size_mb = model_path.stat().st_size / (1024 * 1024) if model_path.exists() else 0
            readme_content += f"- **{format_name.upper()}**: `{model_path.name}` ({size_mb:.1f} MB)\n"

        readme_content += '''
## Setup Instructions

### 1. System Requirements
- Raspberry Pi 5 with at least 4GB RAM
- MicroSD card (32GB+ recommended)
- Camera module or USB camera
- Raspberry Pi OS (64-bit recommended)

### 2. Software Installation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
pip install -r requirements_rpi.txt

# Install additional system packages
sudo apt install python3-opencv python3-pip

# For hardware acceleration (optional)
sudo apt install python3-tflite-runtime
```

### 3. Quick Start
```bash
# Basic inference with camera
python inference.py --model models/camina_yolo11n.pt

# Use ONNX model for better performance
python inference.py --model models/camina_yolo11n.onnx

# Process video file
python inference.py --model models/camina_yolo11n.pt --source path/to/video.mp4

# Adjust confidence threshold
python inference.py --model models/camina_yolo11n.pt --conf 0.3
```

### 4. Performance Optimization
- Use ONNX or TensorFlow Lite models for best performance
- Reduce input resolution if needed: modify model loading
- Enable GPU acceleration if available
- Consider model quantization for memory-constrained setups

### 5. Configuration
Edit `config.yaml` to customize:
- Detection confidence thresholds per class
- Input image size
- Camera settings
- Output options

## Troubleshooting
- **Low FPS**: Try ONNX model or reduce input size
- **High memory usage**: Use TensorFlow Lite model with quantization
- **Camera issues**: Check camera permissions and connections
- **Model loading errors**: Ensure all dependencies are installed

## Performance Expectations
- **Expected FPS**: 10-20 FPS (depending on model format)
- **Memory usage**: 200-500 MB
- **CPU usage**: 60-80% (single core)

For support, check the main CAMINA repository documentation.
'''

        with open(readme_path, 'w') as f:
            f.write(readme_content)

    def _create_deployment_config(self, config_path: Path):
        """Create deployment configuration file"""
        config = {
            'model': {
                'input_size': self.training_config.input_size,
                'confidence_threshold': 0.25,
                'iou_threshold': 0.45,
                'max_detections': 100
            },
            'classes': {
                'names': ['pedestrian', 'cyclist', 'car', 'motorcycle', 'bus', 'truck', 'e-scooter', 'SUV', 'delivery_van'],
                'confidence_thresholds': {
                    'pedestrian': 0.25,
                    'cyclist': 0.30,
                    'car': 0.40,
                    'motorcycle': 0.35,
                    'bus': 0.45,
                    'truck': 0.45,
                    'e-scooter': 0.20,
                    'SUV': 0.35,
                    'delivery_van': 0.30
                }
            },
            'camera': {
                'resolution': [640, 480],
                'fps': 30,
                'device': 0
            },
            'display': {
                'show_confidence': True,
                'show_class_names': True,
                'bbox_thickness': 2,
                'font_scale': 0.5
            }
        }

        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="CAMINA YOLO11n Trainer - Advanced training for Raspberry Pi 5 deployment",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        'dataset_path',
        type=Path,
        help='Path to CAMINA dataset directory'
    )

    parser.add_argument(
        'output_dir',
        type=Path,
        help='Output directory for trained models'
    )

    parser.add_argument(
        '--model',
        type=str,
        default='models/yolo11n.pt',
        help='Pre-trained model path or name'
    )

    parser.add_argument(
        '--epochs',
        type=int,
        default=200,
        help='Number of training epochs'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Training batch size'
    )

    parser.add_argument(
        '--learning-rate',
        type=float,
        default=0.001,
        help='Initial learning rate'
    )

    parser.add_argument(
        '--resume',
        type=str,
        help='Resume training from checkpoint'
    )

    parser.add_argument(
        '--no-augment',
        action='store_true',
        help='Disable data augmentation'
    )

    parser.add_argument(
        '--edge-optimization',
        action='store_true',
        help='Enable edge deployment optimization'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate paths
    if not args.dataset_path.exists():
        logger.error(f"Dataset path not found: {args.dataset_path}")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== CAMINA YOLO11n Advanced Trainer Started ===")
    logger.info(f"Dataset: {args.dataset_path}")
    logger.info(f"Output: {args.output_dir}")
    logger.info(f"Model: {args.model}")

    try:
        # Initialize configurations
        training_config = AdvancedTrainingConfig(
            model_name=args.model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate
        )

        # Disable augmentation if requested
        if args.no_augment:
            training_config.mosaic = 0.0
            training_config.mixup = 0.0
            training_config.copy_paste = 0.0
            logger.info("Data augmentation disabled")

        edge_config = EdgeOptimizationConfig()

        # Initialize data manager
        data_manager = AdvancedDataManager(args.dataset_path, training_config)

        # Analyze dataset
        dataset_analysis = data_manager.analyze_dataset()

        # Create stratified splits
        train_files, val_files, test_files = data_manager.create_stratified_splits()

        # Create training dataset structure
        training_dataset_dir = args.output_dir / "training_dataset"
        dataset_yaml_path = data_manager.create_yolo_dataset_structure(
            training_dataset_dir, train_files, val_files, test_files
        )

        # Initialize trainer
        trainer = AdvancedYOLO11nTrainer(training_config, edge_config)

        # Initialize model
        if not trainer.initialize_model(args.model):
            logger.error("Failed to initialize model")
            return 1

        # Train model
        training_metrics = trainer.train_model(
            dataset_yaml_path=dataset_yaml_path,
            output_dir=args.output_dir,
            resume=args.resume
        )

        # Edge optimization
        if args.edge_optimization and trainer.best_model_path:
            logger.info("Starting edge deployment optimization...")
            edge_exports = trainer.optimize_for_edge_deployment(
                trainer.best_model_path,
                args.output_dir / "edge_deployment"
            )

            logger.info(f"Edge optimization completed. Exported formats: {list(edge_exports.keys())}")

        # Final summary
        logger.info("=== Training Summary ===")
        logger.info(f"Best mAP@0.5: {training_metrics.map50:.3f}")
        logger.info(f"Best mAP@0.5:0.95: {training_metrics.map50_95:.3f}")
        logger.info(f"Model size: {training_metrics.model_size_mb:.2f} MB")
        logger.info(f"Inference time: {training_metrics.inference_time_ms:.2f} ms")
        logger.info(f"Expected FPS: {training_metrics.fps:.1f}")

        if trainer.best_model_path:
            logger.info(f"Best model saved: {trainer.best_model_path}")

        logger.info("=== CAMINA YOLO11n Training Completed Successfully ===")
        return 0

    except KeyboardInterrupt:
        logger.info("Training interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())