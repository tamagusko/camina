# CAMINA Raspberry Pi 5 Deployment Instructions

## Package Contents

This deployment package contains:
- **4 NCNN optimized models** (YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n)
- **Inference test script** for benchmarking
- **Complete documentation** for setup and usage

## Model Overview

| Model | Size | mAP@0.5 | Expected Performance |
|-------|------|---------|---------------------|
| **YOLO11n** | 10.0 MB | 0.563 | ~14 ms (~74 FPS) |
| **YOLOv8n** | 11.6 MB | 0.560 | ~14 ms (~73 FPS) |
| **YOLOv5n** | 9.7 MB | 0.550 | ~15 ms (~67 FPS) |
| **YOLOv10n** | 8.8 MB | 0.543 | ~15 ms (~66 FPS) |

**Recommended**: YOLO11n for best accuracy/performance balance

## 1. Raspberry Pi 5 Setup

### System Requirements
- **Device**: Raspberry Pi 5 (8GB RAM recommended, 4GB minimum)
- **OS**: Raspberry Pi OS (64-bit) - Latest version
- **Storage**: 8GB+ free space
- **Network**: Internet connection for initial setup

### Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install python3-pip python3-venv -y

# Create virtual environment (recommended)
python3 -m venv camina_env
source camina_env/bin/activate

# Install required packages
pip install ultralytics opencv-python numpy psutil
```

## 2. Model Deployment

### Copy Models to Raspberry Pi

```bash
# From your PC, copy the entire deployment package
scp -r raspberry_pi_deployment_all/ pi@raspberrypi:~/camina/

# Or upload individual model directories
scp -r yolo11n_ncnn/ pi@raspberrypi:~/camina/models/
scp -r yolov8n_ncnn/ pi@raspberrypi:~/camina/models/
# ... etc for other models
```

### Directory Structure on RPi
```
~/camina/
├── yolo11n_ncnn/          # Best performing model
├── yolov8n_ncnn/          # Balanced performance
├── yolov5n_ncnn/          # Stable performance
├── yolov10n_ncnn/         # Smallest, fastest
├── raspberry_pi_inference_test.py  # Benchmark script
├── README.md              # Documentation
└── DEPLOYMENT_INSTRUCTIONS.md     # This file
```

## 3. Basic Usage

### Simple Inference

```python
from ultralytics import YOLO

# Load the best performing model
model = YOLO('yolo11n_ncnn', task='detect')

# Run inference on an image
results = model.predict('your_image.jpg', imgsz=640)

# Display results
for result in results:
    result.show()  # Display image with detections
    result.save(filename='output.jpg')  # Save annotated image
```

### Real-time Video Processing

```python
from ultralytics import YOLO
import cv2

# Load model
model = YOLO('yolo11n_ncnn', task='detect')

# Open camera (adjust device number if needed)
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run inference
    results = model.predict(frame, verbose=False)

    # Display results
    annotated_frame = results[0].plot()
    cv2.imshow('CAMINA Detection', annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

## 4. Performance Benchmarking

### Run Complete Benchmark

```bash
# Activate environment
source camina_env/bin/activate

# Run benchmark on all models
python raspberry_pi_inference_test.py --models-dir . --output benchmark_results.json

# Run with custom parameters
python raspberry_pi_inference_test.py --models-dir . --runs 20 --warmup 5
```

### Benchmark Options

```bash
python raspberry_pi_inference_test.py --help
```

Options:
- `--models-dir`: Directory containing NCNN models (default: current)
- `--output`: Output file for results (default: camina_benchmark_results.json)
- `--runs`: Number of runs per test image (default: 10)
- `--warmup`: Number of warmup runs (default: 3)

## 5. Detected Classes

All models detect these 9 urban mobility classes:

| ID | Class | Description |
|----|-------|-------------|
| 0 | Person | Pedestrians |
| 1 | Cyclist | People on bicycles |
| 2 | Car | Standard passenger cars |
| 3 | E-scooter | Electric scooters |
| 4 | SUV | Sport utility vehicles |
| 5 | Motorcyclist | People on motorcycles |
| 6 | Bus | Public buses |
| 7 | Delivery Van | Delivery vehicles |
| 8 | Truck | Large trucks |

## 6. Performance Optimization Tips

### System Optimization

```bash
# Increase GPU memory split (helps with camera)
sudo raspi-config
# Advanced Options > Memory Split > 256

# Enable camera (if using Pi camera)
sudo raspi-config
# Interface Options > Camera > Enable

# Optimize CPU performance
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Model Selection Guide

**For Real-time Applications** (>15 FPS):
- **YOLO11n**: Best accuracy, good speed
- **YOLOv10n**: Fastest, acceptable accuracy

**For High Accuracy** (may sacrifice speed):
- **YOLO11n**: Highest mAP@0.5 (0.563)
- **YOLOv8n**: Good balance

**For Limited Memory** (<4GB RAM):
- **YOLOv10n**: Smallest footprint (8.8 MB)
- **YOLOv5n**: Proven stability (9.7 MB)

## 7. Troubleshooting

### Common Issues

**Model Loading Errors:**
```bash
# Ensure task is specified for NCNN models
model = YOLO('yolo11n_ncnn', task='detect')
```

**Memory Errors:**
```bash
# Reduce image size
results = model.predict('image.jpg', imgsz=320)  # Instead of 640
```

**Slow Performance:**
```bash
# Check CPU governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# Should be 'performance' for best speed
```

**Camera Issues:**
```bash
# Test camera access
raspistill -v -o test.jpg

# Check camera permissions
groups $USER
# Should include 'video' group
```

### Performance Expectations

**Expected Performance on RPi 5:**
- **Inference Time**: 14-20 ms per image
- **Frame Rate**: 50-75 FPS (image inference)
- **Real-time Video**: 15-30 FPS (with display overhead)
- **Memory Usage**: 20-30 MB per model

**If Performance is Lower:**
1. Check CPU governor is set to 'performance'
2. Ensure adequate cooling (thermal throttling affects performance)
3. Close unnecessary applications
4. Use smaller input image size (320x320 instead of 640x640)

## 8. Advanced Usage

### Batch Processing

```python
from ultralytics import YOLO
from pathlib import Path

model = YOLO('yolo11n_ncnn', task='detect')

# Process multiple images
image_dir = Path('images/')
for img_path in image_dir.glob('*.jpg'):
    results = model.predict(img_path)
    results[0].save(filename=f'output_{img_path.name}')
```

### Custom Confidence Thresholds

```python
# Adjust confidence threshold
results = model.predict('image.jpg', conf=0.25)  # Default: 0.25

# Adjust IoU threshold for NMS
results = model.predict('image.jpg', iou=0.7)   # Default: 0.7
```

### Save Detection Data

```python
results = model.predict('image.jpg')

for result in results:
    # Get detection boxes
    boxes = result.boxes
    if boxes is not None:
        for box in boxes:
            # Get coordinates and class
            coords = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
            confidence = box.conf[0].item()
            class_id = box.cls[0].item()

            print(f"Class: {class_id}, Confidence: {confidence:.2f}, Box: {coords}")
```

## 9. Support & Resources

### Documentation
- **Main README**: `README.md` - Complete model overview
- **Benchmark Results**: Generated `benchmark_results.json`
- **YOLO Documentation**: https://docs.ultralytics.com

### Performance Monitoring
```bash
# Monitor system resources during inference
htop

# Monitor temperature
vcgencmd measure_temp

# Monitor memory usage
free -h
```

---

**Generated by CAMINA YOLO Model Export Pipeline**
**Target: Raspberry Pi 5 Edge Deployment**