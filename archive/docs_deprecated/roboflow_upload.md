# CAMINA Roboflow Data Preparation

Prepare CAMINA pipeline results for Roboflow upload in YOLOv11 format with academic reports.

## Quick Start

1. **Run CAMINA pipeline:**
   ```bash
   ./run.sh                    # Complete pipeline
   # or
   ./run_imagenet.sh          # YOLO-World only
   ```

2. **Prepare data for Roboflow:**
   ```bash
   python prepared_data_roboflow.py
   ```

3. **Find results in:**
   ```
   roboflow_datasets/
   ├── [dataset-name]/
   │   ├── data.yaml           # YOLOv11 config
   │   ├── images/train,val/   # Organized images
   │   ├── labels/train,val/   # YOLO format labels
   │   ├── DATASET_REPORT.md   # Summary statistics
   │   └── ACADEMIC_REPORT.md  # Paper-ready analysis
   ```

## What It Does

- ✅ **Formats data** in YOLOv11 structure
- ✅ **Generates academic reports** with statistics
- ✅ **Creates upload instructions**
- ✅ **Validates data integrity**
- ✅ **Function-based implementation** for simplicity and maintainability

## Datasets

| Dataset | Source | Features | Classes |
|---------|--------|----------|----------|
| Complete Pipeline | `./run.sh` | Stage A+B, e-scooter logic, NMS | All 9 classes |
| YOLO-World Only | `./run_imagenet.sh` | YOLO-World detection only | 3 classes |

## Documentation

📖 **Detailed Guides:**
- [Dataset Details](docs/DATASET_DETAILS.md) - Complete dataset specifications
- [Academic Reports](docs/ACADEMIC_REPORTS.md) - Report formats and usage
- [Manual Upload Guide](docs/ROBOFLOW_UPLOAD.md) - Step-by-step upload instructions
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Classes Detected

**All 9 CAMINA Classes:**
```
0: person, 1: cyclist, 2: car, 3: motorcycle, 4: bus,
5: truck, 6: e-scooter, 7: SUV, 8: delivery_van
```

## Architecture

The script has been optimized with a **function-based architecture** for better maintainability:

- **Single main function** `prepare_dataset()` handles all dataset preparation
- **Focused utility functions** for specific tasks (file copying, report generation, validation)
- **Clear separation of concerns** between data processing and report generation
- **Simple configuration** via function parameters instead of complex classes

## Requirements

- Python 3.8+
- No additional dependencies (uses standard library only)
- Completed CAMINA pipeline runs (./run.sh or ./run_imagenet.sh)
