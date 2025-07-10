# CAMINA Models Documentation

## 🤖 CAMINAv1 - Custom Cyclist Detection Model

### Overview
**CAMINAv1** is our custom-trained object detection model based on YOLO11n, specifically designed for accurate urban mobility monitoring with enhanced cyclist detection capabilities.

### Model Details
- **Base Architecture**: YOLO11n
- **Training Dataset**: COCO 2017 with synthetic cyclist class
- **Model File**: `20250629_warmup_best.pt`
- **NCNN Export**: `20250629_warmup_best_ncnn_model/`
- **Classes**: 6 (person, cyclist, car, motorcycle, bus, truck)

### Key Innovation: Synthetic Cyclist Class
CAMINAv1 introduces a novel approach to cyclist detection by:
1. **Analyzing COCO annotations** for person and bicycle objects
2. **Identifying overlapping instances** (IoU ≥ 0.3) of person + bicycle
3. **Creating combined bounding boxes** that represent the full cyclist entity
4. **Training with dedicated cyclist class** (ID: 1) for improved accuracy

### Performance Benefits
- **Improved Accuracy**: Significant improvement over base YOLO11 for cyclist detection
- **Reduced Misclassification**: Eliminates common cyclist→motorcycle confusion
- **Urban Optimized**: Trained specifically for urban mobility scenarios
- **Edge Deployment**: Optimized NCNN format for Raspberry Pi deployment

### Model Comparison

| Model | Cyclist Detection | Deployment | Use Case |
|-------|-------------------|------------|----------|
| Base YOLO11n | Limited (no cyclist class) | Standard | General object detection |
| CAMINAv1 | Dedicated cyclist class | NCNN optimized | Urban mobility monitoring |

### Configuration
```yaml
# Use CAMINAv1 in main_config.yaml
ncnn_model_path: models/20250629_warmup_best_ncnn_model/

# Class mapping in classes.yaml
0: person
1: cyclist    # CAMINAv1 innovation
2: car
3: motorcycle
4: bus
5: truck
```

### Training Process
The CAMINAv1 model was trained using:
- **Epochs**: 100
- **Batch Size**: 16
- **Image Size**: 640x640
- **Dataset**: COCO 2017 + synthetic cyclist annotations
- **Validation**: Test split with balanced class distribution

### Usage
```python
# CAMINAv1 is automatically loaded when using the configured path
from src.camina.app import ModalShareCounterApp
from src.camina.utils.config import load_config

config = load_config()
app = ModalShareCounterApp(config)
app.run()
```

## 🔄 Model Updates

### Version History
- **CAMINAv1** (2025-06-29): Initial release with cyclist detection
- **Future**: CAMINAv2 planned with e-scooter, delivery van, and SUV classes

### Retraining CAMINAv1
For retraining or fine-tuning, see the detailed guide in `custom_model_train/README.md`.

## 🎯 Model Performance Metrics

### Cyclist Detection Accuracy
- **Precision**: Significantly improved over base YOLO11
- **Recall**: Enhanced detection of cyclists in urban environments
- **F1-Score**: Balanced performance across different lighting conditions

### Deployment Efficiency
- **NCNN Format**: Optimized for ARM processors (Raspberry Pi)
- **Inference Speed**: Real-time performance on edge devices
- **Memory Usage**: Efficient resource utilization

## 📊 Class Distribution

The CAMINAv1 model is trained with balanced representation of:
- **Person**: Pedestrians and individuals
- **Cyclist**: Dedicated class for bicycle riders
- **Car**: Standard passenger vehicles
- **Motorcycle**: Motorized two-wheelers
- **Bus**: Public transportation vehicles
- **Truck**: Commercial and delivery vehicles

## 🚀 Future Enhancements

### CAMINAv2 Roadmap
- **E-scooter detection**: Growing urban mobility mode
- **Delivery van classification**: Separate from standard trucks
- **SUV categorization**: Distinct from standard cars
- **Speed estimation integration**: Enhanced mobility analytics
- **Weather adaptation**: Improved performance in different conditions