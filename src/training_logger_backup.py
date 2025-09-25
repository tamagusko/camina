#!/usr/bin/env python3
"""
CAMINA Training Logger
Comprehensive logging system for YOLO model training runs
Saves all training information, metrics, and run details to structured logs
"""

import os
import json
import datetime
from pathlib import Path
from typing import Dict, List, Any
import csv
import glob

class TrainingLogger:
    def __init__(self, base_dir: str = "/home/tiago/repos/camina"):
        self.base_dir = Path(base_dir)
        self.log_dir = self.base_dir / "logs" / "training_runs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamp for this logging session
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log_file = self.log_dir / f"training_session_{self.timestamp}.json"

        print(f"🔍 Training Logger initialized")
        print(f"📁 Log directory: {self.log_dir}")
        print(f"📝 Session log: {self.session_log_file}")

    def collect_system_info(self) -> Dict[str, Any]:
        """Collect system and environment information"""
        import psutil
        import GPUtil

        # Get GPU info
        try:
            gpus = GPUtil.getGPUs()
            gpu_info = [{
                "name": gpu.name,
                "memory_total": f"{gpu.memoryTotal}MB",
                "memory_used": f"{gpu.memoryUsed}MB",
                "memory_free": f"{gpu.memoryFree}MB",
                "load": f"{gpu.load*100:.1f}%",
                "temperature": f"{gpu.temperature}°C"
            } for gpu in gpus]
        except:
            gpu_info = "GPU info not available"

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "system": {
                "cpu_count": psutil.cpu_count(),
                "memory_total": f"{psutil.virtual_memory().total / (1024**3):.2f}GB",
                "memory_available": f"{psutil.virtual_memory().available / (1024**3):.2f}GB",
                "cpu_usage": f"{psutil.cpu_percent()}%"
            },
            "gpu": gpu_info,
            "environment": {
                "python_version": "3.13.7",
                "ultralytics_version": "8.3.200",
                "pytorch_version": "2.8.0+cu128"
            }
        }

    def collect_dataset_info(self) -> Dict[str, Any]:
        """Collect dataset information"""
        return {
            "name": "datasetV3_stratified",
            "total_images": 1834,
            "train_images": 1467,
            "validation_images": 367,
            "split_ratio": "80/20",
            "total_instances": 13148,
            "classes": {
                "Person": {"instances": 6975, "percentage": 53.05, "method": "COCO"},
                "Car": {"instances": 2105, "percentage": 16.01, "method": "COCO"},
                "Cyclist": {"instances": 2012, "percentage": 15.30, "method": "rule-based"},
                "E-scooter": {"instances": 728, "percentage": 5.54, "method": "open-vocabulary"},
                "SUV": {"instances": 456, "percentage": 3.47, "method": "open-vocabulary"},
                "Bus": {"instances": 321, "percentage": 2.44, "method": "COCO"},
                "Motorcyclist": {"instances": 307, "percentage": 2.33, "method": "COCO"},
                "Truck": {"instances": 132, "percentage": 1.00, "method": "COCO"},
                "Delivery Van": {"instances": 112, "percentage": 0.85, "method": "open-vocabulary"}
            },
            "class_imbalance_ratio": "62.3:1",
            "split_method": "random (stratified failed due to class imbalance)"
        }

    def collect_model_configs(self) -> Dict[str, Any]:
        """Collect model configuration information"""
        return {
            "models_to_train": ["YOLOv5n", "YOLOv8n", "YOLOv10n", "YOLO11n"],
            "training_config": {
                "epochs": 150,
                "batch_size": 16,
                "image_size": 640,
                "patience": 75,
                "workers": 8,
                "optimizer": "AdamW (auto)",
                "learning_rate": "auto (0.000769)",
                "momentum": 0.9,
                "weight_decay": 0.0005,
                "amp": True,
                "deterministic": True
            },
            "augmentations": {
                "hsv_h": 0.015,
                "hsv_s": 0.7,
                "hsv_v": 0.4,
                "degrees": 0.0,
                "translate": 0.1,
                "scale": 0.5,
                "shear": 0.0,
                "perspective": 0.0,
                "flipud": 0.0,
                "fliplr": 0.5,
                "mosaic": 1.0,
                "mixup": 0.0,
                "copy_paste": 0.0
            }
        }

    def collect_training_results(self) -> Dict[str, Any]:
        """Collect training results from model directories"""
        results = {}
        models_dir = self.base_dir / "models" / "yolo_comparison"

        for model_dir in models_dir.glob("YOLO*"):
            if model_dir.is_dir():
                model_name = model_dir.name
                results[model_name] = self._extract_model_results(model_dir)

        return results

    def _extract_model_results(self, model_dir: Path) -> Dict[str, Any]:
        """Extract results from individual model directory"""
        results = {
            "status": "not_started",
            "model_info": {},
            "training_metrics": {},
            "final_results": {},
            "files": {}
        }

        train_dir = model_dir / "train"
        if train_dir.exists():
            results["status"] = "in_progress" if not (train_dir / "weights" / "best.pt").exists() else "completed"

            # Check for results.csv
            results_csv = train_dir / "results.csv"
            if results_csv.exists():
                results["training_metrics"] = self._parse_results_csv(results_csv)

            # Check for weights
            weights_dir = train_dir / "weights"
            if weights_dir.exists():
                results["files"]["weights"] = {
                    "best": str(weights_dir / "best.pt") if (weights_dir / "best.pt").exists() else None,
                    "last": str(weights_dir / "last.pt") if (weights_dir / "last.pt").exists() else None
                }

            # Check for plots
            results["files"]["plots"] = [str(f) for f in train_dir.glob("*.png")]

        return results

    def _parse_results_csv(self, csv_file: Path) -> Dict[str, Any]:
        """Parse results.csv file"""
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return {"error": "Empty results file"}

            # Get latest metrics
            latest = rows[-1]

            return {
                "total_epochs": len(rows),
                "latest_epoch": latest.get("epoch", "unknown"),
                "latest_metrics": {
                    "box_loss": float(latest.get("train/box_loss", 0)) if latest.get("train/box_loss") else None,
                    "cls_loss": float(latest.get("train/cls_loss", 0)) if latest.get("train/cls_loss") else None,
                    "dfl_loss": float(latest.get("train/dfl_loss", 0)) if latest.get("train/dfl_loss") else None,
                    "precision": float(latest.get("metrics/precision(B)", 0)) if latest.get("metrics/precision(B)") else None,
                    "recall": float(latest.get("metrics/recall(B)", 0)) if latest.get("metrics/recall(B)") else None,
                    "map50": float(latest.get("metrics/mAP50(B)", 0)) if latest.get("metrics/mAP50(B)") else None,
                    "map50_95": float(latest.get("metrics/mAP50-95(B)", 0)) if latest.get("metrics/mAP50-95(B)") else None
                },
                "training_history": rows[-10:] if len(rows) > 10 else rows  # Last 10 epochs
            }
        except Exception as e:
            return {"error": f"Failed to parse CSV: {str(e)}"}

    def generate_comprehensive_log(self) -> str:
        """Generate comprehensive training log"""
        print("🔍 Collecting system information...")
        system_info = self.collect_system_info()

        print("📊 Collecting dataset information...")
        dataset_info = self.collect_dataset_info()

        print("⚙️ Collecting model configurations...")
        model_configs = self.collect_model_configs()

        print("📈 Collecting training results...")
        training_results = self.collect_training_results()

        # Compile comprehensive log
        comprehensive_log = {
            "session": {
                "timestamp": self.timestamp,
                "log_generated_at": datetime.datetime.now().isoformat(),
                "pipeline_name": "CAMINA YOLO Model Training and Evaluation Pipeline",
                "academic_purpose": "Academic-grade experimental methodology for paper submission",
                "branch": "TRA2026"
            },
            "system_info": system_info,
            "dataset_info": dataset_info,
            "model_configs": model_configs,
            "training_results": training_results,
            "pipeline_status": self._get_pipeline_status(training_results)
        }

        # Save to JSON file
        with open(self.session_log_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_log, f, indent=2, ensure_ascii=False)

        # Generate markdown summary
        markdown_summary = self._generate_markdown_summary(comprehensive_log)
        markdown_file = self.log_dir / f"training_summary_{self.timestamp}.md"

        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(markdown_summary)

        print(f"✅ Comprehensive log saved to: {self.session_log_file}")
        print(f"📝 Markdown summary saved to: {markdown_file}")

        return str(self.session_log_file)

    def _get_pipeline_status(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Determine overall pipeline status"""
        total_models = 4
        completed = sum(1 for result in training_results.values() if result.get("status") == "completed")
        in_progress = sum(1 for result in training_results.values() if result.get("status") == "in_progress")
        not_started = total_models - completed - in_progress

        return {
            "total_models": total_models,
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
            "completion_percentage": (completed / total_models) * 100,
            "current_status": "completed" if completed == total_models else ("in_progress" if in_progress > 0 else "not_started")
        }

    def _generate_markdown_summary(self, log_data: Dict[str, Any]) -> str:
        """Generate markdown summary of training session"""
        pipeline_status = log_data["pipeline_status"]
        timestamp = log_data["session"]["timestamp"]

        markdown = f"""# CAMINA Training Session Log - {timestamp}

## Pipeline Status
- **Total Models**: {pipeline_status["total_models"]}
- **Completed**: {pipeline_status["completed"]}
- **In Progress**: {pipeline_status["in_progress"]}
- **Not Started**: {pipeline_status["not_started"]}
- **Completion**: {pipeline_status["completion_percentage"]:.1f}%

## System Information
- **CPUs**: {log_data["system_info"]["system"]["cpu_count"]}
- **Memory**: {log_data["system_info"]["system"]["memory_total"]}
- **GPU**: {log_data["system_info"]["gpu"][0]["name"] if isinstance(log_data["system_info"]["gpu"], list) else "N/A"}

## Dataset Information
- **Total Images**: {log_data["dataset_info"]["total_images"]:,}
- **Training Images**: {log_data["dataset_info"]["train_images"]:,} ({log_data["dataset_info"]["train_images"]/log_data["dataset_info"]["total_images"]*100:.1f}%)
- **Validation Images**: {log_data["dataset_info"]["validation_images"]:,} ({log_data["dataset_info"]["validation_images"]/log_data["dataset_info"]["total_images"]*100:.1f}%)
- **Total Instances**: {log_data["dataset_info"]["total_instances"]:,}
- **Classes**: 9
- **Class Imbalance**: {log_data["dataset_info"]["class_imbalance_ratio"]}

## Training Configuration
- **Epochs**: {log_data["model_configs"]["training_config"]["epochs"]}
- **Batch Size**: {log_data["model_configs"]["training_config"]["batch_size"]}
- **Image Size**: {log_data["model_configs"]["training_config"]["image_size"]}x{log_data["model_configs"]["training_config"]["image_size"]}
- **Patience**: {log_data["model_configs"]["training_config"]["patience"]} epochs
- **Optimizer**: {log_data["model_configs"]["training_config"]["optimizer"]}

## Model Training Results

"""

        for model_name, results in log_data["training_results"].items():
            status_emoji = {"completed": "✅", "in_progress": "🔄", "not_started": "⏳"}.get(results["status"], "❓")
            markdown += f"### {status_emoji} {model_name}\n"
            markdown += f"- **Status**: {results['status']}\n"

            if "training_metrics" in results and results["training_metrics"]:
                metrics = results["training_metrics"]
                if "latest_metrics" in metrics:
                    latest = metrics["latest_metrics"]
                    markdown += f"- **Latest Epoch**: {metrics.get('latest_epoch', 'N/A')}/{log_data['model_configs']['training_config']['epochs']}\n"
                    if latest.get("map50"):
                        markdown += f"- **mAP@0.5**: {latest['map50']:.3f}\n"
                    if latest.get("precision"):
                        markdown += f"- **Precision**: {latest['precision']:.3f}\n"
                    if latest.get("recall"):
                        markdown += f"- **Recall**: {latest['recall']:.3f}\n"

            markdown += "\n"

        markdown += f"""
---
**Generated by CAMINA Training Logger**
**Timestamp**: {datetime.datetime.now().isoformat()}
**Session ID**: {timestamp}
"""

        return markdown

def main():
    """Main function to run comprehensive logging"""
    logger = TrainingLogger()
    log_file = logger.generate_comprehensive_log()

    print("\n" + "="*80)
    print("🎯 CAMINA Training Logger - Summary")
    print("="*80)
    print(f"📁 Logs saved to: {logger.log_dir}")
    print(f"📝 Session log: {log_file}")
    print("="*80)

if __name__ == "__main__":
    main()