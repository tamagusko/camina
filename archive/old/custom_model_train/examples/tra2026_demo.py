#!/usr/bin/env python3
"""
TRA2026 CAMINA Pipeline Demo
Demonstrates the 9-class object detection training pipeline for research paper.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from camina_pipeline import CaminaPipeline
from camina import setup_logging

def main():
    """
    Demo of CAMINA pipeline for TRA2026 research paper.
    Shows complete workflow: video processing -> auto-labeling -> training -> evaluation
    """
    
    # Setup logging
    setup_logging(level="INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("=== TRA2026 CAMINA Pipeline Demo ===")
    
    # Initialize pipeline with quick test config for demo
    config_path = Path("configs/quick_test_config.yaml")
    pipeline = CaminaPipeline(config_path)
    
    logger.info(f"Pipeline initialized: {pipeline.pipeline_id}")
    logger.info(f"9-class detection schema:")
    for class_id, class_name in pipeline.config.class_schema.CLASSES.items():
        logger.info(f"  {class_id}: {class_name}")
    
    # Demo 1: Video Processing (0.5 FPS frame extraction)
    logger.info("\n=== Demo 1: Video Processing ===")
    video_path = "test_video.mp4"
    if Path(video_path).exists():
        logger.info(f"Processing video: {video_path}")
        logger.info(f"Extraction FPS: {pipeline.video_processor.extraction_fps}")
        logger.info("Ready to extract frames for dataset expansion")
        # In a real run: pipeline.run_video_processing([video_path])
    else:
        logger.info("Test video not found - skipping video processing demo")
    
    # Demo 2: Dataset Management
    logger.info("\n=== Demo 2: Dataset Management ===")
    sdl_dataset = Path("datasets/SDL fine-tuned_v3-cyclist_cleaned")
    if sdl_dataset.with_suffix('.zip').exists():
        logger.info("SDL dataset found - ready for 5->9 class conversion")
        logger.info("Mapping: pedestrian, cyclist, car, motorcycle, bus, truck")
        logger.info("New classes: e-scooter, SUV, delivery_van")
    else:
        logger.info("SDL dataset not found - would use for class expansion")
    
    # Demo 3: Auto-labeling Configuration
    logger.info("\n=== Demo 3: Auto-labeling Configuration ===")
    logger.info("Auto-labeler configured for new classes:")
    for class_id in pipeline.config.class_schema.NEW_CLASSES:
        class_name = pipeline.config.class_schema.CLASSES[class_id]
        logger.info(f"  {class_id}: {class_name}")
    logger.info(f"Confidence threshold: {pipeline.auto_labeler.confidence_threshold}")
    
    # Demo 4: YOLO11n Training Configuration
    logger.info("\n=== Demo 4: YOLO11n Training Configuration ===")
    training_config = pipeline.config.training
    logger.info(f"Model: {training_config.model_name}")
    logger.info(f"Epochs: {training_config.epochs}")
    logger.info(f"Batch size: {training_config.batch_size}")
    logger.info(f"Image size: {training_config.image_size}")
    logger.info("Optimized for Raspberry Pi 5 deployment")
    
    # Demo 5: Complete Pipeline Command
    logger.info("\n=== Demo 5: Complete Pipeline Commands ===")
    logger.info("Full pipeline with video processing:")
    logger.info("  python camina_pipeline.py --videos video1.mp4 video2.mp4")
    logger.info("\nQuick test run (5 epochs):")
    logger.info("  python camina_pipeline.py --quick --epochs 5")
    logger.info("\nTraining only (using existing dataset):")
    logger.info("  python camina_pipeline.py --mode training-only")
    
    logger.info("\n=== TRA2026 Demo Completed Successfully ===")
    logger.info("CAMINA pipeline ready for research paper implementation")

if __name__ == "__main__":
    main()