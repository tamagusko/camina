#!/usr/bin/env python3
"""
Migration script from CAMINA v1 to v2 architecture.
Helps transition from the old monolithic structure to the new clean architecture.
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import json
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CaminaMigrator:
    """Migrates CAMINA v1 codebase to v2 architecture"""
    
    def __init__(self, source_dir: Optional[Path] = None):
        self.source_dir = source_dir or Path.cwd()
        self.backup_dir = self.source_dir / "backup_v1"
        
        # Migration mapping
        self.file_mapping = {
            # Old files to backup
            'run_camina_pipeline.py': 'scripts/legacy_pipeline_runner.py',
            'pipeline_config.yaml': 'configs/legacy_config.yaml',
            'scripts/convert_sdl_to_yolo11.py': 'scripts/legacy_convert_sdl.py',
            'scripts/train_yolo11n.py': 'scripts/legacy_train_yolo11n.py',
            'scripts/sam2_clip_auto_labeling.py': 'scripts/legacy_auto_labeling.py',
            'scripts/evaluation_logging_system.py': 'scripts/legacy_evaluation.py',
            'scripts/model_comparison_framework.py': 'scripts/legacy_model_comparison.py',
            'scripts/rpi5_deployment_optimizer.py': 'scripts/legacy_deployment.py'
        }
        
        logger.info(f"CaminaMigrator initialized for: {self.source_dir}")
    
    def create_backup(self) -> bool:
        """Create backup of existing v1 files"""
        logger.info("Creating backup of v1 files...")
        
        try:
            # Create backup directory
            self.backup_dir.mkdir(exist_ok=True)
            
            # Backup old files
            backed_up_count = 0
            for old_file, backup_path in self.file_mapping.items():
                old_path = self.source_dir / old_file
                if old_path.exists():
                    backup_full_path = self.backup_dir / backup_path
                    backup_full_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old_path, backup_full_path)
                    backed_up_count += 1
                    logger.debug(f"Backed up: {old_file} -> {backup_path}")
            
            # Backup existing results
            for results_dir in ['pipeline_results', 'pipeline_logs', 'runs']:
                results_path = self.source_dir / results_dir
                if results_path.exists():
                    backup_results_path = self.backup_dir / results_dir
                    if backup_results_path.exists():
                        shutil.rmtree(backup_results_path)
                    shutil.copytree(results_path, backup_results_path)
                    logger.debug(f"Backed up directory: {results_dir}")
            
            # Create migration log
            migration_log = {
                'migration_date': datetime.now().isoformat(),
                'source_directory': str(self.source_dir),
                'backup_directory': str(self.backup_dir),
                'backed_up_files': backed_up_count,
                'file_mapping': self.file_mapping
            }
            
            log_file = self.backup_dir / 'migration_log.json'
            with open(log_file, 'w') as f:
                json.dump(migration_log, f, indent=2)
            
            logger.info(f"✅ Backup completed: {backed_up_count} files backed up to {self.backup_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def migrate_configuration(self) -> bool:
        """Migrate old configuration to new format"""
        logger.info("Migrating configuration...")
        
        try:
            old_config_path = self.source_dir / 'pipeline_config.yaml'
            new_config_path = self.source_dir / 'configs' / 'migrated_config.yaml'
            
            if not old_config_path.exists():
                logger.warning("No old configuration file found, using defaults")
                return True
            
            # Load old configuration
            with open(old_config_path, 'r') as f:
                old_config = yaml.safe_load(f)
            
            # Convert to new format
            new_config = self._convert_config_format(old_config)
            
            # Save new configuration
            new_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(new_config_path, 'w') as f:
                yaml.dump(new_config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"✅ Configuration migrated to: {new_config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Configuration migration failed: {e}")
            return False
    
    def _convert_config_format(self, old_config: Dict) -> Dict:
        """Convert old configuration format to new structure"""
        
        # Extract old values with defaults
        pipeline = old_config.get('pipeline', {})
        testing = old_config.get('testing', {})
        output = old_config.get('output', {})
        advanced = old_config.get('advanced', {})
        raspberry_pi = old_config.get('raspberry_pi', {})
        
        # Create new configuration structure
        new_config = {
            'dataset': {
                'sdl_dataset_path': pipeline.get('sdl_dataset_path', 'datasets/SDL fine-tuned_v3-cyclist_cleaned'),
                'output_dataset_path': pipeline.get('output_dataset_path', 'datasets/camina_9class'),
                'train_split': 0.8,
                'val_split': 0.15,
                'test_split': 0.05,
                'min_samples_per_class': 100
            },
            
            'video_processing': {
                'extraction_fps': 0.5,
                'output_format': 'jpg',
                'quality': 95,
                'max_frames_per_video': 1000,
                'frame_size': [640, 640]
            },
            
            'training': {
                'model_name': pipeline.get('base_model', 'yolo11n.pt'),
                'epochs': pipeline.get('epochs', 100),
                'batch_size': pipeline.get('batch_size', 16),
                'image_size': 640,
                'device': pipeline.get('device', 'auto'),
                'workers': 4,
                'patience': 10,
                'learning_rate': 0.001,
                'weight_decay': 0.0005,
                'optimizer': 'AdamW',
                
                # Augmentation (use defaults as old config didn't specify these)
                'mosaic': 1.0,
                'mixup': 0.15,
                'copy_paste': 0.3,
                'flipud': 0.0,
                'fliplr': 0.5,
                'degrees': 0.0,
                'translate': 0.1,
                'scale': 0.9,
                'perspective': 0.0,
                'hsv_h': 0.015,
                'hsv_s': 0.7,
                'hsv_v': 0.4
            },
            
            'auto_labeling': {
                'confidence_threshold': 0.3,
                'nms_threshold': 0.4,
                'min_box_size': 0.01,
                'max_detections': 100,
                'clip_prompts': {
                    6: ['electric scooter', 'e-scooter', 'kick scooter'],
                    7: ['SUV', 'sport utility vehicle', 'large car'],
                    8: ['delivery van', 'cargo van', 'commercial van']
                }
            },
            
            'deployment': {
                'target_device': 'raspberry_pi_5',
                'export_formats': pipeline.get('export_formats', ['onnx', 'ncnn']),
                'quantization': raspberry_pi.get('enable_quantization', True),
                'optimization': raspberry_pi.get('optimize_for_size', True),
                'max_memory_mb': raspberry_pi.get('max_memory_usage_mb', 1000),
                'target_fps': raspberry_pi.get('target_fps', 15)
            },
            
            'advanced': {
                'max_workers': advanced.get('max_workers', 4),
                'use_multiprocessing': advanced.get('use_multiprocessing', False),
                'max_memory_gb': advanced.get('max_memory_gb', 8),
                'enable_memory_monitoring': advanced.get('enable_memory_monitoring', True),
                'retry_failed_steps': advanced.get('retry_failed_steps', 1),
                'continue_on_error': advanced.get('continue_on_error', False),
                'log_level': advanced.get('log_level', 'INFO'),
                'save_detailed_logs': advanced.get('save_detailed_logs', True),
                'validate_inputs': advanced.get('validate_inputs', True),
                'sanitize_paths': advanced.get('sanitize_paths', True)
            },
            
            'output': {
                'results_dir': output.get('results_dir', 'results'),
                'logs_dir': output.get('logs_dir', 'logs'),
                'save_intermediate': output.get('save_intermediate', True),
                'create_report': output.get('create_report', True),
                'create_plots': output.get('create_plots', True),
                'save_model_graphs': output.get('save_model_graphs', True)
            }
        }
        
        return new_config
    
    def create_usage_examples(self) -> bool:
        """Create usage examples for new architecture"""
        logger.info("Creating usage examples...")
        
        try:
            examples_dir = self.source_dir / 'examples'
            examples_dir.mkdir(exist_ok=True)
            
            # Migration guide example
            migration_guide = """# Migration from CAMINA v1 to v2

## Quick Start with New Architecture

```python
# Old way (v1)
from run_camina_pipeline import CAMINAPipelineRunner
runner = CAMINAPipelineRunner('pipeline_config.yaml')
runner.run_full_pipeline()

# New way (v2) 
from camina_pipeline import CaminaPipeline
pipeline = CaminaPipeline('configs/default_config.yaml')
results = pipeline.run_full_pipeline()
```

## Key Changes

### 1. Modular Architecture
- Separate modules for each functionality
- Clean interfaces between components
- Easy to test and maintain

### 2. Configuration Management
- Centralized configuration in `camina/config.py`
- Type-safe configuration with dataclasses
- Easy validation and defaults

### 3. Video Processing
- Dedicated `VideoProcessor` class
- Built-in 0.5 FPS extraction
- Comprehensive frame metadata

### 4. Training Pipeline
- Simplified `YOLO11nTrainer` 
- Automatic device detection
- Research-focused reproducibility

### 5. Results Management
- Comprehensive experiment tracking
- Automated report generation
- Comparison and visualization tools

## Migration Steps

1. Backup your existing work:
   ```bash
   python migrate_to_v2.py --backup-only
   ```

2. Run full migration:
   ```bash
   python migrate_to_v2.py --full-migration
   ```

3. Test new architecture:
   ```bash
   python camina_pipeline.py --quick
   ```

4. Migrate your custom configurations:
   ```bash
   python migrate_to_v2.py --config-only
   ```

## Backward Compatibility

Your existing results and models are fully compatible:
- Training runs in `runs/train/` work with new analysis tools
- Model weights (.pt files) work with new training pipeline
- Dataset formats are identical

## Getting Help

- Check `README_REFACTORED.md` for complete documentation
- Run `python examples/basic_usage.py all` for comprehensive examples
- Use `python camina_pipeline.py --help` for command-line help
"""
            
            guide_file = examples_dir / 'migration_guide.md'
            with open(guide_file, 'w') as f:
                f.write(migration_guide)
            
            logger.info(f"✅ Migration guide created: {guide_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create examples: {e}")
            return False
    
    def validate_migration(self) -> bool:
        """Validate that migration completed successfully"""
        logger.info("Validating migration...")
        
        required_files = [
            'camina/__init__.py',
            'camina/config.py', 
            'camina/data.py',
            'camina/models.py',
            'camina/labeling.py',
            'camina/evaluation.py',
            'camina/utils.py',
            'camina_pipeline.py',
            'configs/default_config.yaml',
            'requirements.txt',
            'README_REFACTORED.md'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.source_dir / file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            logger.error(f"Migration incomplete. Missing files: {missing_files}")
            return False
        
        # Test imports
        try:
            import sys
            sys.path.insert(0, str(self.source_dir))
            
            from camina import CaminaConfig, VideoProcessor, DatasetManager
            from camina_pipeline import CaminaPipeline
            
            logger.info("✅ Import validation successful")
            
        except ImportError as e:
            logger.error(f"Import validation failed: {e}")
            return False
        
        logger.info("✅ Migration validation completed successfully")
        return True
    
    def run_full_migration(self) -> bool:
        """Run complete migration process"""
        logger.info("🚀 Starting CAMINA v1 to v2 Migration")
        logger.info("="*60)
        
        success = True
        
        # Step 1: Create backup
        if not self.create_backup():
            logger.error("Backup failed - aborting migration")
            return False
        
        # Step 2: Migrate configuration
        if not self.migrate_configuration():
            logger.warning("Configuration migration failed - continuing with defaults")
            success = False
        
        # Step 3: Create examples
        if not self.create_usage_examples():
            logger.warning("Example creation failed - continuing")
        
        # Step 4: Validate migration
        if not self.validate_migration():
            logger.error("Migration validation failed")
            success = False
        
        # Final summary
        if success:
            logger.info("="*60)
            logger.info("✅ CAMINA v2 MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("="*60)
            logger.info("Next steps:")
            logger.info("1. Test the new pipeline: python camina_pipeline.py --quick")
            logger.info("2. Check examples: python examples/basic_usage.py all") 
            logger.info("3. Read documentation: README_REFACTORED.md")
            logger.info("4. Your old files are safely backed up in: backup_v1/")
        else:
            logger.error("="*60)
            logger.error("⚠️  MIGRATION COMPLETED WITH WARNINGS")
            logger.error("="*60)
            logger.error("Please check the logs above for issues")
            logger.error("Your old files are backed up in: backup_v1/")
        
        return success


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate CAMINA v1 to v2 architecture',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full migration
  python migrate_to_v2.py
  
  # Backup only
  python migrate_to_v2.py --backup-only
  
  # Configuration only
  python migrate_to_v2.py --config-only
  
  # Validate existing migration
  python migrate_to_v2.py --validate-only
        """
    )
    
    parser.add_argument('--source-dir', 
                       help='Source directory (defaults to current directory)')
    
    parser.add_argument('--backup-only', 
                       action='store_true',
                       help='Only create backup, no migration')
    
    parser.add_argument('--config-only', 
                       action='store_true', 
                       help='Only migrate configuration')
    
    parser.add_argument('--validate-only',
                       action='store_true',
                       help='Only validate existing migration')
    
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize migrator
    source_dir = Path(args.source_dir) if args.source_dir else None
    migrator = CaminaMigrator(source_dir)
    
    try:
        if args.backup_only:
            success = migrator.create_backup()
        elif args.config_only:
            success = migrator.migrate_configuration()
        elif args.validate_only:
            success = migrator.validate_migration()
        else:
            # Full migration
            success = migrator.run_full_migration()
        
        exit_code = 0 if success else 1
        logger.info(f"Migration completed with exit code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == '__main__':
    exit(main())