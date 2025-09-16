# CAMINA – Citizen-led Automated Modal INfrastructure Analytics

**CAMINA** is a production-ready, privacy-compliant system for automated urban mobility monitoring using advanced computer vision. The system provides complete pipeline from auto-labeling to edge deployment, optimized for 9-class urban mobility detection.

## 🎯 Core Features

- **🤖 Auto-Labeling Pipeline**: YOLO-World and Grounding DINO implementations for automated dataset creation
- **🚀 Edge-Optimized Training**: YOLO11n trainer specifically tuned for Raspberry Pi 5 deployment
- **🎯 Urban Mobility Detection**: 9-class detection (pedestrian, cyclist, car, motorcycle, bus, truck, e-scooter, SUV, delivery_van)
- **⚡ Hardware Optimized**: RTX 3060 training, Raspberry Pi 5 inference (15+ FPS target)
- **📊 Production Ready**: Comprehensive error handling, logging, and monitoring
- **🔧 Complete Toolchain**: From raw images to deployed edge models

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/your-username/camina.git
cd camina
pip install -r requirements.txt
```

### 2. Auto-Label Dataset
```bash
# YOLO-World implementation
python dataset_creator_yolow.py

# Or Grounding DINO implementation
python dataset_creator_groundingDino.py
```

### 3. Train Edge Model
```bash
python camina_yolo11n_trainer.py
```

### 4. Validate & Visualize
```bash
python visualize_labels.py
python quick_check_labels.py
```

---

## 📁 Project Structure

```
camina/
├── README.md                           # This file
├── requirements.txt                    # Production dependencies
├── dataset_creator_config.json         # Auto-labeling configuration
│
├── 🤖 AUTO-LABELING TOOLS
├── dataset_creator_yolow.py           # YOLO-World auto-labeling
├── dataset_creator_groundingDino.py   # Grounding DINO auto-labeling
│
├── 🚀 TRAINING & VALIDATION
├── camina_yolo11n_trainer.py          # YOLO11n trainer for Pi5
├── visualize_labels.py                # Label visualization
├── quick_check_labels.py              # Quick validation
├── verify_installation.py             # Installation verification
│
├── 📁 ORGANIZED RESOURCES
├── models/                            # Model files (.pt, .onnx, etc.)
├── config/                           # Production configurations
├── docs/                             # Documentation
│   ├── installation.md              # Installation guide
│   ├── dataset_creators.md          # Auto-labeling documentation
│   ├── visualization.md             # Visualization guide
│   ├── deployment.md                # Raspberry Pi deployment
│   └── calibration.md               # Camera calibration
│
└── old/                              # Legacy files (preserved)
    ├── README.md                     # Legacy file documentation
    ├── src/                          # Previous source structure
    ├── scripts/                      # Legacy scripts
    └── tests/                        # Old test files
```

---

## 🔧 Hardware Requirements

### Training Environment
- **GPU**: NVIDIA RTX 3060 (12GB VRAM) - Optimized configuration
- **CPU**: Intel i5-8400 / AMD Ryzen 5 3600+
- **RAM**: 16GB+ (32GB recommended for large datasets)
- **Storage**: 500GB+ NVMe SSD

### Edge Deployment
- **Device**: Raspberry Pi 5 (8GB RAM recommended)
- **Camera**: Pi Camera Module 3 (NoIR for IR capability)
- **Storage**: 32GB+ microSD (UHS-3 for optimal performance)
- **Performance**: 15+ FPS inference, <25MB model size

---

## 📖 Documentation

Detailed documentation is available in the `docs/` folder:

- **[Installation Guide](docs/installation.md)** - Complete setup instructions
- **[Dataset Creators](docs/dataset_creators.md)** - Auto-labeling pipeline documentation
- **[Visualization Guide](docs/visualization.md)** - Label visualization and validation
- **[Deployment Guide](docs/deployment.md)** - Raspberry Pi 5 deployment
- **[Calibration Setup](docs/calibration.md)** - Camera calibration system

---

## 🛠️ Configuration

Edit `dataset_creator_config.json` to customize:
- Input/output paths
- Model settings and confidence thresholds
- Class-specific parameters
- Hardware optimization settings

See [docs/dataset_creators.md](docs/dataset_creators.md) for detailed configuration options.

---

## 📊 Performance

- **Training**: 200 epochs in 4-6 hours (RTX 3060)
- **Inference**: 15+ FPS on Raspberry Pi 5
- **Model Size**: <25MB optimized for edge deployment
- **Memory Usage**: <1GB RAM during inference
- **Power Consumption**: <15W total system

---

## 🤝 Contributing

CAMINA is actively developed for urban mobility research. Contributions welcome:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- **Legacy System**: See `old/` folder for previous CAMINA implementations
- **Research Papers**: Documentation and citations in `docs/`
- **Community**: Join discussions and share results

---

**Privacy-First | Edge-Optimized | Production-Ready**