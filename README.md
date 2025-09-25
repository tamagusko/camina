# CAMINA - Urban Mobility Detection System

**CAMINA** (Computer-Aided Mobility Investigation and Analysis) is an academic research system for urban mobility object detection. It combines YOLO-World with specialized algorithms for comprehensive 9-class detection including cyclists and e-scooter riders.

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/tamagusko/camina.git
cd camina

# Create virtual environment
python -m venv venv_camina
source venv_camina/bin/activate  # Linux/Mac
# venv_camina\Scripts\activate   # Windows

# Install dependencies
pip install ultralytics rich pyyaml opencv-python pillow

# Run detection
python main.py --images_dir data/images/ --output_dir outputs/
```

## 📋 Detected Classes

| ID | Class | Detection Method | Description |
|----|-------|------------------|-------------|
| 0 | person | YOLO-World | Individual persons |
| 1 | cyclist | Spatial logic | Person + bicycle → cyclist |
| 2 | car | YOLO-World | Standard passenger cars |
| 3 | motorcycle | YOLO-World | Motorcycles and motorbikes |
| 4 | bus | YOLO-World | Public transit buses |
| 5 | truck | YOLO-World | Trucks and lorries |
| 6 | e-scooter | YOLO-World | Electric scooters with riders |
| 7 | SUV | YOLO-World | Sport utility vehicles |
| 8 | delivery_van | YOLO-World | Commercial delivery vans |

## 🏗️ Architecture

### Hybrid Detection Pipeline

1. **YOLO-World Detection**: Open-vocabulary detection using text prompts
2. **Spatial Association**: Person + bicycle → cyclist logic
3. **NMS Consolidation**: Priority-based conflict resolution

### Key Features

- **Academic Research Focus**: Designed for urban mobility studies
- **Cyclist Detection Logic**: Geometric constraints and spatial validation
- **E-scooter Specialization**: Dedicated detection for micro-mobility
- **Priority System**: Intelligent conflict resolution between classes
- **640x640 Compatible**: Works with Roboflow and standard datasets

## 📚 Documentation

Complete documentation is available in the [`docs/`](docs/) folder:

### Quick Navigation
- **🚀 [Quick Start Guide](docs/quick_start.md)** - Get running in 5 minutes
- **📖 [User Guide](docs/user_guide.md)** - Comprehensive usage instructions
- **⚙️ [Configuration Guide](docs/configuration.md)** - Advanced settings
- **🧠 [Training Guide](docs/training_guide.md)** - Model training for research
- **🔧 [Installation Guide](docs/installation.md)** - Detailed setup instructions
- **🐛 [Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Academic Research
- **📄 [Research Paper](paper/draft_v3.md)** - Latest academic paper draft
- **📊 [Paper Evaluation](paper/evaluation_draft_v3.md)** - Comprehensive review
- **🏋️ [Model Training](docs/training_guide.md)** - Academic training pipeline

## ⚙️ Basic Configuration

Main configuration file: `configs/config.yaml`

```yaml
# Detection stages
detection_stages:
  stage_a:
    confidence_threshold: 0.25    # YOLO-World detection confidence
  stage_b:
    confidence_threshold: 0.35    # Specialized class confidence

# Cyclist detection logic
cyclist_detection:
  enabled: true
  iou_threshold: 0.20             # Person-bicycle overlap requirement
  spatial_margin: 5               # Pixel margin for spatial checks

# Priority-based NMS
nms_consolidation:
  enabled: true
  iou_threshold: 0.35
  class_priority: [6, 7, 8, 1, 0, 2, 3, 4, 5]  # E-scooter > SUV > ... > truck
```

## 🚀 Usage Examples

### Basic Detection
```bash
# Batch processing
python main.py --images_dir data/images/ --output_dir results/

# Use custom configuration
python main.py --config configs/config.yaml --images_dir data/images/

# Quick run with shell script
./scripts/run.sh
```

### Academic Model Training
```bash
# Activate training environment
source venv/bin/activate

# Train YOLO comparison models (YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n)
python train_evaluate_yolo_models.py
# OR use the training script
./scripts/run_yolo_comparison.sh

# Results saved to outputs/model_comparison/
```

### Custom Configuration
```bash
# Use custom settings
python main.py --config configs/config.yaml --images_dir data/images/

# GPU processing with custom device
python main.py --images_dir data/images/ --device cuda:0

# Verbose output for debugging
python main.py --images_dir data/images/ --verbose
```

## 📊 Output Formats

### Directory Structure
```
outputs/
├── detections/              # YOLO format labels (.txt files)
├── dataset_viz/            # Visualized images with bounding boxes
├── yolo/                   # Raw detection outputs
└── performance_report.json # Processing statistics
```

### YOLO Format Labels (640x640 normalized)
```
class_id center_x center_y width height confidence
0 0.5 0.3 0.2 0.4 0.85
1 0.7 0.6 0.15 0.25 0.92
```

## 🎓 Academic Usage

### Training Pipeline for Research

The repository includes a comprehensive training pipeline for academic comparison:

```bash
# Setup training environment
python -m venv venv_yolo
source venv_yolo/bin/activate
pip install ultralytics numpy pandas matplotlib seaborn rich pyyaml psutil

# Run academic training pipeline
python train_evaluate_yolo_models.py
```

This generates academic tables for paper submission:

#### Table 2: Per-Class Detection Performance (mAP@0.5)
| Class | Definition | mAP@0.5 | Instances |
|-------|------------|---------|-----------|
| Pedestrian | COCO | [Generated] | [Count] |
| Cyclist | Rule-based | [Generated] | [Count] |
| ... | ... | ... | ... |

#### Table 3: Model Comparison
| Model | mAP@0.5 | Size (MB) | FPS | Training Time |
|-------|---------|-----------|-----|---------------|
| YOLOv5n | [Generated] | [Generated] | [Generated] | [Generated] |
| YOLOv8n | [Generated] | [Generated] | [Generated] | [Generated] |
| ... | ... | ... | ... | ... |

### Citation
```bibtex
@misc{camina_2024,
  title={CAMINA: Computer-Aided Mobility Investigation and Analysis},
  author={Your Name},
  year={2024},
  note={Urban mobility detection system for academic research}
}
```

## 📂 Repository Structure

```
camina/
├── README.md                    # This file
├── camina.py                    # Main detection script
├── train_evaluate_yolo_models.py # Academic training pipeline
├── run_*.sh                     # Execution scripts
├── configs/
│   └── config.yaml             # Main configuration
├── models/                     # Organized model storage
│   ├── yolo_base/             # Base YOLO models
│   ├── yolo_world/            # YOLO-World models
│   ├── yolo_comparison/       # Training results
│   └── camina/                # CAMINA-specific models
├── docs/                      # Complete documentation
│   ├── README.md              # Documentation index
│   ├── quick_start.md         # Quick start guide
│   ├── user_guide.md          # Complete usage guide
│   ├── configuration.md       # Advanced configuration
│   ├── training_guide.md      # Academic training
│   └── ...                    # Technical references
├── paper/                     # Academic paper
│   ├── draft_v3.md           # Latest paper draft
│   └── evaluation_draft_v3.md # Paper evaluation
├── data/                      # Input datasets
├── outputs/                   # Detection results
├── archive/                   # Deprecated/historical files
└── tests/                     # Test suite
```

## 📊 Performance Benchmarks

### RTX 3060 (12GB) Performance
- **Processing Speed**: 15-25 FPS (batch processing)
- **Memory Usage**: 6-8GB VRAM (batch size 16)
- **Training Time**: ~45-60 minutes per model
- **Model Sizes**: 4-6MB (nano variants)

### Expected Accuracy
- **Urban mobility datasets**: mAP@0.5: 0.4-0.7
- **Cyclist detection**: Precision > 0.90 (when person+bicycle present)
- **E-scooter detection**: Good performance with proper prompts

## 🔧 Common Issues & Solutions

### CUDA Out of Memory
```bash
# Reduce batch size
python camina.py --input data/ --batch_size 8

# Use CPU
python camina.py --input data/ --device cpu
```

### No Detections Found
```yaml
# Lower confidence thresholds in configs/config.yaml
detection_stages:
  stage_a:
    confidence_threshold: 0.15  # Lower threshold
```

### Poor E-scooter Detection
```yaml
# Improve text prompts in config
text_prompts:
  e_scooter: "A person riding an electric scooter. E-scooter rider. Person on e-scooter."
```

## 🛠️ Development

### Requirements
- Python 3.8+
- NVIDIA GPU (recommended, 6GB+ VRAM)
- CUDA 11.0+ (for GPU acceleration)

### Core Dependencies
```bash
pip install ultralytics rich pyyaml opencv-python pillow numpy pandas matplotlib
```

### Testing
```bash
# Run test detection
python camina.py --input data/test_image.jpg --output test_results/

# Validate configuration
python camina.py --validate_only
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

See [Code Style Guide](docs/CODE_STYLE.md) for development standards.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- YOLO-World for open-vocabulary detection
- Research community for urban mobility datasets

---

**Note**: This is an academic research system. For production deployment, additional optimization and testing are recommended. See `docs/` folder for comprehensive documentation.