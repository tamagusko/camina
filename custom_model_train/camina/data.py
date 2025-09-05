"""
Data processing modules for CAMINA pipeline.
Handles video processing, dataset management, and frame extraction.
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Generator
import shutil
import yaml
from collections import defaultdict
import json
from datetime import datetime

from .config import CaminaConfig
from .utils import (
    create_directory_structure, 
    ProgressTracker, 
    validate_image_directory,
    get_image_info
)

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Video processing pipeline for frame extraction at specified FPS.
    Optimized for 0.5 FPS extraction for dataset expansion.
    """
    
    def __init__(self, config: CaminaConfig):
        self.config = config
        self.extraction_fps = config.video_processing.extraction_fps
        self.output_format = config.video_processing.output_format
        self.quality = config.video_processing.quality
        self.frame_size = config.video_processing.frame_size
        self.max_frames = config.video_processing.max_frames_per_video
        
        logger.info(f"VideoProcessor initialized for {self.extraction_fps} FPS extraction")
    
    def extract_frames(self, 
                      video_path: Union[str, Path], 
                      output_dir: Union[str, Path],
                      prefix: Optional[str] = None) -> Dict[str, any]:
        """
        Extract frames from video at specified FPS.
        
        Args:
            video_path: Path to input video
            output_dir: Directory to save extracted frames
            prefix: Optional prefix for frame filenames
        
        Returns:
            Dictionary with extraction results
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return {'success': False, 'error': 'Video file not found'}
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return {'success': False, 'error': 'Failed to open video'}
        
        # Get video properties
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / original_fps if original_fps > 0 else 0
        
        logger.info(f"Video info: {total_frames} frames, {original_fps:.2f} FPS, "
                   f"{duration:.2f}s duration")
        
        # Calculate frame extraction interval
        if self.extraction_fps >= original_fps:
            frame_interval = 1
            logger.warning(f"Extraction FPS ({self.extraction_fps}) >= original FPS "
                          f"({original_fps}), extracting every frame")
        else:
            frame_interval = int(original_fps / self.extraction_fps)
        
        # Extract frames
        extracted_frames = []
        frame_count = 0
        saved_count = 0
        
        if prefix is None:
            prefix = video_path.stem
        
        progress = ProgressTracker(
            total=min(total_frames // frame_interval, self.max_frames or float('inf')),
            description=f"Extracting frames from {video_path.name}"
        )
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extract frame at specified interval
                if frame_count % frame_interval == 0:
                    # Resize frame if specified
                    if self.frame_size:
                        frame = cv2.resize(frame, self.frame_size)
                    
                    # Generate filename
                    timestamp = frame_count / original_fps
                    frame_filename = f"{prefix}_frame_{saved_count:06d}_{timestamp:.2f}s.{self.output_format}"
                    frame_path = output_dir / frame_filename
                    
                    # Save frame
                    if self.output_format.lower() == 'jpg':
                        cv2.imwrite(
                            str(frame_path), 
                            frame, 
                            [cv2.IMWRITE_JPEG_QUALITY, self.quality]
                        )
                    else:
                        cv2.imwrite(str(frame_path), frame)
                    
                    extracted_frames.append({
                        'filename': frame_filename,
                        'path': str(frame_path),
                        'timestamp': timestamp,
                        'frame_number': frame_count
                    })
                    
                    saved_count += 1
                    progress.update()
                    
                    # Check max frames limit
                    if self.max_frames and saved_count >= self.max_frames:
                        logger.info(f"Reached maximum frames limit: {self.max_frames}")
                        break
                
                frame_count += 1
        
        finally:
            cap.release()
            progress.finish()
        
        # Calculate statistics
        extraction_stats = {
            'success': True,
            'video_path': str(video_path),
            'output_directory': str(output_dir),
            'video_info': {
                'total_frames': total_frames,
                'original_fps': original_fps,
                'duration_seconds': duration
            },
            'extraction_info': {
                'extraction_fps': self.extraction_fps,
                'frame_interval': frame_interval,
                'extracted_count': saved_count,
                'extraction_rate': saved_count / total_frames if total_frames > 0 else 0
            },
            'frames': extracted_frames
        }
        
        logger.info(f"Frame extraction completed: {saved_count} frames saved "
                   f"from {total_frames} total frames")
        
        return extraction_stats
    
    def process_video_batch(self, 
                           video_paths: List[Union[str, Path]], 
                           output_dir: Union[str, Path]) -> Dict[str, any]:
        """
        Process multiple videos in batch.
        
        Args:
            video_paths: List of video file paths
            output_dir: Base output directory
        
        Returns:
            Batch processing results
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        total_frames = 0
        failed_videos = []
        
        logger.info(f"Processing {len(video_paths)} videos...")
        
        for i, video_path in enumerate(video_paths):
            video_path = Path(video_path)
            logger.info(f"Processing video {i+1}/{len(video_paths)}: {video_path.name}")
            
            # Create subdirectory for each video
            video_output_dir = output_dir / video_path.stem
            
            # Extract frames
            result = self.extract_frames(video_path, video_output_dir)
            
            if result['success']:
                total_frames += result['extraction_info']['extracted_count']
                results.append(result)
            else:
                failed_videos.append({
                    'path': str(video_path),
                    'error': result.get('error', 'Unknown error')
                })
        
        batch_results = {
            'success': len(results) > 0,
            'processed_videos': len(results),
            'failed_videos': len(failed_videos),
            'total_extracted_frames': total_frames,
            'results': results,
            'failures': failed_videos
        }
        
        logger.info(f"Batch processing completed: {len(results)}/{len(video_paths)} videos processed, "
                   f"{total_frames} total frames extracted")
        
        return batch_results
    
    def create_frame_manifest(self, 
                             extraction_results: List[Dict], 
                             output_path: Union[str, Path]):
        """
        Create manifest file with frame extraction metadata.
        
        Args:
            extraction_results: List of extraction result dictionaries
            output_path: Path to save manifest file
        """
        manifest = {
            'created_at': datetime.now().isoformat(),
            'extraction_config': {
                'extraction_fps': self.extraction_fps,
                'output_format': self.output_format,
                'quality': self.quality,
                'frame_size': self.frame_size
            },
            'videos': extraction_results,
            'statistics': {
                'total_videos': len(extraction_results),
                'total_frames': sum(r['extraction_info']['extracted_count'] 
                                  for r in extraction_results),
                'total_duration_seconds': sum(r['video_info']['duration_seconds'] 
                                            for r in extraction_results)
            }
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Frame extraction manifest saved to {output_path}")


class DatasetManager:
    """
    Dataset management for CAMINA 9-class object detection.
    Handles SDL conversion, dataset splitting, and organization.
    """
    
    def __init__(self, config: CaminaConfig):
        self.config = config
        self.class_schema = config.class_schema
        self.dataset_config = config.dataset
        
        self.stats = defaultdict(int)
        
        logger.info(f"DatasetManager initialized for {self.class_schema.num_classes}-class detection")
    
    def convert_sdl_dataset(self) -> bool:
        """
        Convert SDL dataset to CAMINA 9-class format.
        
        Returns:
            True if conversion successful
        """
        sdl_path = Path(self.dataset_config.sdl_dataset_path)
        output_path = Path(self.dataset_config.output_dataset_path)
        
        if not sdl_path.exists():
            logger.error(f"SDL dataset not found: {sdl_path}")
            return False
        
        logger.info(f"Converting SDL dataset from {sdl_path} to {output_path}")
        
        # Create output structure
        self._create_dataset_structure(output_path)
        
        # Convert train and validation splits
        for split in ['train', 'test']:  # SDL has train/test, we map test->val
            yolo_split = 'train' if split == 'train' else 'val'
            success = self._convert_split(sdl_path, output_path, split, yolo_split)
            if not success:
                logger.error(f"Failed to convert {split} split")
                return False
        
        # Create configuration files
        self._create_dataset_yaml(output_path)
        self._create_classes_file(output_path)
        
        # Print conversion statistics
        self._print_conversion_stats()
        
        logger.info("SDL dataset conversion completed successfully")
        return True
    
    def _create_dataset_structure(self, output_path: Path):
        """Create YOLO dataset directory structure"""
        subdirs = [
            'images/train', 'images/val', 'images/test',
            'labels/train', 'labels/val', 'labels/test'
        ]
        create_directory_structure(output_path, subdirs)
    
    def _convert_split(self, 
                      sdl_path: Path, 
                      output_path: Path, 
                      sdl_split: str, 
                      yolo_split: str) -> bool:
        """Convert a specific dataset split"""
        logger.info(f"Converting {sdl_split} split to {yolo_split}...")
        
        # Source directories
        src_img_dir = sdl_path / 'images' / sdl_split
        src_label_dir = sdl_path / 'labels' / sdl_split
        
        # Destination directories
        dst_img_dir = output_path / 'images' / yolo_split
        dst_label_dir = output_path / 'labels' / yolo_split
        
        if not src_img_dir.exists() or not src_label_dir.exists():
            logger.warning(f"Source directories not found for {sdl_split}")
            return True  # Not an error, just no data for this split
        
        # Get image files
        image_files = list(src_img_dir.glob('*.jpg'))
        if not image_files:
            logger.warning(f"No images found in {src_img_dir}")
            return True
        
        progress = ProgressTracker(
            total=len(image_files),
            description=f"Converting {yolo_split} split"
        )
        
        converted_count = 0
        
        for img_file in image_files:
            # Copy image
            dst_img_path = dst_img_dir / img_file.name
            shutil.copy2(img_file, dst_img_path)
            
            # Convert labels
            label_file = src_label_dir / f"{img_file.stem}.txt"
            if label_file.exists():
                dst_label_path = dst_label_dir / f"{img_file.stem}.txt"
                if self._convert_label_file(label_file, dst_label_path):
                    converted_count += 1
            
            progress.update()
        
        progress.finish()
        
        self.stats[f"{yolo_split}_images"] = len(image_files)
        self.stats[f"{yolo_split}_labels"] = converted_count
        
        return True
    
    def _convert_label_file(self, src_label: Path, dst_label: Path) -> bool:
        """Convert individual label file from SDL to YOLO format"""
        try:
            converted_lines = []
            
            with open(src_label, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    
                    old_class_id = int(parts[0])
                    
                    # Map SDL class to CAMINA class
                    if old_class_id in self.class_schema.SDL_MAPPING:
                        new_class_id = self.class_schema.SDL_MAPPING[old_class_id]
                        bbox_coords = parts[1:5]
                        
                        converted_line = f"{new_class_id} {' '.join(bbox_coords)}"
                        converted_lines.append(converted_line)
                        
                        # Update statistics
                        class_name = self.class_schema.CLASSES[new_class_id]
                        self.stats[f"converted_{class_name}"] += 1
            
            # Write converted labels
            with open(dst_label, 'w') as f:
                f.write('\n'.join(converted_lines))
                if converted_lines:
                    f.write('\n')
            
            return len(converted_lines) > 0
            
        except Exception as e:
            logger.error(f"Failed to convert label file {src_label}: {e}")
            return False
    
    def _create_dataset_yaml(self, output_path: Path):
        """Create YOLO dataset configuration file"""
        yaml_path = output_path / 'data.yaml'
        self.config.create_dataset_yaml(yaml_path)
    
    def _create_classes_file(self, output_path: Path):
        """Create classes.txt file"""
        classes_file = output_path / 'classes.txt'
        with open(classes_file, 'w') as f:
            f.write('\n'.join(self.class_schema.class_names))
        logger.info(f"Classes file created: {classes_file}")
    
    def _print_conversion_stats(self):
        """Print detailed conversion statistics"""
        logger.info("=== Dataset Conversion Statistics ===")
        
        # Dataset splits
        for split in ['train', 'val']:
            img_count = self.stats.get(f"{split}_images", 0)
            label_count = self.stats.get(f"{split}_labels", 0)
            logger.info(f"{split.capitalize()}: {img_count} images, {label_count} labels")
        
        # Class distribution
        logger.info("\n=== Class Distribution ===")
        total_objects = sum(v for k, v in self.stats.items() if k.startswith('converted_'))
        
        for class_id, class_name in self.class_schema.CLASSES.items():
            if class_id < 6:  # Only existing classes from SDL
                count = self.stats.get(f"converted_{class_name}", 0)
                percentage = (count / total_objects * 100) if total_objects > 0 else 0
                logger.info(f"{class_name}: {count} objects ({percentage:.1f}%)")
        
        logger.info(f"Total objects: {total_objects}")
    
    def add_frames_to_dataset(self, 
                             frames_dir: Union[str, Path], 
                             split: str = 'train') -> bool:
        """
        Add extracted frames to dataset for auto-labeling.
        
        Args:
            frames_dir: Directory containing extracted frames
            split: Dataset split to add frames to ('train', 'val', 'test')
        
        Returns:
            True if successful
        """
        frames_dir = Path(frames_dir)
        dataset_path = Path(self.dataset_config.output_dataset_path)
        
        if not frames_dir.exists():
            logger.error(f"Frames directory not found: {frames_dir}")
            return False
        
        # Validate image directory
        validation_result = validate_image_directory(frames_dir)
        if not validation_result['valid']:
            logger.error(f"Invalid frames directory: {validation_result['error']}")
            return False
        
        logger.info(f"Adding {validation_result['valid_images']} frames to {split} split")
        
        # Destination directory
        dst_img_dir = dataset_path / 'images' / split
        dst_img_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy frames
        copied_count = 0
        for img_file in frames_dir.rglob('*.jpg'):
            dst_path = dst_img_dir / f"frame_{img_file.stem}_{copied_count:06d}.jpg"
            shutil.copy2(img_file, dst_path)
            copied_count += 1
        
        logger.info(f"Added {copied_count} frames to {split} split")
        return True
    
    def create_data_splits(self, 
                          source_dir: Union[str, Path],
                          train_ratio: Optional[float] = None,
                          val_ratio: Optional[float] = None,
                          test_ratio: Optional[float] = None) -> bool:
        """
        Create train/val/test splits from source directory.
        
        Args:
            source_dir: Directory containing images and labels
            train_ratio: Training split ratio (uses config if None)
            val_ratio: Validation split ratio (uses config if None)
            test_ratio: Test split ratio (uses config if None)
        
        Returns:
            True if successful
        """
        source_dir = Path(source_dir)
        if not source_dir.exists():
            logger.error(f"Source directory not found: {source_dir}")
            return False
        
        # Use config ratios if not provided
        train_ratio = train_ratio or self.dataset_config.train_split
        val_ratio = val_ratio or self.dataset_config.val_split
        test_ratio = test_ratio or self.dataset_config.test_split
        
        # Verify ratios sum to 1.0
        total_ratio = train_ratio + val_ratio + test_ratio
        if abs(total_ratio - 1.0) > 0.01:
            logger.error(f"Split ratios must sum to 1.0, got {total_ratio}")
            return False
        
        # Get all images
        image_files = list(source_dir.glob('*.jpg'))
        if not image_files:
            logger.error(f"No images found in {source_dir}")
            return False
        
        # Shuffle for random split
        np.random.shuffle(image_files)
        
        # Calculate split indices
        total_images = len(image_files)
        train_end = int(total_images * train_ratio)
        val_end = train_end + int(total_images * val_ratio)
        
        # Split files
        train_files = image_files[:train_end]
        val_files = image_files[train_end:val_end]
        test_files = image_files[val_end:]
        
        # Create splits
        dataset_path = Path(self.dataset_config.output_dataset_path)
        splits = {
            'train': train_files,
            'val': val_files,
            'test': test_files
        }
        
        for split_name, files in splits.items():
            if not files:
                continue
                
            img_dir = dataset_path / 'images' / split_name
            label_dir = dataset_path / 'labels' / split_name
            img_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating {split_name} split with {len(files)} images")
            
            for img_file in files:
                # Copy image
                shutil.copy2(img_file, img_dir / img_file.name)
                
                # Copy label if exists
                label_file = source_dir / f"{img_file.stem}.txt"
                if label_file.exists():
                    shutil.copy2(label_file, label_dir / f"{img_file.stem}.txt")
        
        logger.info(f"Dataset splits created: Train={len(train_files)}, "
                   f"Val={len(val_files)}, Test={len(test_files)}")
        
        return True