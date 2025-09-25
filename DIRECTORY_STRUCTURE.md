# CAMINA Repository Structure

## Overview
This repository contains the complete CAMINA (Computer-Aided Mobility Investigation and Analysis) system for urban mobility detection using YOLO models optimized for edge deployment.

## Directory Structure

```
camina/
├── README.md                     # Main project documentation
├── LICENSE                      # MIT License
├── requirements.txt             # Python dependencies
├── main.py                      # Main training pipeline
├── DIRECTORY_STRUCTURE.md       # This file
│
├── configs/                     # Configuration files
├── data/                        # Dataset and data management
│   ├── datasetV3_stratified/    # Main dataset (stratified split)
│   └── raw/                     # Raw data processing
│
├── model/                       # Trained models and deployment
│   ├── yolo_comparison/         # Comparative model training results
│   └── raspberry_pi_deployment_all/  # NCNN models for edge deployment
│
├── src/                         # Source code organized by functionality
│   ├── benchmarks/              # Performance benchmarking scripts
│   │   ├── benchmark_inference_simple.py
│   │   ├── benchmark_ncnn_inference.py
│   │   └── raspberry_pi_inference_test.py
│   │
│   ├── export/                  # Model export and optimization
│   │   ├── export_all_models_to_ncnn.py
│   │   ├── export_best_model_to_ncnn.py
│   │   └── optimize_to_ncnn.py
│   │
│   ├── inference/               # Inference utilities
│   │
│   └── visualization/           # Visualization and analysis
│       ├── create_corrected_detection_visualization.py
│       ├── create_detection_visualization.py
│       ├── create_updated_mosaic.py
│       └── debug_model_classes.py
│
├── tools/                       # Analysis and training utilities
│   ├── extract_only_real_metrics.py
│   ├── extract_real_ap50_only.py
│   ├── train_evaluate_yolo_models.py
│   ├── training_logger.py
│   └── train_with_improvements.py
│
├── experiments/                 # Experimental results and outputs
│   ├── test_benchmark.json
│   └── yolo11n_corrected_predictions_mosaic.png
│
├── outputs/                     # Training and analysis outputs
│   └── model_comparison/        # Model comparison results
│
├── paper/                       # Academic paper materials
│   ├── img/                     # Paper figures and images
│   └── sections/                # Paper sections and content
│
├── docs/                        # Additional documentation
├── tests/                       # Unit tests
├── scripts/                     # Utility scripts
├── runs/                        # Training run outputs
├── backup/                      # Backup files
└── venv/                        # Virtual environment (gitignored)
```

## Key Components

### Core Training (`main.py`)
Main pipeline for training YOLO models with the CAMINA dataset.

### Source Code (`src/`)
- **benchmarks/**: Performance testing and inference speed analysis
- **export/**: Model conversion to NCNN format for edge deployment
- **visualization/**: Detection result visualization and analysis
- **inference/**: Runtime inference utilities

### Models (`model/`)
- **yolo_comparison/**: Trained models (YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n)
- **raspberry_pi_deployment_all/**: NCNN-optimized models for Raspberry Pi 5

### Tools (`tools/`)
Analysis utilities for metrics extraction and training enhancement.

### Paper (`paper/`)
Academic paper materials including figures and documentation.

## Usage

### Training
```bash
python main.py
```

### Model Export
```bash
python src/export/export_all_models_to_ncnn.py
```

### Benchmarking
```bash
python src/benchmarks/raspberry_pi_inference_test.py --models-dir model/raspberry_pi_deployment_all
```

### Visualization
```bash
python src/visualization/create_detection_visualization.py
```

## Dependencies
See `requirements.txt` for Python package dependencies.

## License
MIT License - see LICENSE file for details.