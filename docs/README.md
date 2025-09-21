# CAMINA Documentation

Complete documentation for the CAMINA (Computer-Aided Mobility Investigation and Analysis) project.

## 🚀 Quick Start

New to CAMINA? Start here:

1. **[Quick Start Guide](quick_start.md)** - Get running in 5 minutes
2. **[User Guide](user_guide.md)** - Comprehensive usage instructions
3. **[Configuration Guide](configuration.md)** - Advanced settings and optimization

## 📚 Core Documentation

### User Guides
- **[Quick Start](quick_start.md)** - Basic setup and first detection
- **[User Guide](user_guide.md)** - Complete usage documentation
- **[Configuration](configuration.md)** - Advanced configuration options
- **[Training Guide](training_guide.md)** - Model training for research

### Technical References
- **[Model Configuration](model_configuration.md)** - Model-specific settings
- **[Cyclist Detection](CYCLIST_DETECTION_IMPLEMENTATION.md)** - Spatial association algorithm
- **[Installation](installation.md)** - Detailed setup instructions
- **[Code Style](CODE_STYLE.md)** - Development standards

### Research & Analysis
- **[Dataset Details](DATASET_DETAILS.md)** - Dataset composition and statistics
- **[Optimization Analysis](OPTIMIZATION_ANALYSIS.md)** - Performance optimization
- **[Optimization Summary](OPTIMIZATION_SUMMARY.md)** - Key optimization results
- **[Model Download](MODEL_DOWNLOAD.md)** - Model files and setup

### Operations
- **[Run Scripts](run_scripts.md)** - Guide to execution scripts
- **[Training Pipeline](training_pipeline.md)** - Academic training methodology
- **[YOLO Training](yolo_training.md)** - YOLO model training documentation
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

## 🎯 Quick Navigation

### I want to...

**🚀 Get started quickly** → [Quick Start Guide](quick_start.md)

**📖 Learn how to use CAMINA** → [User Guide](user_guide.md)

**⚙️ Configure detection settings** → [Configuration Guide](configuration.md)

**🧠 Train my own models** → [Training Guide](training_guide.md)

**🔧 Install and setup** → [Installation Guide](installation.md)

**🐛 Fix problems** → [Troubleshooting Guide](TROUBLESHOOTING.md)

**📊 Understand the algorithms** → [Cyclist Detection Implementation](CYCLIST_DETECTION_IMPLEMENTATION.md)

## 🏗️ CAMINA Architecture

### Three-Stage Detection Pipeline

1. **Stage A**: Base object detection (YOLO11n)
   - Classes: person, car, motorcycle, bus, truck
   - Fast general object detection

2. **Cyclist Logic**: Spatial association algorithm
   - Combines person + bicycle → cyclist
   - Geometric validation and proximity checks

3. **Stage B**: Specialized detection (YOLO-World)
   - Classes: e-scooter, SUV, delivery_van
   - Open-vocabulary detection for specialized objects

4. **NMS Consolidation**: Priority-based suppression
   - YOLO-World classes suppress overlapping Stage A detections
   - Configurable priority system

### Class Mapping
```
0: person      5: truck
1: cyclist     6: e-scooter
2: car         7: SUV
3: motorcycle  8: delivery_van
4: bus
```

## 📋 Configuration Overview

Main configuration file: `configs/config.yaml`

```yaml
detection_stages:     # Two-stage detection settings
cyclist_detection:    # Spatial association logic
nms_consolidation:    # Priority-based suppression
text_prompts:         # YOLO-World class prompts
performance:          # Hardware optimization
```

Key parameters:
- **Confidence thresholds**: 0.25 (Stage A), 0.35 (Stage B)
- **IoU threshold**: 0.20 (cyclist logic), 0.35 (NMS)
- **Class priority**: `[6, 7, 8, 1, 0, 2, 3, 4, 5]`
- **Image size**: 640x640 (Roboflow compatible)

## 🎓 Academic Research

### Paper and Evaluation
- **[Main Paper](../paper/draft_v3.md)** - Latest academic paper draft
- **[Paper Evaluation](../paper/evaluation_draft_v3.md)** - Comprehensive review and recommendations

### Training and Benchmarks
- **[Training Guide](training_guide.md)** - Academic model training methodology
- **[YOLO Training](yolo_training.md)** - Multi-model comparison pipeline
- **[Optimization Analysis](OPTIMIZATION_ANALYSIS.md)** - Performance benchmarks

### Expected Results
- **mAP@0.5**: 0.4-0.7 (urban mobility datasets)
- **Training time**: ~45-60 minutes per model (RTX 3060)
- **Model sizes**: 4-6MB (nano variants)
- **Inference speed**: 20-40 FPS (depending on model)

## 🛠️ Development

### Code Organization
- **Main detection**: `main.py`
- **Training pipeline**: `train_evaluate_yolo_models.py`
- **Configuration**: `configs/config.yaml`
- **Models**: `models/` (organized by type)
- **Documentation**: `docs/` (this folder)

### Contributing
- **[Code Style Guide](CODE_STYLE.md)** - Development standards
- **[Installation Guide](installation.md)** - Development setup

## 🔧 Common Use Cases

### Traffic Monitoring
```bash
python main.py --input traffic_video.mp4 --config configs/traffic_config.yaml
```

### Pedestrian Safety Analysis
```bash
python main.py --input pedestrian_area/ --config configs/pedestrian_config.yaml --batch
```

### Micro-mobility Research
```bash
python main.py --input micromobility_data/ --config configs/micromobility_config.yaml --batch
```

### Academic Model Training
```bash
source venv_yolo/bin/activate
python train_evaluate_yolo_models.py
```

## 📊 Performance Optimization

### Hardware Recommendations
- **Minimum**: 6GB GPU, 16GB RAM
- **Recommended**: 8GB+ GPU, 32GB RAM
- **Optimal**: RTX 3060/4060 or better

### Memory Optimization
```yaml
performance:
  batch_size: 16        # Adjust based on GPU memory
  memory_cleanup_interval: 100
  device: auto          # Automatic GPU/CPU selection
```

### Speed vs Quality
- **High Quality**: Lower confidence thresholds, smaller batches
- **High Speed**: Higher confidence thresholds, larger batches
- **Balanced**: Default configuration (recommended)

## 📞 Support and Troubleshooting

### Getting Help
1. **Check [Troubleshooting Guide](TROUBLESHOOTING.md)** for common issues
2. **Review configuration** in [Configuration Guide](configuration.md)
3. **Verify installation** using [Installation Guide](installation.md)
4. **Check model files** using [Model Download Guide](MODEL_DOWNLOAD.md)

### Common Issues
- **CUDA out of memory** → Reduce batch size
- **No detections found** → Lower confidence thresholds
- **Slow processing** → Increase batch size or use faster models
- **Poor detection quality** → Review dataset and configuration

## 📈 Academic Usage

### Citation
```bibtex
@misc{camina_2024,
  title={CAMINA: Computer-Aided Mobility Investigation and Analysis},
  author={Your Name},
  year={2024},
  note={Urban mobility object detection system}
}
```

### Reproducibility
- **Fixed random seeds** for consistent results
- **Documented configurations** for all experiments
- **Version control** for code and model changes
- **Standardized evaluation** metrics and protocols

## 🔄 Recent Updates

- **Repository reorganization** with clean documentation structure
- **Academic training pipeline** for YOLO model comparison
- **Enhanced configuration system** with environment-specific settings
- **Comprehensive user guides** and quick start documentation
- **Performance optimization** guidelines and best practices

---

**Note**: This documentation reflects the current CAMINA system. Legacy documentation is preserved in the `archive/` directory.