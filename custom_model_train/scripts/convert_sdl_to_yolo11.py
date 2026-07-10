#!/usr/bin/env python3
"""
Convert SDL fine-tuned dataset to YOLO11 format with 9-class schema
Maps existing classes to new ID structure and prepares for dataset expansion
"""

import os
import shutil
import yaml
import argparse
from pathlib import Path
from collections import defaultdict
import logging

from class_taxonomy import (
    load_canonical_classes,
    load_class_aliases,
    resolve_to_canonical,
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SDLToYOLO11Converter:
    def __init__(self, sdl_dataset_path, output_path):
        self.sdl_path = Path(sdl_dataset_path)
        self.output_path = Path(output_path)
        
        # Original SDL class order (indices 0-5 as exported by the SDL tool).
        sdl_original_classes = ['bus', 'car', 'cyclist', 'motorcycle', 'person', 'truck']

        # The canonical 9-class taxonomy is the single source of truth
        # (configs/classes.yaml); dataset/toolchain aliases (e.g. person for the
        # SDL "person", motorcyclist for "motorcycle") are translated by
        # custom_model_train/class_mapping.yaml. Deriving both the target class
        # list and the SDL->canonical id remap from those files guarantees this
        # converter can never drift from the taxonomy the rest of the system
        # uses, and fails loudly if an SDL class name is unmapped.
        self.new_classes = load_canonical_classes()
        aliases = load_class_aliases()
        canonical_index = {name: i for i, name in enumerate(self.new_classes)}
        sdl_canonical_names = resolve_to_canonical(sdl_original_classes, aliases=aliases)
        self.class_mapping = {
            sdl_id: canonical_index[canonical_name]
            for sdl_id, canonical_name in enumerate(sdl_canonical_names)
        }
        
        self.stats = defaultdict(int)
        
    def create_output_structure(self):
        """Create YOLO11 directory structure"""
        for split in ['train', 'val', 'test']:
            (self.output_path / 'images' / split).mkdir(parents=True, exist_ok=True)
            (self.output_path / 'labels' / split).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output structure at {self.output_path}")
        
    def convert_labels(self, label_file, output_label_file):
        """Convert SDL label format to YOLO11 with class remapping"""
        converted_lines = []
        
        with open(label_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split()
                if len(parts) != 5:
                    continue
                    
                old_class_id = int(parts[0])
                
                # Skip if class not in our mapping (shouldn't happen with SDL dataset)
                if old_class_id not in self.class_mapping:
                    logger.warning(f"Unknown class ID {old_class_id} in {label_file}")
                    continue
                    
                # Map to new class ID
                new_class_id = self.class_mapping[old_class_id]
                
                # Keep the same bbox coordinates (already normalized)
                bbox_coords = parts[1:5]
                
                converted_line = f"{new_class_id} {' '.join(bbox_coords)}"
                converted_lines.append(converted_line)
                
                self.stats[f"converted_{self.new_classes[new_class_id]}"] += 1
                
        # Write converted labels
        with open(output_label_file, 'w') as f:
            f.write('\n'.join(converted_lines))
            if converted_lines:  # Add final newline if file not empty
                f.write('\n')
                
        return len(converted_lines)
    
    def copy_images(self, src_img_dir, dst_img_dir):
        """Copy images from source to destination"""
        if not src_img_dir.exists():
            logger.error(f"Source image directory does not exist: {src_img_dir}")
            return 0
            
        copied_count = 0
        for img_file in src_img_dir.glob('*.jpg'):
            dst_file = dst_img_dir / img_file.name
            shutil.copy2(img_file, dst_file)
            copied_count += 1
            
        return copied_count
    
    def convert_split(self, split_name):
        """Convert a specific data split (train/test -> train/val/test)"""
        # Map SDL splits to YOLO11 splits
        sdl_split_mapping = {
            'train': 'train',  # SDL train -> YOLO11 train
            'test': 'val'      # SDL test -> YOLO11 val (we'll create test later)
        }
        
        if split_name not in sdl_split_mapping:
            logger.error(f"Unknown split: {split_name}")
            return
            
        yolo_split = sdl_split_mapping[split_name]
        
        # Source directories
        src_img_dir = self.sdl_path / 'images' / split_name
        src_label_dir = self.sdl_path / 'labels' / split_name
        
        # Destination directories  
        dst_img_dir = self.output_path / 'images' / yolo_split
        dst_label_dir = self.output_path / 'labels' / yolo_split
        
        logger.info(f"Converting {split_name} split to {yolo_split}...")
        
        # Copy and convert labels
        label_count = 0
        if src_label_dir.exists():
            for label_file in src_label_dir.glob('*.txt'):
                # Skip cache files
                if label_file.name.endswith('.cache'):
                    continue
                    
                dst_label_file = dst_label_dir / label_file.name
                bbox_count = self.convert_labels(label_file, dst_label_file)
                if bbox_count > 0:
                    label_count += 1
        
        # Copy images
        img_count = self.copy_images(src_img_dir, dst_img_dir)
        
        logger.info(f"Split {yolo_split}: {img_count} images, {label_count} label files")
        self.stats[f"{yolo_split}_images"] = img_count
        self.stats[f"{yolo_split}_labels"] = label_count
    
    def create_data_yaml(self):
        """Create YOLO11 data.yaml configuration"""
        data_config = {
            'path': str(self.output_path.absolute()),
            'train': 'images/train',
            'val': 'images/val', 
            'test': 'images/test',  # Will be populated later
            'nc': 9,
            'names': {i: name for i, name in enumerate(self.new_classes)}
        }
        
        yaml_file = self.output_path / 'data.yaml'
        with open(yaml_file, 'w') as f:
            yaml.dump(data_config, f, default_flow_style=False, sort_keys=False)
            
        logger.info(f"Created data.yaml at {yaml_file}")
    
    def create_classes_txt(self):
        """Create classes.txt file"""
        classes_file = self.output_path / 'classes.txt'
        with open(classes_file, 'w') as f:
            f.write('\n'.join(self.new_classes))
            
        logger.info(f"Created classes.txt at {classes_file}")
    
    def print_statistics(self):
        """Print conversion statistics"""
        logger.info("=== Conversion Statistics ===")
        for key, value in sorted(self.stats.items()):
            logger.info(f"{key}: {value}")
            
        # Calculate class distribution
        logger.info("\n=== Class Distribution ===")
        total_objects = sum(v for k, v in self.stats.items() if k.startswith('converted_'))
        # Only the canonical classes the SDL source actually populates (derived
        # from the id remap; canonical order no longer puts them first six).
        populated_classes = [
            self.new_classes[idx] for idx in sorted(set(self.class_mapping.values()))
        ]
        for class_name in populated_classes:
            count = self.stats.get(f"converted_{class_name}", 0)
            percentage = (count / total_objects * 100) if total_objects > 0 else 0
            logger.info(f"{class_name}: {count} objects ({percentage:.1f}%)")
    
    def convert(self):
        """Run the full conversion process"""
        logger.info("Starting SDL to YOLO11 conversion...")
        
        # Create output structure
        self.create_output_structure()
        
        # Convert data splits
        self.convert_split('train')
        self.convert_split('test') 
        
        # Create configuration files
        self.create_data_yaml()
        self.create_classes_txt()
        
        # Print statistics
        self.print_statistics()
        
        logger.info(f"Conversion completed! Output saved to {self.output_path}")
        logger.info("Note: Test split is empty - will be populated during dataset expansion")

def main():
    parser = argparse.ArgumentParser(description='Convert SDL dataset to YOLO11 format')
    parser.add_argument('--sdl-dataset', 
                       default='datasets/SDL fine-tuned_v3-cyclist_cleaned',
                       help='Path to SDL dataset directory')
    parser.add_argument('--output', 
                       default='all_camina_classes',
                       help='Output directory for YOLO11 dataset')
    
    args = parser.parse_args()
    
    # Initialize converter
    converter = SDLToYOLO11Converter(args.sdl_dataset, args.output)
    
    # Run conversion
    converter.convert()

if __name__ == '__main__':
    main()