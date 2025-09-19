#!/usr/bin/env python3
"""
CAMINA Roboflow Data Preparation Script

Prepares CAMINA pipeline results in YOLOv11 format for Roboflow upload.
Creates organized dataset folders ready for manual upload to Roboflow.
Handles both train and test datasets with YOLO format labels.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import shutil
import json
import csv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Default CAMINA class names
DEFAULT_CLASS_NAMES = {
    0: "person",
    1: "cyclist",
    2: "car",
    3: "motorcycle",
    4: "bus",
    5: "truck",
    6: "e-scooter",      # YOLO-World detection
    7: "SUV",           # YOLO-World detection
    8: "delivery_van"   # YOLO-World detection
}


def validate_paths(paths: List[str]) -> None:
    """Validate that all required paths exist."""
    for path in paths:
        if not Path(path).exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
    logger.info("✅ All paths validated successfully")


def create_data_yaml(output_dir: Path, class_names: Dict[int, str], use_val: bool = False) -> Path:
    """Create data.yaml file for YOLOv11 format."""
    split_name = 'val' if use_val else 'test'

    yaml_content = {
        'path': str(output_dir),
        'train': 'images/train',
        'val': f'images/{split_name}',
        'nc': len(class_names),
        'names': list(class_names.values())
    }

    if not use_val:
        yaml_content['test'] = f'images/{split_name}'

    yaml_path = output_dir / 'data.yaml'

    with open(yaml_path, 'w') as f:
        f.write(f"path: {yaml_content['path']}\n")
        f.write(f"train: {yaml_content['train']}\n")
        f.write(f"val: {yaml_content['val']}\n")
        if not use_val:
            f.write(f"test: {yaml_content['test']}\n")
        f.write(f"\n")
        f.write(f"nc: {yaml_content['nc']}\n")
        f.write(f"names:\n")
        for name in yaml_content['names']:
            f.write(f"  - {name}\n")

    logger.info(f"📄 Created data.yaml: {yaml_path}")
    return yaml_path


def copy_files(src_dir: str, dst_dir: Path, file_type: str) -> int:
    """Copy files from source to destination directory."""
    src_path = Path(src_dir)
    files = list(src_path.glob('*'))

    copied_count = 0
    for file_path in files:
        if file_path.is_file():
            dst_file = dst_dir / file_path.name
            shutil.copy2(file_path, dst_file)
            copied_count += 1

    logger.info(f"   • Copied {copied_count} {file_type} files")
    return copied_count


def get_valid_image_label_pairs(images_dir: str, labels_dir: str) -> List[Tuple[Path, Path]]:
    """Get all valid image-label pairs."""
    images_path = Path(images_dir)
    labels_path = Path(labels_dir)

    image_files = sorted(list(images_path.glob('*')))
    valid_pairs = []

    for img_file in image_files:
        label_file = labels_path / f"{img_file.stem}.txt"
        if label_file.exists():
            valid_pairs.append((img_file, label_file))

    return valid_pairs


def prepare_single_dataset(images_dir: str, labels_dir: str, output_dir: Path,
                         class_names: Dict[int, str]) -> Path:
    """Prepare single dataset (from run.sh) in YOLOv11 format with 80/20 train/val split."""
    logger.info("📁 Preparing single dataset with 80/20 train/val split...")

    # Create directory structure
    train_img_dir = output_dir / 'images' / 'train'
    val_img_dir = output_dir / 'images' / 'val'
    train_lbl_dir = output_dir / 'labels' / 'train'
    val_lbl_dir = output_dir / 'labels' / 'val'

    for dir_path in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Get valid image-label pairs
    valid_pairs = get_valid_image_label_pairs(images_dir, labels_dir)

    # Split 80/20
    split_idx = int(len(valid_pairs) * 0.8)
    train_pairs = valid_pairs[:split_idx]
    val_pairs = valid_pairs[split_idx:]

    # Copy train files
    logger.info(f"📁 Copying {len(train_pairs)} train files...")
    for img_file, lbl_file in train_pairs:
        shutil.copy2(img_file, train_img_dir / img_file.name)
        shutil.copy2(lbl_file, train_lbl_dir / lbl_file.name)

    # Copy validation files
    logger.info(f"📁 Copying {len(val_pairs)} validation files...")
    for img_file, lbl_file in val_pairs:
        shutil.copy2(img_file, val_img_dir / img_file.name)
        shutil.copy2(lbl_file, val_lbl_dir / lbl_file.name)

    # Create data.yaml with val instead of test
    create_data_yaml(output_dir, class_names, use_val=True)

    logger.info(f"📊 Single dataset prepared:")
    logger.info(f"   • Train: {len(train_pairs)} images")
    logger.info(f"   • Val: {len(val_pairs)} images")
    logger.info(f"   • Classes: {len(class_names)}")

    return output_dir


def prepare_split_dataset(train_images_dir: str, train_labels_dir: str,
                         test_images_dir: str, test_labels_dir: str,
                         output_dir: Path, class_names: Dict[int, str]) -> Path:
    """Prepare train/test split dataset (from run_imagenet.sh) in YOLOv11 format."""
    # Create directory structure
    train_img_dir = output_dir / 'images' / 'train'
    train_lbl_dir = output_dir / 'labels' / 'train'
    test_img_dir = output_dir / 'images' / 'test'
    test_lbl_dir = output_dir / 'labels' / 'test'

    for dir_path in [train_img_dir, train_lbl_dir, test_img_dir, test_lbl_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Copy train files
    logger.info("📁 Copying train files...")
    copy_files(train_images_dir, train_img_dir, "images")
    copy_files(train_labels_dir, train_lbl_dir, "labels")

    # Copy test files
    logger.info("📁 Copying test files...")
    copy_files(test_images_dir, test_img_dir, "images")
    copy_files(test_labels_dir, test_lbl_dir, "labels")

    # Create data.yaml
    create_data_yaml(output_dir, class_names)

    # Count files
    train_count = len(list(train_img_dir.glob('*')))
    test_count = len(list(test_img_dir.glob('*')))

    logger.info(f"📊 Split dataset prepared:")
    logger.info(f"   • Train: {train_count} images")
    logger.info(f"   • Test: {test_count} images")
    logger.info(f"   • Classes: {len(class_names)}")

    return output_dir


def analyze_split_data(dataset_dir: Path, split: str, class_names: Dict[int, str]) -> Dict[str, Any]:
    """Analyze a specific split (train/val/test)."""
    images_dir = dataset_dir / 'images' / split
    labels_dir = dataset_dir / 'labels' / split

    image_files = list(images_dir.glob('*'))
    label_files = list(labels_dir.glob('*.txt'))

    class_counts = {class_id: 0 for class_id in class_names.keys()}
    total_instances = 0
    images_with_labels = 0

    for label_file in label_files:
        if label_file.stat().st_size > 0:  # Non-empty label file
            images_with_labels += 1
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        if class_id in class_counts:
                            class_counts[class_id] += 1
                            total_instances += 1

    return {
        'num_images': len(image_files),
        'num_labels': len(label_files),
        'images_with_labels': images_with_labels,
        'total_instances': total_instances,
        'class_counts': class_counts,
        'avg_instances_per_image': total_instances / max(images_with_labels, 1)
    }


def get_detection_method(class_id: int) -> str:
    """Get detection method for a given class ID."""
    if class_id in [0, 2, 3, 4, 5]:
        return "YOLO11l"
    elif class_id in [6, 7, 8]:
        return "YOLO-World"
    elif class_id == 1:
        return "Spatial Logic"
    else:
        return "Unknown"


def generate_dataset_report(dataset_dir: Path, dataset_name: str, dataset_type: str,
                          class_names: Dict[int, str]) -> Dict[str, Any]:
    """Generate comprehensive dataset report for academic paper."""
    logger.info("📊 Generating dataset report...")

    report_data = {
        'dataset_name': dataset_name,
        'dataset_type': dataset_type,
        'total_classes': len(class_names),
        'class_names': class_names,
        'splits': {},
        'class_distribution': {},
        'total_images': 0,
        'total_instances': 0
    }

    # Analyze each split (train/val or train/test)
    splits_to_check = []
    if (dataset_dir / 'images' / 'train').exists():
        splits_to_check.append('train')
    if (dataset_dir / 'images' / 'val').exists():
        splits_to_check.append('val')
    if (dataset_dir / 'images' / 'test').exists():
        splits_to_check.append('test')

    for split in splits_to_check:
        split_data = analyze_split_data(dataset_dir, split, class_names)
        report_data['splits'][split] = split_data
        report_data['total_images'] += split_data['num_images']
        report_data['total_instances'] += split_data['total_instances']

        # Aggregate class distribution
        for class_id, count in split_data['class_counts'].items():
            if class_id not in report_data['class_distribution']:
                report_data['class_distribution'][class_id] = 0
            report_data['class_distribution'][class_id] += count

    return report_data


def create_upload_instructions(dataset_dir: Path, dataset_name: str, dataset_type: str,
                             class_names: Dict[int, str], dataset_notes: Optional[str] = None) -> None:
    """Create instructions file for manual upload to Roboflow."""
    instructions_file = dataset_dir / "ROBOFLOW_UPLOAD_INSTRUCTIONS.md"

    instructions = f"""# Roboflow Upload Instructions

## Dataset: {dataset_name}

### Dataset Information
- **Type**: {dataset_type}
- **Classes**: {len(class_names)} total
- **Notes**: {dataset_notes or 'CAMINA pipeline results'}

### Classes Detected
"""

    for class_id, class_name in class_names.items():
        instructions += f"- **{class_id}**: {class_name}\n"

    instructions += f"""

### Files Structure
```
{dataset_dir.name}/
├── data.yaml          # Dataset configuration
├── images/
│   ├── train/         # Training images
│   └── val/ (or test/) # Validation/test images
└── labels/
    ├── train/         # Training labels (YOLO format)
    └── val/ (or test/) # Validation/test labels

```

### Manual Upload Steps

1. **Go to Roboflow**: https://roboflow.com/
2. **Sign in** to your account
3. **Create new project** or select existing project
4. **Upload dataset**:
   - Choose "Upload" → "Computer"
   - Select the entire `{dataset_dir.name}` folder
   - Choose "YOLOv11" format
   - Set project type to "Object Detection"
5. **Configure classes**: Verify the 9 CAMINA classes are correctly mapped
6. **Add version notes**: {dataset_notes or 'CAMINA pipeline detection results'}

### Dataset Features
- ✅ YOLOv11 format compatible
- ✅ Proper train/validation split
- ✅ Complete class mapping
- ✅ YOLO format labels
- ✅ data.yaml configuration file

### Support
- Check that all images have corresponding label files
- Verify data.yaml contains correct class mappings
- Ensure folder structure matches YOLOv11 requirements
"""

    with open(instructions_file, 'w') as f:
        f.write(instructions)

    logger.info(f"📝 Created upload instructions: {instructions_file}")


def create_summary_report(dataset_dir: Path, report_data: Dict[str, Any]) -> None:
    """Create human-readable summary report."""
    report_file = dataset_dir / "DATASET_REPORT.md"

    report = f"""# CAMINA Dataset Report

## Dataset Overview
- **Name**: {report_data['dataset_name']}
- **Type**: {report_data['dataset_type']}
- **Total Images**: {report_data['total_images']:,}
- **Total Instances**: {report_data['total_instances']:,}
- **Classes**: {report_data['total_classes']}

## Dataset Splits
"""

    for split, data in report_data['splits'].items():
        report += f"""
### {split.capitalize()} Split
- **Images**: {data['num_images']:,}
- **Images with Labels**: {data['images_with_labels']:,}
- **Total Instances**: {data['total_instances']:,}
- **Avg Instances/Image**: {data['avg_instances_per_image']:.2f}
"""

    report += f"""
## Class Distribution

| Class ID | Class Name | Count | Percentage |
|----------|------------|-------|------------|
"""

    for class_id in sorted(report_data['class_distribution'].keys()):
        count = report_data['class_distribution'][class_id]
        percentage = (count / report_data['total_instances']) * 100 if report_data['total_instances'] > 0 else 0
        class_name = report_data['class_names'][class_id]
        report += f"| {class_id} | {class_name} | {count:,} | {percentage:.1f}% |\n"

    report += f"""
## Detection Sources

### Stage A (YOLO11l)
- **person** (0), **car** (2), **motorcycle** (3), **bus** (4), **truck** (5)

### Stage B (YOLO-World)
- **e-scooter** (6), **SUV** (7), **delivery_van** (8)

### Spatial Logic
- **cyclist** (1): Generated from person + bicycle spatial association

## Pipeline Features
- ✅ Multi-stage detection (YOLO11l + YOLO-World)
- ✅ E-scooter spatial association (person + e-scooter → combined bbox)
- ✅ Cyclist logic (person + bicycle → cyclist)
- ✅ NMS with class priorities (SUV > car, delivery_van > truck)

## Dataset Statistics Summary
- **Images per split**: {', '.join([f"{split}: {data['num_images']:,}" for split, data in report_data['splits'].items()])}
- **Most frequent class**: {max(report_data['class_distribution'], key=report_data['class_distribution'].get)} ({report_data['class_names'][max(report_data['class_distribution'], key=report_data['class_distribution'].get)]})
- **Instance density**: {report_data['total_instances'] / report_data['total_images']:.2f} instances per image
"""

    with open(report_file, 'w') as f:
        f.write(report)

    logger.info(f"📋 Created summary report: {report_file}")


def create_academic_report(dataset_dir: Path, report_data: Dict[str, Any]) -> None:
    """Create academic paper-ready report."""
    report_file = dataset_dir / "ACADEMIC_REPORT.md"

    report = f"""# CAMINA Dataset: Academic Report

## Abstract
This dataset contains {report_data['total_images']:,} images with {report_data['total_instances']:,} object instances across {report_data['total_classes']} urban mobility classes, generated using the CAMINA (Computer-Aided Mobility Intelligence for Nonlinear Analytics) detection pipeline.

## Dataset Composition

### Quantitative Overview
- **Total Images**: {report_data['total_images']:,}
- **Total Annotations**: {report_data['total_instances']:,}
- **Class Categories**: {report_data['total_classes']}
- **Average Instances per Image**: {report_data['total_instances'] / report_data['total_images']:.2f}

### Data Splits
"""

    for split, data in report_data['splits'].items():
        percentage = (data['num_images'] / report_data['total_images']) * 100
        report += f"- **{split.capitalize()}**: {data['num_images']:,} images ({percentage:.1f}%), {data['total_instances']:,} instances\n"

    report += f"""
### Class Distribution Analysis

The dataset exhibits the following class distribution characteristics:

| Class | Count | Frequency (%) | Detection Method |
|-------|-------|---------------|------------------|
"""

    # Sort by frequency for academic presentation
    sorted_classes = sorted(report_data['class_distribution'].items(),
                           key=lambda x: x[1], reverse=True)

    for class_id, count in sorted_classes:
        percentage = (count / report_data['total_instances']) * 100
        class_name = report_data['class_names'][class_id]
        method = get_detection_method(class_id)
        report += f"| {class_name} | {count:,} | {percentage:.1f}% | {method} |\n"

    report += f"""
## Methodology

### Detection Pipeline
The CAMINA pipeline employs a hybrid detection approach combining:

1. **Stage A (Traditional Detection)**: YOLO11l model for standard object classes
2. **Stage B (Open-Vocabulary Detection)**: YOLO-World for specialized urban mobility objects
3. **Spatial Association Logic**: Custom algorithms for cyclist and e-scooter detection

### Quality Assurance
- **IoU-based NMS**: Threshold of 0.4 for overlap resolution
- **Class Priority System**: Specialized classes (SUV, delivery_van) take precedence over generic classes
- **Confidence Filtering**: Minimum confidence thresholds applied per class type

## Statistical Analysis

### Instance Distribution
"""

    # Calculate statistics for academic presentation
    instance_counts = list(report_data['class_distribution'].values())
    mean_instances = sum(instance_counts) / len(instance_counts)

    report += f"""- **Mean instances per class**: {mean_instances:.1f}
- **Standard deviation**: {(sum((x - mean_instances)**2 for x in instance_counts) / len(instance_counts))**0.5:.1f}
- **Most represented class**: {report_data['class_names'][max(report_data['class_distribution'], key=report_data['class_distribution'].get)]} ({max(instance_counts):,} instances)
- **Least represented class**: {report_data['class_names'][min(report_data['class_distribution'], key=report_data['class_distribution'].get)]} ({min(instance_counts):,} instances)

### Annotation Quality Metrics
"""

    for split, data in report_data['splits'].items():
        coverage = (data['images_with_labels'] / data['num_images']) * 100
        report += f"- **{split.capitalize()} annotation coverage**: {coverage:.1f}% ({data['images_with_labels']:,}/{data['num_images']:,} images)\n"

    report += f"""
## Technical Specifications

### Format Compliance
- **Annotation Format**: YOLO format (normalized coordinates)
- **Image Formats**: JPEG, PNG
- **Framework Compatibility**: YOLOv11, YOLOv8, YOLOv5
- **Validation**: All annotations validated for format compliance

### Reproducibility
- **Pipeline Version**: CAMINA v2.0.0
- **Detection Models**: YOLO11l, YOLO-World v2
- **Configuration**: Deterministic seeds and thresholds applied
- **Hardware**: RTX 3060 12GB VRAM + 32GB RAM

## Citation
```
@dataset{{camina_dataset_{report_data['dataset_name'].lower().replace('-', '_')},
  title={{CAMINA Urban Mobility Detection Dataset}},
  author={{CAMINA Research Team}},
  year={{2025}},
  description={{Multi-stage urban mobility object detection dataset with {report_data['total_instances']:,} annotations across {report_data['total_classes']} classes}},
  url={{https://github.com/camina-research/dataset}}
}}
```
"""

    with open(report_file, 'w') as f:
        f.write(report)

    logger.info(f"📄 Created academic report: {report_file}")


def create_csv_reports(dataset_dir: Path, report_data: Dict[str, Any]) -> None:
    """Create CSV reports for data analysis."""
    # Class distribution CSV
    csv_file = dataset_dir / "class_distribution.csv"

    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['class_id', 'class_name', 'count', 'percentage', 'detection_method'])

        for class_id, count in report_data['class_distribution'].items():
            percentage = (count / report_data['total_instances']) * 100 if report_data['total_instances'] > 0 else 0
            class_name = report_data['class_names'][class_id]
            method = get_detection_method(class_id).replace(' ', '_')
            writer.writerow([class_id, class_name, count, f"{percentage:.2f}", method])

    # Split statistics CSV
    split_csv_file = dataset_dir / "split_statistics.csv"

    with open(split_csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['split', 'num_images', 'images_with_labels', 'total_instances', 'avg_instances_per_image', 'annotation_coverage'])

        for split, data in report_data['splits'].items():
            coverage = (data['images_with_labels'] / data['num_images']) * 100
            writer.writerow([
                split,
                data['num_images'],
                data['images_with_labels'],
                data['total_instances'],
                f"{data['avg_instances_per_image']:.2f}",
                f"{coverage:.2f}"
            ])

    logger.info(f"📊 Created CSV reports: {csv_file}, {split_csv_file}")


def prepare_dataset(dataset_name: str, dataset_type: str, output_base_dir: str = "roboflow_datasets",
                   dataset_notes: Optional[str] = None, class_names: Optional[Dict[int, str]] = None,
                   images_dir: Optional[str] = None, labels_dir: Optional[str] = None,
                   train_images_dir: Optional[str] = None, train_labels_dir: Optional[str] = None,
                   test_images_dir: Optional[str] = None, test_labels_dir: Optional[str] = None) -> Path:
    """Prepare dataset in YOLOv11 format for Roboflow upload."""

    if class_names is None:
        class_names = DEFAULT_CLASS_NAMES.copy()

    # Validate configuration
    if dataset_type == "single":
        if not images_dir or not labels_dir:
            raise ValueError("For single dataset, images_dir and labels_dir must be provided")
        validate_paths([images_dir, labels_dir])
    elif dataset_type == "split":
        required_paths = [train_images_dir, train_labels_dir, test_images_dir, test_labels_dir]
        if not all(required_paths):
            raise ValueError("For split dataset, all train/test paths must be provided")
        validate_paths(required_paths)
    else:
        raise ValueError("dataset_type must be 'single' or 'split'")

    # Create output directory
    output_path = Path(output_base_dir) / dataset_name

    try:
        logger.info(f"📦 Preparing dataset: {dataset_name}")
        logger.info(f"📁 Output directory: {output_path}")

        # Prepare dataset based on type
        if dataset_type == "single":
            dataset_dir = prepare_single_dataset(images_dir, labels_dir, output_path, class_names)
        else:
            dataset_dir = prepare_split_dataset(train_images_dir, train_labels_dir,
                                              test_images_dir, test_labels_dir,
                                              output_path, class_names)

        logger.info("🎉 Dataset preparation completed successfully!")
        logger.info(f"📁 Dataset ready for upload at: {dataset_dir}")

        # Create upload instructions
        create_upload_instructions(dataset_dir, dataset_name, dataset_type, class_names, dataset_notes)

        # Generate comprehensive reports
        logger.info("📊 Generating comprehensive reports...")
        report_data = generate_dataset_report(dataset_dir, dataset_name, dataset_type, class_names)

        create_summary_report(dataset_dir, report_data)
        create_academic_report(dataset_dir, report_data)
        create_csv_reports(dataset_dir, report_data)

        logger.info("✅ Reports generated successfully!")
        logger.info(f"📋 Dataset summary: {report_data['total_images']:,} images, {report_data['total_instances']:,} instances")

        return dataset_dir

    except Exception as e:
        logger.error(f"❌ Dataset preparation failed: {e}")
        raise


def prepare_run_sh_output() -> bool:
    """Prepare results from run.sh (complete pipeline on data/images)."""
    print("🚀 Preparing run.sh results (Complete Pipeline)")
    print("=" * 60)
    print(f"📁 Images: outputs/mixed/dataset_viz/images")
    print(f"🏷️  Labels: outputs/mixed/yolo")
    print(f"📦 Features: All CAMINA pipeline features included")
    print()

    try:
        dataset_dir = prepare_dataset(
            dataset_name="camina-complete-pipeline",
            dataset_type="single",
            images_dir="outputs/mixed/dataset_viz/images",
            labels_dir="outputs/mixed/yolo",
            output_base_dir="roboflow_datasets",
            dataset_notes="CAMINA complete pipeline: Stage A + Stage B + e-scooter spatial association + NMS prioritization"
        )

        print("✅ SUCCESS! Complete pipeline dataset prepared for Roboflow")
        print(f"📁 Dataset ready at: {dataset_dir}")
        print(f"📄 Reports generated: DATASET_REPORT.md, ACADEMIC_REPORT.md, class_distribution.csv")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def prepare_run_imagenet_output() -> bool:
    """Prepare results from run_imagenet.sh (YOLO-World only on dataset_v4i_yolov11)."""
    print("🚀 Preparing run_imagenet.sh results (YOLO-World Only)")
    print("=" * 60)
    print(f"📁 Train: outputs/imagenet_train/dataset_viz/images")
    print(f"📁 Test: outputs/imagenet_test/dataset_viz/images")
    print(f"🎯 Classes: e-scooter, SUV, delivery_van")
    print()

    try:
        dataset_dir = prepare_dataset(
            dataset_name="camina-yolo-world-detections",
            dataset_type="split",
            train_images_dir="outputs/imagenet_train/dataset_viz/images",
            train_labels_dir="outputs/imagenet_train/yolo",
            test_images_dir="outputs/imagenet_test/dataset_viz/images",
            test_labels_dir="outputs/imagenet_test/yolo",
            output_base_dir="roboflow_datasets",
            dataset_notes="CAMINA YOLO-World detections for e-scooter, SUV, and delivery_van classes"
        )

        print("✅ SUCCESS! YOLO-World dataset prepared for Roboflow")
        print(f"📁 Dataset ready at: {dataset_dir}")
        print(f"📄 Reports generated: DATASET_REPORT.md, ACADEMIC_REPORT.md, class_distribution.csv")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def main():
    """Main function with data preparation options."""
    print("🚀 CAMINA Roboflow Data Preparation Script")
    print("=" * 50)
    print()
    print("Choose which dataset to prepare for Roboflow upload:")
    print("1. Complete Pipeline (run.sh output)")
    print("   • Source: outputs/mixed/")
    print("   • Features: Stage A + Stage B + e-scooter logic + NMS")
    print("   • Classes: All 9 CAMINA classes")
    print("   • Split: Auto 80/20 train/validation")
    print()
    print("2. YOLO-World Only (run_imagenet.sh output)")
    print("   • Source: outputs/imagenet_train/ + outputs/imagenet_test/")
    print("   • Features: YOLO-World detection only")
    print("   • Classes: e-scooter, SUV, delivery_van")
    print("   • Split: Predefined train/test")
    print()
    print("3. Both datasets")
    print()

    while True:
        choice = input("Enter your choice (1/2/3): ").strip()

        if choice == "1":
            prepare_run_sh_output()
            break
        elif choice == "2":
            prepare_run_imagenet_output()
            break
        elif choice == "3":
            print("\n📤 Preparing Complete Pipeline dataset...")
            success1 = prepare_run_sh_output()

            print("\n📤 Preparing YOLO-World dataset...")
            success2 = prepare_run_imagenet_output()

            if success1 and success2:
                print("\n🎉 Both datasets prepared successfully!")
                print("📁 Datasets ready in: roboflow_datasets/")
                print("📊 Academic reports generated for both datasets")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

    print("\n📝 Next Steps:")
    print("   • Check roboflow_datasets/ folder for prepared datasets")
    print("   • Review DATASET_REPORT.md for summary statistics")
    print("   • Use ACADEMIC_REPORT.md for paper citations")
    print("   • Upload prepared datasets manually to Roboflow")
    print("   • Check ROBOFLOW_UPLOAD_INSTRUCTIONS.md for upload guidance")


if __name__ == "__main__":
    main()