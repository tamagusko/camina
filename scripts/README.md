# CAMINA Scripts

This directory contains shell scripts for running various CAMINA workflows.

## Available Scripts

### `run.sh`
Complete CAMINA detection pipeline that processes all images in `data/images/` and generates:
- COCO format annotations
- YOLO format labels
- Preview visualizations
- Summary statistics

**Usage:**
```bash
./scripts/run.sh
```

**Features:**
- E-scooter spatial association (person + e-scooter → combined bbox)
- SUV priority over car in overlaps
- Delivery_van priority over truck in overlaps
- Cyclist logic (person + bicycle → cyclist)
- NMS consolidation with class priorities

### `run_yolo_comparison.sh`
Academic-grade YOLO model training and evaluation pipeline for paper submission.
Trains and evaluates YOLOv5n, YOLOv8n, YOLOv10n, and YOLO11n models.

**Usage:**
```bash
./scripts/run_yolo_comparison.sh
```

**Duration:** 2-8 hours depending on hardware
**Output:** Academic tables ready for paper submission

### `run_escooter.sh`
Specialized pipeline for e-scooter detection tasks.

### `run_imagenet.sh`
ImageNet-based evaluation and testing pipeline.

## Requirements

- Python environment with CAMINA dependencies installed
- GPU recommended for model training
- Sufficient disk space for datasets and outputs

## Output Locations

- **Detection results:** `outputs/mixed/`
- **Model comparison:** `outputs/model_comparison/`
- **Logs:** `logs/`
- **Preview images:** `outputs/*/previews/`