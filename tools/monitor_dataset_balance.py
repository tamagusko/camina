#!/usr/bin/env python3
"""
Dataset Balance Monitor for CAMINA
Monitors instance counts and warns when classes need more data
Pure functional implementation
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tools.mlflow_tracker import (
        count_instances_from_label_files,
        initialize_mlflow_experiment,
        start_dataset_creation_run,
        log_instance_counts_to_mlflow,
        log_training_parameters,
        end_mlflow_run,
        print_mlflow_ui_instructions
    )
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    print("Warning: MLflow not available. Install with: pip install mlflow")


# === CAMINA CLASS NAMES ===

CAMINA_CLASS_NAMES = [
    "person", "cyclist", "car", "e-scooter", "SUV",
    "motorcyclist", "bus", "delivery_van", "truck"
]


# === INSTANCE COUNTING ===

def count_dataset_instances(dataset_path: Path, class_names: List[str]) -> Dict[str, Dict[str, int]]:
    """
    Count instances in train and validation sets.

    Args:
        dataset_path: Path to dataset directory
        class_names: List of class names

    Returns:
        Dictionary with 'train', 'val', and 'total' counts per class
    """
    train_labels_path = dataset_path / "train" / "labels"
    validation_labels_path = dataset_path / "val" / "labels"

    train_counts = count_instances_from_label_files(train_labels_path, class_names)
    validation_counts = count_instances_from_label_files(validation_labels_path, class_names)

    total_counts = {
        class_name: train_counts[class_name] + validation_counts[class_name]
        for class_name in class_names
    }

    return {
        'train': train_counts,
        'val': validation_counts,
        'total': total_counts
    }


def count_dataset_images(dataset_path: Path) -> Dict[str, int]:
    """
    Count image files in dataset.

    Args:
        dataset_path: Path to dataset directory

    Returns:
        Dictionary with train, val, and total image counts
    """
    train_images_path = dataset_path / "train" / "images"
    validation_images_path = dataset_path / "val" / "images"

    train_image_count = len(list(train_images_path.glob("*.[jp][pn]g")))
    validation_image_count = len(list(validation_images_path.glob("*.[jp][pn]g")))

    return {
        'train': train_image_count,
        'val': validation_image_count,
        'total': train_image_count + validation_image_count
    }


# === STATISTICS CALCULATION ===

def calculate_instance_statistics(instance_counts_per_class: Dict[str, int]) -> Dict[str, float]:
    """
    Calculate statistical metrics for instance counts.

    Args:
        instance_counts_per_class: Dictionary mapping class name to count

    Returns:
        Dictionary with num_classes, max, min, avg, and imbalance_ratio
    """
    if not instance_counts_per_class:
        return {
            'num_classes': 0,
            'max_instances': 0,
            'min_instances': 0,
            'avg_instances': 0,
            'imbalance_ratio': float('inf')
        }

    instance_values = list(instance_counts_per_class.values())
    total_instances = sum(instance_values)
    maximum_instances = max(instance_values)
    minimum_instances = min(instance_values)
    average_instances = total_instances / len(instance_counts_per_class)
    imbalance_ratio = maximum_instances / minimum_instances if minimum_instances > 0 else float('inf')

    return {
        'num_classes': len(instance_counts_per_class),
        'max_instances': maximum_instances,
        'min_instances': minimum_instances,
        'avg_instances': average_instances,
        'imbalance_ratio': imbalance_ratio
    }


# === THRESHOLD CATEGORIZATION ===

def categorize_classes_by_thresholds(
    instance_counts_per_class: Dict[str, int],
    minimum_threshold: int,
    target_threshold: int
) -> Dict[str, List[Tuple]]:
    """
    Categorize classes based on instance count thresholds.

    Args:
        instance_counts_per_class: Dictionary mapping class name to count
        minimum_threshold: Minimum acceptable instances per class
        target_threshold: Target instances per class

    Returns:
        Dictionary with 'below_minimum', 'below_target', 'above_target' lists
    """
    classes_below_minimum = []
    classes_below_target = []
    classes_above_target = []

    for class_name, instance_count in instance_counts_per_class.items():
        if instance_count < minimum_threshold:
            instances_needed = minimum_threshold - instance_count
            classes_below_minimum.append((class_name, instance_count, instances_needed))
        elif instance_count < target_threshold:
            instances_needed = target_threshold - instance_count
            classes_below_target.append((class_name, instance_count, instances_needed))
        else:
            classes_above_target.append((class_name, instance_count))

    return {
        'below_minimum': sorted(classes_below_minimum, key=lambda x: x[1]),
        'below_target': sorted(classes_below_target, key=lambda x: x[1]),
        'above_target': classes_above_target
    }


# === PROGRESS CALCULATION ===

def calculate_collection_progress(
    instance_counts_per_class: Dict[str, int],
    target_threshold: int
) -> Dict[str, Dict]:
    """
    Calculate collection progress for each class toward target.

    Args:
        instance_counts_per_class: Dictionary mapping class name to count
        target_threshold: Target instances per class

    Returns:
        Dictionary with progress information per class
    """
    collection_progress = {}

    for class_name, instance_count in instance_counts_per_class.items():
        progress_percentage = (instance_count / target_threshold) * 100
        instances_needed = max(0, target_threshold - instance_count)

        collection_progress[class_name] = {
            "current": instance_count,
            "target": target_threshold,
            "needed": instances_needed,
            "progress_percentage": min(100, progress_percentage)
        }

    return collection_progress


# === ANALYSIS ===

def analyze_dataset_balance(
    dataset_path: str,
    class_names: List[str],
    minimum_threshold: int = 300,
    target_threshold: int = 500
) -> Dict:
    """
    Analyze dataset balance and return comprehensive statistics.

    Args:
        dataset_path: Path to dataset directory
        class_names: List of class names in order
        minimum_threshold: Minimum acceptable instances per class
        target_threshold: Target instances per class

    Returns:
        Dictionary containing all statistics and warnings
    """
    dataset_path_obj = Path(dataset_path)

    # Count instances and images
    instance_counts = count_dataset_instances(dataset_path_obj, class_names)
    image_counts = count_dataset_images(dataset_path_obj)

    # Calculate statistics
    statistics = calculate_instance_statistics(instance_counts['total'])

    # Categorize classes by threshold
    class_categorization = categorize_classes_by_thresholds(
        instance_counts['total'],
        minimum_threshold,
        target_threshold
    )

    # Calculate collection progress
    collection_progress = calculate_collection_progress(
        instance_counts['total'],
        target_threshold
    )

    # Build comprehensive analysis result
    analysis_result = {
        "dataset_path": str(dataset_path_obj),
        "timestamp": datetime.now().isoformat(),
        "images": image_counts,
        "instances": {
            "train": sum(instance_counts['train'].values()),
            "val": sum(instance_counts['val'].values()),
            "total": sum(instance_counts['total'].values())
        },
        "per_class_counts": instance_counts['total'],
        "statistics": statistics,
        "thresholds": {
            "minimum": minimum_threshold,
            "target": target_threshold
        },
        "status": {
            "classes_below_minimum": len(class_categorization['below_minimum']),
            "classes_below_target": len(class_categorization['below_target']),
            "classes_meeting_target": len(class_categorization['above_target'])
        },
        "classes_needing_data": class_categorization,
        "collection_progress": collection_progress
    }

    return analysis_result


# === REPORTING ===

def print_dataset_balance_report(analysis_result: Dict, class_names: List[str], minimum_threshold: int):
    """
    Print a formatted report of dataset balance.

    Args:
        analysis_result: Analysis dictionary from analyze_dataset_balance
        class_names: List of class names in order
        minimum_threshold: Minimum threshold for highlighting
    """
    print("=" * 70)
    print(f"CAMINA DATASET BALANCE REPORT")
    print("=" * 70)
    print(f"Dataset: {analysis_result['dataset_path']}")
    print(f"Generated: {analysis_result['timestamp']}")
    print()

    # Images summary
    images = analysis_result['images']
    print(f"Images:")
    print(f"  Train: {images['train']}")
    print(f"  Val:   {images['val']}")
    print(f"  Total: {images['total']}")
    print()

    # Instances summary
    instances = analysis_result['instances']
    print(f"Total Instances: {instances['total']}")
    print(f"  Train: {instances['train']}")
    print(f"  Val:   {instances['val']}")
    print()

    # Statistics
    stats = analysis_result['statistics']
    print(f"Dataset Statistics:")
    print(f"  Classes: {stats['num_classes']}")
    print(f"  Max instances: {stats['max_instances']}")
    print(f"  Min instances: {stats['min_instances']}")
    print(f"  Avg instances: {stats['avg_instances']:.1f}")
    print(f"  Imbalance ratio: {stats['imbalance_ratio']:.2f}x")
    print()

    # Thresholds
    thresholds = analysis_result['thresholds']
    status = analysis_result['status']
    print(f"Instance Count Goals:")
    print(f"  Minimum threshold: {thresholds['minimum']} instances/class")
    print(f"  Target threshold:  {thresholds['target']} instances/class")
    print()
    print(f"  Meeting target: {status['classes_meeting_target']} classes")
    print(f"  Below target:   {status['classes_below_target']} classes")
    print(f"  Below minimum:  {status['classes_below_minimum']} classes")
    print()

    # Per-class breakdown with progress bars
    print(f"Per-Class Instance Counts:")
    print("-" * 70)

    progress_data = analysis_result['collection_progress']
    for class_name in class_names:
        class_progress = progress_data[class_name]
        current_count = class_progress['current']
        target_count = class_progress['target']
        instances_needed = class_progress['needed']
        progress_percentage = class_progress['progress_percentage']

        # Status indicator
        if current_count >= target_count:
            status_icon = "[OK]"
        elif current_count >= minimum_threshold:
            status_icon = "[!]"
        else:
            status_icon = "[X]"

        # Progress bar
        bar_length = 30
        filled_length = int(bar_length * progress_percentage / 100)
        progress_bar = "#" * filled_length + "-" * (bar_length - filled_length)

        print(f"  {status_icon} {class_name:15s} [{progress_bar}] {current_count:4d}/{target_count} ({progress_percentage:5.1f}%)")

        if instances_needed > 0:
            print(f"      Need {instances_needed} more instances to reach target")

    print()

    # Warnings for classes needing data
    classes_needing_data = analysis_result['classes_needing_data']

    if classes_needing_data['below_minimum']:
        print(f"CRITICAL: Classes below minimum threshold ({thresholds['minimum']})")
        print("-" * 70)
        for class_name, count, needed in classes_needing_data['below_minimum']:
            print(f"  {class_name}: {count} instances (need {needed} more)")
            print(f"    Priority: HIGH - Add {needed}+ images with '{class_name}'")
        print()

    if classes_needing_data['below_target']:
        print(f"Classes below target threshold ({thresholds['target']})")
        print("-" * 70)
        for class_name, count, needed in classes_needing_data['below_target']:
            print(f"  {class_name}: {count} instances (need {needed} more for target)")
        print()

    # Collection recommendations
    if classes_needing_data['below_minimum'] or classes_needing_data['below_target']:
        print("Recommendations:")
        print("-" * 70)

        # Prioritize classes below minimum
        if classes_needing_data['below_minimum']:
            print("  1. HIGH PRIORITY: Focus on collecting images for:")
            for class_name, count, needed in classes_needing_data['below_minimum'][:3]:
                print(f"     - {class_name} ({needed}+ more needed)")

        # Then classes below target
        if classes_needing_data['below_target']:
            print("  2. MEDIUM PRIORITY: Increase instances for:")
            sorted_below_target = sorted(classes_needing_data['below_target'], key=lambda x: x[2], reverse=True)
            for class_name, count, needed in sorted_below_target[:3]:
                print(f"     - {class_name} ({needed} more for target)")

        print()
        print("  Tip: Use YOLO-World or manual annotation to add these classes")
        print()

    else:
        print("EXCELLENT: All classes meet target threshold!")
        print()

    print("=" * 70)


def save_analysis_report(analysis_result: Dict, output_path: str):
    """
    Save analysis report to JSON file.

    Args:
        analysis_result: Analysis dictionary from analyze_dataset_balance
        output_path: Path to save JSON report
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as file:
        json.dump(analysis_result, file, indent=2)

    print(f"Report saved to: {output_file}")


# === MLFLOW INTEGRATION ===

def track_dataset_balance_with_mlflow(
    analysis_result: Dict,
    minimum_threshold: int,
    target_threshold: int,
    experiment_name: str = "CAMINA_Urban_Mobility"
):
    """
    Track dataset balance in MLflow.

    Args:
        analysis_result: Analysis dictionary from analyze_dataset_balance
        minimum_threshold: Minimum acceptable instances per class
        target_threshold: Target instances per class
        experiment_name: MLflow experiment name
    """
    if not MLFLOW_AVAILABLE:
        print("Warning: MLflow not available. Skipping MLflow tracking.")
        return

    initialize_mlflow_experiment(experiment_name)

    dataset_name = Path(analysis_result['dataset_path']).name

    mlflow_run = start_dataset_creation_run(dataset_name, analysis_result['dataset_path'])

    try:
        # Log instance counts with thresholds
        log_instance_counts_to_mlflow(
            analysis_result['per_class_counts'],
            minimum_threshold,
            target_threshold
        )

        # Log image counts
        log_training_parameters({
            "train_images": analysis_result['images']['train'],
            "val_images": analysis_result['images']['val'],
            "total_images": analysis_result['images']['total']
        })

    finally:
        end_mlflow_run()

    print("\nDataset balance tracked in MLflow")
    print_mlflow_ui_instructions()


# === MAIN EXECUTION ===

def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor CAMINA dataset balance and instance counts")
    parser.add_argument("--dataset", type=str, required=True,
                       help="Path to dataset directory")
    parser.add_argument("--min-threshold", type=int, default=300,
                       help="Minimum instances per class (default: 300)")
    parser.add_argument("--target-threshold", type=int, default=500,
                       help="Target instances per class (default: 500)")
    parser.add_argument("--output", type=str, default="dataset_balance_report.json",
                       help="Output JSON report path")
    parser.add_argument("--mlflow", action="store_true",
                       help="Track with MLflow")
    parser.add_argument("--experiment-name", type=str, default="CAMINA_Urban_Mobility",
                       help="MLflow experiment name")

    args = parser.parse_args()

    # Analyze dataset
    print("Analyzing dataset...")
    analysis_result = analyze_dataset_balance(
        dataset_path=args.dataset,
        class_names=CAMINA_CLASS_NAMES,
        minimum_threshold=args.min_threshold,
        target_threshold=args.target_threshold
    )

    # Print report
    print_dataset_balance_report(analysis_result, CAMINA_CLASS_NAMES, args.min_threshold)

    # Save report
    save_analysis_report(analysis_result, args.output)

    # Track with MLflow if requested
    if args.mlflow:
        track_dataset_balance_with_mlflow(
            analysis_result,
            args.min_threshold,
            args.target_threshold,
            args.experiment_name
        )


if __name__ == "__main__":
    main()
