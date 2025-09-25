#!/usr/bin/env python3
"""
Extract ONLY real metrics from YOLO models - no estimated values
Only extracts what's actually available from YOLO validation and training logs
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from ultralytics import YOLO
import yaml

def load_training_results(model_path):
    """Load final training results from results.csv"""
    results_file = model_path / "train" / "results.csv"

    if not results_file.exists():
        return None

    df = pd.read_csv(results_file)
    final_epoch = df.iloc[-1]  # Last epoch results

    return {
        'final_epoch': int(final_epoch['epoch']),
        'final_precision': float(final_epoch['metrics/precision(B)']),
        'final_recall': float(final_epoch['metrics/recall(B)']),
        'final_map50': float(final_epoch['metrics/mAP50(B)']),
        'final_map50_95': float(final_epoch['metrics/mAP50-95(B)']),
        'final_box_loss': float(final_epoch['train/box_loss']),
        'final_cls_loss': float(final_epoch['train/cls_loss']),
        'val_box_loss': float(final_epoch['val/box_loss']),
        'val_cls_loss': float(final_epoch['val/cls_loss'])
    }

def extract_real_validation_metrics(model_path):
    """Extract REAL per-class AP from YOLO validation"""
    best_model_path = model_path / "train" / "weights" / "best.pt"

    if not best_model_path.exists():
        print(f"❌ Model not found: {best_model_path}")
        return None

    # Load the model
    model = YOLO(str(best_model_path))

    # Run validation to get per-class metrics
    data_yaml = "/home/tiago/repos/camina/data/datasetV3_stratified/data.yaml"
    results = model.val(data=data_yaml, verbose=False)

    # Class name mapping
    class_name_mapping = {
        'person': 'Person', 'cyclist': 'Cyclist', 'car': 'Car', 'e-scooter': 'E-scooter',
        'suv': 'SUV', 'motorcyclist': 'Motorcyclist', 'bus': 'Bus',
        'delivery van': 'Delivery Van', 'truck': 'Truck'
    }

    # Get class names
    with open(data_yaml, 'r') as f:
        data_config = yaml.safe_load(f)
    class_names = data_config['names']

    validation_metrics = {
        'overall_metrics': {
            'map50': float(results.box.map50),
            'map50_95': float(results.box.map),
            'precision': float(results.box.mp),
            'recall': float(results.box.mr)
        },
        'class_wise_ap': {},
        'source': 'yolo_validation_real'
    }

    # Extract REAL per-class AP@0.5 values
    if hasattr(results.box, 'maps') and results.box.maps is not None:
        maps_values = results.box.maps  # Per-class AP@0.5

        for i, class_name in enumerate(class_names):
            if i < len(maps_values):
                mapped_name = class_name_mapping.get(class_name, class_name)
                ap_value = float(maps_values[i])
                validation_metrics['class_wise_ap'][mapped_name] = ap_value

    return validation_metrics

def generate_real_metrics_table():
    """Generate table with only REAL metrics"""

    models = {
        "YOLOv5n": Path("/home/tiago/repos/camina/models/yolo_comparison/YOLOv5n"),
        "YOLOv8n": Path("/home/tiago/repos/camina/models/yolo_comparison/YOLOv8n"),
        "YOLOv10n": Path("/home/tiago/repos/camina/models/yolo_comparison/YOLOv10n"),
        "YOLO11n": Path("/home/tiago/repos/camina/models/yolo_comparison/YOLO11n")
    }

    real_metrics = {}

    print("="*80)
    print("🎯 Extracting ONLY Real Metrics from YOLO Models")
    print("="*80)

    for model_name, model_path in models.items():
        print(f"\n📊 Processing {model_name}...")

        # Load training results
        training_results = load_training_results(model_path)
        if not training_results:
            print(f"❌ No training results for {model_name}")
            continue

        print(f"   ✅ Training results loaded (Final epoch: {training_results['final_epoch']})")

        # Extract validation metrics
        validation_metrics = extract_real_validation_metrics(model_path)
        if not validation_metrics:
            print(f"❌ Validation failed for {model_name}")
            continue

        print(f"   ✅ Validation metrics extracted")

        # Combine metrics
        real_metrics[model_name] = {
            'model_name': model_name,
            'training_results': training_results,
            'validation_metrics': validation_metrics
        }

        print(f"   📈 Overall mAP@0.5: {validation_metrics['overall_metrics']['map50']:.3f}")

    return real_metrics

def create_academic_table(real_metrics):
    """Create academic table with only real metrics"""

    class_instances = {
        "Person": 6975, "Car": 2105, "Cyclist": 2012, "E-scooter": 728,
        "SUV": 456, "Motorcyclist": 307, "Bus": 321, "Delivery Van": 112, "Truck": 132
    }

    class_order = ["Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery Van", "Truck"]
    model_order = ["YOLO11n", "YOLOv10n", "YOLOv5n", "YOLOv8n"]

    table = "# Table 2: Real Per-Class Performance (YOLO Validation Only)\n\n"
    table += "| Class | Instances | YOLO11n AP@0.5 | YOLOv10n AP@0.5 | YOLOv5n AP@0.5 | YOLOv8n AP@0.5 |\n"
    table += "|-------|-----------|----------------|------------------|----------------|----------------|\n"

    for class_name in class_order:
        instances = class_instances.get(class_name, 0)
        table += f"| **{class_name}** | {instances:,} "

        for model_name in model_order:
            if model_name in real_metrics:
                ap = real_metrics[model_name]['validation_metrics']['class_wise_ap'].get(class_name, 0.0)
                table += f"| {ap:.3f} "
            else:
                table += "| - "

        table += "|\n"

    # Overall performance
    table += "\n## Overall Performance\n\n"
    table += "| Model | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall | Final Epoch |\n"
    table += "|-------|---------|--------------|-----------|--------|-------------|\n"

    for model_name in model_order:
        if model_name in real_metrics:
            val_metrics = real_metrics[model_name]['validation_metrics']['overall_metrics']
            train_results = real_metrics[model_name]['training_results']

            table += f"| **{model_name}** "
            table += f"| {val_metrics['map50']:.3f} "
            table += f"| {val_metrics['map50_95']:.3f} "
            table += f"| {val_metrics['precision']:.3f} "
            table += f"| {val_metrics['recall']:.3f} "
            table += f"| {train_results['final_epoch']} |\n"

    table += "\n*All metrics extracted directly from YOLO validation - no estimated values*\n"

    return table

def main():
    print("="*80)
    print("🎯 CAMINA Real Metrics Extraction (No Estimates)")
    print("="*80)

    # Extract real metrics
    real_metrics = generate_real_metrics_table()

    # Create output directory
    output_dir = Path("/home/tiago/repos/camina/outputs/model_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save raw metrics
    results_dir = output_dir / "results"
    results_dir.mkdir(exist_ok=True)

    with open(results_dir / "real_metrics_only.json", 'w') as f:
        json.dump(real_metrics, f, indent=2)

    print(f"\n✅ Raw metrics saved to: {results_dir / 'real_metrics_only.json'}")

    # Create academic table
    table_content = create_academic_table(real_metrics)

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    with open(tables_dir / "table2_real_validation_only.md", 'w') as f:
        f.write(table_content)

    print(f"✅ Academic table saved to: {tables_dir / 'table2_real_validation_only.md'}")

    print("="*80)
    print("📊 Real Metrics Extraction Complete")
    print("="*80)
    print("\n🎯 Key Findings:")

    if real_metrics:
        best_model = max(real_metrics.keys(),
                        key=lambda x: real_metrics[x]['validation_metrics']['overall_metrics']['map50'])
        best_map = real_metrics[best_model]['validation_metrics']['overall_metrics']['map50']
        print(f"   🏆 Best Model: {best_model} (mAP@0.5: {best_map:.3f})")

        print(f"   📈 Performance Range: {min(real_metrics[m]['validation_metrics']['overall_metrics']['map50'] for m in real_metrics):.3f} - {max(real_metrics[m]['validation_metrics']['overall_metrics']['map50'] for m in real_metrics):.3f}")

        # Best performing class
        all_class_aps = {}
        for model_name in real_metrics:
            for class_name, ap in real_metrics[model_name]['validation_metrics']['class_wise_ap'].items():
                if class_name not in all_class_aps:
                    all_class_aps[class_name] = []
                all_class_aps[class_name].append(ap)

        if all_class_aps:
            avg_class_performance = {cls: np.mean(aps) for cls, aps in all_class_aps.items()}
            best_class = max(avg_class_performance.keys(), key=avg_class_performance.get)
            worst_class = min(avg_class_performance.keys(), key=avg_class_performance.get)

            print(f"   🎯 Best Detected Class: {best_class} (avg AP: {avg_class_performance[best_class]:.3f})")
            print(f"   ⚠️  Most Challenging: {worst_class} (avg AP: {avg_class_performance[worst_class]:.3f})")

if __name__ == "__main__":
    main()