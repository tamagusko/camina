#!/usr/bin/env python3
"""
Prepare E-Scooter Dataset for Roboflow Upload
Direct preparation script for outputs/escooter/ data
"""

import os
import shutil
from pathlib import Path
import csv
import time

# CAMINA class names
CLASS_NAMES = {
    0: "person",
    1: "cyclist",
    2: "car",
    3: "motorcycle",
    4: "bus",
    5: "truck",
    6: "e-scooter",
    7: "SUV",
    8: "delivery_van"
}

def prepare_escooter_dataset():
    """Prepare e-scooter dataset for Roboflow upload."""
    start_time = time.time()

    print("🛴 Preparing E-Scooter Dataset for Roboflow")
    print("=" * 50)

    # Input paths
    images_dir = Path("outputs/escooter/dataset_viz/images")
    labels_dir = Path("outputs/escooter/yolo")
    output_dir = Path("roboflow_datasets/camina-escooter-dataset")

    # Validate input paths
    if not images_dir.exists():
        print(f"❌ Images directory not found: {images_dir}")
        return

    if not labels_dir.exists():
        print(f"❌ Labels directory not found: {labels_dir}")
        return

    print(f"📂 Images: {images_dir}")
    print(f"🏷️  Labels: {labels_dir}")
    print(f"📁 Output: {output_dir}")
    print()

    # Create output structure
    train_img_dir = output_dir / 'images' / 'train'
    val_img_dir = output_dir / 'images' / 'val'
    train_lbl_dir = output_dir / 'labels' / 'train'
    val_lbl_dir = output_dir / 'labels' / 'val'

    for dir_path in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Get all images and corresponding labels
    image_files = list(images_dir.glob('*.jpg'))
    print(f"📸 Found {len(image_files)} images")

    # Filter to only include images that have corresponding labels
    valid_pairs = []
    for img_file in image_files:
        label_file = labels_dir / f"{img_file.stem}.txt"
        if label_file.exists():
            valid_pairs.append((img_file, label_file))

    print(f"✅ Found {len(valid_pairs)} image-label pairs")

    if len(valid_pairs) == 0:
        print("❌ No valid image-label pairs found!")
        return

    # Split 80/20 train/validation
    split_idx = int(len(valid_pairs) * 0.8)
    train_pairs = valid_pairs[:split_idx]
    val_pairs = valid_pairs[split_idx:]

    print(f"📊 Split: {len(train_pairs)} train, {len(val_pairs)} validation")

    # Copy train files
    print("📁 Copying training files...")
    for img_file, lbl_file in train_pairs:
        shutil.copy2(img_file, train_img_dir / img_file.name)
        shutil.copy2(lbl_file, train_lbl_dir / lbl_file.name)

    # Copy validation files
    print("📁 Copying validation files...")
    for img_file, lbl_file in val_pairs:
        shutil.copy2(img_file, val_img_dir / img_file.name)
        shutil.copy2(lbl_file, val_lbl_dir / lbl_file.name)

    # Create data.yaml
    yaml_path = output_dir / 'data.yaml'
    with open(yaml_path, 'w') as f:
        f.write(f"path: {output_dir}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"\nnc: {len(CLASS_NAMES)}\n")
        f.write("names:\n")
        for name in CLASS_NAMES.values():
            f.write(f"  - {name}\n")

    print(f"📄 Created data.yaml: {yaml_path}")

    # Generate statistics report
    generate_report(output_dir, train_pairs, val_pairs)

    elapsed_time = time.time() - start_time
    print(f"\n🎉 E-Scooter dataset prepared successfully!")
    print(f"📁 Output: {output_dir}")
    print(f"⏱️  Time: {elapsed_time:.1f} seconds")
    print(f"📊 Ready for Roboflow upload!")

def generate_report(output_dir: Path, train_pairs, val_pairs):
    """Generate dataset statistics report."""
    print("\n📊 Generating dataset report...")

    # Count detections per class
    class_counts = {class_id: 0 for class_id in CLASS_NAMES.keys()}
    total_instances = 0

    all_pairs = train_pairs + val_pairs
    for _, label_file in all_pairs:
        if label_file.exists() and label_file.stat().st_size > 0:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        if class_id in class_counts:
                            class_counts[class_id] += 1
                            total_instances += 1

    # Create markdown report
    report_file = output_dir / "ESCOOTER_DATASET_REPORT.md"
    with open(report_file, 'w') as f:
        f.write("# CAMINA E-Scooter Dataset Report\n\n")
        f.write("## Dataset Overview\n")
        f.write(f"- **Total Images**: {len(all_pairs):,}\n")
        f.write(f"- **Total Instances**: {total_instances:,}\n")
        f.write(f"- **Classes**: {len(CLASS_NAMES)}\n")
        f.write(f"- **Train Split**: {len(train_pairs)} images\n")
        f.write(f"- **Validation Split**: {len(val_pairs)} images\n\n")

        f.write("## Class Distribution\n\n")
        f.write("| Class ID | Class Name | Count | Percentage |\n")
        f.write("|----------|------------|-------|------------|\n")

        for class_id, count in class_counts.items():
            percentage = (count / total_instances) * 100 if total_instances > 0 else 0
            class_name = CLASS_NAMES[class_id]
            f.write(f"| {class_id} | {class_name} | {count:,} | {percentage:.1f}% |\n")

        f.write(f"\n## Dataset Features\n")
        f.write("- ✅ E-scooter spatial association (person + e-scooter → combined bbox)\n")
        f.write("- ✅ Cyclist logic (person + bicycle → cyclist)\n")
        f.write("- ✅ NMS with class priorities\n")
        f.write("- ✅ Multi-stage detection (YOLO11l + YOLO-World)\n")
        f.write("- ✅ 600 diverse e-scooter rider images\n")
        f.write("- ✅ YOLOv11 format ready for Roboflow\n")

    # Create CSV report
    csv_file = output_dir / "class_distribution.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['class_id', 'class_name', 'count', 'percentage'])
        for class_id, count in class_counts.items():
            percentage = (count / total_instances) * 100 if total_instances > 0 else 0
            class_name = CLASS_NAMES[class_id]
            writer.writerow([class_id, class_name, count, f"{percentage:.2f}"])

    print(f"📋 Generated report: {report_file}")
    print(f"📊 Generated CSV: {csv_file}")

    # Print summary
    print(f"\n📈 Dataset Summary:")
    print(f"   • Total images: {len(all_pairs)}")
    print(f"   • Total detections: {total_instances}")
    print(f"   • Most detected class: {CLASS_NAMES[max(class_counts, key=class_counts.get)]} ({max(class_counts.values())} instances)")

if __name__ == "__main__":
    prepare_escooter_dataset()