#!/usr/bin/env python3
"""
Debug script to examine YOLO11n model class mappings and understand the labeling issue.
"""

import sys
import os
sys.path.append('/home/tiago/repos/camina/venv_viz/lib/python3.13/site-packages')

from ultralytics import YOLO
import yaml

def debug_model_classes():
    """Debug the YOLO11n model to understand class mappings."""

    model_path = "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt"

    print("="*80)
    print("DEBUGGING YOLO11n MODEL CLASS MAPPINGS")
    print("="*80)

    # Load the model
    try:
        model = YOLO(model_path)
        print(f"✓ Successfully loaded model from: {model_path}")
    except Exception as e:
        print(f"✗ Error loading model: {e}")
        return

    # Check model properties
    print(f"\nModel type: {type(model.model)}")
    print(f"Model device: {model.device}")

    # Get class names from model
    if hasattr(model, 'names'):
        model_classes = model.names
        print(f"\nModel has {len(model_classes)} classes:")
        for i, class_name in model_classes.items():
            print(f"  {i}: {class_name}")
    else:
        print("\n✗ Model doesn't have 'names' attribute")

    # Expected CAMINA classes
    expected_classes = ["Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery Van", "Truck"]
    print(f"\nExpected CAMINA classes ({len(expected_classes)}):")
    for i, class_name in enumerate(expected_classes):
        print(f"  {i}: {class_name}")

    # Compare classes
    print(f"\n" + "="*50)
    print("CLASS MAPPING COMPARISON")
    print("="*50)

    if hasattr(model, 'names'):
        print("Index | Model Class    | Expected Class | Match")
        print("-" * 50)
        for i in range(max(len(model_classes), len(expected_classes))):
            model_class = model_classes.get(i, "N/A") if i < len(model_classes) else "N/A"
            expected_class = expected_classes[i] if i < len(expected_classes) else "N/A"
            match = "✓" if model_class == expected_class else "✗"
            print(f"{i:5} | {model_class:14} | {expected_class:14} | {match}")

    # Check if there's a data.yaml file
    model_dir = os.path.dirname(model_path)
    data_yaml_path = os.path.join(model_dir, "../data.yaml")
    if os.path.exists(data_yaml_path):
        print(f"\nFound data.yaml at: {data_yaml_path}")
        with open(data_yaml_path, 'r') as f:
            data_config = yaml.safe_load(f)
            if 'names' in data_config:
                print("Class names from data.yaml:")
                for i, name in enumerate(data_config['names']):
                    print(f"  {i}: {name}")

    # Check training configuration
    train_dir = os.path.join(os.path.dirname(model_path), "..")
    for config_file in ["args.yaml", "data.yaml"]:
        config_path = os.path.join(train_dir, config_file)
        if os.path.exists(config_path):
            print(f"\nFound {config_file} at: {config_path}")
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if isinstance(config, dict) and 'names' in config:
                    print(f"Class names from {config_file}:")
                    names = config['names']
                    if isinstance(names, list):
                        for i, name in enumerate(names):
                            print(f"  {i}: {name}")
                    elif isinstance(names, dict):
                        for i, name in names.items():
                            print(f"  {i}: {name}")

    print("="*80)
    print("DEBUG COMPLETE")
    print("="*80)

if __name__ == "__main__":
    debug_model_classes()