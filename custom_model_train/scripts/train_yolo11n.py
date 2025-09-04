#!/usr/bin/env python3
"""
YOLO11n Training Script for 9-Class CAMINA Dataset
Optimized for Raspberry Pi 5 deployment with comprehensive logging
"""

import os
import sys
import argparse
import logging
import time
import json
from pathlib import Path
from datetime import datetime
import torch
import yaml

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class YOLO11nTrainer:
    def __init__(self, data_yaml, model_path='yolo11n.pt', project_name='camina_expansion'):
        """
        Initialize YOLO11n trainer for CAMINA dataset
        
        Args:
            data_yaml: Path to dataset YAML configuration
            model_path: Path to pretrained YOLO11n model
            project_name: Project name for experiment tracking
        """
        self.data_yaml = Path(data_yaml)
        self.model_path = Path(model_path)
        self.project_name = project_name
        
        # Training parameters optimized for 9-class detection
        self.training_params = {
            'epochs': 100,
            'batch': 16,
            'imgsz': 640,
            'device': 'auto',  # Will be determined automatically
            'workers': 4,
            'patience': 10,
            'save_period': 10,
            'cos_lr': True,  # Cosine learning rate
            'optimizer': 'AdamW',
            'lr0': 0.001,  # Initial learning rate
            'weight_decay': 0.0005,
            'warmup_epochs': 3,
            'box': 7.5,  # Box loss gain
            'cls': 0.5,  # Class loss gain
            'dfl': 1.5,  # DFL loss gain
            'mosaic': 1.0,  # Mosaic augmentation probability
            'mixup': 0.15,  # MixUp augmentation probability
            'copy_paste': 0.3,  # Copy-paste augmentation probability
            'degrees': 0.0,  # Rotation augmentation range
            'translate': 0.1,  # Translation augmentation
            'scale': 0.9,  # Scale augmentation range
            'shear': 0.0,  # Shear augmentation range
            'perspective': 0.0,  # Perspective augmentation
            'flipud': 0.0,  # Vertical flip probability
            'fliplr': 0.5,  # Horizontal flip probability
            'hsv_h': 0.015,  # Hue augmentation range
            'hsv_s': 0.7,  # Saturation augmentation range
            'hsv_v': 0.4,  # Value augmentation range
        }
        
        # Raspberry Pi 5 optimization parameters
        self.rpi_optimization = {
            'half': False,  # Use FP16 (may not be supported on all RPi)
            'int8': True,   # Use INT8 quantization for deployment
            'optimize': True,  # Optimize for inference
        }
        
        # Experiment tracking
        self.experiment_id = f"yolo11n_9class_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.results_dir = Path('runs') / 'train' / self.experiment_id
        
        logger.info(f"Initialized YOLO11n trainer for experiment: {self.experiment_id}")
        
    def validate_dataset(self):
        """Validate dataset configuration and structure"""
        if not self.data_yaml.exists():
            raise FileNotFoundError(f"Dataset YAML not found: {self.data_yaml}")
        
        # Load and validate YAML
        with open(self.data_yaml, 'r') as f:
            data_config = yaml.safe_load(f)
        
        required_keys = ['path', 'train', 'val', 'nc', 'names']
        for key in required_keys:
            if key not in data_config:
                raise ValueError(f"Missing required key in data.yaml: {key}")
        
        # Check if dataset path exists
        dataset_path = Path(data_config['path'])
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset path not found: {dataset_path}")
        
        # Validate splits
        for split in ['train', 'val']:
            split_path = dataset_path / data_config[split]
            if not split_path.exists():
                logger.warning(f"Split directory not found: {split_path}")
        
        # Check class count
        if data_config['nc'] != 9:
            logger.warning(f"Expected 9 classes, found {data_config['nc']}")
        
        # Validate class names
        expected_classes = ['pedestrian', 'cyclist', 'car', 'motorcycle', 'bus', 'truck', 'e-scooter', 'SUV', 'delivery_van']
        actual_classes = list(data_config['names'].values()) if isinstance(data_config['names'], dict) else data_config['names']
        
        if len(actual_classes) != len(expected_classes):
            logger.warning(f"Class count mismatch. Expected: {len(expected_classes)}, Got: {len(actual_classes)}")
        
        logger.info("Dataset validation completed successfully")
        return data_config
    
    def setup_device(self):
        """Setup optimal device for training"""
        if torch.cuda.is_available():
            device = 'cuda'
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"Using CUDA device: {gpu_name} ({gpu_memory:.1f} GB)")
            
            # Adjust batch size based on GPU memory
            if gpu_memory < 6:  # Less than 6GB VRAM
                self.training_params['batch'] = 8
                logger.info("Reduced batch size to 8 due to limited GPU memory")
                
        elif torch.backends.mps.is_available():
            device = 'mps'
            logger.info("Using Apple Metal Performance Shaders (MPS)")
            # MPS has memory limitations, use smaller batch
            self.training_params['batch'] = 8
            
        else:
            device = 'cpu'
            logger.info("Using CPU for training (will be slower)")
            # CPU training requires smaller batch and more workers
            self.training_params['batch'] = 4
            self.training_params['workers'] = 8
        
        self.training_params['device'] = device
        return device
    
    def create_training_config(self, output_file=None):
        """Create comprehensive training configuration file"""
        config = {
            'experiment_info': {
                'experiment_id': self.experiment_id,
                'timestamp': datetime.now().isoformat(),
                'model_type': 'YOLO11n',
                'dataset': str(self.data_yaml),
                'target_deployment': 'Raspberry Pi 5',
                'classes': 9,
                'description': 'CAMINA dataset expansion with 9 urban mobility classes'
            },
            'model_config': {
                'base_model': str(self.model_path),
                'architecture': 'YOLO11n',
                'input_size': self.training_params['imgsz'],
            },
            'training_params': self.training_params.copy(),
            'augmentation_config': {
                'mosaic': self.training_params['mosaic'],
                'mixup': self.training_params['mixup'],
                'copy_paste': self.training_params['copy_paste'],
                'geometric': {
                    'degrees': self.training_params['degrees'],
                    'translate': self.training_params['translate'],
                    'scale': self.training_params['scale'],
                    'shear': self.training_params['shear'],
                    'perspective': self.training_params['perspective'],
                    'flipud': self.training_params['flipud'],
                    'fliplr': self.training_params['fliplr'],
                },
                'color': {
                    'hsv_h': self.training_params['hsv_h'],
                    'hsv_s': self.training_params['hsv_s'],
                    'hsv_v': self.training_params['hsv_v'],
                }
            },
            'raspberry_pi_optimization': self.rpi_optimization.copy()
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Training configuration saved to {output_file}")
        
        return config
    
    def train(self, resume=False, pretrained=True):
        """
        Start YOLO11n training process
        
        Args:
            resume: Resume from last checkpoint
            pretrained: Use pretrained weights
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("Ultralytics package not installed. Install with: pip install ultralytics")
            return False
        
        # Validate dataset
        data_config = self.validate_dataset()
        
        # Setup device
        device = self.setup_device()
        
        # Create training configuration
        config_file = Path('configs') / f"{self.experiment_id}_config.json"
        config_file.parent.mkdir(exist_ok=True)
        self.create_training_config(str(config_file))
        
        # Initialize model
        if pretrained and self.model_path.exists():
            logger.info(f"Loading pretrained model: {self.model_path}")
            model = YOLO(str(self.model_path))
        else:
            logger.info("Initializing model from scratch")
            model = YOLO('yolo11n.yaml')  # Architecture file
        
        # Start training
        logger.info("Starting YOLO11n training...")
        start_time = time.time()
        
        results = model.train(
            data=str(self.data_yaml),
            epochs=self.training_params['epochs'],
            batch=self.training_params['batch'],
            imgsz=self.training_params['imgsz'],
            device=self.training_params['device'],
            workers=self.training_params['workers'],
            patience=self.training_params['patience'],
            save_period=self.training_params['save_period'],
            project='runs/train',
            name=self.experiment_id,
            exist_ok=True,
            pretrained=pretrained,
            optimizer=self.training_params['optimizer'],
            lr0=self.training_params['lr0'],
            weight_decay=self.training_params['weight_decay'],
            warmup_epochs=self.training_params['warmup_epochs'],
            cos_lr=self.training_params['cos_lr'],
            box=self.training_params['box'],
            cls=self.training_params['cls'],
            dfl=self.training_params['dfl'],
            mosaic=self.training_params['mosaic'],
            mixup=self.training_params['mixup'],
            copy_paste=self.training_params['copy_paste'],
            degrees=self.training_params['degrees'],
            translate=self.training_params['translate'],
            scale=self.training_params['scale'],
            shear=self.training_params['shear'],
            perspective=self.training_params['perspective'],
            flipud=self.training_params['flipud'],
            fliplr=self.training_params['fliplr'],
            hsv_h=self.training_params['hsv_h'],
            hsv_s=self.training_params['hsv_s'],
            hsv_v=self.training_params['hsv_v'],
            resume=resume
        )
        
        training_time = time.time() - start_time
        logger.info(f"Training completed in {training_time/3600:.2f} hours")
        
        # Save training summary
        self.save_training_summary(results, training_time)
        
        return results
    
    def save_training_summary(self, results, training_time):
        """Save comprehensive training summary"""
        summary_file = self.results_dir / 'training_summary.json'
        
        try:
            # Extract key metrics
            best_fitness = float(results.best_fitness) if hasattr(results, 'best_fitness') else 0.0
            
            summary = {
                'experiment_id': self.experiment_id,
                'training_time_hours': training_time / 3600,
                'total_epochs': self.training_params['epochs'],
                'best_fitness': best_fitness,
                'model_size_mb': self.get_model_size(),
                'training_params': self.training_params,
                'device_used': self.training_params['device'],
                'timestamp': datetime.now().isoformat(),
                'results_directory': str(self.results_dir)
            }
            
            # Save to JSON
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Training summary saved to {summary_file}")
            
        except Exception as e:
            logger.error(f"Failed to save training summary: {e}")
    
    def get_model_size(self):
        """Get trained model size in MB"""
        try:
            best_weights = self.results_dir / 'weights' / 'best.pt'
            if best_weights.exists():
                size_mb = best_weights.stat().st_size / (1024 * 1024)
                return round(size_mb, 2)
        except:
            pass
        return 0.0
    
    def export_for_raspberry_pi(self, model_path=None):
        """
        Export trained model for Raspberry Pi 5 deployment
        
        Args:
            model_path: Path to trained model (uses best.pt if None)
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("Ultralytics package required for export")
            return False
        
        if model_path is None:
            model_path = self.results_dir / 'weights' / 'best.pt'
        
        if not Path(model_path).exists():
            logger.error(f"Model not found: {model_path}")
            return False
        
        # Load trained model
        model = YOLO(str(model_path))
        
        # Export formats suitable for Raspberry Pi 5
        export_formats = ['onnx', 'tflite', 'ncnn']
        
        for format_name in export_formats:
            try:
                logger.info(f"Exporting to {format_name.upper()} format...")
                
                export_params = {
                    'format': format_name,
                    'imgsz': self.training_params['imgsz'],
                    'optimize': True,
                    'half': False,  # Raspberry Pi may not support FP16
                }
                
                if format_name == 'tflite':
                    export_params['int8'] = True  # Quantize to INT8 for better RPi performance
                
                exported_model = model.export(**export_params)
                logger.info(f"Successfully exported to {format_name}: {exported_model}")
                
            except Exception as e:
                logger.error(f"Failed to export to {format_name}: {e}")
        
        logger.info("Model export for Raspberry Pi 5 completed")
        return True

def main():
    parser = argparse.ArgumentParser(description='Train YOLO11n for CAMINA 9-class dataset')
    parser.add_argument('--data', default='all_camina_classes/data.yaml',
                       help='Path to dataset YAML file')
    parser.add_argument('--model', default='yolo11n.pt',
                       help='Path to pretrained model')
    parser.add_argument('--epochs', type=int, default=100,
                       help='Number of training epochs')
    parser.add_argument('--batch', type=int, default=16,
                       help='Batch size')
    parser.add_argument('--imgsz', type=int, default=640,
                       help='Image size for training')
    parser.add_argument('--device', default='auto',
                       help='Training device (auto, cpu, cuda, mps)')
    parser.add_argument('--resume', action='store_true',
                       help='Resume training from last checkpoint')
    parser.add_argument('--export', action='store_true',
                       help='Export model for Raspberry Pi after training')
    parser.add_argument('--project', default='camina_expansion',
                       help='Project name for experiment tracking')
    
    args = parser.parse_args()
    
    # Initialize trainer
    trainer = YOLO11nTrainer(
        data_yaml=args.data,
        model_path=args.model,
        project_name=args.project
    )
    
    # Override parameters from command line
    trainer.training_params.update({
        'epochs': args.epochs,
        'batch': args.batch,
        'imgsz': args.imgsz,
        'device': args.device if args.device != 'auto' else 'auto'
    })
    
    # Start training
    results = trainer.train(resume=args.resume)
    
    if results and args.export:
        # Export for Raspberry Pi
        trainer.export_for_raspberry_pi()
    
    logger.info("Training pipeline completed!")

if __name__ == '__main__':
    main()