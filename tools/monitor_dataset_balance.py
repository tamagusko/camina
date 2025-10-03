#!/usr/bin/env python3
"""
Dataset Balance Monitor for CAMINA
Monitors instance counts and warns when classes need more data
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tools.mlflow_tracker import CAMINAMLflowTracker, load_instance_counts_from_labels
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    print("⚠️ MLflow not available. Install with: pip install mlflow")


class DatasetBalanceMonitor:
    """Monitor dataset balance and track progress toward instance count goals"""

    def __init__(self, dataset_path: str, class_names: List[str],
                 min_threshold: int = 300, target_threshold: int = 500):
        """
        Initialize dataset balance monitor

        Args:
            dataset_path: Path to dataset directory
            class_names: List of class names in order
            min_threshold: Minimum acceptable instances per class
            target_threshold: Target instances per class
        """
        self.dataset_path = Path(dataset_path)
        self.class_names = class_names
        self.min_threshold = min_threshold
        self.target_threshold = target_threshold

        self.train_counts = {}
        self.val_counts = {}
        self.total_counts = {}

    def analyze_dataset(self) -> Dict:
        """
        Analyze dataset and return comprehensive statistics

        Returns:
            Dictionary containing all statistics and warnings
        """
        # Load instance counts
        train_labels = self.dataset_path / "train" / "labels"
        val_labels = self.dataset_path / "val" / "labels"

        self.train_counts = load_instance_counts_from_labels(train_labels, self.class_names)
        self.val_counts = load_instance_counts_from_labels(val_labels, self.class_names)
        self.total_counts = {
            name: self.train_counts[name] + self.val_counts[name]
            for name in self.class_names
        }

        # Count images
        train_images = len(list((self.dataset_path / "train" / "images").glob("*.[jp][pn]g")))
        val_images = len(list((self.dataset_path / "val" / "images").glob("*.[jp][pn]g")))

        # Calculate statistics
        total_instances = sum(self.total_counts.values())
        max_count = max(self.total_counts.values()) if self.total_counts else 0
        min_count = min(self.total_counts.values()) if self.total_counts else 0
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

        # Categorize classes
        classes_below_min = []
        classes_below_target = []
        classes_above_target = []

        for class_name, count in self.total_counts.items():
            if count < self.min_threshold:
                classes_below_min.append((class_name, count, self.min_threshold - count))
            elif count < self.target_threshold:
                classes_below_target.append((class_name, count, self.target_threshold - count))
            else:
                classes_above_target.append((class_name, count))

        # Calculate collection progress
        collection_progress = {}
        for class_name, count in self.total_counts.items():
            progress_pct = (count / self.target_threshold) * 100
            collection_progress[class_name] = {
                "current": count,
                "target": self.target_threshold,
                "needed": max(0, self.target_threshold - count),
                "progress_pct": min(100, progress_pct)
            }

        return {
            "dataset_path": str(self.dataset_path),
            "timestamp": datetime.now().isoformat(),
            "images": {
                "train": train_images,
                "val": val_images,
                "total": train_images + val_images
            },
            "instances": {
                "train": sum(self.train_counts.values()),
                "val": sum(self.val_counts.values()),
                "total": total_instances
            },
            "per_class_counts": self.total_counts,
            "statistics": {
                "num_classes": len(self.class_names),
                "max_instances": max_count,
                "min_instances": min_count,
                "imbalance_ratio": imbalance_ratio,
                "avg_instances": total_instances / len(self.class_names) if self.class_names else 0
            },
            "thresholds": {
                "minimum": self.min_threshold,
                "target": self.target_threshold
            },
            "status": {
                "classes_below_minimum": len(classes_below_min),
                "classes_below_target": len(classes_below_target),
                "classes_meeting_target": len(classes_above_target)
            },
            "classes_needing_data": {
                "below_minimum": sorted(classes_below_min, key=lambda x: x[1]),
                "below_target": sorted(classes_below_target, key=lambda x: x[1])
            },
            "collection_progress": collection_progress
        }

    def print_report(self, analysis: Dict):
        """Print a formatted report of dataset balance"""

        print("=" * 70)
        print(f"📊 CAMINA DATASET BALANCE REPORT")
        print("=" * 70)
        print(f"Dataset: {analysis['dataset_path']}")
        print(f"Generated: {analysis['timestamp']}")
        print()

        # Images summary
        images = analysis['images']
        print(f"📁 Images:")
        print(f"   Train: {images['train']}")
        print(f"   Val:   {images['val']}")
        print(f"   Total: {images['total']}")
        print()

        # Instances summary
        instances = analysis['instances']
        print(f"🎯 Total Instances: {instances['total']}")
        print(f"   Train: {instances['train']}")
        print(f"   Val:   {instances['val']}")
        print()

        # Statistics
        stats = analysis['statistics']
        print(f"📈 Dataset Statistics:")
        print(f"   Classes: {stats['num_classes']}")
        print(f"   Max instances: {stats['max_instances']}")
        print(f"   Min instances: {stats['min_instances']}")
        print(f"   Avg instances: {stats['avg_instances']:.1f}")
        print(f"   Imbalance ratio: {stats['imbalance_ratio']:.2f}x")
        print()

        # Thresholds
        thresholds = analysis['thresholds']
        status = analysis['status']
        print(f"🎯 Instance Count Goals:")
        print(f"   Minimum threshold: {thresholds['minimum']} instances/class")
        print(f"   Target threshold:  {thresholds['target']} instances/class")
        print()
        print(f"   ✅ Meeting target: {status['classes_meeting_target']} classes")
        print(f"   ⚡ Below target:   {status['classes_below_target']} classes")
        print(f"   ⚠️  Below minimum:  {status['classes_below_minimum']} classes")
        print()

        # Per-class breakdown with progress bars
        print(f"📋 Per-Class Instance Counts:")
        print("-" * 70)

        progress_data = analysis['collection_progress']
        for class_name in self.class_names:
            prog = progress_data[class_name]
            count = prog['current']
            target = prog['target']
            needed = prog['needed']
            pct = prog['progress_pct']

            # Status indicator
            if count >= target:
                status_icon = "✅"
            elif count >= self.min_threshold:
                status_icon = "⚡"
            else:
                status_icon = "⚠️"

            # Progress bar
            bar_length = 30
            filled = int(bar_length * pct / 100)
            bar = "█" * filled + "░" * (bar_length - filled)

            print(f"   {status_icon} {class_name:15s} [{bar}] {count:4d}/{target} ({pct:5.1f}%)")

            if needed > 0:
                print(f"      └─ Need {needed} more instances to reach target")

        print()

        # Warnings for classes needing data
        needing_data = analysis['classes_needing_data']

        if needing_data['below_minimum']:
            print("⚠️  CRITICAL: Classes below minimum threshold ({})".format(thresholds['minimum']))
            print("-" * 70)
            for class_name, count, needed in needing_data['below_minimum']:
                print(f"   • {class_name}: {count} instances (need {needed} more)")
                print(f"     Priority: HIGH - Add {needed}+ images with '{class_name}'")
            print()

        if needing_data['below_target']:
            print("⚡ Classes below target threshold ({})".format(thresholds['target']))
            print("-" * 70)
            for class_name, count, needed in needing_data['below_target']:
                print(f"   • {class_name}: {count} instances (need {needed} more for target)")
            print()

        # Collection recommendations
        if needing_data['below_minimum'] or needing_data['below_target']:
            print("💡 Recommendations:")
            print("-" * 70)

            # Prioritize classes below minimum
            if needing_data['below_minimum']:
                print("   1. HIGH PRIORITY: Focus on collecting images for:")
                for class_name, count, needed in needing_data['below_minimum'][:3]:
                    print(f"      - {class_name} ({needed}+ more needed)")

            # Then classes below target
            if needing_data['below_target']:
                print("   2. MEDIUM PRIORITY: Increase instances for:")
                for class_name, count, needed in sorted(needing_data['below_target'], key=lambda x: x[2], reverse=True)[:3]:
                    print(f"      - {class_name} ({needed} more for target)")

            print()
            print("   💡 Tip: Use YOLO-World or manual annotation to add these classes")
            print()

        else:
            print("🎉 EXCELLENT: All classes meet target threshold!")
            print()

        print("=" * 70)

    def save_report(self, analysis: Dict, output_path: str = "dataset_balance_report.json"):
        """Save analysis report to JSON file"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)

        print(f"💾 Report saved to: {output_path}")

    def track_with_mlflow(self, analysis: Dict, experiment_name: str = "CAMINA_Urban_Mobility"):
        """Track dataset balance in MLflow"""
        if not MLFLOW_AVAILABLE:
            print("⚠️ MLflow not available. Skipping MLflow tracking.")
            return

        tracker = CAMINAMLflowTracker(experiment_name=experiment_name)

        dataset_name = Path(analysis['dataset_path']).name

        with tracker.start_dataset_tracking(dataset_name, analysis['dataset_path']):
            # Log instance counts with thresholds
            tracker.log_instance_counts(
                analysis['per_class_counts'],
                min_threshold=self.min_threshold,
                target_threshold=self.target_threshold
            )

            # Log image counts
            tracker.log_training_params({
                "train_images": analysis['images']['train'],
                "val_images": analysis['images']['val'],
                "total_images": analysis['images']['total']
            })

        print("\n✅ Dataset balance tracked in MLflow")
        tracker.print_mlflow_ui_command()


def main():
    """Main execution"""
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

    # Define CAMINA class names
    class_names = [
        "person", "cyclist", "car", "e-scooter", "SUV",
        "motorcyclist", "bus", "delivery_van", "truck"
    ]

    # Create monitor
    monitor = DatasetBalanceMonitor(
        dataset_path=args.dataset,
        class_names=class_names,
        min_threshold=args.min_threshold,
        target_threshold=args.target_threshold
    )

    # Analyze dataset
    print("🔍 Analyzing dataset...")
    analysis = monitor.analyze_dataset()

    # Print report
    monitor.print_report(analysis)

    # Save report
    monitor.save_report(analysis, args.output)

    # Track with MLflow if requested
    if args.mlflow:
        monitor.track_with_mlflow(analysis, args.experiment_name)


if __name__ == "__main__":
    main()
