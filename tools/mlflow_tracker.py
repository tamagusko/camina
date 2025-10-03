#!/usr/bin/env python3
"""
MLflow Integration for CAMINA Pipeline
Minimal implementation focusing on instance count tracking and model performance
"""

import mlflow
import mlflow.pytorch
from pathlib import Path
import json
from typing import Dict, List, Optional
from datetime import datetime
import yaml


class CAMINAMLflowTracker:
    """MLflow tracker for CAMINA urban mobility detection pipeline"""

    def __init__(self, experiment_name: str = "CAMINA_Urban_Mobility", tracking_uri: str = "mlruns"):
        """
        Initialize MLflow tracker

        Args:
            experiment_name: Name of the MLflow experiment
            tracking_uri: Directory for MLflow tracking data
        """
        self.experiment_name = experiment_name
        self.tracking_uri = str(Path(tracking_uri).absolute())

        # Set MLflow tracking URI
        mlflow.set_tracking_uri(f"file://{self.tracking_uri}")

        # Set or create experiment
        mlflow.set_experiment(experiment_name)

        print(f"✅ MLflow initialized")
        print(f"   Experiment: {experiment_name}")
        print(f"   Tracking URI: {self.tracking_uri}")

    def start_dataset_tracking(self, dataset_name: str, dataset_path: str) -> mlflow.ActiveRun:
        """
        Start tracking a dataset creation/update run

        Args:
            dataset_name: Name of the dataset
            dataset_path: Path to dataset directory

        Returns:
            MLflow active run context
        """
        run = mlflow.start_run(run_name=f"dataset_{dataset_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        # Log dataset metadata
        mlflow.set_tag("pipeline_stage", "dataset_creation")
        mlflow.set_tag("dataset_name", dataset_name)
        mlflow.log_param("dataset_path", dataset_path)
        mlflow.log_param("timestamp", datetime.now().isoformat())

        return run

    def log_instance_counts(self, instance_counts: Dict[str, int],
                           min_threshold: int = 300,
                           target_threshold: int = 500):
        """
        Log instance counts per class with threshold validation

        Args:
            instance_counts: Dictionary mapping class name to instance count
            min_threshold: Minimum acceptable instances per class (default: 300)
            target_threshold: Target instances per class (default: 500)
        """
        total_instances = sum(instance_counts.values())

        # Log overall metrics
        mlflow.log_metric("total_instances", total_instances)
        mlflow.log_metric("num_classes", len(instance_counts))
        mlflow.log_param("min_threshold", min_threshold)
        mlflow.log_param("target_threshold", target_threshold)

        # Track class balance
        classes_below_min = []
        classes_below_target = []
        classes_above_target = []

        # Log per-class counts and check thresholds
        for class_name, count in instance_counts.items():
            safe_class_name = class_name.replace(" ", "_").replace("-", "_")

            # Log count
            mlflow.log_metric(f"instances_{safe_class_name}", count)

            # Calculate percentage
            percentage = (count / total_instances) * 100 if total_instances > 0 else 0
            mlflow.log_metric(f"percentage_{safe_class_name}", percentage)

            # Check thresholds
            if count < min_threshold:
                classes_below_min.append((class_name, count))
                mlflow.set_tag(f"status_{safe_class_name}", "⚠️ BELOW_MINIMUM")
            elif count < target_threshold:
                classes_below_target.append((class_name, count))
                mlflow.set_tag(f"status_{safe_class_name}", "⚡ BELOW_TARGET")
            else:
                classes_above_target.append((class_name, count))
                mlflow.set_tag(f"status_{safe_class_name}", "✅ MEETS_TARGET")

        # Calculate balance metrics
        if instance_counts:
            max_count = max(instance_counts.values())
            min_count = min(instance_counts.values())
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

            mlflow.log_metric("max_instances", max_count)
            mlflow.log_metric("min_instances", min_count)
            mlflow.log_metric("imbalance_ratio", imbalance_ratio)

        # Log summary statistics
        mlflow.log_metric("classes_below_minimum", len(classes_below_min))
        mlflow.log_metric("classes_below_target", len(classes_below_target))
        mlflow.log_metric("classes_meeting_target", len(classes_above_target))

        # Create warning summary
        warnings = []
        if classes_below_min:
            warnings.append(f"⚠️ {len(classes_below_min)} classes below minimum ({min_threshold})")
            for class_name, count in sorted(classes_below_min, key=lambda x: x[1]):
                warnings.append(f"   - {class_name}: {count} (need {min_threshold - count} more)")

        if classes_below_target:
            warnings.append(f"⚡ {len(classes_below_target)} classes below target ({target_threshold})")
            for class_name, count in sorted(classes_below_target, key=lambda x: x[1]):
                warnings.append(f"   - {class_name}: {count} (need {target_threshold - count} more for target)")

        # Print summary
        print(f"\n📊 Instance Count Summary:")
        print(f"   Total instances: {total_instances}")
        print(f"   Classes: {len(instance_counts)}")
        print(f"   Imbalance ratio: {imbalance_ratio:.2f}x" if 'imbalance_ratio' in locals() else "")

        if warnings:
            print(f"\n⚠️ Dataset Balance Warnings:")
            for warning in warnings:
                print(f"   {warning}")
        else:
            print(f"\n✅ All classes meet target threshold ({target_threshold}+ instances)")

        return {
            "classes_below_min": classes_below_min,
            "classes_below_target": classes_below_target,
            "warnings": warnings
        }

    def start_training_run(self, model_name: str, dataset_name: str) -> mlflow.ActiveRun:
        """
        Start tracking a model training run

        Args:
            model_name: Name of the model (e.g., 'YOLOv8n')
            dataset_name: Name of the dataset used

        Returns:
            MLflow active run context
        """
        run = mlflow.start_run(run_name=f"train_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        mlflow.set_tag("pipeline_stage", "training")
        mlflow.set_tag("model_name", model_name)
        mlflow.set_tag("dataset_name", dataset_name)
        mlflow.log_param("timestamp", datetime.now().isoformat())

        return run

    def log_training_params(self, params: Dict):
        """Log training hyperparameters"""
        for key, value in params.items():
            mlflow.log_param(key, value)

    def log_training_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """
        Log training metrics (supports both single values and per-epoch tracking)

        Args:
            metrics: Dictionary of metric names to values
            step: Optional step/epoch number for time-series tracking
        """
        for key, value in metrics.items():
            if step is not None:
                mlflow.log_metric(key, value, step=step)
            else:
                mlflow.log_metric(key, value)

    def log_per_class_metrics(self, class_metrics: Dict[str, Dict[str, float]]):
        """
        Log per-class performance metrics

        Args:
            class_metrics: Dict mapping class name to metrics dict
                          Example: {"person": {"ap50": 0.65, "precision": 0.70}, ...}
        """
        for class_name, metrics in class_metrics.items():
            safe_class_name = class_name.replace(" ", "_").replace("-", "_")

            for metric_name, value in metrics.items():
                mlflow.log_metric(f"{metric_name}_{safe_class_name}", value)

    def log_model_artifacts(self, model_path: str, additional_artifacts: Optional[List[str]] = None):
        """
        Log model weights and related artifacts

        Args:
            model_path: Path to model weights file
            additional_artifacts: List of additional file/directory paths to log
        """
        # Log model weights
        if Path(model_path).exists():
            mlflow.log_artifact(model_path)

            # Log model size
            model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)
            mlflow.log_metric("model_size_mb", model_size_mb)

        # Log additional artifacts (configs, plots, etc.)
        if additional_artifacts:
            for artifact_path in additional_artifacts:
                if Path(artifact_path).exists():
                    if Path(artifact_path).is_dir():
                        mlflow.log_artifacts(artifact_path)
                    else:
                        mlflow.log_artifact(artifact_path)

    def log_edge_deployment_metrics(self, device_name: str, metrics: Dict[str, float]):
        """
        Log edge deployment performance metrics

        Args:
            device_name: Name of edge device (e.g., 'Raspberry_Pi_5')
            metrics: Performance metrics (inference_time_ms, fps, etc.)
        """
        mlflow.set_tag("deployment_device", device_name)

        for metric_name, value in metrics.items():
            mlflow.log_metric(f"{device_name}_{metric_name}", value)

    def end_run(self):
        """End the current MLflow run"""
        mlflow.end_run()
        print("✅ MLflow run completed")

    def get_experiment_url(self) -> str:
        """Get the MLflow UI URL for this experiment"""
        return f"file://{self.tracking_uri}"

    @staticmethod
    def print_mlflow_ui_command():
        """Print command to start MLflow UI"""
        print("\n🌐 To view results in MLflow UI, run:")
        print("   mlflow ui")
        print("   Then open: http://localhost:5000")


def load_instance_counts_from_labels(labels_dir: Path, class_names: List[str]) -> Dict[str, int]:
    """
    Count instances per class from YOLO label files

    Args:
        labels_dir: Directory containing .txt label files
        class_names: List of class names in order

    Returns:
        Dictionary mapping class name to instance count
    """
    instance_counts = {name: 0 for name in class_names}

    labels_dir = Path(labels_dir)
    if not labels_dir.exists():
        print(f"⚠️ Labels directory not found: {labels_dir}")
        return instance_counts

    # Count instances in each label file
    for label_file in labels_dir.glob("*.txt"):
        try:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        class_id = int(parts[0])
                        if 0 <= class_id < len(class_names):
                            instance_counts[class_names[class_id]] += 1
        except Exception as e:
            print(f"⚠️ Error reading {label_file}: {e}")

    return instance_counts


# Example usage functions
def track_dataset_creation_example():
    """Example: Track dataset creation with instance count monitoring"""

    tracker = CAMINAMLflowTracker(experiment_name="CAMINA_Urban_Mobility")

    # Start dataset tracking run
    with tracker.start_dataset_tracking("datasetV3_stratified", "data/datasetV3_stratified"):

        # Define class names
        class_names = [
            "person", "cyclist", "car", "e-scooter", "SUV",
            "motorcyclist", "bus", "delivery_van", "truck"
        ]

        # Load instance counts from train and validation sets
        train_counts = load_instance_counts_from_labels(
            Path("data/datasetV3_stratified/train/labels"),
            class_names
        )
        val_counts = load_instance_counts_from_labels(
            Path("data/datasetV3_stratified/val/labels"),
            class_names
        )

        # Combine counts
        total_counts = {name: train_counts[name] + val_counts[name] for name in class_names}

        # Log instance counts with threshold checking (300 min, 500 target)
        warnings = tracker.log_instance_counts(
            total_counts,
            min_threshold=300,
            target_threshold=500
        )

        # Log split information
        tracker.log_training_params({
            "train_images": len(list(Path("data/datasetV3_stratified/train/images").glob("*"))),
            "val_images": len(list(Path("data/datasetV3_stratified/val/images").glob("*"))),
            "split_ratio": "80/20"
        })

    tracker.print_mlflow_ui_command()


def track_training_example():
    """Example: Track model training with MLflow"""

    tracker = CAMINAMLflowTracker(experiment_name="CAMINA_Urban_Mobility")

    # Start training run
    with tracker.start_training_run("YOLOv8n", "datasetV3_stratified"):

        # Log training parameters
        tracker.log_training_params({
            "model": "YOLOv8n",
            "epochs": 150,
            "batch_size": 16,
            "image_size": 640,
            "optimizer": "SGD",
            "learning_rate": 0.01
        })

        # Log final metrics
        tracker.log_training_metrics({
            "map50_overall": 0.560,
            "precision": 0.573,
            "recall": 0.580
        })

        # Log per-class metrics
        class_metrics = {
            "person": {"ap50": 0.651, "precision": 0.670, "recall": 0.721},
            "cyclist": {"ap50": 0.533, "precision": 0.579, "recall": 0.612},
            "car": {"ap50": 0.687, "precision": 0.680, "recall": 0.780},
            "e-scooter": {"ap50": 0.449, "precision": 0.506, "recall": 0.491},
            # ... add other classes
        }
        tracker.log_per_class_metrics(class_metrics)

        # Log model artifacts
        tracker.log_model_artifacts(
            "model/yolo_comparison/YOLOv8n/train/weights/best.pt",
            additional_artifacts=[
                "model/yolo_comparison/YOLOv8n/train/results.png",
                "model/yolo_comparison/YOLOv8n/train/confusion_matrix.png"
            ]
        )

        # Log edge deployment metrics
        tracker.log_edge_deployment_metrics("Raspberry_Pi_5", {
            "inference_time_ms": 65.46,
            "fps": 15.3,
            "model_size_mb": 11.65
        })

    tracker.print_mlflow_ui_command()


if __name__ == "__main__":
    print("=" * 60)
    print("CAMINA MLflow Integration Examples")
    print("=" * 60)

    # Example 1: Track dataset
    print("\n📊 Example 1: Track dataset with instance counts")
    track_dataset_creation_example()

    print("\n" + "=" * 60)

    # Example 2: Track training
    print("\n🎯 Example 2: Track model training")
    track_training_example()
