# CAMINA Training Guide

Comprehensive guide for training YOLO models with CAMINA datasets for academic research.

## Overview

Train and compare YOLOv5n, YOLOv8n, YOLOv10n, and YOLO11n models using your urban mobility datasets. This guide provides the academic training pipeline for generating quantitative results.

## Prerequisites

- Python virtual environment with ultralytics
- NVIDIA GPU with 8GB+ memory
- Dataset in YOLOv11 format (640x640 images)
- At least 1000+ annotated images

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv_yolo
source venv_yolo/bin/activate

# Install dependencies
pip install ultralytics numpy pandas matplotlib seaborn rich pyyaml psutil
```

### 2. Prepare Dataset

Ensure your dataset follows YOLOv11 structure:
```
data/dataset_v4i_yolov11/
├── train/
│   ├── images/
│   └── labels/
├── val/
│   ├── images/
│   └── labels/
└── data.yaml
```

### 3. Run Training Pipeline

```bash
# Activate environment and run
source venv_yolo/bin/activate
python train_evaluate_yolo_models.py
```

## Training Configuration

### Model Settings (640x640 Roboflow compatible)
- **Image size**: 640x640 pixels
- **Batch size**: 16 (adjust based on GPU memory)
- **Epochs**: 100 with early stopping (patience: 50)
- **Workers**: 8 parallel data loading threads

### Identical Parameters Across Models
```python
ModelConfig(
    epochs=100,
    batch_size=16,
    imgsz=640,          # Roboflow standard
    patience=50,
    save_period=10,
    workers=8,
    device="auto"
)
```

## Expected Results

### Academic Tables Generated

#### Table 2: Per-Class Detection Performance (mAP@0.5)
| Class | New Definition | mAP@0.5 | Instances |
|-------|----------------|---------|-----------|
| Pedestrian | No (COCO) | [Generated] | [Count] |
| Cyclist | Yes (rule-based) | [Generated] | [Count] |
| car | No (COCO) | [Generated] | [Count] |
| E-scooter | Yes (open-vocabulary) | [Generated] | [Count] |
| SUV | Yes (open-vocabulary) | [Generated] | [Count] |
| Motorcyclist | COCONUT | [Generated] | [Count] |
| bus | COCONUT | [Generated] | [Count] |
| Delivery Van | Yes (open-vocabulary) | [Generated] | [Count] |
| truck | COCONUT | [Generated] | [Count] |

#### Table 3: Model Comparison
| Model | mAP@0.5 | Model Size (MB) | Video FPS | Training Time (hrs) |
|-------|---------|-----------------|-----------|-------------------|
| YOLOv5n | [Generated] | [Generated] | [Generated] | [Generated] |
| YOLOv8n | [Generated] | [Generated] | [Generated] | [Generated] |
| YOLOv10n | [Generated] | [Generated] | [Generated] | [Generated] |
| YOLO11n | [Generated] | [Generated] | [Generated] | [Generated] |

## Output Structure

```
models/yolo_comparison/
├── YOLOv5n/
│   ├── train/results.csv
│   ├── best.pt
│   └── training_plots/
├── YOLOv8n/
├── YOLOv10n/
├── YOLO11n/
└── comparison_report.md

outputs/model_comparison/
├── results/
│   ├── academic_tables.csv
│   └── performance_metrics.json
├── plots/
│   ├── model_comparison.png
│   └── per_class_performance.png
└── logs/
    └── training_log_[timestamp].txt
```

## Advanced Configuration

### GPU Memory Optimization
```python
# For 8GB GPU
batch_size = 16

# For 6GB GPU
batch_size = 8

# For 4GB GPU
batch_size = 4
```

### Custom Dataset Paths
```python
# Update dataset path in script
dataset_path = Path("your/custom/dataset/path")
```

### Training Hyperparameters
```yaml
# Modify in training script if needed
lr0: 0.01                    # Initial learning rate
lrf: 0.01                    # Final learning rate
momentum: 0.937              # SGD momentum
weight_decay: 0.0005         # Optimizer weight decay
warmup_epochs: 3.0           # Warmup epochs
warmup_momentum: 0.8         # Warmup initial momentum
```

## Performance Benchmarks

### Expected Training Times (RTX 3060)
- **YOLOv5n**: ~45 minutes (1200 images, 100 epochs)
- **YOLOv8n**: ~50 minutes
- **YOLOv10n**: ~55 minutes
- **YOLO11n**: ~60 minutes

### Model Sizes
- **YOLOv5n**: ~4MB
- **YOLOv8n**: ~6MB
- **YOLOv10n**: ~5MB
- **YOLO11n**: ~5MB

### Expected mAP@0.5 Ranges
- **Urban mobility datasets**: 0.4-0.7
- **Well-annotated datasets**: 0.6-0.8
- **Challenging datasets**: 0.3-0.5

## Troubleshooting

### CUDA Out of Memory
```bash
# Reduce batch size
batch_size = 8  # or 4 for very limited memory
```

### Training Not Converging
```python
# Adjust learning rate
lr0 = 0.005  # Lower initial learning rate
patience = 100  # Increase patience
```

### Model Loading Errors
```bash
# Clear cache and restart
rm -rf ~/.cache/torch/hub/ultralytics*
python train_evaluate_yolo_models.py
```

### Poor Performance Results
1. **Check dataset quality**: Verify annotations are correct
2. **Increase training data**: Add more diverse samples
3. **Adjust confidence thresholds**: Lower for recall, higher for precision
4. **Review class distribution**: Ensure balanced dataset

## Academic Usage

### Citation Format
```bibtex
@misc{camina_training_2024,
  title={CAMINA YOLO Training Pipeline},
  author={Your Name},
  year={2024},
  note={Academic training methodology for urban mobility detection}
}
```

### Reproducibility Guidelines
1. **Fixed random seeds**: Set in training script
2. **Identical hyperparameters**: Same across all models
3. **Same dataset splits**: Consistent train/val division
4. **Environment documentation**: Python/CUDA versions recorded

### Statistical Analysis
- **Confidence intervals**: Report ±1 standard deviation
- **Multiple runs**: Average results across 3+ training runs
- **Significance testing**: Use appropriate statistical tests
- **Cross-validation**: Consider k-fold for small datasets

## Integration with CAMINA

### Using Trained Models
```python
# Replace default models in main.py
detection_stages:
  stage_a:
    model_path: models/yolo_comparison/YOLO11n/best.pt
```

### Custom Class Mappings
```yaml
# Update class names if needed
class_names: [person, cyclist, car, motorcycle, bus, truck]
class_mapping: {0: 'person', 1: 'cyclist', ...}
```

### Performance Evaluation
```bash
# Test trained models on CAMINA pipeline
python main.py --model models/yolo_comparison/YOLO11n/best.pt --input test_data/
```

## Best Practices

### Dataset Preparation
- **Minimum 1000 images** per class for reliable training
- **Balanced distribution** across classes
- **High-quality annotations** with consistent labeling
- **Diverse scenarios** (lighting, weather, angles)

### Training Strategy
- **Monitor validation loss** for overfitting
- **Save checkpoints** every 10 epochs
- **Early stopping** to prevent overfitting
- **Learning rate scheduling** for optimal convergence

### Model Selection
- **Compare multiple metrics**: mAP@0.5, mAP@0.5:0.95, precision, recall
- **Consider inference speed** for deployment scenarios
- **Evaluate model size** for edge deployment
- **Test on held-out dataset** for unbiased evaluation

### Results Reporting
- **Include all metrics** in academic tables
- **Report confidence intervals** for statistical rigor
- **Document training conditions** for reproducibility
- **Compare with baseline methods** for context