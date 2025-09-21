# CAMINA Dataset Creator - Refactored Implementation

This repository contains refactored and extended CAMINA dataset creation system with two auto-labeling implementations optimized for RTX 3060 (12GB VRAM).

## 🚀 What's New

- **Configuration-driven approach**: All settings now loaded from `dataset_creator_config.json`
- **Two model implementations**: YOLO-World and Grounding DINO
- **Production-ready error handling**: Comprehensive error handling and logging
- **Memory optimization**: Optimized for RTX 3060 with 12GB VRAM
- **Consistent output format**: Both implementations produce identical YOLO format output

## 📁 File Structure

```
├── dataset_creator_config.json          # Centralized configuration file
├── dataset_creator_yolow.py            # YOLO-World implementation
├── dataset_creator_groundingDino.py    # Grounding DINO implementation
├── visualize_labels.py                 # Compatible visualization tool
├── quick_check_labels.py              # Quick label checking tool
└── DATASET_CREATOR_README.md          # This documentation
```

## 🎯 9-Class Urban Mobility Detection

Both implementations detect these urban mobility objects:

| Class ID | Class Name    | Default Confidence | Usage |
|----------|---------------|-------------------|--------|
| 0        | pedestrian    | 0.30              | People walking on streets |
| 1        | cyclist       | 0.30              | People on bicycles |
| 2        | car           | 0.40              | Standard passenger cars |
| 3        | motorcycle    | 0.35              | Motorcycles and scooters |
| 4        | bus           | 0.45              | Public transit buses |
| 5        | truck         | 0.45              | Freight and cargo trucks |
| 6        | e-scooter     | 0.20              | Electric scooters |
| 7        | SUV           | 0.35              | Sport utility vehicles |
| 8        | delivery_van  | 0.30              | Commercial delivery vans |

## ⚙️ Configuration File

The `dataset_creator_config.json` file contains all settings:

```json
{
  "metadata": {
    "version": "1.0.0",
    "description": "CAMINA Dataset Creator Configuration",
    "target_hardware": "RTX 3060 (12GB VRAM)"
  },
  "classes": {
    "0": "pedestrian",
    "1": "cyclist",
    ...
  },
  "confidence_thresholds": {
    "pedestrian": 0.30,
    "cyclist": 0.30,
    ...
  },
  "text_prompts": {
    "pedestrian": ["person walking", "pedestrian", ...],
    ...
  },
  "memory_config": {
    "max_vram_gb": 10.0,
    "batch_size_base": 8,
    ...
  },
  "detection_settings": {
    "initial_confidence": 0.1,
    "iou_threshold": 0.4,
    ...
  },
  "grounding_dino_config": {
    "model_config": "GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py",
    "model_weights": "groundingdino_swint_ogc.pth",
    ...
  }
}
```

## 🛠️ Usage

### YOLO-World Implementation

```bash
# Basic usage
python3 dataset_creator_yolow.py input_images/ output_dataset/

# Advanced usage
python3 dataset_creator_yolow.py input_images/ output_dataset/ \
    --model yolov8m-world.pt \
    --batch-size 16 \
    --confidence-scale 1.2 \
    --validate \
    --verbose

# Custom config file
python3 dataset_creator_yolow.py input_images/ output_dataset/ \
    --config custom_config.json
```

### Grounding DINO Implementation

```bash
# Basic usage
python3 dataset_creator_groundingDino.py input_images/ output_dataset/

# Advanced usage
python3 dataset_creator_groundingDino.py input_images/ output_dataset/ \
    --batch-size 1 \
    --confidence-scale 0.9 \
    --validate \
    --verbose

# Custom config file
python3 dataset_creator_groundingDino.py input_images/ output_dataset/ \
    --config custom_config.json
```

### Command Line Arguments

| Argument | YOLO-World | Grounding DINO | Description |
|----------|------------|----------------|-------------|
| `input_dir` | ✅ | ✅ | Directory containing input images |
| `output_dir` | ✅ | ✅ | Directory to save labeled dataset |
| `--model` | ✅ | ❌ | YOLO-World model path (default: yolov8m-world.pt) |
| `--batch-size` | ✅ | ✅ | Batch size (auto-detected if not specified) |
| `--max-workers` | ✅ | ✅ | Maximum number of worker processes |
| `--confidence-scale` | ✅ | ✅ | Scale factor for confidence thresholds |
| `--validate` | ✅ | ✅ | Validate dataset after creation |
| `--verbose` | ✅ | ✅ | Enable verbose logging |
| `--config` | ✅ | ✅ | Path to configuration file |

## 🎨 Visualization

Both implementations are fully compatible with existing visualization tools:

```bash
# Quick check first few images
python3 quick_check_labels.py output_dataset/

# Detailed visualization with statistics
python3 visualize_labels.py output_dataset/ --summary --save

# Check specific image
python3 visualize_labels.py output_dataset/ --image example.jpg
```

## 🧠 Model Comparison

| Feature | YOLO-World | Grounding DINO |
|---------|------------|----------------|
| **Speed** | ⚡⚡⚡ Fast | ⚡⚡ Medium |
| **Memory Usage** | 🟢 Moderate | 🟡 Higher |
| **Accuracy** | 🎯 Good | 🎯🎯 Excellent |
| **Text Flexibility** | 🔤 Limited | 🔤🔤 High |
| **Batch Processing** | ✅ Yes | ❌ Single image |
| **Setup Complexity** | 🟢 Easy | 🟡 Complex |

## 💾 Output Structure

Both implementations produce identical output structure:

```
output_dataset/
├── images/                    # Copied input images
│   ├── image1.jpg
│   ├── image2.png
│   └── ...
├── labels/                    # YOLO format labels
│   ├── image1.txt
│   ├── image2.txt
│   └── ...
├── dataset.yaml              # YOLO dataset configuration
└── dataset_creation_summary.json  # Processing statistics
```

### YOLO Label Format

Each label file contains detections in YOLO format:
```
class_id center_x center_y width height
0 0.5 0.3 0.1 0.2
2 0.7 0.6 0.15 0.25
```

## 🔧 Memory Optimization

Both implementations include RTX 3060-specific optimizations:

- **Dynamic batch sizing**: Automatically adjusts based on image size and available VRAM
- **Memory monitoring**: Tracks GPU memory usage and performs cleanup
- **Graceful degradation**: Reduces batch size on OOM errors
- **Efficient cleanup**: Regular memory cleanup during processing

## 🚨 Error Handling

Production-ready error handling includes:

- **Configuration validation**: Comprehensive config file validation
- **Dependency checking**: Clear error messages for missing dependencies
- **GPU memory management**: OOM error handling and recovery
- **File I/O errors**: Robust handling of corrupted/missing files
- **Graceful interruption**: Clean shutdown on Ctrl+C

## 📊 Statistics and Logging

Both implementations provide detailed logging:

```
2025-09-16 10:30:15 - INFO - Configuration loaded from: dataset_creator_config.json
2025-09-16 10:30:16 - INFO - YOLOWorldDetector initialized on device: cuda
2025-09-16 10:30:16 - INFO - Using GPU: NVIDIA GeForce RTX 3060 (12.0GB)
2025-09-16 10:30:17 - INFO - Found 150 images
2025-09-16 10:30:17 - INFO - Using batch size: 8
Processing images: 100%|██████████| 150/150 [02:15<00:00,  1.11it/s]
2025-09-16 10:32:32 - INFO - === DATASET CREATION SUMMARY ===
2025-09-16 10:32:32 - INFO - Total images processed: 150
2025-09-16 10:32:32 - INFO - Successful: 148
2025-09-16 10:32:32 - INFO - Failed: 2
2025-09-16 10:32:32 - INFO - Total detections: 542
```

## 🔍 Requirements

### Common Dependencies
```bash
pip install torch torchvision numpy opencv-python Pillow tqdm psutil pyyaml matplotlib
```

### YOLO-World Additional
```bash
pip install ultralytics
```

### Grounding DINO Additional
```bash
# Follow official Grounding DINO installation guide
git clone https://github.com/IDEA-Research/GroundingDINO.git
cd GroundingDINO
pip install -e .
# Download model weights as per official instructions
```

## 🎛️ Customization

You can customize the behavior by:

1. **Modifying configuration**: Edit `dataset_creator_config.json`
2. **Adjusting confidence thresholds**: Per-class confidence tuning
3. **Text prompt engineering**: Customize prompts for better detection
4. **Memory settings**: Adjust for different GPU configurations
5. **Adding new classes**: Extend the 9-class system

## 🐛 Troubleshooting

### Common Issues

**GPU Out of Memory**:
```bash
# Reduce batch size
python3 dataset_creator_yolow.py input/ output/ --batch-size 4
```

**Missing Dependencies**:
```bash
# Check error messages for specific packages
pip install [missing-package]
```

**Configuration Errors**:
```bash
# Validate your config file structure
python3 -c "import json; print(json.load(open('dataset_creator_config.json')))"
```

**Grounding DINO Setup Issues**:
```bash
# Ensure model files exist
ls GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py
ls groundingdino_swint_ogc.pth
```

## 📈 Performance Tips

1. **Use SSD storage**: Faster I/O improves overall performance
2. **Optimize batch size**: Let auto-detection find optimal size
3. **Pre-resize images**: Smaller images = faster processing
4. **Use YOLO-World for speed**: Choose Grounding DINO for accuracy
5. **Monitor GPU usage**: Use `nvidia-smi` to monitor utilization

## 🤝 Contributing

When contributing to the dataset creators:

1. Maintain backward compatibility with existing visualization tools
2. Follow the established error handling patterns
3. Update configuration schema when adding new features
4. Test with RTX 3060 memory constraints
5. Document any new configuration options

## 📝 License

This implementation maintains the same license as the original CAMINA project.

---

**Created**: 2025-09-16
**Author**: CAMINA Team
**Version**: 1.0.0
**Target Hardware**: RTX 3060 (12GB VRAM)