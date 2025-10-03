#!/usr/bin/env python3
"""
YOLO Training with MLflow Integration
Wrapper for CAMINA YOLO training pipeline with automatic MLflow tracking
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
    from tools.mlflow_tracker import CAMINAMLflowTracker, load_instance_counts_from_labels
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    print("⚠️ MLflow not available. Install with: pip install mlflow")

from ultralytics import YOLO


class YOLOTrainerWithMLflow:
    """YOLO trainer with integrated MLflow tracking"""

    def __init__(self, experiment_name: str = "CAMINA_Urban_Mobility"):
        """Initialize trainer with MLflow tracking"""
        self.experiment_name = experiment_name
        self.tracker = CAMINAMLflowTracker(experiment_name=experiment_name) if MLFLOW_AVAILABLE else None

    def train_model(self,
                   model_name: str,
                   model_path: str,
                   data_yaml: str,
                   epochs: int = 150,
                   batch: int = 16,
                   imgsz: int = 640,
                   device: str = "0",
                   project: str = "model/yolo_comparison",
                   **kwargs) -> Dict:
        """
        Train YOLO model with MLflow tracking

        Args:
            model_name: Name of model (e.g., 'YOLOv8n')
            model_path: Path to base model weights
            data_yaml: Path to dataset YAML file
            epochs: Number of training epochs
            batch: Batch size
            imgsz: Image size
            device: Device to use (cuda:0, cpu, etc.)
            project: Project directory for outputs
            **kwargs: Additional YOLO training arguments

        Returns:
            Dictionary with training results and metrics
        """
        print(f"\n{'='*70}")
        print(f"🎯 Training {model_name} with MLflow Tracking")
        print(f"{'='*70}\n")

        # Load dataset info
        with open(data_yaml, 'r') as f:
            data_config = yaml.safe_load(f)

        dataset_name = Path(data_yaml).parent.name
        class_names = data_config.get('names', [])

        # Start MLflow run
        if self.tracker:
            run = self.tracker.start_training_run(model_name, dataset_name)
        else:
            run = None

        try:
            # Log training parameters
            if self.tracker:
                training_params = {
                    "model": model_name,
                    "model_path": model_path,
                    "epochs": epochs,
                    "batch_size": batch,
                    "image_size": imgsz,
                    "device": device,
                    "dataset": dataset_name,
                    "num_classes": len(class_names),
                    "optimizer": kwargs.get("optimizer", "auto"),
                    "learning_rate": kwargs.get("lr0", 0.01),
                }
                self.tracker.log_training_params(training_params)

                # Log dataset instance counts
                dataset_root = Path(data_yaml).parent
                train_labels = dataset_root / "train" / "labels"
                val_labels = dataset_root / "val" / "labels"

                if train_labels.exists():
                    train_counts = load_instance_counts_from_labels(train_labels, class_names)
                    val_counts = load_instance_counts_from_labels(val_labels, class_names)
                    total_counts = {name: train_counts[name] + val_counts[name] for name in class_names}

                    # Log instance counts
                    self.tracker.log_instance_counts(total_counts, min_threshold=300, target_threshold=500)

            # Initialize and train model
            print(f"🔄 Loading base model: {model_path}")
            model = YOLO(model_path)

            print(f"🚀 Starting training for {epochs} epochs...")
            results = model.train(
                data=data_yaml,
                epochs=epochs,
                batch=batch,
                imgsz=imgsz,
                device=device,
                project=project,
                name=model_name,
                exist_ok=True,
                **kwargs
            )

            # Get final metrics from results
            metrics_file = Path(project) / model_name / "train" / "results.csv"
            best_weights = Path(project) / model_name / "train" / "weights" / "best.pt"

            # Validate the best model
            print(f"\n🔍 Validating best model...")
            metrics = model.val(data=data_yaml, split='val')

            # Extract overall metrics
            overall_metrics = {
                "map50": float(metrics.box.map50),
                "map50_95": float(metrics.box.map),
                "precision": float(metrics.box.p.mean()) if hasattr(metrics.box, 'p') else 0,
                "recall": float(metrics.box.r.mean()) if hasattr(metrics.box, 'r') else 0,
            }

            # Extract per-class metrics
            per_class_metrics = {}
            if hasattr(metrics.box, 'maps') and metrics.box.maps is not None:
                maps_values = metrics.box.maps
                for i, class_name in enumerate(class_names):
                    if i < len(maps_values):
                        per_class_metrics[class_name] = {
                            "ap50": float(maps_values[i])
                        }

            print(f"\n📊 Training Results:")
            print(f"   mAP@0.5: {overall_metrics['map50']:.3f}")
            print(f"   Precision: {overall_metrics['precision']:.3f}")
            print(f"   Recall: {overall_metrics['recall']:.3f}")

            # Log metrics to MLflow
            if self.tracker:
                # Log overall metrics
                self.tracker.log_training_metrics(overall_metrics)

                # Log per-class metrics
                self.tracker.log_per_class_metrics(per_class_metrics)

                # Log model artifacts
                artifacts = [str(best_weights)]

                # Add training plots if they exist
                train_dir = Path(project) / model_name / "train"
                for plot in ["results.png", "confusion_matrix.png", "F1_curve.png", "PR_curve.png"]:
                    plot_path = train_dir / plot
                    if plot_path.exists():
                        artifacts.append(str(plot_path))

                self.tracker.log_model_artifacts(str(best_weights), artifacts[1:])

            # Save results summary
            results_summary = {
                "model_name": model_name,
                "dataset": dataset_name,
                "timestamp": datetime.now().isoformat(),
                "training_params": training_params if self.tracker else {},
                "overall_metrics": overall_metrics,
                "per_class_metrics": per_class_metrics,
                "best_weights": str(best_weights)
            }

            summary_path = Path(project) / model_name / "train" / "mlflow_summary.json"
            with open(summary_path, 'w') as f:
                json.dump(results_summary, f, indent=2)

            print(f"\n✅ Training completed successfully!")
            print(f"   Best weights: {best_weights}")
            print(f"   Summary saved: {summary_path}")

            return results_summary

        finally:
            if self.tracker:
                self.tracker.end_run()

    def train_all_models(self,
                        models_config: List[Dict],
                        data_yaml: str,
                        epochs: int = 150,
                        **common_kwargs) -> List[Dict]:
        """
        Train multiple YOLO models with MLflow tracking

        Args:
            models_config: List of model configurations
                          [{"name": "YOLOv8n", "path": "yolov8n.pt"}, ...]
            data_yaml: Path to dataset YAML file
            epochs: Number of training epochs
            **common_kwargs: Common training arguments for all models

        Returns:
            List of training results for each model
        """
        all_results = []

        for i, model_cfg in enumerate(models_config):
            model_name = model_cfg["name"]
            model_path = model_cfg["path"]

            print(f"\n{'='*70}")
            print(f"Training model {i+1}/{len(models_config)}: {model_name}")
            print(f"{'='*70}\n")

            try:
                results = self.train_model(
                    model_name=model_name,
                    model_path=model_path,
                    data_yaml=data_yaml,
                    epochs=epochs,
                    **common_kwargs
                )
                all_results.append(results)

            except Exception as e:
                print(f"\n❌ Error training {model_name}: {e}")
                all_results.append({
                    "model_name": model_name,
                    "error": str(e),
                    "status": "failed"
                })

        # Print summary comparison
        print(f"\n{'='*70}")
        print(f"📊 ALL MODELS TRAINING SUMMARY")
        print(f"{'='*70}\n")

        successful = [r for r in all_results if "error" not in r]

        if successful:
            print(f"Model         mAP@0.5  Precision  Recall")
            print("-" * 50)
            for result in successful:
                metrics = result.get("overall_metrics", {})
                print(f"{result['model_name']:12s}  {metrics.get('map50', 0):.3f}    "
                     f"{metrics.get('precision', 0):.3f}      {metrics.get('recall', 0):.3f}")

        failed = [r for r in all_results if "error" in r]
        if failed:
            print(f"\n❌ Failed models: {len(failed)}")
            for result in failed:
                print(f"   - {result['model_name']}: {result['error']}")

        if self.tracker:
            print("\n")
            self.tracker.print_mlflow_ui_command()

        return all_results


def main():
    """Main execution"""
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
        print("\n⚠️ MLflow is not installed. Install with:")
        print("   pip install mlflow")
        print("\nContinuing without MLflow tracking...")

    # Create trainer
    trainer = YOLOTrainerWithMLflow(experiment_name=args.experiment)

    # Train model
    results = trainer.train_model(
        model_name=args.model,
        model_path=args.model_path,
        data_yaml=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        project=args.project
    )

    print(f"\n🎉 Training completed!")
    print(f"   Results: {json.dumps(results['overall_metrics'], indent=2)}")


if __name__ == "__main__":
    main()
