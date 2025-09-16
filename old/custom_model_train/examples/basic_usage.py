#!/usr/bin/env python3
"""
Basic usage examples for CAMINA pipeline.
Demonstrates common use cases and workflows.
"""

import logging
from pathlib import Path

# Setup logging for examples
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import CAMINA components
from camina import (
    CaminaConfig,
    VideoProcessor,
    DatasetManager,
    YOLO11nTrainer,
    AutoLabeler,
    ResultsManager
)


def example_1_complete_pipeline():
    """Example 1: Run complete CAMINA pipeline"""
    print("=" * 60)
    print("EXAMPLE 1: Complete CAMINA Pipeline")
    print("=" * 60)
    
    from camina_pipeline import CaminaPipeline
    
    # Initialize with default configuration
    pipeline = CaminaPipeline()
    
    # Example video files (replace with your actual videos)
    video_files = [
        "sample_video1.mp4",
        "sample_video2.mp4"
    ]
    
    # Run complete pipeline
    results = pipeline.run_full_pipeline(video_paths=video_files)
    
    if results['success']:
        print("✅ Pipeline completed successfully!")
        print(f"Duration: {results['total_time_formatted']}")
    else:
        print("❌ Pipeline failed!")
        print(f"Error: {results.get('error', 'Unknown error')}")
    
    return results


def example_2_video_processing():
    """Example 2: Video processing and frame extraction"""
    print("=" * 60)
    print("EXAMPLE 2: Video Processing at 0.5 FPS")
    print("=" * 60)
    
    # Load configuration
    config = CaminaConfig()
    
    # Initialize video processor
    processor = VideoProcessor(config)
    
    # Process single video
    video_path = "sample_video.mp4"
    output_dir = "extracted_frames"
    
    if Path(video_path).exists():
        results = processor.extract_frames(video_path, output_dir)
        
        if results['success']:
            print(f"✅ Extracted {results['extraction_info']['extracted_count']} frames")
            print(f"Output directory: {results['output_directory']}")
        else:
            print(f"❌ Frame extraction failed: {results['error']}")
    else:
        print(f"⚠️  Video file not found: {video_path}")
        print("Creating synthetic example...")
        
        # Create example with synthetic video
        import cv2
        import numpy as np
        
        # Create a simple test video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter('test_video.mp4', fourcc, 2.0, (640, 480))
        
        for i in range(10):  # 5 seconds at 2 FPS
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            # Add some simple shapes
            cv2.rectangle(frame, (100+i*10, 100), (200+i*10, 200), (0, 255, 0), -1)
            out.write(frame)
        
        out.release()
        print("Created test_video.mp4")
        
        # Now extract frames
        results = processor.extract_frames("test_video.mp4", output_dir)
        print(f"✅ Extracted {results['extraction_info']['extracted_count']} frames from synthetic video")
    
    return results


def example_3_dataset_conversion():
    """Example 3: Dataset conversion from SDL to CAMINA format"""
    print("=" * 60)
    print("EXAMPLE 3: Dataset Conversion")
    print("=" * 60)
    
    config = CaminaConfig()
    manager = DatasetManager(config)
    
    # Check if SDL dataset exists
    sdl_path = Path(config.dataset.sdl_dataset_path)
    
    if sdl_path.exists():
        print(f"Converting SDL dataset from: {sdl_path}")
        success = manager.convert_sdl_dataset()
        
        if success:
            print("✅ Dataset conversion completed!")
            output_path = Path(config.dataset.output_dataset_path)
            print(f"CAMINA dataset created at: {output_path}")
            
            # Check dataset structure
            for split in ['train', 'val']:
                img_dir = output_path / 'images' / split
                label_dir = output_path / 'labels' / split
                
                if img_dir.exists() and label_dir.exists():
                    img_count = len(list(img_dir.glob('*.jpg')))
                    label_count = len(list(label_dir.glob('*.txt')))
                    print(f"  {split}: {img_count} images, {label_count} labels")
        else:
            print("❌ Dataset conversion failed!")
    else:
        print(f"⚠️  SDL dataset not found at: {sdl_path}")
        print("Please download and extract the SDL dataset first.")
    
    return success if sdl_path.exists() else False


def example_4_training():
    """Example 4: YOLO11n training"""
    print("=" * 60)
    print("EXAMPLE 4: YOLO11n Training")
    print("=" * 60)
    
    config = CaminaConfig()
    
    # Set quick training parameters for demo
    config.training.epochs = 5
    config.training.batch_size = 4
    
    trainer = YOLO11nTrainer(config)
    
    # Check for dataset
    dataset_path = Path(config.dataset.output_dataset_path)
    data_yaml = dataset_path / 'data.yaml'
    
    if data_yaml.exists():
        print(f"Training on dataset: {data_yaml}")
        print(f"Epochs: {config.training.epochs}")
        print(f"Batch size: {config.training.batch_size}")
        
        # Start training
        results = trainer.train(data_yaml)
        
        if results['success']:
            print("✅ Training completed successfully!")
            print(f"Experiment ID: {results['experiment_id']}")
            print(f"Training time: {results['training_time_seconds']:.1f} seconds")
            
            # Model information
            model_info = results.get('model_info', {})
            print(f"Best fitness: {model_info.get('best_fitness', 0):.4f}")
            print(f"Model size: {model_info.get('model_size_mb', 0):.2f} MB")
            
        else:
            print("❌ Training failed!")
            print(f"Error: {results.get('error', 'Unknown error')}")
    else:
        print(f"⚠️  Dataset not found: {data_yaml}")
        print("Please run dataset conversion first (Example 3)")
    
    return results if data_yaml.exists() else {'success': False}


def example_5_auto_labeling():
    """Example 5: Auto-labeling for new classes"""
    print("=" * 60)
    print("EXAMPLE 5: Auto-Labeling")
    print("=" * 60)
    
    config = CaminaConfig()
    labeler = AutoLabeler(config)
    
    # Create sample images directory
    images_dir = Path("sample_images")
    images_dir.mkdir(exist_ok=True)
    
    # Check if we have sample images
    image_files = list(images_dir.glob('*.jpg'))
    
    if not image_files:
        print("⚠️  No sample images found. Creating synthetic examples...")
        
        import cv2
        import numpy as np
        
        # Create sample images with simple shapes
        for i in range(3):
            img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
            
            # Add some shapes representing vehicles
            cv2.rectangle(img, (100+i*50, 200), (200+i*50, 300), (0, 255, 0), -1)  # Car-like
            cv2.circle(img, (300+i*30, 150), 30, (255, 0, 0), -1)  # Person-like
            
            cv2.imwrite(str(images_dir / f"sample_{i}.jpg"), img)
        
        image_files = list(images_dir.glob('*.jpg'))
        print(f"Created {len(image_files)} sample images")
    
    # Initialize auto-labeler (CPU mode for compatibility)
    print("Initializing auto-labeling models...")
    success = labeler.initialize_models(device='cpu')
    
    if not success:
        print("⚠️  Model initialization failed, using simplified labeling...")
    
    # Label images
    labels_dir = images_dir.parent / "auto_labels"
    results = labeler.label_directory(images_dir, labels_dir, overwrite=True)
    
    if results['success']:
        stats = results['statistics']
        print("✅ Auto-labeling completed!")
        print(f"Processed: {stats['processed_images']}/{stats['total_images']} images")
        print(f"Total detections: {stats['total_detections']}")
        
        # Show class distribution
        print("Class distribution:")
        for class_name, count in stats['class_counts'].items():
            if count > 0:
                print(f"  {class_name}: {count}")
    else:
        print("❌ Auto-labeling failed!")
    
    return results


def example_6_results_analysis():
    """Example 6: Results analysis and reporting"""
    print("=" * 60)
    print("EXAMPLE 6: Results Analysis")
    print("=" * 60)
    
    config = CaminaConfig()
    manager = ResultsManager(config)
    
    # Look for training experiments
    runs_dir = Path("runs/train")
    
    if runs_dir.exists():
        # Load experiments
        experiments = manager.load_experiments_batch(runs_dir)
        
        if experiments:
            print(f"Found {len(experiments)} experiments")
            
            # List experiments
            for exp_id, exp_data in experiments.items():
                print(f"  - {exp_id}")
                
                if 'training_results' in exp_data:
                    model_info = exp_data['training_results'].get('model_info', {})
                    fitness = model_info.get('best_fitness', 0)
                    size = model_info.get('model_size_mb', 0)
                    print(f"    Fitness: {fitness:.4f}, Size: {size:.2f} MB")
            
            # Generate comprehensive report
            print("\nGenerating comprehensive report...")
            report = manager.generate_comprehensive_report()
            
            if 'report_metadata' in report:
                print("✅ Report generated successfully!")
                
                # Show summary statistics
                if 'summary_statistics' in report:
                    stats = report['summary_statistics']
                    print("\nSummary Statistics:")
                    
                    for metric, values in stats.items():
                        if isinstance(values, dict):
                            print(f"  {metric}:")
                            print(f"    Mean: {values.get('mean', 0):.4f}")
                            print(f"    Std: {values.get('std', 0):.4f}")
                
                # Show recommendations
                if 'recommendations' in report:
                    print("\nRecommendations:")
                    for i, rec in enumerate(report['recommendations'][:3], 1):
                        print(f"  {i}. {rec}")
            
            # Export CSV summary
            csv_file = manager.export_results_csv()
            print(f"Results exported to: {csv_file}")
            
        else:
            print("No experiments found in runs/train")
    else:
        print("No training runs directory found")
        print("Please run training first (Example 4)")
    
    return len(experiments) if runs_dir.exists() else 0


def example_7_custom_configuration():
    """Example 7: Custom configuration"""
    print("=" * 60)
    print("EXAMPLE 7: Custom Configuration")
    print("=" * 60)
    
    # Create custom configuration
    config = CaminaConfig()
    
    # Modify training parameters
    config.training.epochs = 50
    config.training.batch_size = 8
    config.training.learning_rate = 0.0005
    
    # Modify video processing
    config.video_processing.extraction_fps = 1.0  # 1 FPS instead of 0.5
    config.video_processing.max_frames_per_video = 500
    
    # Modify dataset splits
    config.dataset.train_split = 0.7
    config.dataset.val_split = 0.2
    config.dataset.test_split = 0.1
    
    print("Custom configuration created:")
    print(f"  Training epochs: {config.training.epochs}")
    print(f"  Batch size: {config.training.batch_size}")
    print(f"  Learning rate: {config.training.learning_rate}")
    print(f"  Extraction FPS: {config.video_processing.extraction_fps}")
    print(f"  Train/Val/Test split: {config.dataset.train_split}/{config.dataset.val_split}/{config.dataset.test_split}")
    
    # Save configuration
    config_file = Path("custom_config.yaml")
    config.save_to_file(config_file)
    print(f"✅ Configuration saved to: {config_file}")
    
    # Load configuration back
    loaded_config = CaminaConfig(config_file)
    print("✅ Configuration loaded successfully!")
    
    return True


def run_all_examples():
    """Run all examples in sequence"""
    print("🚀 Running CAMINA Usage Examples")
    print("=" * 80)
    
    examples = [
        ("Video Processing", example_2_video_processing),
        ("Dataset Conversion", example_3_dataset_conversion),
        ("Custom Configuration", example_7_custom_configuration),
        ("Auto-Labeling", example_5_auto_labeling),
        ("Training", example_4_training),
        ("Results Analysis", example_6_results_analysis),
        # ("Complete Pipeline", example_1_complete_pipeline),  # Skip for demo
    ]
    
    results = {}
    
    for name, example_func in examples:
        print(f"\n🔄 Running: {name}")
        try:
            result = example_func()
            results[name] = result
            print(f"✅ {name} completed")
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = False
        
        print()  # Add spacing
    
    # Summary
    print("=" * 80)
    print("EXAMPLES SUMMARY")
    print("=" * 80)
    
    for name, result in results.items():
        if isinstance(result, dict):
            status = "✅ SUCCESS" if result.get('success', False) else "❌ FAILED"
        elif isinstance(result, bool):
            status = "✅ SUCCESS" if result else "❌ FAILED"
        else:
            status = "✅ SUCCESS" if result else "❌ FAILED"
        
        print(f"{status}: {name}")
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        
        examples_map = {
            "1": example_1_complete_pipeline,
            "2": example_2_video_processing,
            "3": example_3_dataset_conversion,
            "4": example_4_training,
            "5": example_5_auto_labeling,
            "6": example_6_results_analysis,
            "7": example_7_custom_configuration,
            "all": run_all_examples
        }
        
        if example_num in examples_map:
            examples_map[example_num]()
        else:
            print(f"Unknown example: {example_num}")
            print("Available examples: 1, 2, 3, 4, 5, 6, 7, all")
    else:
        print("CAMINA Usage Examples")
        print("Usage: python basic_usage.py <example_number>")
        print()
        print("Available examples:")
        print("  1 - Complete pipeline")
        print("  2 - Video processing")
        print("  3 - Dataset conversion")
        print("  4 - Training")
        print("  5 - Auto-labeling")
        print("  6 - Results analysis")
        print("  7 - Custom configuration")
        print("  all - Run all examples")
        print()
        print("Example: python basic_usage.py 2")