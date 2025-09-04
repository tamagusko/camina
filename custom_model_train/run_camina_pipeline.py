#!/usr/bin/env python3
"""
CAMINA Dataset Expansion Pipeline Runner
Automated pipeline execution and comprehensive testing suite
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import shutil
import yaml

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CAMINAPipelineRunner:
    """Complete CAMINA pipeline automation and testing"""
    
    def __init__(self, config_file: str = None):
        self.start_time = datetime.now()
        self.pipeline_id = f"camina_run_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # Default configuration
        self.config = {
            'pipeline': {
                'sdl_dataset_path': 'datasets/SDL fine-tuned_v3-cyclist_cleaned',
                'output_dataset_path': 'all_camina_classes',
                'base_model': 'yolo11n.pt',
                'epochs': 100,
                'batch_size': 16,
                'device': 'auto',
                'models_to_compare': ['yolov8n', 'yolo11n'],
                'test_video_path': None,
                'export_formats': ['ncnn', 'onnx'],
                'cleanup_after_test': False
            },
            'testing': {
                'quick_test_epochs': 3,
                'test_batch_size': 4,
                'create_test_video': True,
                'run_memory_profiling': True,
                'validate_outputs': True,
                'run_benchmarks': True
            },
            'output': {
                'results_dir': 'pipeline_results',
                'logs_dir': 'pipeline_logs',
                'save_intermediate': True,
                'create_report': True
            }
        }
        
        # Load custom config if provided
        if config_file and Path(config_file).exists():
            self.load_config(config_file)
        
        # Setup directories
        self.results_dir = Path(self.config['output']['results_dir']) / self.pipeline_id
        self.logs_dir = Path(self.config['output']['logs_dir']) / self.pipeline_id
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Test tracking
        self.test_results = []
        self.pipeline_steps = []
        
        logger.info(f"Initialized CAMINA Pipeline Runner: {self.pipeline_id}")
    
    def load_config(self, config_file: str):
        """Load configuration from file"""
        with open(config_file, 'r') as f:
            custom_config = yaml.safe_load(f)
        
        # Deep merge configuration
        def merge_dict(base, custom):
            for key, value in custom.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
        
        merge_dict(self.config, custom_config)
        logger.info(f"Loaded configuration from {config_file}")
    
    def run_command(self, cmd: List[str], description: str, timeout: int = 3600) -> Tuple[bool, str, str]:
        """Run command with logging and error handling"""
        logger.info(f"Running: {description}")
        logger.debug(f"Command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd()
            )
            
            duration = time.time() - start_time
            success = result.returncode == 0
            
            # Log results
            log_file = self.logs_dir / f"{description.lower().replace(' ', '_')}.log"
            with open(log_file, 'w') as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Duration: {duration:.2f}s\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"STDOUT:\n{result.stdout}\n")
                f.write(f"STDERR:\n{result.stderr}\n")
            
            if success:
                logger.info(f"✅ {description} completed in {duration:.2f}s")
            else:
                logger.error(f"❌ {description} failed (exit code: {result.returncode})")
                if result.stderr:
                    logger.error(f"Error: {result.stderr[:500]}")
            
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {description} timed out after {timeout}s")
            return False, "", "Command timed out"
        except Exception as e:
            logger.error(f"❌ {description} failed with exception: {str(e)}")
            return False, "", str(e)
    
    def record_test(self, test_name: str, success: bool, duration: float, details: Dict = None):
        """Record test results"""
        result = {
            'test_name': test_name,
            'success': success,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        self.test_results.append(result)
        
        status = "✅ PASSED" if success else "❌ FAILED"
        logger.info(f"{status}: {test_name} ({duration:.2f}s)")
    
    def record_pipeline_step(self, step_name: str, success: bool, duration: float, outputs: List[str] = None):
        """Record pipeline step results"""
        step = {
            'step_name': step_name,
            'success': success,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'outputs': outputs or []
        }
        self.pipeline_steps.append(step)
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are available"""
        logger.info("Checking dependencies...")
        
        # Required Python packages
        required_packages = [
            'ultralytics', 'opencv-python', 'numpy', 'pandas', 
            'matplotlib', 'seaborn', 'torch', 'torchvision'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"Missing packages: {missing_packages}")
            logger.error("Install with: pip install " + " ".join(missing_packages))
            return False
        
        # Check for base model
        base_model_path = Path(self.config['pipeline']['base_model'])
        if not base_model_path.exists():
            logger.warning(f"Base model not found: {base_model_path}")
            logger.info("Will download automatically during training")
        
        # Check SDL dataset
        sdl_path = Path(self.config['pipeline']['sdl_dataset_path'])
        if not sdl_path.exists():
            logger.error(f"SDL dataset not found: {sdl_path}")
            return False
        
        logger.info("✅ Dependencies check passed")
        return True
    
    def create_test_data(self) -> bool:
        """Create test data and resources"""
        logger.info("Creating test data...")
        
        try:
            # Create test images directory
            test_images_dir = Path('test_images')
            test_images_dir.mkdir(exist_ok=True)
            
            # Copy sample images from SDL dataset for testing
            sdl_images_dir = Path(self.config['pipeline']['sdl_dataset_path']) / 'images' / 'train'
            if sdl_images_dir.exists():
                sample_images = list(sdl_images_dir.glob('*.jpg'))[:10]
                for img in sample_images:
                    shutil.copy2(img, test_images_dir / img.name)
                logger.info(f"Copied {len(sample_images)} test images")
            
            # Create test video if requested
            if self.config['testing']['create_test_video']:
                self.create_test_video()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create test data: {e}")
            return False
    
    def create_test_video(self) -> bool:
        """Create synthetic test video for benchmarking"""
        try:
            import cv2
            import numpy as np
            
            video_path = Path('test_video.mp4')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
            
            # Create 10-second test video with moving objects
            for i in range(300):  # 10 seconds at 30fps
                frame = np.random.randint(50, 100, (480, 640, 3), dtype=np.uint8)
                
                # Add moving rectangles (simulating vehicles)
                x1 = int((i * 3) % 640)
                x2 = int((i * 2 + 100) % 640)
                
                # Car-like rectangle
                cv2.rectangle(frame, (x1, 200), (x1+80, 250), (0, 255, 0), -1)
                # Person-like rectangle
                cv2.rectangle(frame, (x2, 300), (x2+30, 400), (255, 0, 0), -1)
                
                out.write(frame)
            
            out.release()
            self.config['pipeline']['test_video_path'] = str(video_path)
            logger.info(f"Created test video: {video_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create test video: {e}")
            return False
    
    def run_dataset_conversion(self) -> bool:
        """Run SDL dataset conversion to YOLO11 format"""
        start_time = time.time()
        
        cmd = [
            sys.executable, 'scripts/convert_sdl_to_yolo11.py',
            '--sdl-dataset', self.config['pipeline']['sdl_dataset_path'],
            '--output', self.config['pipeline']['output_dataset_path']
        ]
        
        success, stdout, stderr = self.run_command(cmd, "Dataset Conversion", timeout=600)
        duration = time.time() - start_time
        
        # Validate outputs
        outputs = []
        if success:
            dataset_path = Path(self.config['pipeline']['output_dataset_path'])
            if dataset_path.exists():
                outputs.append(str(dataset_path / 'data.yaml'))
                outputs.append(str(dataset_path / 'classes.txt'))
        
        self.record_pipeline_step("Dataset Conversion", success, duration, outputs)
        return success
    
    def run_training_test(self, quick_test: bool = True) -> bool:
        """Run YOLO11n training test"""
        start_time = time.time()
        
        epochs = self.config['testing']['quick_test_epochs'] if quick_test else self.config['pipeline']['epochs']
        batch_size = self.config['testing']['test_batch_size'] if quick_test else self.config['pipeline']['batch_size']
        
        cmd = [
            sys.executable, 'scripts/train_yolo11n.py',
            '--data', f"{self.config['pipeline']['output_dataset_path']}/data.yaml",
            '--epochs', str(epochs),
            '--batch', str(batch_size),
            '--device', self.config['pipeline']['device'],
            '--project', f"test_training_{self.pipeline_id}"
        ]
        
        test_name = "Quick Training Test" if quick_test else "Full Training"
        success, stdout, stderr = self.run_command(cmd, test_name, timeout=1800 if quick_test else 7200)
        duration = time.time() - start_time
        
        # Find model outputs
        outputs = []
        if success:
            runs_dir = Path('runs/train')
            if runs_dir.exists():
                latest_run = max(runs_dir.glob(f"test_training_{self.pipeline_id}*"), 
                               key=os.path.getctime, default=None)
                if latest_run:
                    weights_dir = latest_run / 'weights'
                    if weights_dir.exists():
                        for weight_file in ['best.pt', 'last.pt']:
                            weight_path = weights_dir / weight_file
                            if weight_path.exists():
                                outputs.append(str(weight_path))
        
        self.record_pipeline_step(test_name, success, duration, outputs)
        return success
    
    def run_auto_labeling_test(self) -> bool:
        """Run SAM2+CLIP auto-labeling test"""
        start_time = time.time()
        
        cmd = [
            sys.executable, 'scripts/sam2_clip_auto_labeling.py',
            '--image-dir', 'test_images',
            '--output-dir', f'sam2_test_output_{self.pipeline_id}',
            '--confidence', '0.3',
            '--visualize'
        ]
        
        success, stdout, stderr = self.run_command(cmd, "Auto-labeling Test", timeout=600)
        duration = time.time() - start_time
        
        outputs = []
        if success:
            output_dir = Path(f'sam2_test_output_{self.pipeline_id}')
            if output_dir.exists():
                outputs.extend([str(p) for p in output_dir.rglob('*.txt')])  # Label files
                outputs.extend([str(p) for p in output_dir.rglob('*.jpg')])  # Visualization files
        
        self.record_pipeline_step("Auto-labeling Test", success, duration, outputs)
        return success
    
    def run_model_comparison_test(self) -> bool:
        """Run model comparison test"""
        start_time = time.time()
        
        cmd = [
            sys.executable, 'scripts/model_comparison_framework.py',
            '--data', f"{self.config['pipeline']['output_dataset_path']}/data.yaml",
            '--epochs', str(self.config['testing']['quick_test_epochs']),
            '--models'] + self.config['pipeline']['models_to_compare']
        
        if self.config['pipeline']['test_video_path']:
            cmd.extend(['--video', self.config['pipeline']['test_video_path']])
        
        success, stdout, stderr = self.run_command(cmd, "Model Comparison Test", timeout=3600)
        duration = time.time() - start_time
        
        outputs = []
        if success:
            results_dir = Path('results')
            if results_dir.exists():
                latest_comparison = max(results_dir.glob('model_comparison_*'), 
                                      key=os.path.getctime, default=None)
                if latest_comparison:
                    outputs.extend([str(p) for p in latest_comparison.glob('*.csv')])
                    outputs.extend([str(p) for p in latest_comparison.glob('*.json')])
        
        self.record_pipeline_step("Model Comparison Test", success, duration, outputs)
        return success
    
    def run_deployment_optimization_test(self) -> bool:
        """Run Raspberry Pi deployment optimization test"""
        start_time = time.time()
        
        # Find latest trained model
        runs_dir = Path('runs/train')
        model_path = None
        
        if runs_dir.exists():
            latest_run = max(runs_dir.glob(f"test_training_{self.pipeline_id}*"), 
                           key=os.path.getctime, default=None)
            if latest_run:
                weights_dir = latest_run / 'weights'
                for weight_file in ['best.pt', 'last.pt']:
                    weight_path = weights_dir / weight_file
                    if weight_path.exists():
                        model_path = str(weight_path)
                        break
        
        if not model_path:
            logger.warning("No trained model found, using base model for deployment test")
            model_path = self.config['pipeline']['base_model']
        
        cmd = [
            sys.executable, 'scripts/rpi5_deployment_optimizer.py',
            '--model', model_path,
            '--output', f'deployment_test_{self.pipeline_id}',
            '--format', self.config['pipeline']['export_formats'][0]  # Use first format
        ]
        
        success, stdout, stderr = self.run_command(cmd, "Deployment Optimization Test", timeout=600)
        duration = time.time() - start_time
        
        outputs = []
        if success:
            deployment_dir = Path(f'deployment_test_{self.pipeline_id}')
            if deployment_dir.exists():
                outputs.extend([str(p) for p in deployment_dir.rglob('*')])
        
        self.record_pipeline_step("Deployment Optimization Test", success, duration, outputs)
        return success
    
    def run_evaluation_system_test(self) -> bool:
        """Run evaluation and logging system test"""
        start_time = time.time()
        
        cmd = [
            sys.executable, 'scripts/evaluation_logging_system.py',
            '--action', 'report',
            '--db-path', f'test_experiments_{self.pipeline_id}.db',
            '--output', f'test_evaluation_report_{self.pipeline_id}.json'
        ]
        
        success, stdout, stderr = self.run_command(cmd, "Evaluation System Test", timeout=300)
        duration = time.time() - start_time
        
        outputs = []
        if success:
            report_file = Path(f'test_evaluation_report_{self.pipeline_id}.json')
            if report_file.exists():
                outputs.append(str(report_file))
        
        self.record_pipeline_step("Evaluation System Test", success, duration, outputs)
        return success
    
    def validate_outputs(self) -> bool:
        """Validate all pipeline outputs"""
        logger.info("Validating pipeline outputs...")
        
        validations = []
        
        # 1. Check dataset structure
        dataset_path = Path(self.config['pipeline']['output_dataset_path'])
        if dataset_path.exists():
            required_files = ['data.yaml', 'classes.txt']
            required_dirs = ['images/train', 'images/val', 'labels/train', 'labels/val']
            
            for file in required_files:
                file_path = dataset_path / file
                validations.append(('Dataset file: ' + file, file_path.exists()))
            
            for dir in required_dirs:
                dir_path = dataset_path / dir
                validations.append(('Dataset directory: ' + dir, dir_path.exists()))
        
        # 2. Check training outputs
        runs_dir = Path('runs/train')
        if runs_dir.exists():
            training_runs = list(runs_dir.glob(f"test_training_{self.pipeline_id}*"))
            validations.append(('Training run created', len(training_runs) > 0))
            
            if training_runs:
                latest_run = max(training_runs, key=os.path.getctime)
                weights_dir = latest_run / 'weights'
                validations.append(('Model weights created', weights_dir.exists()))
        
        # 3. Check deployment outputs
        deployment_dir = Path(f'deployment_test_{self.pipeline_id}')
        if deployment_dir.exists():
            validations.append(('Deployment package created', True))
            readme_file = deployment_dir / 'README.md'
            validations.append(('Deployment README created', readme_file.exists()))
        
        # Log validation results
        passed = sum(1 for _, result in validations if result)
        total = len(validations)
        
        logger.info(f"Validation results: {passed}/{total} passed")
        
        for description, result in validations:
            status = "✅" if result else "❌"
            logger.info(f"{status} {description}")
        
        return passed == total
    
    def run_memory_profiling(self) -> Dict:
        """Run memory profiling during training"""
        try:
            import psutil
            
            logger.info("Starting memory profiling...")
            
            # Simple memory monitoring during a quick training run
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Run quick training with monitoring
            start_time = time.time()
            cmd = [
                sys.executable, 'scripts/train_yolo11n.py',
                '--data', f"{self.config['pipeline']['output_dataset_path']}/data.yaml",
                '--epochs', '1',
                '--batch', '2',
                '--device', 'cpu',  # Use CPU for consistent profiling
                '--project', f"memory_test_{self.pipeline_id}"
            ]
            
            max_memory = initial_memory
            memory_samples = []
            
            # Start subprocess
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Monitor memory usage
            while proc.poll() is None:
                try:
                    current_memory = psutil.Process(proc.pid).memory_info().rss / 1024 / 1024
                    max_memory = max(max_memory, current_memory)
                    memory_samples.append(current_memory)
                    time.sleep(1)
                except psutil.NoSuchProcess:
                    break
            
            proc.wait()
            
            duration = time.time() - start_time
            avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0
            
            profile_results = {
                'initial_memory_mb': initial_memory,
                'max_memory_mb': max_memory,
                'avg_memory_mb': avg_memory,
                'memory_increase_mb': max_memory - initial_memory,
                'duration_seconds': duration,
                'samples_count': len(memory_samples)
            }
            
            logger.info(f"Memory profiling completed: Max={max_memory:.1f}MB, "
                       f"Avg={avg_memory:.1f}MB, Increase={max_memory-initial_memory:.1f}MB")
            
            return profile_results
            
        except Exception as e:
            logger.error(f"Memory profiling failed: {e}")
            return {}
    
    def run_benchmarks(self) -> Dict:
        """Run performance benchmarks"""
        logger.info("Running performance benchmarks...")
        
        benchmarks = {}
        
        try:
            # 1. Dataset conversion benchmark
            start_time = time.time()
            dataset_path = Path(self.config['pipeline']['output_dataset_path'])
            if dataset_path.exists():
                # Count files
                train_images = len(list((dataset_path / 'images' / 'train').glob('*.jpg')))
                val_images = len(list((dataset_path / 'images' / 'val').glob('*.jpg')))
                train_labels = len(list((dataset_path / 'labels' / 'train').glob('*.txt')))
                val_labels = len(list((dataset_path / 'labels' / 'val').glob('*.txt')))
                
                benchmarks['dataset_conversion'] = {
                    'train_images': train_images,
                    'val_images': val_images,
                    'train_labels': train_labels,
                    'val_labels': val_labels,
                    'total_samples': train_images + val_images
                }
            
            # 2. Training speed benchmark (if we have training logs)
            runs_dir = Path('runs/train')
            if runs_dir.exists():
                training_runs = list(runs_dir.glob(f"test_training_{self.pipeline_id}*"))
                if training_runs:
                    # Simple training speed estimate
                    for run_dir in training_runs:
                        results_file = run_dir / 'results.csv'
                        if results_file.exists():
                            # Could parse training results here
                            benchmarks['training_completed'] = True
                            break
            
            logger.info(f"Benchmarks completed: {len(benchmarks)} metrics collected")
            return benchmarks
            
        except Exception as e:
            logger.error(f"Benchmarking failed: {e}")
            return {}
    
    def generate_report(self) -> Dict:
        """Generate comprehensive pipeline report"""
        logger.info("Generating comprehensive report...")
        
        total_duration = (datetime.now() - self.start_time).total_seconds()
        
        # Count successes and failures
        test_passed = sum(1 for test in self.test_results if test['success'])
        test_total = len(self.test_results)
        step_passed = sum(1 for step in self.pipeline_steps if step['success'])
        step_total = len(self.pipeline_steps)
        
        report = {
            'pipeline_info': {
                'pipeline_id': self.pipeline_id,
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_duration_seconds': total_duration,
                'total_duration_formatted': f"{total_duration/3600:.2f} hours"
            },
            'configuration': self.config,
            'summary': {
                'pipeline_steps_passed': step_passed,
                'pipeline_steps_total': step_total,
                'pipeline_success_rate': step_passed / step_total if step_total > 0 else 0,
                'tests_passed': test_passed,
                'tests_total': test_total,
                'test_success_rate': test_passed / test_total if test_total > 0 else 0,
                'overall_success': step_passed == step_total and test_passed == test_total
            },
            'pipeline_steps': self.pipeline_steps,
            'test_results': self.test_results,
            'validation_results': {},  # Will be filled by validation
            'performance_metrics': {},  # Will be filled by benchmarks
            'recommendations': []
        }
        
        # Add recommendations based on results
        if step_passed < step_total:
            report['recommendations'].append(
                "Some pipeline steps failed. Check individual step logs for details."
            )
        
        if test_passed < test_total:
            report['recommendations'].append(
                "Some tests failed. Review test logs and fix issues before production deployment."
            )
        
        if step_passed == step_total and test_passed == test_total:
            report['recommendations'].append(
                "All pipeline steps and tests passed. System is ready for production use."
            )
        
        # Save report
        report_file = self.results_dir / 'pipeline_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Pipeline report saved: {report_file}")
        return report
    
    def cleanup_test_files(self):
        """Clean up temporary test files"""
        if not self.config['pipeline']['cleanup_after_test']:
            logger.info("Skipping cleanup (cleanup_after_test = False)")
            return
        
        logger.info("Cleaning up test files...")
        
        cleanup_patterns = [
            'test_images/',
            'test_video.mp4',
            f'sam2_test_output_{self.pipeline_id}/',
            f'deployment_test_{self.pipeline_id}/',
            f'test_experiments_{self.pipeline_id}.db',
            f'test_evaluation_report_{self.pipeline_id}.json'
        ]
        
        for pattern in cleanup_patterns:
            path = Path(pattern)
            try:
                if path.is_file():
                    path.unlink()
                    logger.debug(f"Removed file: {path}")
                elif path.is_dir():
                    shutil.rmtree(path)
                    logger.debug(f"Removed directory: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove {path}: {e}")
    
    def run_full_pipeline(self) -> bool:
        """Run the complete CAMINA pipeline"""
        logger.info("🚀 Starting CAMINA Dataset Expansion Pipeline")
        logger.info("="*60)
        
        success = True
        
        try:
            # Phase 1: Prerequisites
            logger.info("Phase 1: Prerequisites and Setup")
            if not self.check_dependencies():
                return False
            
            if not self.create_test_data():
                return False
            
            # Phase 2: Core Pipeline
            logger.info("Phase 2: Core Pipeline Execution")
            
            # Step 1: Dataset Conversion
            if not self.run_dataset_conversion():
                success = False
            
            # Step 2: Training Test
            if not self.run_training_test(quick_test=True):
                success = False
            
            # Step 3: Auto-labeling Test
            if not self.run_auto_labeling_test():
                success = False
            
            # Step 4: Model Comparison Test
            if not self.run_model_comparison_test():
                success = False
            
            # Step 5: Deployment Optimization Test
            if not self.run_deployment_optimization_test():
                success = False
            
            # Step 6: Evaluation System Test
            if not self.run_evaluation_system_test():
                success = False
            
            # Phase 3: Validation and Analysis
            logger.info("Phase 3: Validation and Analysis")
            
            # Validate outputs
            validation_success = self.validate_outputs()
            
            # Run performance profiling if requested
            if self.config['testing']['run_memory_profiling']:
                memory_profile = self.run_memory_profiling()
                self.test_results.append({
                    'test_name': 'Memory Profiling',
                    'success': len(memory_profile) > 0,
                    'duration': 0,
                    'timestamp': datetime.now().isoformat(),
                    'details': memory_profile
                })
            
            # Run benchmarks if requested
            if self.config['testing']['run_benchmarks']:
                benchmark_results = self.run_benchmarks()
                self.test_results.append({
                    'test_name': 'Performance Benchmarks',
                    'success': len(benchmark_results) > 0,
                    'duration': 0,
                    'timestamp': datetime.now().isoformat(),
                    'details': benchmark_results
                })
            
            # Phase 4: Reporting
            logger.info("Phase 4: Report Generation")
            
            if self.config['output']['create_report']:
                report = self.generate_report()
                
                # Print summary
                logger.info("="*60)
                logger.info("PIPELINE EXECUTION SUMMARY")
                logger.info("="*60)
                logger.info(f"Pipeline ID: {self.pipeline_id}")
                logger.info(f"Total Duration: {report['pipeline_info']['total_duration_formatted']}")
                logger.info(f"Pipeline Steps: {report['summary']['pipeline_steps_passed']}/{report['summary']['pipeline_steps_total']}")
                logger.info(f"Tests: {report['summary']['tests_passed']}/{report['summary']['tests_total']}")
                logger.info(f"Overall Success: {'✅ YES' if report['summary']['overall_success'] else '❌ NO'}")
                logger.info("="*60)
                
                # Print recommendations
                if report['recommendations']:
                    logger.info("RECOMMENDATIONS:")
                    for i, rec in enumerate(report['recommendations'], 1):
                        logger.info(f"{i}. {rec}")
                    logger.info("="*60)
            
            # Phase 5: Cleanup
            if self.config['pipeline']['cleanup_after_test']:
                self.cleanup_test_files()
            
            return success and validation_success
            
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
            return False
        except Exception as e:
            logger.error(f"Pipeline failed with exception: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def run_tests_only(self) -> bool:
        """Run only the test suite without full pipeline"""
        logger.info("🧪 Running CAMINA Pipeline Test Suite")
        logger.info("="*60)
        
        # Create test data
        if not self.create_test_data():
            return False
        
        # Run individual tests
        tests = [
            ("Dependencies Check", lambda: self.check_dependencies()),
            ("Dataset Structure", lambda: Path(self.config['pipeline']['sdl_dataset_path']).exists()),
            ("Basic Script Syntax", self.test_script_syntax),
            ("Memory Usage", lambda: self.run_memory_profiling() != {}),
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            start_time = time.time()
            try:
                success = test_func()
                duration = time.time() - start_time
                self.record_test(test_name, success, duration)
                if not success:
                    all_passed = False
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Test '{test_name}' failed with exception: {e}")
                self.record_test(test_name, False, duration, {'error': str(e)})
                all_passed = False
        
        # Generate test report
        if self.config['output']['create_report']:
            self.generate_report()
        
        return all_passed
    
    def test_script_syntax(self) -> bool:
        """Test that all Python scripts have valid syntax"""
        scripts_dir = Path('scripts')
        if not scripts_dir.exists():
            return False
        
        python_files = list(scripts_dir.glob('*.py'))
        all_valid = True
        
        for script in python_files:
            try:
                with open(script, 'r') as f:
                    compile(f.read(), str(script), 'exec')
                logger.debug(f"✅ Syntax OK: {script.name}")
            except SyntaxError as e:
                logger.error(f"❌ Syntax Error in {script.name}: {e}")
                all_valid = False
            except Exception as e:
                logger.error(f"❌ Error reading {script.name}: {e}")
                all_valid = False
        
        return all_valid

def main():
    parser = argparse.ArgumentParser(description='CAMINA Pipeline Runner and Test Suite')
    parser.add_argument('--mode', choices=['full', 'test', 'pipeline'], default='full',
                       help='Run mode: full (pipeline+tests), test (tests only), pipeline (pipeline only)')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--quick', action='store_true',
                       help='Quick mode with reduced epochs and batch sizes')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip cleanup of test files')
    parser.add_argument('--output-dir', default='pipeline_results',
                       help='Output directory for results')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize runner
    runner = CAMINAPipelineRunner(args.config)
    
    # Override config with command line arguments
    if args.quick:
        runner.config['testing']['quick_test_epochs'] = 1
        runner.config['testing']['test_batch_size'] = 2
        runner.config['pipeline']['epochs'] = 5
    
    if args.no_cleanup:
        runner.config['pipeline']['cleanup_after_test'] = False
    
    if args.output_dir:
        runner.config['output']['results_dir'] = args.output_dir
    
    # Run based on mode
    try:
        if args.mode == 'full':
            success = runner.run_full_pipeline()
        elif args.mode == 'test':
            success = runner.run_tests_only()
        elif args.mode == 'pipeline':
            success = runner.run_full_pipeline()
        
        exit_code = 0 if success else 1
        logger.info(f"Pipeline runner completed with exit code: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Runner interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Runner failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()