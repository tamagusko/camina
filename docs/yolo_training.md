# CAMINA YOLO Model Training and Evaluation Pipeline

## Overview

This pipeline provides a comprehensive, academic-grade training and evaluation system for comparing YOLO models (YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n) on the CAMINA urban mobility dataset. The system is designed to generate quantitative results for academic paper submission with rigorous experimental methodology.

## Dataset Information

- **Classes**: 6 classes (bus, car, cyclist, motorcycle, person, truck)
- **Training Images**: 1,223 images
- **Test Images**: 72 images
- **Format**: YOLO format with absolute paths
- **Location**: `data/dataset_v4i_yolov11/`

## Features

### 🎯 Academic Requirements Met
- **Table 2**: Per-Class Detection Performance (mAP@0.5) with instance counts
- **Table 3**: Model Comparison (mAP@0.5, Model Size MB, Video FPS, Training Time hrs)
- **Rigorous Methodology**: Identical training parameters across all models
- **Reproducibility**: Comprehensive system information and experimental logs

### 🔬 Scientific Approach
- Function-based architecture (no classes) for clarity
- Comprehensive error handling and progress tracking
- Academic-quality results tables ready for paper inclusion
- Performance visualization plots and confusion matrices
- Detailed experimental reports with system specifications

### 📊 Metrics Calculated
- **Performance**: mAP@0.5, mAP@0.5-0.95 per class and overall
- **Efficiency**: Model size (MB), Inference speed (FPS), Training time (hours)
- **Dataset**: Instance counts per class for statistical significance
- **System**: Hardware specifications for reproducibility

## Quick Start

### Prerequisites
```bash
# Install required packages
pip install -r requirements.txt

# Verify installation
python3 verify_installation.py
```

### Run Complete Pipeline
```bash
# Execute the full training and evaluation pipeline
./run_yolo_comparison.sh
```

### Manual Execution
```bash
# Run Python script directly
python3 train_evaluate_yolo_models.py
```

## Expected Runtime

| Hardware | Expected Time | Notes |
|----------|---------------|-------|
| RTX 3060 (12GB) | 2-4 hours | Recommended configuration |
| RTX 4090 (24GB) | 1-2 hours | Optimal performance |
| CPU Only | 8-12 hours | Not recommended for production |

## Output Structure

```
outputs/model_comparison/
├── models/                     # Trained model weights
│   ├── YOLOv5n/
│   ├── YOLOv8n/
│   ├── YOLOv10n/
│   └── YOLO11n/
├── tables/                     # Academic tables (CSV format)
│   ├── table2_per_class_performance.csv
│   └── table3_model_comparison.csv
├── plots/                      # Performance visualizations
│   ├── model_comparison_plots.png
│   └── per_class_performance_heatmap.png
├── results/                    # Comprehensive reports
│   ├── comprehensive_experimental_report.json
│   └── experiment_summary.json
└── logs/                       # Training logs
    └── yolo_comparison_YYYYMMDD_HHMMSS.log
```

## Academic Table Formats

### Table 2: Per-Class Detection Performance (mAP@0.5)
| Class | Instances | YOLOv5n | YOLOv8n | YOLOv10n | YOLO11n |
|-------|-----------|---------|---------|----------|---------|
| bus | X | 0.XXX | 0.XXX | 0.XXX | 0.XXX |
| car | X | 0.XXX | 0.XXX | 0.XXX | 0.XXX |
| cyclist | X | 0.XXX | 0.XXX | 0.XXX | 0.XXX |
| motorcycle | X | 0.XXX | 0.XXX | 0.XXX | 0.XXX |
| person | X | 0.XXX | 0.XXX | 0.XXX | 0.XXX |
| truck | X | 0.XXX | 0.XXX | 0.XXX | 0.XXX |
| Average | | 0.XXX | 0.XXX | 0.XXX | 0.XXX |

### Table 3: Model Comparison
| Model | mAP@0.5 | Model Size (MB) | Video FPS | Training Time (hrs) |
|-------|---------|-----------------|-----------|-------------------|
| YOLOv5n | 0.XXX | XX.X | XX.X | X.X |
| YOLOv8n | 0.XXX | XX.X | XX.X | X.X |
| YOLOv10n | 0.XXX | XX.X | XX.X | X.X |
| YOLO11n | 0.XXX | XX.X | XX.X | X.X |

## Technical Specifications

### Training Parameters (Identical Across All Models)
- **Epochs**: 100
- **Batch Size**: 16
- **Image Size**: 640x640
- **Patience**: 50 (early stopping)
- **Workers**: 8
- **Device**: Auto-detection (GPU preferred)

### Evaluation Metrics
- **mAP@0.5**: Primary metric for academic comparison
- **mAP@0.5-0.95**: Comprehensive IoU range evaluation
- **Inference FPS**: Measured on first 100 test images
- **Model Size**: Actual file size of best.pt weights
- **Training Time**: Wall-clock time in hours

## Reproducibility Features

### System Information Captured
- CPU count and memory specifications
- GPU model and VRAM capacity
- Python and PyTorch versions
- CUDA version and availability
- Timestamp and experimental conditions

### Experimental Controls
- Fixed random seeds (where applicable)
- Identical hyperparameters across models
- Standardized evaluation procedures
- Comprehensive logging of all operations

## Usage for Paper Submission

1. **Run Pipeline**: Execute `./run_yolo_comparison.sh`
2. **Collect Tables**: Use CSV files from `outputs/model_comparison/tables/`
3. **Include Plots**: Use PNG files from `outputs/model_comparison/plots/`
4. **Cite Methods**: Reference the training parameters and evaluation methodology
5. **Report System**: Include hardware specifications from the comprehensive report

## Customization Options

### Modify Training Parameters
Edit the `ModelConfig` dataclass in `train_evaluate_yolo_models.py`:
```python
@dataclass
class ModelConfig:
    epochs: int = 200        # Increase for longer training
    batch_size: int = 32     # Adjust based on GPU memory
    imgsz: int = 832         # Higher resolution
    patience: int = 100      # More patience for convergence
```

### Add Additional Models
Extend the `model_configs` list in `main()`:
```python
model_configs = [
    ModelConfig(name="YOLOv5s", model_path="yolov5s.pt"),
    ModelConfig(name="YOLOv8s", model_path="yolov8s.pt"),
    # Add more models as needed
]
```

### Custom Dataset
Update the dataset path in `main()`:
```python
dataset_path = Path("path/to/your/dataset")
```

## Troubleshooting

### Common Issues

1. **CUDA Out of Memory**
   - Reduce batch size: Set `batch_size = 8` or `batch_size = 4`
   - Use smaller image size: Set `imgsz = 416`

2. **Slow Training**
   - Increase workers: Set `workers = 16` (if CPU cores available)
   - Ensure GPU is being used: Check CUDA availability

3. **Dataset Errors**
   - Verify `data.yaml` paths are absolute
   - Check image and label file counts match
   - Ensure proper YOLO format labels

### Debug Mode
Add verbose logging by modifying the logging level:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Performance Optimization

### For Academic Use
- Use default settings for fair comparison
- Ensure identical conditions across all models
- Document any modifications in your paper

### For Production Use
- Increase epochs for better convergence
- Use larger models (YOLOv8s, YOLOv8m) for higher accuracy
- Implement model ensemble techniques
- Use advanced augmentation strategies

## Citation

When using this pipeline for academic work, please cite:
- The CAMINA project
- The specific YOLO model implementations from Ultralytics
- Your experimental methodology based on this pipeline

## Support

For issues with this pipeline:
1. Check the log files in `logs/`
2. Verify system requirements and dependencies
3. Review the troubleshooting section
4. Check Ultralytics documentation for YOLO-specific issues

## License

This pipeline is part of the CAMINA project and follows the same licensing terms.