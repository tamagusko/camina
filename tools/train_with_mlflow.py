#!/usr/bin/env python3
"""
YOLO Training with MLflow Integration
Pure functional wrapper for CAMINA YOLO training pipeline with automatic MLflow tracking
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tools.mlflow_tracker import (
        count_instances_from_label_files,
        initialize_mlflow_experiment,
        start_model_training_run,
        log_training_parameters,
        log_training_metrics,
        log_per_class_performance,
        log_model_artifacts,
        log_edge_deployment_performance,
        log_instance_counts_to_mlflow,
        end_mlflow_run,
        print_mlflow_ui_instructions
    )
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    print("Warning: MLflow not available. Install with: pip install mlflow")

from ultralytics import YOLO


# === DATASET LOADING ===

def load_dataset_configuration(data_yaml_path: str) -> Dict:
    """
    Load dataset configuration from YAML file.

    Args:
        data_yaml_path: Path to dataset YAML file

    Returns:
        Dictionary with dataset configuration
    """
    with open(data_yaml_path, 'r') as file:
        data_config = yaml.safe_load(file)

    return data_config


def extract_dataset_info(data_yaml_path: str) -> Dict[str, any]:
    """
    Extract dataset information from YAML path and content.

    Args:
        data_yaml_path: Path to dataset YAML file

    Returns:
        Dictionary with dataset_name, dataset_root, and class_names
    """
    data_config = load_dataset_configuration(data_yaml_path)

    dataset_yaml_file = Path(data_yaml_path)
    dataset_name = dataset_yaml_file.parent.name
    dataset_root_path = dataset_yaml_file.parent
    class_names = data_config.get('names', [])

    return {
        'dataset_name': dataset_name,
        'dataset_root': dataset_root_path,
        'class_names': class_names,
        'num_classes': len(class_names)
    }


# === TRAINING EXECUTION ===

def train_yolo_model(
    model_name: str,
    model_weights_path: str,
    data_yaml_path: str,
    epochs: int = 150,
    batch_size: int = 16,
    image_size: int = 640,
    device: str = "0",
    project_directory: str = "model/yolo_comparison",
    **additional_training_args
) -> Dict:
    """
    Train YOLO model with the given configuration.

    Args:
        model_name: Name of model (e.g., 'YOLOv8n')
        model_weights_path: Path to base model weights
        data_yaml_path: Path to dataset YAML file
        epochs: Number of training epochs
        batch_size: Batch size for training
        image_size: Input image size
        device: Device to use (cuda:0, cpu, etc.)
        project_directory: Project directory for outputs
        **additional_training_args: Additional YOLO training arguments

    Returns:
        Dictionary with training information and metrics
    """
    print(f"\n{'='*70}")
    print(f"Training {model_name}")
    print(f"{'='*70}\n")

    # Load model
    print(f"Loading base model: {model_weights_path}")
    yolo_model = YOLO(model_weights_path)

    # Start training
    print(f"Starting training for {epochs} epochs...")
    training_results = yolo_model.train(
        data=data_yaml_path,
        epochs=epochs,
        batch=batch_size,
        imgsz=image_size,
        device=device,
        project=project_directory,
        name=model_name,
        exist_ok=True,
        **additional_training_args
    )

    # Define output paths
    model_output_directory = Path(project_directory) / model_name / "train"
    best_weights_path = model_output_directory / "weights" / "best.pt"

    training_info = {
        'model_name': model_name,
        'output_directory': str(model_output_directory),
        'best_weights_path': str(best_weights_path),
        'training_completed': best_weights_path.exists()
    }

    return training_info


# === MODEL VALIDATION ===

def validate_trained_model(yolo_model: YOLO, data_yaml_path: str, class_names: List[str]) -> Dict:
    """
    Validate trained model and extract metrics.

    Args:
        yolo_model: Trained YOLO model
        data_yaml_path: Path to dataset YAML file
        class_names: List of class names

    Returns:
        Dictionary with overall and per-class metrics
    """
    print(f"\nValidating model...")
    validation_metrics = yolo_model.val(data=data_yaml_path, split='val')

    # Extract overall metrics
    overall_metrics = {
        "map50": float(validation_metrics.box.map50),
        "map50_95": float(validation_metrics.box.map),
        "precision": float(validation_metrics.box.p.mean()) if hasattr(validation_metrics.box, 'p') else 0,
        "recall": float(validation_metrics.box.r.mean()) if hasattr(validation_metrics.box, 'r') else 0,
    }

    # Extract per-class metrics
    per_class_metrics = {}
    if hasattr(validation_metrics.box, 'maps') and validation_metrics.box.maps is not None:
        ap50_values = validation_metrics.box.maps
        for class_index, class_name in enumerate(class_names):
            if class_index < len(ap50_values):
                per_class_metrics[class_name] = {
                    "ap50": float(ap50_values[class_index])
                }

    print(f"\nTraining Results:")
    print(f"  mAP@0.5: {overall_metrics['map50']:.3f}")
    print(f"  Precision: {overall_metrics['precision']:.3f}")
    print(f"  Recall: {overall_metrics['recall']:.3f}")

    return {
        'overall_metrics': overall_metrics,
        'per_class_metrics': per_class_metrics
    }


# === ARTIFACT COLLECTION ===

def collect_training_artifacts(model_output_directory: Path) -> List[str]:
    """
    Collect paths to training artifacts for logging.

    Args:
        model_output_directory: Directory containing training outputs

    Returns:
        List of artifact file paths
    """
    artifact_names = ["results.png", "confusion_matrix.png", "F1_curve.png", "PR_curve.png"]
    artifact_paths = []

    for artifact_name in artifact_names:
        artifact_path = model_output_directory / artifact_name
        if artifact_path.exists():
            artifact_paths.append(str(artifact_path))

    return artifact_paths


# === TRAINING WITH MLFLOW ===

def train_yolo_model_with_mlflow(
    model_name: str,
    model_weights_path: str,
    data_yaml_path: str,
    epochs: int = 150,
    batch_size: int = 16,
    image_size: int = 640,
    device: str = "0",
    project_directory: str = "model/yolo_comparison",
    experiment_name: str = "CAMINA_Urban_Mobility",
    **additional_training_args
) -> Dict:
    """
    Train YOLO model with comprehensive MLflow tracking.

    Args:
        model_name: Name of model (e.g., 'YOLOv8n')
        model_weights_path: Path to base model weights
        data_yaml_path: Path to dataset YAML file
        epochs: Number of training epochs
        batch_size: Batch size for training
        image_size: Input image size
        device: Device to use (cuda:0, cpu, etc.)
        project_directory: Project directory for outputs
        experiment_name: MLflow experiment name
        **additional_training_args: Additional YOLO training arguments

    Returns:
        Dictionary with training results and metrics
    """
    print(f"\n{'='*70}")
    print(f"Training {model_name} with MLflow Tracking")
    print(f"{'='*70}\n")

    # Extract dataset information
    dataset_info = extract_dataset_info(data_yaml_path)

    # Initialize MLflow if available
    if MLFLOW_AVAILABLE:
        initialize_mlflow_experiment(experiment_name)
        mlflow_run = start_model_training_run(model_name, dataset_info['dataset_name'])
    else:
        mlflow_run = None
        print("\nMLflow is not installed. Continuing without MLflow tracking...")

    try:
        # Log training parameters
        if MLFLOW_AVAILABLE:
            training_parameters = {
                "model": model_name,
                "model_path": model_weights_path,
                "epochs": epochs,
                "batch_size": batch_size,
                "image_size": image_size,
                "device": device,
                "dataset": dataset_info['dataset_name'],
                "num_classes": dataset_info['num_classes'],
                "optimizer": additional_training_args.get("optimizer", "auto"),
                "learning_rate": additional_training_args.get("lr0", 0.01),
            }
            log_training_parameters(training_parameters)

            # Log dataset instance counts
            train_labels_path = dataset_info['dataset_root'] / "train" / "labels"
            validation_labels_path = dataset_info['dataset_root'] / "val" / "labels"

            if train_labels_path.exists():
                train_instance_counts = count_instances_from_label_files(
                    train_labels_path,
                    dataset_info['class_names']
                )
                validation_instance_counts = count_instances_from_label_files(
                    validation_labels_path,
                    dataset_info['class_names']
                )
                total_instance_counts = {
                    class_name: train_instance_counts[class_name] + validation_instance_counts[class_name]
                    for class_name in dataset_info['class_names']
                }

                # Log instance counts
                log_instance_counts_to_mlflow(total_instance_counts, minimum_threshold=300, target_threshold=500)

        # Train the model
        training_info = train_yolo_model(
            model_name=model_name,
            model_weights_path=model_weights_path,
            data_yaml_path=data_yaml_path,
            epochs=epochs,
            batch_size=batch_size,
            image_size=image_size,
            device=device,
            project_directory=project_directory,
            **additional_training_args
        )

        # Validate the trained model
        trained_yolo_model = YOLO(training_info['best_weights_path'])
        validation_results = validate_trained_model(
            trained_yolo_model,
            data_yaml_path,
            dataset_info['class_names']
        )

        # Log metrics to MLflow
        if MLFLOW_AVAILABLE:
            # Log overall metrics
            log_training_metrics(validation_results['overall_metrics'])

            # Log per-class metrics
            log_per_class_performance(validation_results['per_class_metrics'])

            # Collect and log artifacts
            model_output_directory = Path(training_info['output_directory'])
            artifact_paths = collect_training_artifacts(model_output_directory)

            log_model_artifacts(
                training_info['best_weights_path'],
                additional_artifact_paths=artifact_paths
            )

        # Create results summary
        results_summary = {
            "model_name": model_name,
            "dataset": dataset_info['dataset_name'],
            "timestamp": datetime.now().isoformat(),
            "training_params": training_parameters if MLFLOW_AVAILABLE else {},
            "overall_metrics": validation_results['overall_metrics'],
            "per_class_metrics": validation_results['per_class_metrics'],
            "best_weights": training_info['best_weights_path']
        }

        # Save summary to JSON
        summary_output_path = Path(training_info['output_directory']) / "mlflow_summary.json"
        with open(summary_output_path, 'w') as file:
            json.dump(results_summary, file, indent=2)

        print(f"\nTraining completed successfully!")
        print(f"  Best weights: {training_info['best_weights_path']}")
        print(f"  Summary saved: {summary_output_path}")

        return results_summary

    finally:
        if MLFLOW_AVAILABLE:
            end_mlflow_run()


# === BATCH TRAINING ===

def train_multiple_yolo_models(
    models_configuration: List[Dict],
    data_yaml_path: str,
    epochs: int = 150,
    experiment_name: str = "CAMINA_Urban_Mobility",
    **common_training_args
) -> List[Dict]:
    """
    Train multiple YOLO models with MLflow tracking.

    Args:
        models_configuration: List of model configurations
                            [{"name": "YOLOv8n", "path": "yolov8n.pt"}, ...]
        data_yaml_path: Path to dataset YAML file
        epochs: Number of training epochs
        experiment_name: MLflow experiment name
        **common_training_args: Common training arguments for all models

    Returns:
        List of training results for each model
    """
    all_training_results = []

    for model_index, model_config in enumerate(models_configuration):
        model_name = model_config["name"]
        model_path = model_config["path"]

        print(f"\n{'='*70}")
        print(f"Training model {model_index+1}/{len(models_configuration)}: {model_name}")
        print(f"{'='*70}\n")

        try:
            training_result = train_yolo_model_with_mlflow(
                model_name=model_name,
                model_weights_path=model_path,
                data_yaml_path=data_yaml_path,
                epochs=epochs,
                experiment_name=experiment_name,
                **common_training_args
            )
            all_training_results.append(training_result)

        except Exception as error:
            print(f"\nError training {model_name}: {error}")
            all_training_results.append({
                "model_name": model_name,
                "error": str(error),
                "status": "failed"
            })

    # Print summary comparison
    print(f"\n{'='*70}")
    print(f"ALL MODELS TRAINING SUMMARY")
    print(f"{'='*70}\n")

    successful_results = [result for result in all_training_results if "error" not in result]

    if successful_results:
        print(f"Model         mAP@0.5  Precision  Recall")
        print("-" * 50)
        for result in successful_results:
            metrics = result.get("overall_metrics", {})
            print(f"{result['model_name']:12s}  {metrics.get('map50', 0):.3f}    "
                 f"{metrics.get('precision', 0):.3f}      {metrics.get('recall', 0):.3f}")

    failed_results = [result for result in all_training_results if "error" in result]
    if failed_results:
        print(f"\nFailed models: {len(failed_results)}")
        for result in failed_results:
            print(f"  - {result['model_name']}: {result['error']}")

    if MLFLOW_AVAILABLE:
        print("\n")
        print_mlflow_ui_instructions()

    return all_training_results


# === MAIN EXECUTION ===

def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Train YOLO models with MLflow tracking")
    parser.add_argument("--model", type=str, required=True,
                       help="Model name (e.g., YOLOv8n)")
    parser.add_argument("--model-path", type=str, required=True,
                       help="Path to base model weights")
    parser.add_argument("--data", type=str, required=True,
                       help="Path to dataset YAML file")
    parser.add_argument("--epochs", type=int, default=150,
                       help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=16,
                       help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640,
                       help="Image size")
    parser.add_argument("--device", type=str, default="0",
                       help="Device (cuda:0, cpu, etc.)")
    parser.add_argument("--project", type=str, default="model/yolo_comparison",
                       help="Project directory")
    parser.add_argument("--experiment", type=str, default="CAMINA_Urban_Mobility",
                       help="MLflow experiment name")

    args = parser.parse_args()

    # Check if MLflow is available
    if not MLFLOW_AVAILABLE:
        print("\nWarning: MLflow is not installed. Install with:")
        print("  pip install mlflow")
        print("\nContinuing without MLflow tracking...")

    # Train model
    training_result = train_yolo_model_with_mlflow(
        model_name=args.model,
        model_weights_path=args.model_path,
        data_yaml_path=args.data,
        epochs=args.epochs,
        batch_size=args.batch,
        image_size=args.imgsz,
        device=args.device,
        project_directory=args.project,
        experiment_name=args.experiment
    )

    print(f"\nTraining completed!")
    print(f"  Results: {json.dumps(training_result['overall_metrics'], indent=2)}")


if __name__ == "__main__":
    main()
