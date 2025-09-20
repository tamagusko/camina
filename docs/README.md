# CAMINA Documentation

This directory contains all documentation for the CAMINA (Computer-Aided Mobility Investigation and Analysis) project.

## 📚 Documentation Structure

### Academic Papers
- **[../paper/](../paper/)** - Academic paper drafts and evaluations
  - `draft_v3.md` - Latest paper draft
  - `evaluation_draft_v3.md` - Evaluation methodology and results

### Quick Start
- **[Main README.md](../README.md)** - Complete setup and usage guide
- **[Installation Guide](installation.md)** - Detailed installation instructions
- **[Model Download Guide](MODEL_DOWNLOAD.md)** - Model files and setup
- **[Run Scripts Guide](run_scripts.md)** - Guide to running different analysis scripts

### Technical Documentation
- **[Cyclist Detection Implementation](CYCLIST_DETECTION_IMPLEMENTATION.md)** - Detailed cyclist logic algorithm
- **[Model Configuration](model_configuration.md)** - Model-specific settings
- **[Code Style Guide](CODE_STYLE.md)** - Development standards
- **[Training Pipeline](training_pipeline.md)** - Training methodology and pipeline
- **[YOLO Training](yolo_training.md)** - YOLO model training documentation

### Research and Analysis
- **[Optimization Analysis](OPTIMIZATION_ANALYSIS.md)** - Performance optimization details
- **[Optimization Summary](OPTIMIZATION_SUMMARY.md)** - Key optimization results
- **[Dataset Details](DATASET_DETAILS.md)** - Dataset composition and statistics

### Development
- **[Equipment Specifications](EQUIPMENTS.md)** - Hardware requirements and recommendations
- **[Models Information](MODELS.md)** - Detailed model specifications
- **[Bug Reports](BUGS.md)** - Known issues and workarounds
- **[TODO Items](TODO.md)** - Development roadmap
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

### Reference Materials
- **[Academic Reports](ACADEMIC_REPORTS.md)** - Academic report templates and guidelines
- **[Roboflow Upload](roboflow_upload.md)** - Instructions for dataset upload to Roboflow
- **[Calibration](calibration.md)** - Camera calibration procedures
- **[Deployment](deployment.md)** - Deployment guidelines
- **[Visualization](visualization.md)** - Visualization tools and techniques

## 🚀 Getting Started

1. **New Users**: Start with the [main README.md](../README.md)
2. **Developers**: Review [Code Style Guide](CODE_STYLE.md) and [Cyclist Detection Implementation](CYCLIST_DETECTION_IMPLEMENTATION.md)
3. **Researchers**: Check [Optimization Analysis](OPTIMIZATION_ANALYSIS.md) and [Models Information](MODELS.md)
4. **Issues**: Consult [Bug Reports](BUGS.md) and troubleshooting section in main README

## 📋 Key Concepts

### Two-Stage Detection Pipeline
1. **Stage A**: YOLO11n + cyclist logic for base classes
2. **Stage B**: YOLO-World for specialized classes (e-scooter, SUV, delivery_van)
3. **Stage C**: NMS consolidation with priority system

### Priority System
- YOLO-World classes (6, 7, 8) suppress overlapping YOLO11n classes
- Configurable class priority order: `[6, 7, 8, 1, 0, 2, 3, 4, 5]`
- Deterministic tie-breaking for reproducible results

### Cyclist Detection Logic
- Rule-based algorithm combining person + bicycle detections
- Geometric constraints and spatial relationship validation
- IoU threshold: 0.20, spatial margin: 5px

## 🔧 Configuration

Main configuration file: `configs/config.yaml`

Key sections:
- `detection_stages`: Stage A and B settings
- `cyclist_detection`: Cyclist logic parameters
- `nms_consolidation`: Priority and suppression rules
- `text_prompts`: YOLO-World class prompts
- `performance`: Memory and batch settings

## 📞 Support

For issues and questions:
1. Check the [troubleshooting section](../README.md#-troubleshooting) in main README
2. Review [Bug Reports](BUGS.md) for known issues
3. Consult [TODO Items](TODO.md) for planned improvements
4. Check git commit history for recent changes

---

**Note**: This documentation reflects the production CAMINA system (v2.0+). Legacy documentation for older versions is preserved in the `archive/` directory.