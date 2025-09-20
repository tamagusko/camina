# CAMINA Models Directory

This directory contains all trained and pre-trained models used in the CAMINA project, organized by type and purpose.

## Directory Structure

### `camina/`
Contains CAMINA-specific trained models and their derivatives:
- `20250629_warmup_best.pt` - Best performing CAMINA model checkpoint
- `20250629_warmup_best.torchscript` - TorchScript version for deployment
- `20250629_warmup_best_ncnn_model/` - NCNN optimized model for mobile/edge deployment
- `yolo11n_ncnn_model/` - NCNN optimized YOLOv11n model

### `yolo_base/`
Contains base YOLO models used for training and comparison:
- `yolo11n.pt` - YOLOv11 nano model
- `yolo11l.pt` - YOLOv11 large model
- `yolo11m.pt` - YOLOv11 medium model
- `yolov8n.pt` - YOLOv8 nano model
- `yolov5nu.pt` - YOLOv5 nano-ultralytics model

### `yolo_world/`
Contains YOLO-World models for open-vocabulary object detection:
- `yolov8s-world*.pt` - YOLOv8 small world models
- `yolov8m-world*.pt` - YOLOv8 medium world models
- `yolov8l-world*.pt` - YOLOv8 large world models
- `groundingdino_swint_ogc.pth` - Grounding DINO model for text-guided detection

### `yolo_comparison/`
Contains results and trained models from the YOLO comparison study.

## Usage

Models are referenced in scripts using relative paths from the project root:
```python
# Example usage
model = YOLO("models/yolo_base/yolo11n.pt")
```

## Model Download

Most base models will be automatically downloaded by Ultralytics on first use. For custom models, ensure they are placed in the appropriate subdirectory.