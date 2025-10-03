#!/usr/bin/env python3
"""
MLflow Integration for CAMINA Pipeline
Pure functional implementation focusing on instance count tracking and model performance
"""

import mlflow
import mlflow.pytorch
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


# === EXPERIMENT INITIALIZATION ===

def initialize_mlflow_experiment(experiment_name: str, tracking_directory: str = "mlruns") -> str:
    """
    Initialize MLflow experiment and return tracking URI.

    Args:
        experiment_name: Name of the experiment
        tracking_directory: Directory to store MLflow data

    Returns:
        Absolute path to tracking URI
    """
    tracking_uri_absolute = str(Path(tracking_directory).absolute())
    mlflow.set_tracking_uri(f"file://{tracking_uri_absolute}")
    mlflow.set_experiment(experiment_name)

    print(f"MLflow initialized: {experiment_name}")
    print(f"Tracking URI: {tracking_uri_absolute}")

    return tracking_uri_absolute


# === RUN MANAGEMENT ===

def start_dataset_creation_run(dataset_name: str, dataset_path: str) -> mlflow.ActiveRun:
    """
    Start MLflow run for dataset creation/update.

    Args:
        dataset_name: Name of the dataset
        dataset_path: Path to dataset directory

    Returns:
        Active MLflow run context
    """
    timestamp_formatted = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_name = f"dataset_{dataset_name}_{timestamp_formatted}"

    mlflow_run = mlflow.start_run(run_name=run_name)

    mlflow.set_tag("pipeline_stage", "dataset_creation")
    mlflow.set_tag("dataset_name", dataset_name)
    mlflow.log_param("dataset_path", dataset_path)
    mlflow.log_param("timestamp", datetime.now().isoformat())

    return mlflow_run


def start_model_training_run(model_name: str, dataset_name: str) -> mlflow.ActiveRun:
    """
    Start MLflow run for model training.

    Args:
        model_name: Name of the model (e.g., 'YOLOv8n')
        dataset_name: Name of the dataset used

    Returns:
        Active MLflow run context
    """
    timestamp_formatted = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_name = f"train_{model_name}_{timestamp_formatted}"

    mlflow_run = mlflow.start_run(run_name=run_name)

    mlflow.set_tag("pipeline_stage", "training")
    mlflow.set_tag("model_name", model_name)
    mlflow.set_tag("dataset_name", dataset_name)
    mlflow.log_param("timestamp", datetime.now().isoformat())

    return mlflow_run


def end_mlflow_run():
    """End the current MLflow run."""
    mlflow.end_run()
    print("MLflow run completed")


# === INSTANCE COUNTING ===

def count_instances_from_label_files(labels_directory: Path, class_names: List[str]) -> Dict[str, int]:
    """
    Count instances per class from YOLO label files.

    Args:
        labels_directory: Directory containing .txt label files
        class_names: Ordered list of class names

    Returns:
        Dictionary mapping class name to instance count
    """
    instance_counts_per_class = {class_name: 0 for class_name in class_names}

    labels_path = Path(labels_directory)
    if not labels_path.exists():
        print(f"Warning: Labels directory not found: {labels_path}")
        return instance_counts_per_class

    for label_file_path in labels_path.glob("*.txt"):
        try:
            with open(label_file_path, 'r') as label_file:
                for line in label_file:
                    line_parts = line.strip().split()
                    if line_parts:
                        class_index = int(line_parts[0])
                        if 0 <= class_index < len(class_names):
                            instance_counts_per_class[class_names[class_index]] += 1
        except Exception as error:
            print(f"Warning: Error reading {label_file_path}: {error}")

    return instance_counts_per_class


# === THRESHOLD CHECKING ===

def categorize_classes_by_threshold(
    instance_counts_per_class: Dict[str, int],
    minimum_threshold: int,
    target_threshold: int
) -> Dict[str, List[tuple]]:
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


# === STATISTICS CALCULATION ===

def calculate_dataset_statistics(instance_counts_per_class: Dict[str, int]) -> Dict[str, float]:
    """
    Calculate overall dataset statistics.

    Args:
        instance_counts_per_class: Dictionary mapping class name to count

    Returns:
        Dictionary with total, max, min, and imbalance_ratio
    """
    if not instance_counts_per_class:
        return {
            'total': 0,
            'max': 0,
            'min': 0,
            'imbalance_ratio': float('inf')
        }

    instance_values = list(instance_counts_per_class.values())
    total_instances = sum(instance_values)
    maximum_instances = max(instance_values)
    minimum_instances = min(instance_values)
    imbalance_ratio = maximum_instances / minimum_instances if minimum_instances > 0 else float('inf')

    return {
        'total': total_instances,
        'max': maximum_instances,
        'min': minimum_instances,
        'imbalance_ratio': imbalance_ratio
    }


# === MLFLOW LOGGING ===

def log_instance_counts_to_mlflow(
    instance_counts_per_class: Dict[str, int],
    minimum_threshold: int,
    target_threshold: int
) -> Dict[str, List[tuple]]:
    """
    Log instance counts and threshold checks to MLflow.

    Args:
        instance_counts_per_class: Dictionary mapping class name to count
        minimum_threshold: Minimum acceptable instances per class
        target_threshold: Target instances per class

    Returns:
        Dictionary with class categorization by threshold
    """
    dataset_stats = calculate_dataset_statistics(instance_counts_per_class)
    class_categories = categorize_classes_by_threshold(
        instance_counts_per_class,
        minimum_threshold,
        target_threshold
    )

    # Log overall metrics
    mlflow.log_metric("total_instances", dataset_stats['total'])
    mlflow.log_metric("num_classes", len(instance_counts_per_class))
    mlflow.log_metric("max_instances", dataset_stats['max'])
    mlflow.log_metric("min_instances", dataset_stats['min'])
    mlflow.log_metric("imbalance_ratio", dataset_stats['imbalance_ratio'])
    mlflow.log_param("minimum_threshold", minimum_threshold)
    mlflow.log_param("target_threshold", target_threshold)

    # Log per-class counts and percentages
    total_instances = dataset_stats['total']
    for class_name, instance_count in instance_counts_per_class.items():
        sanitized_class_name = class_name.replace(" ", "_").replace("-", "_")
        mlflow.log_metric(f"instances_{sanitized_class_name}", instance_count)

        percentage = (instance_count / total_instances * 100) if total_instances > 0 else 0
        mlflow.log_metric(f"percentage_{sanitized_class_name}", percentage)

        # Set status tag
        if instance_count < minimum_threshold:
            mlflow.set_tag(f"status_{sanitized_class_name}", "BELOW_MINIMUM")
        elif instance_count < target_threshold:
            mlflow.set_tag(f"status_{sanitized_class_name}", "BELOW_TARGET")
        else:
            mlflow.set_tag(f"status_{sanitized_class_name}", "MEETS_TARGET")

    # Log category counts
    mlflow.log_metric("classes_below_minimum", len(class_categories['below_minimum']))
    mlflow.log_metric("classes_below_target", len(class_categories['below_target']))
    mlflow.log_metric("classes_meeting_target", len(class_categories['above_target']))

    # Print summary
    print(f"\nInstance Count Summary:")
    print(f"  Total instances: {dataset_stats['total']}")
    print(f"  Classes: {len(instance_counts_per_class)}")
    print(f"  Imbalance ratio: {dataset_stats['imbalance_ratio']:.2f}x")

    if class_categories['below_minimum']:
        print(f"\nWarning: {len(class_categories['below_minimum'])} classes below minimum ({minimum_threshold})")
        for class_name, count, needed in class_categories['below_minimum']:
            print(f"  - {class_name}: {count} (need {needed} more)")

    if class_categories['below_target']:
        print(f"\nNote: {len(class_categories['below_target'])} classes below target ({target_threshold})")
        for class_name, count, needed in class_categories['below_target']:
            print(f"  - {class_name}: {count} (need {needed} more for target)")

    if not class_categories['below_minimum'] and not class_categories['below_target']:
        print(f"\nAll classes meet target threshold ({target_threshold}+ instances)")

    return class_categories


def log_training_parameters(parameters: Dict):
    """
    Log training hyperparameters to MLflow.

    Args:
        parameters: Dictionary of parameter names to values
    """
    for parameter_name, parameter_value in parameters.items():
        mlflow.log_param(parameter_name, parameter_value)


def log_training_metrics(metrics: Dict[str, float], epoch_number: Optional[int] = None):
    """
    Log training metrics to MLflow with optional epoch tracking.

    Args:
        metrics: Dictionary of metric names to values
        epoch_number: Optional epoch number for time-series tracking
    """
    for metric_name, metric_value in metrics.items():
        if epoch_number is not None:
            mlflow.log_metric(metric_name, metric_value, step=epoch_number)
        else:
            mlflow.log_metric(metric_name, metric_value)


def log_per_class_performance(class_metrics: Dict[str, Dict[str, float]]):
    """
    Log per-class performance metrics to MLflow.

    Args:
        class_metrics: Dictionary mapping class name to metrics dictionary
                      Example: {"person": {"ap50": 0.65, "precision": 0.70}, ...}
    """
    for class_name, metrics_dict in class_metrics.items():
        sanitized_class_name = class_name.replace(" ", "_").replace("-", "_")

        for metric_name, metric_value in metrics_dict.items():
            mlflow_metric_name = f"{metric_name}_{sanitized_class_name}"
            mlflow.log_metric(mlflow_metric_name, metric_value)


def log_model_artifacts(model_weights_path: str, additional_artifact_paths: Optional[List[str]] = None):
    """
    Log model weights and additional artifacts to MLflow.

    Args:
        model_weights_path: Path to model weights file
        additional_artifact_paths: List of additional file/directory paths to log
    """
    model_path = Path(model_weights_path)

    if model_path.exists():
        mlflow.log_artifact(str(model_path))

        model_size_megabytes = model_path.stat().st_size / (1024 * 1024)
        mlflow.log_metric("model_size_mb", model_size_megabytes)

    if additional_artifact_paths:
        for artifact_path_str in additional_artifact_paths:
            artifact_path = Path(artifact_path_str)
            if artifact_path.exists():
                if artifact_path.is_dir():
                    mlflow.log_artifacts(str(artifact_path))
                else:
                    mlflow.log_artifact(str(artifact_path))


def log_edge_deployment_performance(device_name: str, performance_metrics: Dict[str, float]):
    """
    Log edge deployment performance metrics to MLflow.

    Args:
        device_name: Name of edge device (e.g., 'Raspberry_Pi_5')
        performance_metrics: Performance metrics (inference_time_ms, fps, etc.)
    """
    mlflow.set_tag("deployment_device", device_name)

    for metric_name, metric_value in performance_metrics.items():
        mlflow_metric_name = f"{device_name}_{metric_name}"
        mlflow.log_metric(mlflow_metric_name, metric_value)


# === UTILITY FUNCTIONS ===

def print_mlflow_ui_instructions():
    """Print instructions to start MLflow UI."""
    print("\nTo view results in MLflow UI:")
    print("  mlflow ui")
    print("  Then open: http://localhost:5000")


# === EXAMPLE USAGE ===

def example_track_dataset_creation():
    """Example: Track dataset creation with instance count monitoring"""

    # Initialize experiment
    initialize_mlflow_experiment("CAMINA_Urban_Mobility")

    # Define class names for CAMINA
    camina_class_names = [
        "person", "cyclist", "car", "e-scooter", "SUV",
        "motorcyclist", "bus", "delivery_van", "truck"
    ]

    # Start dataset tracking run
    mlflow_run = start_dataset_creation_run("datasetV3_stratified", "data/datasetV3_stratified")

    try:
        # Count instances from train and validation sets
        train_instance_counts = count_instances_from_label_files(
            Path("data/datasetV3_stratified/train/labels"),
            camina_class_names
        )
        validation_instance_counts = count_instances_from_label_files(
            Path("data/datasetV3_stratified/val/labels"),
            camina_class_names
        )

        # Combine counts
        total_instance_counts = {
            class_name: train_instance_counts[class_name] + validation_instance_counts[class_name]
            for class_name in camina_class_names
        }

        # Log instance counts with threshold checking (300 min, 500 target)
        class_categories = log_instance_counts_to_mlflow(
            total_instance_counts,
            minimum_threshold=300,
            target_threshold=500
        )

        # Log split information
        train_image_count = len(list(Path("data/datasetV3_stratified/train/images").glob("*")))
        val_image_count = len(list(Path("data/datasetV3_stratified/val/images").glob("*")))

        log_training_parameters({
            "train_images": train_image_count,
            "val_images": val_image_count,
            "split_ratio": "80/20"
        })

    finally:
        end_mlflow_run()

    print_mlflow_ui_instructions()


def example_track_model_training():
    """Example: Track model training with MLflow"""

    # Initialize experiment
    initialize_mlflow_experiment("CAMINA_Urban_Mobility")

    # Start training run
    mlflow_run = start_model_training_run("YOLOv8n", "datasetV3_stratified")

    try:
        # Log training parameters
        log_training_parameters({
            "model": "YOLOv8n",
            "epochs": 150,
            "batch_size": 16,
            "image_size": 640,
            "optimizer": "SGD",
            "learning_rate": 0.01
        })

        # Log final metrics
        log_training_metrics({
            "map50_overall": 0.560,
            "precision": 0.573,
            "recall": 0.580
        })

        # Log per-class metrics
        per_class_metrics = {
            "person": {"ap50": 0.651, "precision": 0.670, "recall": 0.721},
            "cyclist": {"ap50": 0.533, "precision": 0.579, "recall": 0.612},
            "car": {"ap50": 0.687, "precision": 0.680, "recall": 0.780},
            "e-scooter": {"ap50": 0.449, "precision": 0.506, "recall": 0.491},
        }
        log_per_class_performance(per_class_metrics)

        # Log model artifacts
        log_model_artifacts(
            "model/yolo_comparison/YOLOv8n/train/weights/best.pt",
            additional_artifact_paths=[
                "model/yolo_comparison/YOLOv8n/train/results.png",
                "model/yolo_comparison/YOLOv8n/train/confusion_matrix.png"
            ]
        )

        # Log edge deployment metrics
        log_edge_deployment_performance("Raspberry_Pi_5", {
            "inference_time_ms": 65.46,
            "fps": 15.3,
            "model_size_mb": 11.65
        })

    finally:
        end_mlflow_run()

    print_mlflow_ui_instructions()


if __name__ == "__main__":
    print("=" * 60)
    print("CAMINA MLflow Integration Examples")
    print("=" * 60)

    # Example 1: Track dataset
    print("\nExample 1: Track dataset with instance counts")
    example_track_dataset_creation()

    print("\n" + "=" * 60)

    # Example 2: Track training
    print("\nExample 2: Track model training")
    example_track_model_training()
