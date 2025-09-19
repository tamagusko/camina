#!/usr/bin/env python3
"""
CAMINA Pipeline - Main orchestrator for 9-class object detection training.
Clean, research-focused implementation for easy reproducibility.
"""

import logging
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime

from camina import (
    CaminaConfig, 
    VideoProcessor, 
    DatasetManager, 
    YOLO11nTrainer, 
    AutoLabeler,
    ResultsManager,
    setup_logging
)

logger = logging.getLogger(__name__)


class CaminaPipeline:
    """
    Main CAMINA pipeline orchestrator.
    Coordinates video processing, auto-labeling, training, and evaluation.
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize CAMINA pipeline.
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = CaminaConfig(config_path)
        if not self.config.validate():
            raise ValueError("Invalid configuration")
        
        # Initialize components
        self.video_processor = VideoProcessor(self.config)
        self.dataset_manager = DatasetManager(self.config)
        self.trainer = YOLO11nTrainer(self.config)
        self.auto_labeler = AutoLabeler(self.config)
        self.results_manager = ResultsManager(self.config)
        
        # Pipeline state
        self.pipeline_id = f"camina_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.results = {}
        
        logger.info(f"CAMINA Pipeline initialized: {self.pipeline_id}")
    
    def run_video_processing(self, 
                           video_paths: List[Union[str, Path]], 
                           output_dir: Union[str, Path] = "extracted_frames") -> bool:
        """
        Extract frames from videos at 0.5 FPS.
        
        Args:
            video_paths: List of video file paths
            output_dir: Directory to save extracted frames
        
        Returns:
            True if successful
        """
        logger.info("=== Video Processing Phase ===")
        
        start_time = time.time()
        
        # Process videos
        batch_results = self.video_processor.process_video_batch(
            video_paths, output_dir
        )
        
        # Create manifest
        if batch_results['success']:
            manifest_path = Path(output_dir) / 'extraction_manifest.json'
            self.video_processor.create_frame_manifest(
                batch_results['results'], manifest_path
            )
        
        # Store results
        processing_time = time.time() - start_time
        self.results['video_processing'] = {
            'success': batch_results['success'],
            'processing_time_seconds': processing_time,
            'total_frames': batch_results['total_extracted_frames'],
            'processed_videos': batch_results['processed_videos'],
            'failed_videos': batch_results['failed_videos'],
            'output_directory': str(output_dir)
        }
        
        logger.info(f"Video processing completed in {processing_time:.1f}s")
        logger.info(f"Extracted {batch_results['total_extracted_frames']} frames "
                   f"from {batch_results['processed_videos']} videos")
        
        return batch_results['success']
    
    def run_dataset_conversion(self) -> bool:
        """
        Convert SDL dataset to CAMINA 9-class format.
        
        Returns:
            True if successful
        """
        logger.info("=== Dataset Conversion Phase ===")
        
        start_time = time.time()
        
        # Convert SDL dataset
        success = self.dataset_manager.convert_sdl_dataset()
        
        # Store results
        conversion_time = time.time() - start_time
        self.results['dataset_conversion'] = {
            'success': success,
            'conversion_time_seconds': conversion_time,
            'input_dataset': self.config.dataset.sdl_dataset_path,
            'output_dataset': self.config.dataset.output_dataset_path
        }
        
        logger.info(f"Dataset conversion completed in {conversion_time:.1f}s")
        
        return success
    
    def run_auto_labeling(self, 
                         frames_dir: Union[str, Path],
                         initialize_models: bool = True) -> bool:
        """
        Auto-label extracted frames for new classes.
        
        Args:
            frames_dir: Directory containing extracted frames
            initialize_models: Whether to initialize detection models
        
        Returns:
            True if successful
        """
        logger.info("=== Auto-Labeling Phase ===")
        
        start_time = time.time()
        
        # Initialize models if requested
        if initialize_models:
            model_init_success = self.auto_labeler.initialize_models()
            if not model_init_success:
                logger.warning("Model initialization failed, continuing with limited functionality")
        
        # Create labels directory
        labels_dir = Path(frames_dir).parent / 'labels'
        
        # Auto-label frames
        labeling_results = self.auto_labeler.label_directory(
            frames_dir, labels_dir
        )
        
        # Add labeled frames to dataset
        if labeling_results['success']:
            self.dataset_manager.add_frames_to_dataset(frames_dir, split='train')
        
        # Store results
        labeling_time = time.time() - start_time
        self.results['auto_labeling'] = {
            'success': labeling_results['success'],
            'labeling_time_seconds': labeling_time,
            'frames_directory': str(frames_dir),
            'labels_directory': str(labels_dir),
            'statistics': labeling_results.get('statistics', {})
        }
        
        logger.info(f"Auto-labeling completed in {labeling_time:.1f}s")
        
        return labeling_results['success']
    
    def run_training(self, 
                    data_yaml_path: Optional[Union[str, Path]] = None,
                    model_path: Optional[Union[str, Path]] = None) -> bool:
        """
        Train YOLO11n model on 9-class dataset.
        
        Args:
            data_yaml_path: Path to dataset YAML (uses default if None)
            model_path: Path to pre-trained model (uses config default if None)
        
        Returns:
            True if successful
        """
        logger.info("=== Training Phase ===")
        
        # Use default paths if not specified
        if data_yaml_path is None:
            dataset_path = Path(self.config.dataset.output_dataset_path)
            data_yaml_path = dataset_path / 'data.yaml'
            
            # Create data.yaml if it doesn't exist
            if not data_yaml_path.exists():
                self.config.create_dataset_yaml(data_yaml_path)
        
        if model_path is None:
            model_path = self.config.training.model_name
        
        start_time = time.time()
        
        # Start training
        training_results = self.trainer.train(data_yaml_path, model_path)
        
        # Store results
        training_time = time.time() - start_time
        self.results['training'] = {
            'success': training_results['success'],
            'training_time_seconds': training_time,
            'experiment_id': training_results.get('experiment_id'),
            'model_info': training_results.get('model_info', {}),
            'data_yaml_path': str(data_yaml_path),
            'model_path': str(model_path)
        }
        
        if training_results['success']:
            logger.info(f"Training completed successfully in {training_time/3600:.2f} hours")
            
            # Validate model
            validation_results = self.trainer.validate_model()
            self.results['validation'] = validation_results
            
            # Export model
            export_results = self.trainer.export_model()
            self.results['export'] = export_results
        else:
            logger.error("Training failed")
        
        return training_results['success']
    
    def run_evaluation(self, experiments_dir: Union[str, Path] = "runs/train") -> Dict:
        """
        Evaluate and analyze training results.
        
        Args:
            experiments_dir: Directory containing training experiments
        
        Returns:
            Evaluation results
        """
        logger.info("=== Evaluation Phase ===")
        
        start_time = time.time()
        
        # Load experiments
        experiments = self.results_manager.load_experiments_batch(experiments_dir)
        
        if not experiments:
            logger.warning("No experiments found for evaluation")
            return {'success': False, 'error': 'No experiments found'}
        
        # Generate comprehensive report
        report = self.results_manager.generate_comprehensive_report()
        
        # Create visualizations
        experiment_ids = list(experiments.keys())
        if len(experiment_ids) == 1:
            # Single experiment plots
            plots = self.results_manager.create_training_plots(experiment_ids[0])
        elif len(experiment_ids) > 1:
            # Comparison plots
            plots = self.results_manager.create_comparison_plots(experiment_ids)
        else:
            plots = {}
        
        # Export CSV summary
        csv_file = self.results_manager.export_results_csv()
        
        # Store results
        evaluation_time = time.time() - start_time
        evaluation_results = {
            'success': True,
            'evaluation_time_seconds': evaluation_time,
            'experiments_analyzed': len(experiments),
            'report_generated': 'report_metadata' in report,
            'plots_created': len(plots),
            'csv_exported': csv_file
        }
        
        self.results['evaluation'] = evaluation_results
        
        logger.info(f"Evaluation completed in {evaluation_time:.1f}s")
        logger.info(f"Analyzed {len(experiments)} experiments")
        
        return evaluation_results
    
    def run_full_pipeline(self, 
                         video_paths: Optional[List[Union[str, Path]]] = None,
                         skip_video_processing: bool = False,
                         skip_auto_labeling: bool = False) -> Dict:
        """
        Run complete CAMINA pipeline.
        
        Args:
            video_paths: List of video files to process
            skip_video_processing: Skip video frame extraction
            skip_auto_labeling: Skip auto-labeling phase
        
        Returns:
            Complete pipeline results
        """
        logger.info("🚀 Starting Complete CAMINA Pipeline")
        logger.info("="*60)
        
        pipeline_start = time.time()
        overall_success = True
        
        try:
            # Phase 1: Video Processing
            if not skip_video_processing and video_paths:
                success = self.run_video_processing(video_paths)
                if not success:
                    logger.error("Video processing failed")
                    overall_success = False
            
            # Phase 2: Dataset Conversion
            success = self.run_dataset_conversion()
            if not success:
                logger.error("Dataset conversion failed")
                overall_success = False
            
            # Phase 3: Auto-Labeling
            if not skip_auto_labeling and not skip_video_processing:
                frames_dir = "extracted_frames"  # Default from video processing
                success = self.run_auto_labeling(frames_dir)
                if not success:
                    logger.warning("Auto-labeling failed, continuing with existing data")
            
            # Phase 4: Training
            success = self.run_training()
            if not success:
                logger.error("Training failed")
                overall_success = False
            
            # Phase 5: Evaluation
            evaluation_results = self.run_evaluation()
            if not evaluation_results['success']:
                logger.warning("Evaluation failed")
            
            # Final results
            total_time = time.time() - pipeline_start
            
            pipeline_results = {
                'pipeline_id': self.pipeline_id,
                'success': overall_success,
                'total_time_seconds': total_time,
                'total_time_formatted': f"{total_time/3600:.2f} hours",
                'phases': self.results,
                'completed_at': datetime.now().isoformat()
            }
            
            # Log final summary
            logger.info("="*60)
            logger.info("PIPELINE EXECUTION SUMMARY")
            logger.info("="*60)
            logger.info(f"Pipeline ID: {self.pipeline_id}")
            logger.info(f"Overall Success: {'✅ YES' if overall_success else '❌ NO'}")
            logger.info(f"Total Duration: {total_time/3600:.2f} hours")
            
            # Phase summary
            for phase_name, phase_results in self.results.items():
                if isinstance(phase_results, dict) and 'success' in phase_results:
                    status = "✅" if phase_results['success'] else "❌"
                    duration = phase_results.get('processing_time_seconds', 
                               phase_results.get('conversion_time_seconds',
                               phase_results.get('labeling_time_seconds',
                               phase_results.get('training_time_seconds',
                               phase_results.get('evaluation_time_seconds', 0)))))
                    logger.info(f"{status} {phase_name}: {duration:.1f}s")
            
            logger.info("="*60)
            
            return pipeline_results
            
        except Exception as e:
            total_time = time.time() - pipeline_start
            logger.error(f"Pipeline failed after {total_time:.1f}s: {e}")
            
            return {
                'pipeline_id': self.pipeline_id,
                'success': False,
                'error': str(e),
                'total_time_seconds': total_time,
                'phases': self.results,
                'failed_at': datetime.now().isoformat()
            }


def main():
    """Main entry point for CAMINA pipeline"""
    parser = argparse.ArgumentParser(
        description='CAMINA: 9-Class Object Detection Training Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline with video processing
  python camina_pipeline.py --videos video1.mp4 video2.mp4
  
  # Run training only
  python camina_pipeline.py --mode training-only
  
  # Run with custom configuration
  python camina_pipeline.py --config custom_config.yaml
  
  # Quick test run
  python camina_pipeline.py --quick --epochs 5
        """
    )
    
    parser.add_argument('--config', 
                       help='Configuration file path')
    
    parser.add_argument('--mode', 
                       choices=['full', 'training-only', 'evaluation-only'],
                       default='full',
                       help='Pipeline execution mode')
    
    parser.add_argument('--videos', 
                       nargs='+',
                       help='Video files for frame extraction')
    
    parser.add_argument('--skip-video-processing', 
                       action='store_true',
                       help='Skip video frame extraction')
    
    parser.add_argument('--skip-auto-labeling', 
                       action='store_true',
                       help='Skip auto-labeling phase')
    
    parser.add_argument('--epochs', 
                       type=int,
                       help='Number of training epochs (overrides config)')
    
    parser.add_argument('--batch-size', 
                       type=int,
                       help='Training batch size (overrides config)')
    
    parser.add_argument('--quick', 
                       action='store_true',
                       help='Quick test run with reduced parameters')
    
    parser.add_argument('--output-dir', 
                       default='results',
                       help='Output directory for results')
    
    parser.add_argument('--log-level', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO',
                       help='Logging level')
    
    parser.add_argument('--log-file',
                       help='Log file path')
    
    args = parser.parse_args()
    
    # Setup logging
    log_file = Path(args.log_file) if args.log_file else None
    setup_logging(args.log_level, log_file)
    
    try:
        # Initialize pipeline
        pipeline = CaminaPipeline(args.config)
        
        # Override config with command line arguments
        if args.epochs:
            pipeline.config.training.epochs = args.epochs
        
        if args.batch_size:
            pipeline.config.training.batch_size = args.batch_size
        
        if args.quick:
            # Quick test settings
            pipeline.config.training.epochs = 5
            pipeline.config.training.batch_size = 4
            pipeline.config.video_processing.max_frames_per_video = 100
        
        # Run pipeline based on mode
        if args.mode == 'full':
            results = pipeline.run_full_pipeline(
                video_paths=args.videos,
                skip_video_processing=args.skip_video_processing,
                skip_auto_labeling=args.skip_auto_labeling
            )
        
        elif args.mode == 'training-only':
            # Run only dataset conversion and training
            pipeline.run_dataset_conversion()
            results = {'success': pipeline.run_training()}
        
        elif args.mode == 'evaluation-only':
            # Run only evaluation
            results = pipeline.run_evaluation()
        
        # Exit with appropriate code
        exit_code = 0 if results['success'] else 1
        logger.info(f"Pipeline completed with exit code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        return 1
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return 1


if __name__ == '__main__':
    exit(main())