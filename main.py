#!/usr/bin/env python3
"""
CAMINA Main Entry Point

Production-ready two-stage detection pipeline for urban mobility object detection.

This is the single entry point for the CAMINA system that implements:
- Stage A: YOLO11n + cyclist logic for COCO classes
- Stage B: YOLO-World for new classes (e-scooter, SUV, delivery_van)
- NMS consolidation and COCO-style output

Usage:
    python main.py --config configs/config.yaml
    python main.py --images_dir data/images --device cuda:0 --batch 16 --clean
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config import load_config, setup_environment_from_config, CAMINAConfig
from src.detector_yolo11n import YOLO11nDetector
from src.detector_yolo_world import YOLOWorldDetector
from src.merger_nms import NMSConsolidator
from src.escooter_logic import EscooterSpatialAssociator
from src.io_utils import ImageLoader, AnnotationWriter, DatasetValidator, create_output_directories
from src.utils import (
    setup_logging, MemoryManager, PerformanceMonitor, BatchProcessor,
    validate_device, clean_output_directory, format_duration, get_git_info
)

logger = logging.getLogger(__name__)


class CAMINAPipeline:
    """
    Main CAMINA detection pipeline orchestrating two-stage detection.
    """

    def __init__(self, config: CAMINAConfig):
        """
        Initialize CAMINA pipeline.

        Args:
            config: CAMINA configuration instance
        """
        self.config = config
        self.stage_a_detector = None
        self.stage_b_detector = None
        self.escooter_associator = None
        self.nms_consolidator = None
        self.image_loader = ImageLoader(cache_size=50)
        self.memory_manager = MemoryManager(
            max_memory_gb=config.performance.max_vram_gb,
            threshold=config.performance.memory_threshold
        )
        self.performance_monitor = PerformanceMonitor()
        self.batch_processor = BatchProcessor(
            base_batch_size=config.performance.batch_size_base,
            max_batch_size=config.performance.max_batch_size,
            min_batch_size=config.performance.min_batch_size,
            memory_manager=self.memory_manager
        )

        logger.info(f"Initialized CAMINA pipeline v{config.metadata.version}")

    def initialize(self) -> bool:
        """
        Initialize all pipeline components.

        Returns:
            True if initialization successful
        """
        logger.info("Initializing CAMINA pipeline components...")

        try:
            # Initialize Stage A detector (YOLO11n + cyclist logic)
            if self.config.stage_a.enabled:
                logger.info("Initializing Stage A: YOLO11n + cyclist logic")
                self.stage_a_detector = YOLO11nDetector(
                    self.config.stage_a,
                    self.config.cyclist_detection
                )
                if not self.stage_a_detector.initialize():
                    logger.error("Failed to initialize Stage A detector")
                    return False
                logger.info("Stage A detector initialized successfully")

            # Initialize Stage B detector (YOLO-World)
            if self.config.stage_b.enabled:
                logger.info("Initializing Stage B: YOLO-World")
                self.stage_b_detector = YOLOWorldDetector(
                    self.config.stage_b,
                    self.config.text_prompts
                )
                if not self.stage_b_detector.initialize():
                    logger.error("Failed to initialize Stage B detector")
                    return False
                logger.info("Stage B detector initialized successfully")

            # Initialize E-scooter spatial associator
            if self.config.escooter_association.enabled:
                logger.info("Initializing E-scooter spatial associator")
                self.escooter_associator = EscooterSpatialAssociator(
                    iou_threshold=self.config.escooter_association.iou_threshold,
                    vertical_margin_px=self.config.escooter_association.vertical_margin_px,
                    spatial_margin_px=self.config.escooter_association.spatial_margin_px,
                    min_bbox_area=self.config.escooter_association.min_bbox_area,
                    confidence_threshold=self.config.escooter_association.confidence_threshold
                )
                logger.info("E-scooter spatial associator initialized successfully")

            # Initialize NMS consolidator
            if self.config.nms_consolidation.enabled:
                logger.info("Initializing NMS consolidator")
                self.nms_consolidator = NMSConsolidator(self.config.nms_consolidation)
                logger.info("NMS consolidator initialized successfully")

            logger.info("All pipeline components initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            return False

    def process_images(self,
                      images_dir: Path,
                      output_dir: Path,
                      batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Process all images in directory using two-stage detection pipeline.

        Args:
            images_dir: Directory containing input images
            output_dir: Directory for output files
            batch_size: Override batch size from config

        Returns:
            Processing results and statistics
        """
        if not self.stage_a_detector and not self.stage_b_detector:
            raise RuntimeError("No detectors initialized")

        # Find all supported images
        supported_formats = set(self.config.detection.supported_formats)
        image_paths = []

        for image_path in images_dir.rglob('*'):
            if image_path.is_file() and image_path.suffix.lower() in supported_formats:
                image_paths.append(image_path)

        if not image_paths:
            logger.warning(f"No supported images found in {images_dir}")
            return {'total_images': 0, 'total_detections': 0, 'processing_time': 0.0}

        logger.info(f"Found {len(image_paths)} images to process")

        # Create output directories
        output_dirs = create_output_directories(
            output_dir,
            ['coco', 'yolo', 'summary', 'visualizations']
        )

        # Initialize annotation writer
        annotation_writer = AnnotationWriter(output_dirs['coco'])

        # Process images
        with self.performance_monitor.time_context('total_processing'):
            detections_per_image = self._process_image_batch(
                image_paths, batch_size or self.config.performance.batch_size_base
            )

        # Save annotations
        class_mapping = self.config.get_all_classes()

        # Save COCO format
        coco_path = annotation_writer.save_coco_annotations(
            detections_per_image, class_mapping
        )

        # Save YOLO format
        annotation_writer_yolo = AnnotationWriter(output_dirs['yolo'])
        yolo_paths = annotation_writer_yolo.save_yolo_annotations(
            detections_per_image, class_mapping
        )

        # Save summary
        summary_writer = AnnotationWriter(output_dirs['summary'])
        summary_path = summary_writer.save_summary_ndjson(
            detections_per_image, class_mapping
        )

        # Validate dataset
        validator = DatasetValidator()
        validation_report = validator.validate_detections(
            detections_per_image, class_mapping
        )

        # Calculate statistics
        total_detections = sum(len(detections) for _, detections in detections_per_image)
        processing_time = self.performance_monitor.timings.get('total_processing', {}).get('duration', 0.0)

        results = {
            'total_images': len(image_paths),
            'total_detections': total_detections,
            'processing_time': processing_time,
            'images_per_second': len(image_paths) / max(processing_time, 0.001),
            'detections_per_image': total_detections / max(len(image_paths), 1),
            'output_files': {
                'coco_annotations': coco_path,
                'yolo_annotations': yolo_paths,
                'summary': summary_path
            },
            'validation_report': validation_report,
            'performance_stats': self.performance_monitor.get_statistics()
        }

        # Log final statistics
        self._log_final_statistics(results)

        return results

    def _process_image_batch(self,
                           image_paths: List[Path],
                           batch_size: int) -> List[Tuple[str, List[Dict]]]:
        """
        Process images in batches using the two-stage pipeline.

        Args:
            image_paths: List of image paths to process
            batch_size: Batch size for processing

        Returns:
            List of (image_path, detections) tuples
        """
        detections_per_image = []

        def process_batch(batch_paths: List[Path]) -> List[Tuple[str, List[Dict]]]:
            """Process a batch of images."""
            batch_results = []

            for image_path in batch_paths:
                with self.performance_monitor.time_context(f'image_{image_path.name}'):
                    # Load image
                    image, dimensions = self.image_loader.load_image(image_path)
                    if image is None or dimensions is None:
                        logger.warning(f"Failed to load image: {image_path}")
                        continue

                    img_width, img_height = dimensions

                    # Stage A: YOLO11n + cyclist logic
                    stage_a_detections = []
                    if self.stage_a_detector:
                        with self.performance_monitor.time_context('stage_a'):
                            stage_a_detections = self.stage_a_detector.detect(
                                image, self.config.stage_a.confidence_threshold
                            )

                    # Stage B: YOLO-World
                    stage_b_detections = []
                    if self.stage_b_detector:
                        with self.performance_monitor.time_context('stage_b'):
                            stage_b_detections = self.stage_b_detector.detect(
                                image, self.config.stage_b.confidence_threshold
                            )

                    # E-scooter spatial association: person + e-scooter → combined e-scooter
                    if self.escooter_associator and stage_a_detections and stage_b_detections:
                        with self.performance_monitor.time_context('escooter_association'):
                            # Extract person detections from Stage A
                            person_detections = [
                                det for det in stage_a_detections
                                if det.get('class_id') == 0  # person class
                            ]

                            # Extract e-scooter detections from Stage B
                            escooter_detections = [
                                det for det in stage_b_detections
                                if det.get('class_id') == 6  # e-scooter class
                            ]

                            if person_detections and escooter_detections:
                                # Perform spatial association
                                combined_escooters, unmatched_persons, unmatched_escooters = (
                                    self.escooter_associator.associate_person_escooter(
                                        person_detections, escooter_detections, img_width, img_height
                                    )
                                )

                                # Update detections:
                                # 1. Remove matched persons and e-scooters from original lists
                                updated_stage_a = [
                                    det for i, det in enumerate(stage_a_detections)
                                    if det.get('class_id') != 0 or i in unmatched_persons
                                ]

                                updated_stage_b = [
                                    det for i, det in enumerate(stage_b_detections)
                                    if det.get('class_id') != 6 or i in unmatched_escooters
                                ]

                                # 2. Add combined e-scooter detections to Stage B
                                updated_stage_b.extend(combined_escooters)

                                # Update detection lists
                                stage_a_detections = updated_stage_a
                                stage_b_detections = updated_stage_b

                                logger.debug(f"E-scooter association: Created {len(combined_escooters)} combined detections")

                    # NMS consolidation
                    final_detections = []
                    if self.nms_consolidator:
                        with self.performance_monitor.time_context('nms_consolidation'):
                            final_detections = self.nms_consolidator.consolidate(
                                stage_a_detections, stage_b_detections,
                                img_width, img_height
                            )
                    else:
                        final_detections = stage_a_detections + stage_b_detections

                    # Update counters
                    self.performance_monitor.increment_counter('images_processed')
                    self.performance_monitor.increment_counter('total_detections', len(final_detections))
                    self.performance_monitor.increment_counter('stage_a_detections', len(stage_a_detections))
                    self.performance_monitor.increment_counter('stage_b_detections', len(stage_b_detections))

                    batch_results.append((str(image_path), final_detections))

                    logger.debug(
                        f"Processed {image_path.name}: "
                        f"Stage A: {len(stage_a_detections)}, "
                        f"Stage B: {len(stage_b_detections)}, "
                        f"Final: {len(final_detections)}"
                    )

            return batch_results

        # Process images in batches with progress reporting
        def progress_callback(processed: int, total: int):
            percent = (processed / total) * 100
            logger.info(f"Progress: {processed}/{total} images ({percent:.1f}%)")

        # Use batch processor for dynamic batch sizing
        batch_results = self.batch_processor.process_batches(
            image_paths,
            process_batch,
            progress_callback
        )

        # Flatten results
        for batch_result in batch_results:
            if isinstance(batch_result, list):
                detections_per_image.extend(batch_result)
            else:
                detections_per_image.append(batch_result)

        return detections_per_image

    def _log_final_statistics(self, results: Dict[str, Any]):
        """Log final processing statistics."""
        logger.info("=== CAMINA Processing Complete ===")
        logger.info(f"Images processed: {results['total_images']}")
        logger.info(f"Total detections: {results['total_detections']}")
        logger.info(f"Average detections per image: {results['detections_per_image']:.2f}")
        logger.info(f"Processing time: {format_duration(results['processing_time'])}")
        logger.info(f"Processing speed: {results['images_per_second']:.2f} images/second")

        # Validation summary
        validation = results['validation_report']
        if validation['is_valid']:
            logger.info("✅ Dataset validation: PASSED")
        else:
            logger.warning(f"⚠️  Dataset validation: {validation['error_count']} errors, {validation['warning_count']} warnings")

        # Performance statistics
        self.performance_monitor.log_statistics()


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="CAMINA - Two-stage Urban Mobility Object Detection Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config configs/config.yaml
  python main.py --images_dir data/images --device cuda:0 --batch 16
  python main.py --images_dir data/test --output_dir outputs/test --clean
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='configs/config.yaml',
        help='Path to YAML configuration file (default: configs/config.yaml)'
    )

    parser.add_argument(
        '--images_dir',
        type=str,
        help='Directory containing input images (overrides config)'
    )

    parser.add_argument(
        '--output_dir',
        type=str,
        help='Output directory for results (overrides config)'
    )

    parser.add_argument(
        '--device',
        type=str,
        choices=['cpu', 'cuda', 'cuda:0', 'cuda:1'],
        help='Device to use for inference (overrides config)'
    )

    parser.add_argument(
        '--batch_size',
        type=int,
        help='Batch size for processing (overrides config)'
    )

    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean output directory before processing'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--validate_only',
        action='store_true',
        help='Only validate configuration, do not process images'
    )

    return parser


def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Load configuration
    try:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Configuration file not found: {config_path}")
            sys.exit(1)

        # Prepare CLI overrides
        cli_args = {
            'device': args.device,
            'batch_size': args.batch_size,
            'output_dir': args.output_dir,
            'clean': args.clean
        }

        config = load_config(config_path, cli_args)

    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Setup logging
    try:
        log_level = 'DEBUG' if args.verbose else config.logging.level
        logging_config = {
            'level': log_level,
            'format': config.logging.format,
            'date_format': config.logging.date_format,
            'file': config.logging.file,
            'max_file_size': config.logging.max_file_size,
            'backup_count': config.logging.backup_count
        }
        setup_logging(logging_config)

    except Exception as e:
        print(f"Error setting up logging: {e}")
        sys.exit(1)

    # Log startup information
    git_info = get_git_info()
    logger.info("=== CAMINA Pipeline Starting ===")
    logger.info(f"Version: {config.metadata.version}")
    logger.info(f"Configuration: {config_path}")
    logger.info(f"Git branch: {git_info['branch']} (commit: {git_info['commit']})")
    logger.info(f"Target hardware: {config.metadata.target_hardware}")

    # Setup environment for reproducibility
    setup_environment_from_config(config)

    # Validate configuration only
    if args.validate_only:
        logger.info("Configuration validation successful")
        logger.info("Exiting (validate_only mode)")
        sys.exit(0)

    # Determine input and output directories
    images_dir = Path(args.images_dir) if args.images_dir else Path(config.cli.default_images_dir)
    output_dir = Path(args.output_dir) if args.output_dir else Path(config.cli.default_output_dir)

    # Validate input directory
    if not images_dir.exists():
        logger.error(f"Images directory not found: {images_dir}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean output directory if requested
    if config.cli.clean_on_start or args.clean:
        logger.info("Cleaning output directory...")
        cleaned_count = clean_output_directory(output_dir)
        logger.info(f"Cleaned {cleaned_count} files from output directory")

    # Initialize and run pipeline
    try:
        pipeline = CAMINAPipeline(config)

        if not pipeline.initialize():
            logger.error("Failed to initialize CAMINA pipeline")
            sys.exit(1)

        # Process images
        logger.info(f"Processing images from: {images_dir}")
        logger.info(f"Output directory: {output_dir}")

        start_time = time.time()
        results = pipeline.process_images(
            images_dir,
            output_dir,
            args.batch_size
        )
        total_time = time.time() - start_time

        # Final summary
        logger.info("=== Processing Summary ===")
        logger.info(f"Total processing time: {format_duration(total_time)}")
        logger.info(f"Images processed: {results['total_images']}")
        logger.info(f"Total detections: {results['total_detections']}")

        if results['validation_report']['is_valid']:
            logger.info("✅ All validations passed")
            sys.exit(0)
        else:
            logger.warning("⚠️  Some validation errors occurred")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()