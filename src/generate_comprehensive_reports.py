#!/usr/bin/env python3
"""
Generate comprehensive training reports for CAMINA YOLO models
Using REAL per-class metrics extracted from YOLO validation
"""

import json
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

def load_real_metrics():
    """Load the real per-class metrics from JSON"""
    json_file = Path("/home/tiago/repos/camina/outputs/model_comparison/results/real_perclass_metrics.json")

    if not json_file.exists():
        print(f"❌ Real metrics file not found: {json_file}")
        return None

    with open(json_file, 'r') as f:
        return json.load(f)

def generate_model_performance_comparison():
    """Generate comprehensive model comparison report"""

    real_metrics = load_real_metrics()
    if not real_metrics:
        return

    report = f"""# CAMINA YOLO Model Performance Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Executive Summary

This report presents comprehensive performance analysis of four YOLO models trained on the CAMINA urban mobility dataset. All metrics are extracted directly from YOLO validation results.

### Dataset Overview
- **Total Classes**: 9 urban mobility classes
- **Training Strategy**: 150 epochs per model
- **Dataset Split**: 80/20 train-validation
- **Key Challenge**: Severe class imbalance (Person: 6,975 vs Delivery Van: 112 instances)

"""

    # Overall performance comparison
    report += "## Overall Model Performance\n\n"
    report += "| Model | Overall mAP@0.5 | Overall mAP@0.5-0.95 | Precision | Recall |\n"
    report += "|-------|-----------------|----------------------|-----------|--------|\n"

    model_order = ["YOLO11n", "YOLOv8n", "YOLOv10n", "YOLOv5n"]

    for model_name in model_order:
        if model_name in real_metrics:
            metrics = real_metrics[model_name]['overall_metrics']
            report += f"| **{model_name}** | {metrics['map50']:.3f} | {metrics['map50_95']:.3f} | {metrics['precision']:.3f} | {metrics['recall']:.3f} |\n"

    # Performance insights
    best_model = max(real_metrics.keys(), key=lambda x: real_metrics[x]['overall_metrics']['map50'])
    report += f"\n### Key Findings\n"
    report += f"- **Best Overall Performance**: {best_model} (mAP@0.5: {real_metrics[best_model]['overall_metrics']['map50']:.3f})\n"
    report += f"- **Performance Range**: {min(real_metrics[m]['overall_metrics']['map50'] for m in real_metrics):.3f} - {max(real_metrics[m]['overall_metrics']['map50'] for m in real_metrics):.3f}\n"

    # Per-class analysis
    report += "\n## Per-Class Performance Analysis\n\n"

    class_instances = {
        "Person": 6975, "Car": 2105, "Cyclist": 2012, "E-scooter": 728,
        "SUV": 456, "Motorcyclist": 307, "Bus": 321, "Delivery Van": 112, "Truck": 132
    }

    class_order = ["Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery Van", "Truck"]

    # Class performance insights
    for class_name in class_order:
        instances = class_instances.get(class_name, 0)
        report += f"\n### {class_name} ({instances:,} instances)\n"

        class_aps = []
        for model_name in model_order:
            if model_name in real_metrics:
                ap = real_metrics[model_name]['class_wise_ap'].get(class_name, 0.0)
                class_aps.append((model_name, ap))

        class_aps.sort(key=lambda x: x[1], reverse=True)
        best_model_class = class_aps[0][0]
        best_ap = class_aps[0][1]
        worst_ap = class_aps[-1][1]

        report += f"- **Best Model**: {best_model_class} (AP@0.5: {best_ap:.3f})\n"
        report += f"- **Performance Range**: {worst_ap:.3f} - {best_ap:.3f}\n"

        # Performance interpretation
        if best_ap > 0.7:
            report += f"- **Assessment**: Excellent detection performance\n"
        elif best_ap > 0.5:
            report += f"- **Assessment**: Good detection performance\n"
        elif best_ap > 0.3:
            report += f"- **Assessment**: Moderate performance, room for improvement\n"
        else:
            report += f"- **Assessment**: Challenging class, likely affected by class imbalance\n"

    # Class imbalance impact analysis
    report += "\n## Class Imbalance Impact Analysis\n\n"

    # Calculate correlation between instances and performance
    instance_counts = []
    avg_performances = []

    for class_name in class_order:
        instances = class_instances.get(class_name, 0)
        class_performances = []

        for model_name in model_order:
            if model_name in real_metrics:
                ap = real_metrics[model_name]['class_wise_ap'].get(class_name, 0.0)
                class_performances.append(ap)

        if class_performances:
            instance_counts.append(instances)
            avg_performances.append(np.mean(class_performances))

    if len(instance_counts) > 1:
        correlation = np.corrcoef(instance_counts, avg_performances)[0, 1]
        report += f"**Instance Count vs Performance Correlation**: {correlation:.3f}\n\n"

        if correlation > 0.3:
            report += "**Finding**: Strong positive correlation between training instances and model performance.\n"
            report += "Classes with fewer instances (Delivery Van, Truck) show significantly lower detection performance.\n\n"

    # Recommendations
    report += "## Recommendations\n\n"
    report += "### Model Selection\n"
    report += f"- **Recommended Model**: {best_model} for overall best performance\n"
    report += f"- **Alternative**: Consider ensemble approach for improved robustness\n\n"

    report += "### Dataset Improvements\n"
    report += "1. **Address Class Imbalance**: Collect more samples for underperforming classes (Delivery Van, Truck)\n"
    report += "2. **Data Augmentation**: Apply class-specific augmentation strategies\n"
    report += "3. **Synthetic Data**: Consider synthetic sample generation for rare classes\n\n"

    report += "### Training Improvements\n"
    report += "1. **Class Weights**: Implement inverse frequency weighting\n"
    report += "2. **Focal Loss**: Consider focal loss to address class imbalance\n"
    report += "3. **Extended Training**: Longer training might benefit underperforming classes\n\n"

    report += "---\n"
    report += "*This report is based on real YOLO validation metrics extracted directly from model outputs.*\n"

    return report

def generate_latex_table():
    """Generate LaTeX formatted table for academic publication"""

    real_metrics = load_real_metrics()
    if not real_metrics:
        return ""

    latex_content = """\\begin{table}[htbp]
\\centering
\\caption{Per-Class Performance Analysis of YOLO Models on CAMINA Dataset}
\\label{tab:perclass_performance}
\\resizebox{\\textwidth}{!}{%
\\begin{tabular}{l|r|cccc|cccc|cccc|cccc}
\\hline
\\multirow{2}{*}{\\textbf{Class}} & \\multirow{2}{*}{\\textbf{Instances}} &
\\multicolumn{4}{c|}{\\textbf{YOLO11n}} &
\\multicolumn{4}{c|}{\\textbf{YOLOv10n}} &
\\multicolumn{4}{c|}{\\textbf{YOLOv5n}} &
\\multicolumn{4}{c}{\\textbf{YOLOv8n}} \\\\
\\cline{3-18}
& & Prec & mAP & Rec & F1 & Prec & mAP & Rec & F1 & Prec & mAP & Rec & F1 & Prec & mAP & Rec & F1 \\\\
\\hline
"""

    class_instances = {
        "Person": 6975, "Car": 2105, "Cyclist": 2012, "E-scooter": 728,
        "SUV": 456, "Motorcyclist": 307, "Bus": 321, "Delivery Van": 112, "Truck": 132
    }

    class_order = ["Person", "Cyclist", "Car", "E-scooter", "SUV", "Motorcyclist", "Bus", "Delivery Van", "Truck"]
    model_order = ["YOLO11n", "YOLOv10n", "YOLOv5n", "YOLOv8n"]

    for class_name in class_order:
        instances = class_instances.get(class_name, 0)
        latex_content += f"\\textbf{{{class_name}}} & {instances:,} "

        for model_name in model_order:
            if model_name in real_metrics:
                model_data = real_metrics[model_name]
                precision = model_data.get('class_wise_precision', {}).get(class_name, 0.0)
                ap = model_data.get('class_wise_ap', {}).get(class_name, 0.0)
                recall = model_data.get('class_wise_recall', {}).get(class_name, 0.0)
                f1 = model_data.get('class_wise_f1', {}).get(class_name, 0.0)

                latex_content += f"& {precision:.3f} & {ap:.3f} & {recall:.3f} & {f1:.3f} "

        latex_content += "\\\\\n"

    latex_content += """\\hline
\\end{tabular}%
}
\\end{table}

\\begin{table}[htbp]
\\centering
\\caption{Overall Model Performance Summary}
\\label{tab:overall_performance}
\\begin{tabular}{l|cccc}
\\hline
\\textbf{Model} & \\textbf{mAP@0.5} & \\textbf{mAP@0.5:0.95} & \\textbf{Precision} & \\textbf{Recall} \\\\
\\hline
"""

    for model_name in model_order:
        if model_name in real_metrics:
            metrics = real_metrics[model_name]['overall_metrics']
            latex_content += f"\\textbf{{{model_name}}} & {metrics['map50']:.3f} & {metrics['map50_95']:.3f} & {metrics['precision']:.3f} & {metrics['recall']:.3f} \\\\\n"

    latex_content += """\\hline
\\end{tabular}
\\end{table}"""

    return latex_content

def main():
    print("="*80)
    print("🎯 CAMINA Comprehensive Training Report Generation")
    print("="*80)

    # Generate comprehensive report
    report_content = generate_model_performance_comparison()

    if report_content:
        # Save comprehensive report
        output_dir = Path("/home/tiago/repos/camina/outputs/model_comparison")
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / "comprehensive_training_report.md"
        with open(report_file, 'w') as f:
            f.write(report_content)

        print(f"✅ Comprehensive report saved to: {report_file}")

        # Generate LaTeX table
        latex_content = generate_latex_table()
        if latex_content:
            latex_file = output_dir / "tables" / "performance_tables.tex"
            latex_file.parent.mkdir(parents=True, exist_ok=True)
            with open(latex_file, 'w') as f:
                f.write(latex_content)

            print(f"✅ LaTeX tables saved to: {latex_file}")

    print("="*80)
    print("📊 Report Generation Complete")
    print("="*80)

if __name__ == "__main__":
    main()