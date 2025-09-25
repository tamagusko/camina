# CAMINA YOLO Model Training and Comparison Guide

This guide provides complete commands to train YOLO models and generate comprehensive comparison reports for the CAMINA urban mobility detection project.

## Quick Start - Complete Pipeline

### Option 1: Full Training + Analysis (if starting fresh)
```bash
# Step 1: Train all YOLO models (150 epochs each) - Takes ~8-12 hours
python train_evaluate_yolo_models.py

# Step 2: Extract real per-class metrics from trained models
python extract_real_perclass_metrics.py

# Step 3: Generate comprehensive reports and LaTeX tables
python generate_comprehensive_reports.py

# Step 4: Create performance visualizations
python generate_performance_visualizations.py
```

### Option 2: Analysis Only (if models already trained)
```bash
# Complete analysis pipeline - Takes ~5-10 minutes
python extract_real_perclass_metrics.py && \
python generate_comprehensive_reports.py && \
python generate_performance_visualizations.py
```

## Individual Script Functions

### 1. Training Script
```bash
python train_evaluate_yolo_models.py
```
**Purpose:** Trains all 4 YOLO models (YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n)
- **Duration:** 8-12 hours total
- **Output:** Trained model weights in `models/yolo_comparison/*/train/weights/best.pt`
- **Training:** 150 epochs per model on 80/20 train-validation split

### 2. Real Metrics Extraction
```bash
python extract_real_perclass_metrics.py
```
**Purpose:** Extracts actual per-class AP@0.5 values from YOLO validation
- **Duration:** 2-3 minutes
- **Critical Fix:** Corrects Table 2 per-class mAP@0.5 values (was showing overall metrics)
- **Outputs:**
  - `outputs/model_comparison/results/real_perclass_metrics.json`
  - `outputs/model_comparison/tables/table2_REAL_perclass_metrics.md`

### 3. Comprehensive Report Generation
```bash
python generate_comprehensive_reports.py
```
**Purpose:** Creates detailed academic analysis reports
- **Duration:** 1 minute
- **Outputs:**
  - `outputs/model_comparison/comprehensive_training_report.md`
  - `outputs/model_comparison/tables/performance_tables.tex` (LaTeX for papers)

### 4. Performance Visualizations
```bash
python generate_performance_visualizations.py
```
**Purpose:** Creates performance comparison charts
- **Duration:** 1-2 minutes
- **Outputs:** All saved to `outputs/model_comparison/visualizations/`
  - `per_class_performance_comparison.png`
  - `overall_performance_radar.png`
  - `class_imbalance_impact.png`

## Output Directory Structure

After running all scripts, you'll have:

```
outputs/model_comparison/
├── comprehensive_training_report.md          # Detailed analysis report
├── results/
│   └── real_perclass_metrics.json           # Raw validation metrics
├── tables/
│   ├── table2_REAL_perclass_metrics.md      # Corrected Table 2
│   └── performance_tables.tex               # LaTeX tables for papers
└── visualizations/
    ├── per_class_performance_comparison.png  # Bar chart comparison
    ├── overall_performance_radar.png         # Radar chart
    └── class_imbalance_impact.png           # Scatter plot analysis
```

## Key Features

### ✅ Real Per-Class Metrics
- Extracts actual per-class AP@0.5 values (not overall metrics)
- Shows true performance differences:
  - **E-scooter**: 0.879-0.908 (excellent)
  - **Cyclist**: 0.561-0.589 (good)
  - **Person**: 0.452-0.479 (moderate)
  - **Delivery Van**: 0.081-0.185 (poor due to class imbalance)

### ✅ Academic Publication Ready
- LaTeX formatted tables
- Comprehensive performance analysis
- Class imbalance impact analysis
- Model recommendations

### ✅ Complete Dataset Analysis
- 9 urban mobility classes
- Severe class imbalance (Person: 6,975 vs Delivery Van: 112 instances)
- 80/20 train-validation split
- Instance count vs performance correlation analysis

## Results Summary

**Best Overall Model:** YOLO11n (mAP@0.5: 0.563)

**Model Performance Ranking:**
1. YOLO11n: 0.563
2. YOLOv8n: 0.560
3. YOLOv5n: 0.550
4. YOLOv10n: 0.543

**Class Performance Insights:**
- **Best Detected**: E-scooter (excellent performance across all models)
- **Most Challenging**: Delivery Van, Truck (affected by class imbalance)
- **Moderate Performance**: Person, Car, Cyclist (room for improvement)

## Requirements

Ensure these packages are installed:
```bash
pip install ultralytics numpy matplotlib pandas seaborn pathlib
```

## Dataset Information

- **Classes**: Person, Cyclist, Car, E-scooter, SUV, Motorcyclist, Bus, Delivery Van, Truck
- **Total Instances**: 13,153 annotations
- **Severe Imbalance**: 62.3:1 ratio (Person:Delivery Van)
- **Training Strategy**: 150 epochs, batch size optimized per model

## Troubleshooting

**If training fails:**
- Check CUDA/GPU availability
- Verify dataset paths in `data/datasetV3_stratified/data.yaml`
- Ensure sufficient disk space (~10GB for all models)

**If analysis fails:**
- Ensure model weights exist in `models/yolo_comparison/*/train/weights/best.pt`
- Check that training completed successfully for all 4 models

---

*Generated for CAMINA Urban Mobility Detection Project*
*All scripts extract real YOLO validation metrics for accurate academic reporting*