# CAMINA - Urban Mobility Detection System

**CAMINA** (Computer-Aided Mobility Investigation and Analysis) is an academic research system for urban mobility object detection optimized for edge deployment. It features 4 trained YOLO models (YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n) with NCNN optimization for Raspberry Pi 5 deployment.

## ✨ Key Features

- **9-class urban mobility detection**: Person, Cyclist, Car, E-scooter, SUV, Motorcyclist, Bus, Delivery Van, Truck
- **Edge deployment ready**: NCNN-optimized models for Raspberry Pi 5
- **High performance**: YOLO11n achieves 0.563 mAP@0.5 with ~70+ FPS on edge devices
- **Production ready**: Complete deployment package with benchmarking tools

## 🚀 Quick Start

### Training Pipeline
```bash
# Clone and setup
git clone https://github.com/tamagusko/camina.git
cd camina

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run training pipeline
python main.py
```

### Edge Deployment (Raspberry Pi 5)
```bash
# Copy deployment package to Pi
scp -r model/raspberry_pi_deployment_all/ pi@raspberrypi:~/camina/

# Run inference benchmark
python src/benchmarks/raspberry_pi_inference_test.py --models-dir model/raspberry_pi_deployment_all

# Use in applications
from ultralytics import YOLO
model = YOLO('yolo11n_ncnn', task='detect')
results = model.predict('image.jpg')
```

## 📋 Detected Classes

| ID | Class | Description |
|----|-------|-------------|
| 0 | Person | Individual persons |
| 1 | Cyclist | People on bicycles |
| 2 | Car | Standard passenger cars |
| 3 | E-scooter | Electric scooters |
| 4 | SUV | Sport utility vehicles |
| 5 | Motorcyclist | People on motorcycles |
| 6 | Bus | Public buses |
| 7 | Delivery Van | Delivery vehicles |
| 8 | Truck | Large trucks |

## 🏆 Model Performance

| Model | mAP@0.5 | NCNN Size | Expected RPi5 FPS | Best Use |
|-------|---------|-----------|-------------------|----------|
| **YOLO11n** | 0.563 | 10.0 MB | ~74 | Best overall |
| **YOLOv8n** | 0.560 | 11.6 MB | ~73 | Balanced |
| **YOLOv5n** | 0.550 | 9.7 MB | ~67 | Stable |
| **YOLOv10n** | 0.543 | 8.8 MB | ~66 | Fastest |

## 📁 Project Structure

```
├── main.py                           # Main training pipeline
├── DIRECTORY_STRUCTURE.md            # Detailed structure documentation
│
├── src/                              # Source code organized by functionality
│   ├── benchmarks/                   # Performance testing and analysis
│   ├── export/                       # Model export and optimization
│   ├── visualization/                # Detection visualization and analysis
│   └── inference/                    # Runtime inference utilities
│
├── tools/                            # Analysis and training utilities
│   ├── extract_real_ap50_only.py     # Clean metrics extraction
│   ├── train_evaluate_yolo_models.py # Model training and evaluation
│   └── training_logger.py            # Training logging utilities
│
├── model/                            # Trained models and deployment
│   ├── yolo_comparison/              # Comparative model results
│   └── raspberry_pi_deployment_all/  # NCNN edge deployment package
│
├── data/                             # Dataset and data management
├── outputs/                          # Training and analysis outputs
├── paper/                            # Academic paper materials
├── experiments/                      # Experimental results
└── docs/                             # Additional documentation
```

## 🔧 Key Commands

### Model Training and Evaluation
```bash
# Train all 4 YOLO models
python main.py

# Extract real per-class metrics
python tools/extract_real_ap50_only.py

# Evaluate trained models
python tools/train_evaluate_yolo_models.py
```

### Model Export and Optimization
```bash
# Export all models to NCNN
python src/export/export_all_models_to_ncnn.py

# Export single best model
python src/export/export_best_model_to_ncnn.py
```

### Performance Benchmarking
```bash
# Simple inference benchmark
python src/benchmarks/benchmark_inference_simple.py

# Comprehensive Raspberry Pi benchmark
python src/benchmarks/raspberry_pi_inference_test.py --models-dir model/raspberry_pi_deployment_all
```

### Visualization
```bash
# Create detection visualizations
python src/visualization/create_detection_visualization.py
```

## 🎓 Academic Features

- **Clean metrics extraction**: Real per-class AP@0.5 values without estimation
- **Comprehensive model comparison**: 4 YOLO architectures with identical training
- **Edge deployment focus**: NCNN optimization for ARM processors
- **Publication-ready visualizations**: High-quality detection result mosaics

## 📊 Dataset

- **9 urban mobility classes** with specialized focus on cyclists and e-scooters
- **Stratified 80/20 train/test split** ensuring class balance
- **Semi-automated labeling** using YOLO-World for efficiency
- **Quality validation** with manual verification

## 🍓 Raspberry Pi 5 Deployment

The complete deployment package includes:
- **4 NCNN-optimized models** ready for edge inference
- **Comprehensive benchmarking tools** for performance analysis
- **Complete documentation** with setup instructions
- **Expected performance**: 14ms inference time (~70+ FPS)

## 📄 Requirements

- Python 3.8+
- PyTorch
- Ultralytics YOLOv8
- OpenCV
- For Raspberry Pi: NCNN backend support

See `requirements.txt` for complete dependency list.

## 📚 Documentation

- **DIRECTORY_STRUCTURE.md**: Complete repository organization
- **model/raspberry_pi_deployment_all/README.md**: Edge deployment guide
- **paper/**: Academic paper materials and figures

## 🤝 Contributing

This is an academic research project. For issues or contributions, please follow standard academic collaboration practices.

## 📜 License

MIT License - see LICENSE file for details.

## 📖 Citation

If you use CAMINA in your research, please cite:
```
[Citation information to be added upon publication]
```

---

**CAMINA** - Enabling privacy-preserving urban mobility analysis at the edge.