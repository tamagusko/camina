#!/usr/bin/env python3
"""
Generate performance visualizations for CAMINA YOLO models
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import seaborn as sns

# Set style
plt.style.use('default')
sns.set_palette("husl")

def load_real_metrics():
    """Load the real per-class metrics from JSON"""
    json_file = Path("/home/tiago/repos/camina/outputs/model_comparison/results/real_perclass_metrics.json")

    with open(json_file, 'r') as f:
        return json.load(f)

def create_per_class_comparison():
    """Create per-class performance comparison chart"""

    real_metrics = load_real_metrics()

    class_order = ["Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery Van", "Truck"]
    model_order = ["YOLO11n", "YOLOv8n", "YOLOv10n", "YOLOv5n"]

    # Prepare data
    data = []
    for class_name in class_order:
        for model_name in model_order:
            if model_name in real_metrics:
                ap = real_metrics[model_name]['class_wise_ap'].get(class_name, 0.0)
                data.append({
                    'Class': class_name,
                    'Model': model_name,
                    'mAP@0.5': ap
                })

    df = pd.DataFrame(data)

    # Create the plot
    fig, ax = plt.subplots(figsize=(14, 8))

    # Create grouped bar chart
    x = np.arange(len(class_order))
    width = 0.2

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    for i, model in enumerate(model_order):
        model_data = df[df['Model'] == model]
        values = [model_data[model_data['Class'] == cls]['mAP@0.5'].iloc[0] if len(model_data[model_data['Class'] == cls]) > 0 else 0
                 for cls in class_order]

        bars = ax.bar(x + i * width, values, width, label=model, color=colors[i], alpha=0.8)

        # Add value labels on bars
        for bar, value in zip(bars, values):
            if value > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.01,
                       f'{value:.3f}', ha='center', va='bottom', fontsize=8)

    ax.set_xlabel('Classes', fontsize=12, fontweight='bold')
    ax.set_ylabel('mAP@0.5', fontsize=12, fontweight='bold')
    ax.set_title('Per-Class Performance Comparison Across YOLO Models', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(class_order, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.0)

    plt.tight_layout()

    output_dir = Path("/home/tiago/repos/camina/outputs/model_comparison/visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_dir / "per_class_performance_comparison.png", dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_dir / "per_class_performance_comparison.png")

def create_overall_performance_radar():
    """Create radar chart for overall model performance"""

    real_metrics = load_real_metrics()
    model_order = ["YOLO11n", "YOLOv8n", "YOLOv10n", "YOLOv5n"]

    # Prepare data
    metrics = ['mAP@0.5', 'mAP@0.5:0.95', 'Precision', 'Recall']

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]  # Complete the circle

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    for i, model_name in enumerate(model_order):
        if model_name in real_metrics:
            overall = real_metrics[model_name]['overall_metrics']
            values = [
                overall['map50'],
                overall['map50_95'],
                overall['precision'],
                overall['recall']
            ]
            values += values[:1]  # Complete the circle

            ax.plot(angles, values, 'o-', linewidth=2, label=model_name, color=colors[i])
            ax.fill(angles, values, alpha=0.1, color=colors[i])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 1)
    ax.set_title('Overall Model Performance Comparison', y=1.08, fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
    ax.grid(True)

    output_dir = Path("/home/tiago/repos/camina/outputs/model_comparison/visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_dir / "overall_performance_radar.png", dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_dir / "overall_performance_radar.png")

def create_class_imbalance_impact():
    """Create visualization showing class imbalance impact"""

    real_metrics = load_real_metrics()

    class_instances = {
        "Person": 6975, "Car": 2105, "Cyclist": 2012, "E-scooter": 728,
        "SUV": 456, "Motorcyclist": 307, "Bus": 321, "Delivery Van": 112, "Truck": 132
    }

    class_order = ["Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery Van", "Truck"]
    model_order = ["YOLO11n", "YOLOv8n", "YOLOv10n", "YOLOv5n"]

    # Calculate average performance per class
    avg_performance = []
    instance_counts = []

    for class_name in class_order:
        class_performances = []
        for model_name in model_order:
            if model_name in real_metrics:
                ap = real_metrics[model_name]['class_wise_ap'].get(class_name, 0.0)
                class_performances.append(ap)

        if class_performances:
            avg_performance.append(np.mean(class_performances))
            instance_counts.append(class_instances[class_name])

    # Create scatter plot
    fig, ax = plt.subplots(figsize=(12, 8))

    scatter = ax.scatter(instance_counts, avg_performance, s=100, alpha=0.7, c=range(len(class_order)), cmap='viridis')

    # Add labels for each point
    for i, class_name in enumerate(class_order):
        ax.annotate(class_name, (instance_counts[i], avg_performance[i]),
                   xytext=(5, 5), textcoords='offset points', fontsize=10, fontweight='bold')

    # Add correlation line
    if len(instance_counts) > 1:
        z = np.polyfit(instance_counts, avg_performance, 1)
        p = np.poly1d(z)
        ax.plot(instance_counts, p(instance_counts), "r--", alpha=0.8, linewidth=2)

        # Calculate correlation
        correlation = np.corrcoef(instance_counts, avg_performance)[0, 1]
        ax.text(0.05, 0.95, f'Correlation: {correlation:.3f}', transform=ax.transAxes,
               fontsize=12, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.set_xlabel('Training Instances (log scale)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Average mAP@0.5', fontsize=12, fontweight='bold')
    ax.set_title('Class Imbalance Impact on Model Performance', fontsize=14, fontweight='bold')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    output_dir = Path("/home/tiago/repos/camina/outputs/model_comparison/visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_dir / "class_imbalance_impact.png", dpi=300, bbox_inches='tight')
    plt.close()

    return str(output_dir / "class_imbalance_impact.png")

def main():
    print("="*80)
    print("📊 CAMINA Performance Visualization Generation")
    print("="*80)

    # Create visualizations
    print("🎨 Creating per-class performance comparison...")
    per_class_plot = create_per_class_comparison()
    print(f"✅ Saved: {per_class_plot}")

    print("🎨 Creating overall performance radar chart...")
    radar_plot = create_overall_performance_radar()
    print(f"✅ Saved: {radar_plot}")

    print("🎨 Creating class imbalance impact analysis...")
    imbalance_plot = create_class_imbalance_impact()
    print(f"✅ Saved: {imbalance_plot}")

    print("="*80)
    print("📊 Visualization Generation Complete")
    print("="*80)

if __name__ == "__main__":
    main()