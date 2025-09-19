#!/usr/bin/env python3
"""
Optimized YOLO-World Supplement Script for CAMINA Dataset

This script efficiently runs YOLO-World detection on an existing dataset to detect
e-scooter, SUV, and delivery_van classes and merges results with existing COCO + cyclist labels.

Key optimizations:
- Batch processing for efficient GPU utilization
- Memory management with CUDA cleanup
- Robust error handling and recovery
- Concurrent I/O operations
- Production-ready logging and monitoring

Author: CAMINA Team (Optimized by Claude)
Date: 2025-09-18
"""

import os
import sys
import json
import logging
import argparse
import gc
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import warnings

import cv2
import numpy as np
import torch
from tqdm import tqdm
from PIL import Image
import yaml

# Suppress unnecessary warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Configure logging with more detailed formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Performance tracking
class PerformanceTracker:
    """Track processing performance metrics"""

    def __init__(self):
        self.start_time = time.time()
        self.processed_images = 0
        self.total_detections = 0
        self.gpu_memory_peaks = []

    def record_batch(self, batch_size: int, detections: int):
        """Record batch processing metrics"""
        self.processed_images += batch_size
        self.total_detections += detections

        if torch.cuda.is_available():
            memory_mb = torch.cuda.memory_allocated() / 1024 / 1024
            self.gpu_memory_peaks.append(memory_mb)

    def get_stats(self) -> Dict:
        """Get performance statistics"""
        elapsed = time.time() - self.start_time
        return {
            'total_time_sec': elapsed,
            'images_per_second': self.processed_images / elapsed if elapsed > 0 else 0,
            'total_images': self.processed_images,
            'total_detections': self.total_detections,
            'avg_detections_per_image': self.total_detections / max(self.processed_images, 1),
            'peak_gpu_memory_mb': max(self.gpu_memory_peaks) if self.gpu_memory_peaks else 0
        }


@contextmanager
def cuda_memory_manager():
    """Context manager for CUDA memory cleanup"""
    try:
        yield
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()


class OptimizedYOLOWorldSupplementor:
    """Optimized YOLO-World supplementor with batch processing and memory management"""

    def __init__(self, config_path: str = "dataset_creator_config.json"):
        """Initialize with configuration and optimization settings"""
        self.config = self._load_config_with_validation(config_path)
        self.model = None
        self.device = self._setup_device()
        self.performance_tracker = PerformanceTracker()

        # Setup class mappings from config (fixed alignment issue)
        self._setup_class_mappings()

        # Batch processing configuration
        self.batch_size = self._calculate_optimal_batch_size()
        self.max_workers = min(4, os.cpu_count() or 4)

        logger.info(f"Initialized with device: {self.device}, batch_size: {self.batch_size}")

    def _load_config_with_validation(self, config_path: str) -> Dict:
        """Load and validate configuration with detailed error handling"""
        try:
            config_path = Path(config_path)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Validate required sections
            required_sections = ['classes', 'confidence_thresholds', 'text_prompts', 'yolo_world_config']
            missing_sections = [section for section in required_sections if section not in config]
            if missing_sections:
                raise ValueError(f"Missing required configuration sections: {missing_sections}")

            logger.info(f"Configuration loaded and validated from {config_path}")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def _setup_device(self) -> torch.device:
        """Setup and optimize device configuration"""
        if torch.cuda.is_available():
            device = torch.device('cuda')
            # Log GPU information
            gpu_name = torch.cuda.get_device_name()
            memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"Using GPU: {gpu_name} ({memory_gb:.1f}GB)")

            # Set memory growth to avoid OOM
            torch.cuda.set_per_process_memory_fraction(0.9)

        else:
            device = torch.device('cpu')
            logger.warning("CUDA not available, falling back to CPU (will be significantly slower)")

        return device

    def _setup_class_mappings(self):
        """Setup class mappings aligned with configuration"""
        # Get existing classes (COCO + cyclist) from hybrid config
        existing_classes_config = self.config.get('hybrid_config', {}).get('coco_classes', {})
        new_classes_config = self.config.get('hybrid_config', {}).get('new_classes', {})

        # Convert string keys to integers and create mappings
        self.existing_classes = {int(k): v for k, v in existing_classes_config.items()}
        self.new_classes = {int(k): v for k, v in new_classes_config.items()}

        # Combined mapping for output
        self.all_classes = {**self.existing_classes, **self.new_classes}

        logger.info(f"Existing classes: {list(self.existing_classes.values())}")
        logger.info(f"New classes to detect: {list(self.new_classes.values())}")

    def _calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on available memory"""
        if not torch.cuda.is_available():
            return 1

        memory_config = self.config.get('memory_config', {})
        max_vram_gb = memory_config.get('max_vram_gb', 8.0)
        base_batch_size = memory_config.get('batch_size_base', 4)
        max_batch_size = memory_config.get('max_batch_size', 16)

        # Get actual GPU memory
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3

        # Conservative calculation: use 70% of available memory
        usable_memory = min(max_vram_gb, gpu_memory_gb * 0.7)

        # Estimate: ~1GB per 4 images for YOLOv8l-world
        estimated_batch_size = int(usable_memory * 4)

        # Clamp to reasonable range
        batch_size = min(max(estimated_batch_size, 1), max_batch_size)

        return batch_size

    def initialize_yolo_world(self) -> bool:
        """Initialize YOLO-World model with optimized settings"""
        try:
            from ultralytics import YOLO

            model_name = self.config['yolo_world_config']['model_name']
            logger.info(f"Initializing YOLO-World model: {model_name}")

            # Initialize model with device specification
            self.model = YOLO(model_name).to(self.device)

            # Set custom vocabulary for new classes only
            new_class_names = list(self.new_classes.values())
            self.model.set_classes(new_class_names)

            # Optimize model for inference
            if torch.cuda.is_available():
                self.model.model.half()  # Use FP16 for memory efficiency
                torch.backends.cudnn.benchmark = True  # Optimize for consistent input sizes

            logger.info(f"YOLO-World initialized with classes: {new_class_names}")
            logger.info(f"Model optimization: {'FP16+CuDNN' if torch.cuda.is_available() else 'CPU'}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize YOLO-World: {e}")
            return False

    def _batch_images(self, image_paths: List[Path], batch_size: int) -> Generator[List[Path], None, None]:
        """Generate batches of image paths"""
        for i in range(0, len(image_paths), batch_size):
            yield image_paths[i:i + batch_size]

    def _load_image_batch(self, image_paths: List[Path]) -> Tuple[List[np.ndarray], List[Tuple[int, int]]]:
        """Load a batch of images with concurrent processing"""
        images = []
        dimensions = []

        def load_single_image(path: Path) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int]]]:
            """Load single image with error handling"""
            try:
                image = cv2.imread(str(path))
                if image is None:
                    logger.warning(f"Could not load image: {path}")
                    return None, None

                h, w = image.shape[:2]
                return image, (h, w)

            except Exception as e:
                logger.warning(f"Error loading image {path}: {e}")
                return None, None

        # Use concurrent loading for I/O bound operations
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {executor.submit(load_single_image, path): path
                             for path in image_paths}

            for future in as_completed(future_to_path):
                image, dims = future.result()
                if image is not None:
                    images.append(image)
                    dimensions.append(dims)

        return images, dimensions

    def detect_batch_new_classes(self, image_batch: List[np.ndarray],
                                dimensions: List[Tuple[int, int]],
                                confidence_threshold: float = 0.1) -> List[List[Dict]]:
        """Detect new classes in a batch of images"""
        batch_detections = []

        if not image_batch:
            return batch_detections

        try:
            with cuda_memory_manager():
                # Run batch inference
                results = self.model(image_batch, conf=confidence_threshold, verbose=False)

                # Process results for each image
                for idx, (result, (height, width)) in enumerate(zip(results, dimensions)):
                    image_detections = []

                    if result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes.xyxy.cpu().numpy()
                        confidences = result.boxes.conf.cpu().numpy()
                        class_ids = result.boxes.cls.cpu().numpy().astype(int)

                        for box, conf, cls_id in zip(boxes, confidences, class_ids):
                            # Validate class_id range
                            if 0 <= cls_id < len(self.new_classes):
                                class_name = list(self.new_classes.values())[cls_id]

                                # Apply class-specific confidence threshold
                                class_threshold = self.config['confidence_thresholds'].get(class_name, 0.25)

                                if conf >= class_threshold:
                                    # Convert to YOLO format (normalized coordinates)
                                    x1, y1, x2, y2 = box
                                    x_center = (x1 + x2) / 2 / width
                                    y_center = (y1 + y2) / 2 / height
                                    bbox_width = (x2 - x1) / width
                                    bbox_height = (y2 - y1) / height

                                    # Map to final class ID (maintain alignment with config)
                                    final_class_id = min(self.new_classes.keys()) + cls_id

                                    # Validate bbox coordinates
                                    if all(0 <= coord <= 1 for coord in [x_center, y_center, bbox_width, bbox_height]):
                                        image_detections.append({
                                            'class_id': final_class_id,
                                            'class_name': class_name,
                                            'confidence': float(conf),
                                            'bbox': [x_center, y_center, bbox_width, bbox_height]
                                        })

                    batch_detections.append(image_detections)

                # Record performance metrics
                total_detections = sum(len(dets) for dets in batch_detections)
                self.performance_tracker.record_batch(len(image_batch), total_detections)

        except Exception as e:
            logger.error(f"Batch detection failed: {e}")
            # Return empty results for failed batch
            batch_detections = [[] for _ in image_batch]

        return batch_detections

    def _load_existing_labels_safe(self, label_path: Path) -> List[List[float]]:
        """Load existing YOLO format labels with comprehensive error handling"""
        labels = []

        if not label_path.exists():
            return labels

        try:
            with open(label_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split()
                        if len(parts) < 5:
                            logger.warning(f"Invalid label format in {label_path}:{line_num}")
                            continue

                        # Validate class_id and coordinates
                        class_id = int(float(parts[0]))  # Handle float class_ids
                        coordinates = [float(x) for x in parts[1:5]]

                        # Validate coordinate ranges
                        if not all(0 <= coord <= 1 for coord in coordinates):
                            logger.warning(f"Invalid coordinates in {label_path}:{line_num}")
                            continue

                        labels.append([float(class_id)] + coordinates)

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing line {line_num} in {label_path}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to load labels from {label_path}: {e}")

        return labels

    def _save_combined_labels_safe(self, output_path: Path, existing_labels: List[List[float]],
                                  new_detections: List[Dict]) -> bool:
        """Save combined labels with atomic write and validation"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file first (atomic write)
            temp_path = output_path.with_suffix('.tmp')

            with open(temp_path, 'w', encoding='utf-8') as f:
                # Write existing labels
                for label in existing_labels:
                    class_id = int(label[0])
                    bbox = label[1:5]
                    # Validate before writing
                    if all(0 <= coord <= 1 for coord in bbox):
                        f.write(f"{class_id} {' '.join(f'{coord:.6f}' for coord in bbox)}\n")

                # Write new detections
                for detection in new_detections:
                    class_id = detection['class_id']
                    bbox = detection['bbox']
                    # Validate before writing
                    if all(0 <= coord <= 1 for coord in bbox):
                        f.write(f"{class_id} {' '.join(f'{coord:.6f}' for coord in bbox)}\n")

            # Atomic move
            temp_path.replace(output_path)
            return True

        except Exception as e:
            logger.error(f"Failed to save labels to {output_path}: {e}")
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
            return False

    def process_dataset_optimized(self, dataset_path: str, output_path: str):
        """Process entire dataset with optimized batch processing"""
        dataset_path = Path(dataset_path)
        output_path = Path(output_path)

        logger.info(f"Processing dataset: {dataset_path} -> {output_path}")

        # Validate input dataset
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {dataset_path}")

        # Create output directory structure
        output_path.mkdir(parents=True, exist_ok=True)

        total_stats = {class_name: 0 for class_name in self.new_classes.values()}

        # Process train and test splits
        for split in ['train', 'test']:
            split_input = dataset_path / split
            split_output = output_path / split

            if not split_input.exists():
                logger.warning(f"Split directory not found: {split_input}")
                continue

            logger.info(f"Processing {split} split with batch size {self.batch_size}...")

            # Create output directories
            (split_output / 'images').mkdir(parents=True, exist_ok=True)
            (split_output / 'labels').mkdir(parents=True, exist_ok=True)

            # Copy images efficiently
            self._copy_images_parallel(split_input / 'images', split_output / 'images')

            # Get all image files
            images_dir = split_input / 'images'
            labels_dir = split_input / 'labels'

            if not images_dir.exists():
                logger.warning(f"Images directory not found: {images_dir}")
                continue

            # Get supported image files
            supported_extensions = self.config.get('detection_settings', {}).get('supported_formats', ['.jpg', '.png'])
            image_files = []
            for ext in supported_extensions:
                image_files.extend(images_dir.glob(f'*{ext}'))
                image_files.extend(images_dir.glob(f'*{ext.upper()}'))

            if not image_files:
                logger.warning(f"No supported images found in {images_dir}")
                continue

            logger.info(f"Found {len(image_files)} images to process")

            split_stats = {class_name: 0 for class_name in self.new_classes.values()}

            # Process in batches
            with tqdm(total=len(image_files), desc=f"Processing {split}", unit="img") as pbar:
                for batch_paths in self._batch_images(image_files, self.batch_size):
                    try:
                        # Load batch of images
                        images, dimensions = self._load_image_batch(batch_paths)

                        if not images:
                            pbar.update(len(batch_paths))
                            continue

                        # Run batch detection
                        batch_detections = self.detect_batch_new_classes(images, dimensions)

                        # Process results for each image in batch
                        for img_path, detections in zip(batch_paths, batch_detections):
                            # Load existing labels
                            label_file = labels_dir / f"{img_path.stem}.txt"
                            existing_labels = self._load_existing_labels_safe(label_file)

                            # Update statistics
                            for detection in detections:
                                split_stats[detection['class_name']] += 1

                            # Save combined labels
                            output_label_file = split_output / 'labels' / f"{img_path.stem}.txt"
                            self._save_combined_labels_safe(output_label_file, existing_labels, detections)

                        pbar.update(len(batch_paths))

                        # Periodic memory cleanup
                        if pbar.n % (self.batch_size * 10) == 0:
                            with cuda_memory_manager():
                                pass

                    except Exception as e:
                        logger.error(f"Error processing batch: {e}")
                        pbar.update(len(batch_paths))
                        continue

            # Log split statistics
            logger.info(f"{split.capitalize()} detection statistics:")
            for class_name, count in split_stats.items():
                logger.info(f"  {class_name}: {count} detections")
                total_stats[class_name] += count

        # Create updated configuration files
        self._create_updated_data_yaml(output_path)
        self._generate_comprehensive_report(dataset_path, output_path, total_stats)

        # Log performance metrics
        perf_stats = self.performance_tracker.get_stats()
        logger.info("=== PERFORMANCE METRICS ===")
        logger.info(f"Total processing time: {perf_stats['total_time_sec']:.1f}s")
        logger.info(f"Images per second: {perf_stats['images_per_second']:.2f}")
        logger.info(f"Total detections: {perf_stats['total_detections']}")
        logger.info(f"Peak GPU memory: {perf_stats['peak_gpu_memory_mb']:.1f}MB")

    def _copy_images_parallel(self, src_dir: Path, dst_dir: Path):
        """Copy images with parallel processing"""
        if not src_dir.exists():
            logger.warning(f"Source images directory not found: {src_dir}")
            return

        logger.info(f"Copying images: {src_dir} -> {dst_dir}")

        # Use system copy for efficiency
        try:
            import shutil
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            logger.info("Images copied successfully")
        except Exception as e:
            logger.error(f"Failed to copy images: {e}")

    def _create_updated_data_yaml(self, output_path: Path):
        """Create updated data.yaml with all classes"""
        # Get class names in correct order
        class_names = []
        for i in range(len(self.all_classes)):
            if i in self.all_classes:
                class_names.append(self.all_classes[i])

        data_yaml = {
            'train': '../train/images',
            'val': '../test/images',  # Use test as validation
            'test': '../test/images',
            'nc': len(self.all_classes),
            'names': class_names
        }

        yaml_path = output_path / 'data.yaml'
        try:
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data_yaml, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Updated data.yaml created with {len(class_names)} classes")
        except Exception as e:
            logger.error(f"Failed to create data.yaml: {e}")

    def _generate_comprehensive_report(self, input_path: Path, output_path: Path, detection_stats: Dict):
        """Generate comprehensive summary report"""
        logger.info("Generating comprehensive summary report...")

        # Performance metrics
        perf_stats = self.performance_tracker.get_stats()

        # Count instances in each split
        summary = {
            'dataset_info': {
                'input_path': str(input_path),
                'output_path': str(output_path),
                'processing_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_classes': len(self.all_classes),
                'existing_classes': list(self.existing_classes.values()),
                'new_classes_added': list(self.new_classes.values())
            },
            'performance_metrics': perf_stats,
            'detection_summary': detection_stats,
            'class_counts': {}
        }

        # Detailed class analysis per split
        for split in ['train', 'test']:
            split_dir = output_path / split / 'labels'
            if not split_dir.exists():
                continue

            class_counts = {i: 0 for i in range(len(self.all_classes))}

            for label_file in split_dir.glob('*.txt'):
                try:
                    with open(label_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                class_id = int(float(line.split()[0]))
                                if 0 <= class_id < len(self.all_classes):
                                    class_counts[class_id] += 1
                except Exception as e:
                    logger.warning(f"Error reading {label_file}: {e}")

            summary['class_counts'][split] = {}
            for class_id, count in class_counts.items():
                if class_id in self.all_classes:
                    class_name = self.all_classes[class_id]
                    summary['class_counts'][split][class_name] = count

        # Save detailed summary
        try:
            report_path = output_path / 'detection_summary.json'
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            logger.info(f"Comprehensive report saved to: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save summary report: {e}")

        # Print summary to console
        self._print_summary_report(summary)

    def _print_summary_report(self, summary: Dict):
        """Print formatted summary report to console"""
        logger.info("=== DETECTION SUMMARY ===")

        perf = summary['performance_metrics']
        logger.info(f"Processing time: {perf['total_time_sec']:.1f}s")
        logger.info(f"Throughput: {perf['images_per_second']:.2f} images/sec")
        logger.info(f"Total new detections: {perf['total_detections']}")

        for split, counts in summary['class_counts'].items():
            logger.info(f"\n{split.upper()} split class distribution:")
            for class_name, count in counts.items():
                marker = "NEW" if class_name in self.new_classes.values() else "EXISTING"
                logger.info(f"  {class_name:15s}: {count:6d} instances ({marker})")


def main():
    """Main entry point with enhanced argument parsing and error handling"""
    parser = argparse.ArgumentParser(
        description="Optimized YOLO-World supplement for CAMINA dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dataset data/dataset_v4i_yolov11 --output outputs/dataset_updated
  %(prog)s --dataset /path/to/dataset --batch-size 8 --workers 4
        """
    )

    parser.add_argument("--dataset", default="data/dataset_v4i_yolov11",
                       help="Path to input dataset (default: data/dataset_v4i_yolov11)")
    parser.add_argument("--output", default="outputs/dataset_v4i_yolov11_updated",
                       help="Path to output dataset (default: outputs/dataset_v4i_yolov11_updated)")
    parser.add_argument("--config", default="dataset_creator_config.json",
                       help="Path to configuration file (default: dataset_creator_config.json)")
    parser.add_argument("--batch-size", type=int, default=None,
                       help="Override batch size (default: auto-calculated)")
    parser.add_argument("--workers", type=int, default=None,
                       help="Number of worker threads for I/O (default: auto)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=== OPTIMIZED CAMINA YOLO-World Supplement ===")
    logger.info(f"Input dataset: {args.dataset}")
    logger.info(f"Output path: {args.output}")
    logger.info(f"Configuration: {args.config}")

    try:
        # Initialize supplementor
        supplementor = OptimizedYOLOWorldSupplementor(args.config)

        # Override batch size if specified
        if args.batch_size:
            supplementor.batch_size = args.batch_size
            logger.info(f"Batch size overridden to: {args.batch_size}")

        # Override worker count if specified
        if args.workers:
            supplementor.max_workers = args.workers
            logger.info(f"Worker threads overridden to: {args.workers}")

        # Initialize YOLO-World model
        if not supplementor.initialize_yolo_world():
            logger.error("Failed to initialize YOLO-World model")
            sys.exit(1)

        # Process dataset
        supplementor.process_dataset_optimized(args.dataset, args.output)

        logger.info("=== PROCESSING COMPLETED SUCCESSFULLY ===")

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Processing failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        # Final cleanup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()