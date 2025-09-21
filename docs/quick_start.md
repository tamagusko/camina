# CAMINA Quick Start Guide

Get started with CAMINA urban mobility object detection in minutes.

## Prerequisites

- Python 3.8+
- NVIDIA GPU with CUDA support
- 8GB+ GPU memory recommended

## Installation

1. **Clone repository:**
   ```bash
   git clone https://github.com/your-repo/camina.git
   cd camina
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv_camina
   source venv_camina/bin/activate  # Linux/Mac
   # or
   venv_camina\Scripts\activate     # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install ultralytics rich pyyaml opencv-python pillow
   ```

## Basic Usage

### Single Image Detection
```bash
python main.py --input path/to/image.jpg --output results/
```

### Batch Processing
```bash
python main.py --input path/to/images/ --output results/ --batch
```

### Video Processing
```bash
python main.py --input path/to/video.mp4 --output results/
```

## Expected Results

CAMINA detects 9 classes:
- **Stage A (YOLO11n)**: person, car, motorcycle, bus, truck
- **Cyclist Logic**: person + bicycle → cyclist
- **Stage B (YOLO-World)**: e-scooter, SUV, delivery_van

## Configuration

Basic configuration in `configs/config.yaml`:

```yaml
detection_stages:
  stage_a:
    model_path: models/yolo_base/yolo11n.pt
    confidence_threshold: 0.25
  stage_b:
    model_path: models/yolo_world/yolov8s-world.pt
    confidence_threshold: 0.35

cyclist_detection:
  enabled: true
  iou_threshold: 0.20
  spatial_margin: 5

nms_consolidation:
  enabled: true
  iou_threshold: 0.35
  class_priority: [6, 7, 8, 1, 0, 2, 3, 4, 5]
```

## Output Structure

```
results/
├── detections/              # YOLO format labels
├── dataset_viz/             # Visualized images
├── yolo/                    # Stage outputs
└── performance_report.json  # Processing statistics
```

## Next Steps

- 📖 **[User Guide](user_guide.md)** - Detailed usage instructions
- ⚙️ **[Configuration](configuration.md)** - Advanced settings
- 🔧 **[Training Guide](training_guide.md)** - Model training
- 📊 **[Performance](optimization.md)** - Optimization tips

## Troubleshooting

### Common Issues

**CUDA out of memory:**
```yaml
performance:
  batch_size: 4  # Reduce batch size
  memory_cleanup_interval: 100
```

**Missing models:**
```bash
# Models are downloaded automatically on first run
# Or manually download to models/ folder
```

**No detections found:**
- Check confidence thresholds in config
- Verify input image quality
- Ensure GPU has sufficient memory

## Support

- 📖 **Documentation**: See other guides in `docs/`
- 🐛 **Issues**: Check troubleshooting section
- 💬 **Questions**: Open GitHub issue