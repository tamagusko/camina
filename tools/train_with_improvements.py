#!/usr/bin/env python3
"""
CAMINA YOLO Training with Class Balance Improvements
Test if code improvements and class weights help performance
"""

from ultralytics import YOLO
import numpy as np

def calculate_class_weights():
    """Calculate inverse frequency weights for class imbalance"""

    class_instances = {
        "Person": 6975, "Car": 2105, "Cyclist": 2012, "E-scooter": 728,
        "SUV": 456, "Motorcyclist": 307, "Bus": 321, "Delivery Van": 112, "Truck": 132
    }

    total_instances = sum(class_instances.values())
    num_classes = len(class_instances)

    # Calculate inverse frequency weights
    class_weights = {}
    for class_name, count in class_instances.items():
        weight = total_instances / (num_classes * count)
        class_weights[class_name] = weight

    print("📊 Calculated Class Weights:")
    for class_name, weight in class_weights.items():
        print(f"   {class_name}: {weight:.3f}")

    return list(class_weights.values())

def train_single_model_improved():
    """Test improved training on best performing model (YOLO11n)"""

    print("="*80)
    print("🎯 CAMINA Improved Training Test - YOLO11n")
    print("="*80)

    # Calculate class weights
    class_weights = calculate_class_weights()

    # Load model
    model = YOLO('yolo11n.pt')

    # Enhanced training configuration
    training_config = {
        'data': '/home/tiago/repos/camina/data/datasetV3_stratified/data.yaml',
        'epochs': 200,  # Extended training
        'patience': 20,  # Early stopping
        'batch': 16,
        'imgsz': 640,
        'save': True,
        'cache': True,
        'device': 0,  # GPU
        'workers': 8,
        'project': '/home/tiago/repos/camina/model/improved_training',
        'name': 'YOLO11n_improved',
        'exist_ok': True,

        # Class balance improvements
        'cls_pw': 2.0,  # Class weight power
        'box': 7.5,     # Box loss gain
        'cls': 0.5,     # Class loss gain

        # Enhanced augmentation
        'hsv_h': 0.015,   # Hue augmentation
        'hsv_s': 0.7,     # Saturation augmentation
        'hsv_v': 0.4,     # Value augmentation
        'degrees': 15.0,  # Rotation degrees
        'translate': 0.2, # Translation fraction
        'scale': 0.9,     # Scale fraction
        'shear': 2.0,     # Shear degrees
        'perspective': 0.0001,  # Perspective fraction
        'flipud': 0.2,    # Vertical flip probability
        'fliplr': 0.5,    # Horizontal flip probability
        'mosaic': 1.0,    # Mosaic probability
        'mixup': 0.15,    # Mixup probability
        'copy_paste': 0.3, # Copy-paste probability

        # Learning rate schedule
        'lr0': 0.001,     # Initial learning rate
        'lrf': 0.01,      # Final learning rate fraction
        'momentum': 0.937,
        'weight_decay': 0.0005,
        'warmup_epochs': 3,
        'warmup_momentum': 0.8,
        'warmup_bias_lr': 0.1,

        # Validation
        'val': True,
        'split': 'val',
        'save_period': 10
    }

    print(f"🚀 Starting improved training with:")
    print(f"   📈 Extended epochs: {training_config['epochs']}")
    print(f"   ⚖️  Class balance: Enhanced")
    print(f"   🔄 Augmentation: Enhanced")
    print(f"   📊 Early stopping: {training_config['patience']} epochs")

    # Train the model
    results = model.train(**training_config)

    print("="*80)
    print("✅ Improved Training Complete")
    print("="*80)

    # Get final metrics
    final_metrics = {
        'map50': float(results.results_dict['metrics/mAP50(B)']),
        'map50_95': float(results.results_dict['metrics/mAP50-95(B)']),
        'precision': float(results.results_dict['metrics/precision(B)']),
        'recall': float(results.results_dict['metrics/recall(B)'])
    }

    print(f"📊 Final Results:")
    print(f"   mAP@0.5: {final_metrics['map50']:.3f}")
    print(f"   mAP@0.5:0.95: {final_metrics['map50_95']:.3f}")
    print(f"   Precision: {final_metrics['precision']:.3f}")
    print(f"   Recall: {final_metrics['recall']:.3f}")

    # Compare with baseline
    baseline_map50 = 0.549  # From previous YOLO11n training
    improvement = final_metrics['map50'] - baseline_map50

    print(f"\n🎯 Performance Comparison:")
    print(f"   Baseline (150 epochs): {baseline_map50:.3f}")
    print(f"   Improved training: {final_metrics['map50']:.3f}")
    print(f"   Improvement: {improvement:+.3f}")

    if improvement > 0.010:
        print("✅ Significant improvement! Retraining with improvements is beneficial.")
    elif improvement > 0.005:
        print("📈 Modest improvement. Consider full retraining if time permits.")
    else:
        print("❌ Minimal improvement. Current models are near optimal.")

if __name__ == "__main__":
    train_single_model_improved()