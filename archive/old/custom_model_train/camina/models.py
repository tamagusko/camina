"""
Model training and management for CAMINA pipeline.
Optimized YOLO11n training for research reproducibility.
"""

import torch
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import json
import time
from datetime import datetime
import yaml
import numpy as np

from .config import CaminaConfig, TrainingConfig
from .utils import get_device, create_experiment_id, format_duration, save_json

logger = logging.getLogger(__name__)


class YOLO11nTrainer:
    """
    Clean, research-focused YOLO11n trainer for 9-class object detection.
    Optimized for reproducibility and easy parameter tuning.
    """
    
    def __init__(self, config: CaminaConfig):
        self.config = config
        self.training_config = config.training
        self.class_schema = config.class_schema
        
        # Experiment tracking
        self.experiment_id = create_experiment_id("yolo11n")
        self.start_time = None
        self.results = {}
        
        # Model and device
        self.model = None
        self.device = None
        
        # Paths
        self.runs_dir = Path('runs/train')
        self.experiment_dir = None
        
        logger.info(f"YOLO11nTrainer initialized: {self.experiment_id}")
    
    def validate_dataset(self, data_yaml_path: Union[str, Path]) -> bool:
        """
        Validate dataset configuration and structure.
        
        Args:
            data_yaml_path: Path to dataset YAML file
        
        Returns:
            True if dataset is valid
        """
        data_yaml_path = Path(data_yaml_path)
        
        if not data_yaml_path.exists():
            logger.error(f"Dataset YAML not found: {data_yaml_path}")
            return False
        
        try:
            # Load dataset configuration
            with open(data_yaml_path, 'r') as f:
                data_config = yaml.safe_load(f)
            
            # Check required keys
            required_keys = ['path', 'train', 'val', 'nc', 'names']
            for key in required_keys:
                if key not in data_config:
                    logger.error(f"Missing required key in dataset YAML: {key}")
                    return False
            
            # Validate dataset path
            dataset_path = Path(data_config['path'])
            if not dataset_path.exists():
                logger.error(f"Dataset path not found: {dataset_path}")
                return False
            
            # Check splits exist
            train_dir = dataset_path / data_config['train']
            val_dir = dataset_path / data_config['val']
            
            if not train_dir.exists():
                logger.error(f"Training directory not found: {train_dir}")
                return False
            
            if not val_dir.exists():
                logger.error(f"Validation directory not found: {val_dir}")
                return False
            
            # Count images and labels
            train_images = len(list(train_dir.glob('*.jpg')))
            val_images = len(list(val_dir.glob('*.jpg')))
            
            if train_images == 0:
                logger.error("No training images found")
                return False
            
            if val_images == 0:
                logger.warning("No validation images found")
            
            # Validate class count
            expected_classes = self.class_schema.num_classes
            actual_classes = data_config['nc']
            
            if actual_classes != expected_classes:
                logger.warning(f"Class count mismatch: expected {expected_classes}, "
                             f"got {actual_classes}")
            
            logger.info(f"Dataset validation passed: {train_images} train, "
                       f"{val_images} val images")
            
            return True
            
        except Exception as e:
            logger.error(f"Dataset validation failed: {e}")
            return False
    
    def setup_training(self, 
                      data_yaml_path: Union[str, Path],
                      model_path: Optional[Union[str, Path]] = None) -> bool:
        """
        Setup training environment and model.
        
        Args:
            data_yaml_path: Path to dataset YAML file
            model_path: Optional path to pre-trained model
        
        Returns:
            True if setup successful
        """
        try:
            # Import ultralytics
            from ultralytics import YOLO
        except ImportError:
            logger.error("Ultralytics package not installed. Install with: pip install ultralytics")
            return False
        
        # Validate dataset
        if not self.validate_dataset(data_yaml_path):
            return False
        
        # Setup device
        self.device = get_device(self.training_config.device)
        logger.info(f"Training device: {self.device}")
        
        # Adjust batch size based on device and memory
        self._adjust_batch_size()
        
        # Initialize model
        if model_path and Path(model_path).exists():
            logger.info(f"Loading pre-trained model: {model_path}")
            self.model = YOLO(str(model_path))
        else:
            logger.info("Initializing YOLO11n model from scratch")
            self.model = YOLO('yolo11n.yaml')  # Architecture config
        
        # Create experiment directory
        self.experiment_dir = self.runs_dir / self.experiment_id
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        
        # Save training configuration
        self._save_training_config(data_yaml_path, model_path)
        
        logger.info("Training setup completed successfully")
        return True
    
    def _adjust_batch_size(self):
        """Adjust batch size based on available hardware"""
        original_batch = self.training_config.batch_size
        
        if self.device.type == 'cuda':
            # Check GPU memory
            if torch.cuda.is_available():
                gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
                
                if gpu_memory_gb < 4:
                    self.training_config.batch_size = min(8, original_batch)
                    logger.info(f"Reduced batch size to {self.training_config.batch_size} "
                               f"due to limited GPU memory ({gpu_memory_gb:.1f}GB)")
                elif gpu_memory_gb < 8:
                    self.training_config.batch_size = min(16, original_batch)
                    logger.info(f"Adjusted batch size to {self.training_config.batch_size} "
                               f"for {gpu_memory_gb:.1f}GB GPU")
        
        elif self.device.type == 'mps':
            # Apple Silicon has memory limitations
            self.training_config.batch_size = min(8, original_batch)
            logger.info(f"Adjusted batch size to {self.training_config.batch_size} for MPS")
        
        elif self.device.type == 'cpu':
            # CPU training needs smaller batch size but more workers
            self.training_config.batch_size = min(4, original_batch)
            self.training_config.workers = min(8, self.training_config.workers * 2)
            logger.info(f"CPU training: batch_size={self.training_config.batch_size}, "
                       f"workers={self.training_config.workers}")
    
    def _save_training_config(self, 
                             data_yaml_path: Union[str, Path],
                             model_path: Optional[Union[str, Path]]):
        """Save comprehensive training configuration"""
        config_data = {
            'experiment_info': {
                'experiment_id': self.experiment_id,
                'timestamp': datetime.now().isoformat(),
                'dataset_yaml': str(data_yaml_path),
                'model_path': str(model_path) if model_path else None,
                'target_classes': self.class_schema.num_classes,
                'class_names': self.class_schema.class_names
            },
            'hardware': {
                'device': str(self.device),
                'cuda_available': torch.cuda.is_available(),
                'mps_available': torch.backends.mps.is_available(),
                'gpu_count': torch.cuda.device_count() if torch.cuda.is_available() else 0
            },
            'training_parameters': {
                'epochs': self.training_config.epochs,
                'batch_size': self.training_config.batch_size,
                'image_size': self.training_config.image_size,
                'workers': self.training_config.workers,
                'patience': self.training_config.patience,
                'learning_rate': self.training_config.learning_rate,
                'weight_decay': self.training_config.weight_decay,
                'optimizer': self.training_config.optimizer
            },
            'augmentation': {
                'mosaic': self.training_config.mosaic,
                'mixup': self.training_config.mixup,
                'copy_paste': self.training_config.copy_paste,
                'flips': {
                    'flipud': self.training_config.flipud,
                    'fliplr': self.training_config.fliplr
                },
                'geometric': {
                    'degrees': self.training_config.degrees,
                    'translate': self.training_config.translate,
                    'scale': self.training_config.scale,
                    'perspective': self.training_config.perspective
                },
                'color': {
                    'hsv_h': self.training_config.hsv_h,
                    'hsv_s': self.training_config.hsv_s,
                    'hsv_v': self.training_config.hsv_v
                }
            }
        }
        
        config_file = self.experiment_dir / 'training_config.json'
        save_json(config_data, config_file)
        logger.info(f"Training configuration saved: {config_file}")
    
    def train(self, 
             data_yaml_path: Union[str, Path],
             model_path: Optional[Union[str, Path]] = None,
             resume: bool = False) -> Dict[str, Any]:
        """
        Execute model training.
        
        Args:
            data_yaml_path: Path to dataset YAML file
            model_path: Optional path to pre-trained model
            resume: Whether to resume from checkpoint
        
        Returns:
            Training results dictionary
        """
        # Setup training environment
        if not self.setup_training(data_yaml_path, model_path):
            return {'success': False, 'error': 'Training setup failed'}
        
        logger.info("Starting YOLO11n training...")
        logger.info(f"Dataset: {data_yaml_path}")
        logger.info(f"Epochs: {self.training_config.epochs}")
        logger.info(f"Batch size: {self.training_config.batch_size}")
        logger.info(f"Device: {self.device}")
        
        self.start_time = time.time()
        
        try:
            # Start training
            results = self.model.train(
                data=str(data_yaml_path),
                epochs=self.training_config.epochs,
                batch=self.training_config.batch_size,
                imgsz=self.training_config.image_size,
                device=str(self.device),
                workers=self.training_config.workers,
                patience=self.training_config.patience,
                project=str(self.runs_dir),
                name=self.experiment_id,
                exist_ok=True,
                resume=resume,
                
                # Optimizer parameters
                optimizer=self.training_config.optimizer,
                lr0=self.training_config.learning_rate,
                weight_decay=self.training_config.weight_decay,
                
                # Augmentation parameters
                mosaic=self.training_config.mosaic,
                mixup=self.training_config.mixup,
                copy_paste=self.training_config.copy_paste,
                degrees=self.training_config.degrees,
                translate=self.training_config.translate,
                scale=self.training_config.scale,
                perspective=self.training_config.perspective,
                flipud=self.training_config.flipud,
                fliplr=self.training_config.fliplr,
                hsv_h=self.training_config.hsv_h,
                hsv_s=self.training_config.hsv_s,
                hsv_v=self.training_config.hsv_v,
                
                # Other parameters
                verbose=True,
                save_period=10,  # Save checkpoint every 10 epochs
                plots=True       # Generate training plots
            )
            
            # Training completed successfully
            training_time = time.time() - self.start_time
            
            # Process results
            training_results = self._process_results(results, training_time)
            
            logger.info(f"Training completed successfully in {format_duration(training_time)}")
            return training_results
            
        except Exception as e:
            training_time = time.time() - self.start_time if self.start_time else 0
            logger.error(f"Training failed after {format_duration(training_time)}: {e}")
            return {
                'success': False,
                'error': str(e),
                'training_time': training_time,
                'experiment_id': self.experiment_id
            }
    
    def _process_results(self, results, training_time: float) -> Dict[str, Any]:
        """Process and save training results"""
        try:
            # Extract key metrics
            best_epoch = getattr(results, 'best_epoch', 0)
            best_fitness = float(getattr(results, 'best_fitness', 0.0))
            
            # Get model paths
            weights_dir = self.experiment_dir / 'weights'
            best_model = weights_dir / 'best.pt'
            last_model = weights_dir / 'last.pt'
            
            # Calculate model size
            model_size_mb = 0.0
            if best_model.exists():
                model_size_mb = best_model.stat().st_size / (1024 * 1024)
            
            # Create results summary
            results_summary = {
                'success': True,
                'experiment_id': self.experiment_id,
                'training_time_seconds': training_time,
                'training_time_formatted': format_duration(training_time),
                'model_info': {
                    'architecture': 'YOLO11n',
                    'classes': self.class_schema.num_classes,
                    'best_epoch': best_epoch,
                    'best_fitness': best_fitness,
                    'model_size_mb': round(model_size_mb, 2)
                },
                'training_config': {
                    'epochs': self.training_config.epochs,
                    'batch_size': self.training_config.batch_size,
                    'image_size': self.training_config.image_size,
                    'device': str(self.device)
                },
                'model_paths': {
                    'best_weights': str(best_model) if best_model.exists() else None,
                    'last_weights': str(last_model) if last_model.exists() else None,
                    'experiment_dir': str(self.experiment_dir)
                }
            }
            
            # Save results
            results_file = self.experiment_dir / 'training_results.json'
            save_json(results_summary, results_file)
            
            logger.info(f"Training results saved: {results_file}")
            
            # Log key metrics
            logger.info("=== Training Results ===")
            logger.info(f"Best epoch: {best_epoch}")
            logger.info(f"Best fitness: {best_fitness:.4f}")
            logger.info(f"Model size: {model_size_mb:.2f} MB")
            logger.info(f"Training time: {format_duration(training_time)}")
            
            return results_summary
            
        except Exception as e:
            logger.error(f"Failed to process results: {e}")
            return {
                'success': False,
                'error': f'Results processing failed: {e}',
                'training_time_seconds': training_time,
                'experiment_id': self.experiment_id
            }
    
    def export_model(self, 
                    model_path: Optional[Union[str, Path]] = None,
                    formats: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Export trained model for deployment.
        
        Args:
            model_path: Path to model weights (uses best.pt if None)
            formats: Export formats (uses config defaults if None)
        
        Returns:
            Export results
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("Ultralytics package required for model export")
            return {'success': False, 'error': 'Ultralytics not available'}
        
        # Get model path
        if model_path is None and self.experiment_dir:
            model_path = self.experiment_dir / 'weights' / 'best.pt'
        
        if not model_path or not Path(model_path).exists():
            logger.error(f"Model not found: {model_path}")
            return {'success': False, 'error': 'Model file not found'}
        
        # Get export formats
        if formats is None:
            formats = self.config.deployment.export_formats
        
        logger.info(f"Exporting model to formats: {formats}")
        
        # Load model
        model = YOLO(str(model_path))
        
        exported_files = {}
        export_errors = {}
        
        for format_name in formats:
            try:
                logger.info(f"Exporting to {format_name.upper()}...")
                
                export_params = {
                    'format': format_name,
                    'imgsz': self.training_config.image_size,
                    'optimize': True,
                    'half': False  # Use FP32 for better compatibility
                }
                
                # Format-specific parameters
                if format_name == 'tflite':
                    export_params['int8'] = self.config.deployment.quantization
                elif format_name == 'onnx':
                    export_params['simplify'] = True
                
                # Export model
                exported_path = model.export(**export_params)
                exported_files[format_name] = str(exported_path)
                
                logger.info(f"✅ {format_name.upper()} export successful: {exported_path}")
                
            except Exception as e:
                error_msg = str(e)
                export_errors[format_name] = error_msg
                logger.error(f"❌ {format_name.upper()} export failed: {error_msg}")
        
        # Create export summary
        export_results = {
            'success': len(exported_files) > 0,
            'model_path': str(model_path),
            'exported_formats': list(exported_files.keys()),
            'exported_files': exported_files,
            'export_errors': export_errors,
            'export_timestamp': datetime.now().isoformat()
        }
        
        # Save export results
        if self.experiment_dir:
            export_file = self.experiment_dir / 'export_results.json'
            save_json(export_results, export_file)
            logger.info(f"Export results saved: {export_file}")
        
        return export_results
    
    def validate_model(self, 
                      model_path: Optional[Union[str, Path]] = None,
                      data_yaml_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Validate trained model on test set.
        
        Args:
            model_path: Path to model weights
            data_yaml_path: Path to dataset YAML
        
        Returns:
            Validation results
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("Ultralytics package required for validation")
            return {'success': False, 'error': 'Ultralytics not available'}
        
        # Get model path
        if model_path is None and self.experiment_dir:
            model_path = self.experiment_dir / 'weights' / 'best.pt'
        
        if not model_path or not Path(model_path).exists():
            logger.error(f"Model not found: {model_path}")
            return {'success': False, 'error': 'Model file not found'}
        
        # Load model
        model = YOLO(str(model_path))
        
        try:
            logger.info("Running model validation...")
            
            # Run validation
            val_results = model.val(
                data=str(data_yaml_path) if data_yaml_path else None,
                imgsz=self.training_config.image_size,
                device=str(self.device),
                verbose=True
            )
            
            # Extract metrics
            validation_results = {
                'success': True,
                'model_path': str(model_path),
                'metrics': {
                    'map50': float(val_results.box.map50),
                    'map50_95': float(val_results.box.map),
                    'precision': float(val_results.box.p.mean()),
                    'recall': float(val_results.box.r.mean()),
                    'f1_score': float(2 * val_results.box.p.mean() * val_results.box.r.mean() / 
                                    (val_results.box.p.mean() + val_results.box.r.mean()))
                },
                'validation_timestamp': datetime.now().isoformat()
            }
            
            # Save validation results
            if self.experiment_dir:
                val_file = self.experiment_dir / 'validation_results.json'
                save_json(validation_results, val_file)
                logger.info(f"Validation results saved: {val_file}")
            
            # Log metrics
            logger.info("=== Validation Results ===")
            for metric, value in validation_results['metrics'].items():
                logger.info(f"{metric}: {value:.4f}")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {'success': False, 'error': str(e)}


def create_trainer(config: CaminaConfig) -> YOLO11nTrainer:
    """Create YOLO11n trainer with configuration"""
    return YOLO11nTrainer(config)