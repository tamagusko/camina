# CAMINA Dataset Expansion: 9-Class Urban Mobility Detection Pipeline

A comprehensive computer vision pipeline for expanding the CAMINA dataset from 6 to 9 classes using advanced semi-automated labeling and multi-model comparison framework optimized for Raspberry Pi 5 deployment.

## 🎯 Project Overview

This project implements a complete pipeline for urban mobility monitoring using YOLO11 format specifications, targeting 9-class detection optimized for edge deployment on Raspberry Pi 5.

### Classes

**Current (6)** → **Target (9)**
- `person` → `pedestrian` (class_id: 0)
- `cyclist` (class_id: 1)
- `car` (class_id: 2)
- `motorcycle` (class_id: 3)
- `bus` (class_id: 4)
- `truck` (class_id: 5)
- **NEW:** `e-scooter` (class_id: 6)
- **NEW:** `SUV` (class_id: 7)
- **NEW:** `delivery_van` (class_id: 8)

### Key Features

- 🤖 **SAM2 + CLIP Auto-Labeling**: Semi-automated labeling for new classes
- 🏁 **Multi-Model Comparison**: YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n, YOLO12n
- 🍓 **Raspberry Pi 5 Optimized**: NCNN format deployment
- 📊 **Comprehensive Logging**: SQLite database with detailed metrics
- 🔄 **YOLO11 Native Format**: Complete YOLO11 ecosystem integration

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone and setup
git clone <repository>
cd camina/custom_model_train

# Install dependencies
pip install ultralytics opencv-python numpy pandas matplotlib seaborn
pip install torch torchvision torchaudio
pip install clip-by-openai  # For CLIP model
# pip install sam2  # For SAM2 (when available)
```

### 2. Convert Existing Dataset

```bash
# Convert SDL dataset to YOLO11 format with 9-class schema
python scripts/convert_sdl_to_yolo11.py \
  --sdl-dataset "datasets/SDL fine-tuned_v3-cyclist_cleaned" \
  --output "all_camina_classes"
```

**Output:**
```
all_camina_classes/
├── images/
│   ├── train/ (1,224 images)
│   ├── val/ (72 images)
│   └── test/ (empty - for expansion)
├── labels/
│   ├── train/ (1,222 label files)
│   ├── val/ (72 label files)
│   └── test/
├── data.yaml (YOLO11 config)
└── classes.txt
```

### 3. Semi-Automated Labeling for New Classes

```bash
# Use SAM2 + CLIP for auto-labeling new classes
python scripts/sam2_clip_auto_labeling.py \
  --image-dir "path/to/new_images" \
  --output-dir "auto_labeled_output" \
  --confidence 0.3 \
  --visualize
```

**Key Parameters:**
- `--confidence 0.3`: Detection confidence threshold
- `--visualize`: Save detection visualizations
- `--device auto`: Automatically select best device (CUDA/MPS/CPU)

### 4. Train YOLO11n Model

```bash
# Train YOLO11n with 9-class dataset
python scripts/train_yolo11n.py \
  --data all_camina_classes/data.yaml \
  --epochs 100 \
  --batch 16 \
  --device auto \
  --export
```

**Advanced Training Options:**
```bash
python scripts/train_yolo11n.py \
  --data all_camina_classes/data.yaml \
  --epochs 100 \
  --batch 16 \
  --imgsz 640 \
  --device cuda \
  --project "camina_expansion" \
  --export  # Export for Raspberry Pi after training
```

### 5. Model Comparison Framework

```bash
# Compare multiple YOLO models
python scripts/model_comparison_framework.py \
  --data all_camina_classes/data.yaml \
  --video path/to/test_video.mp4 \
  --epochs 50 \
  --models yolov8n yolo11n yolov10n \
  --ncnn
```

**Full Comparison:**
```bash
python scripts/model_comparison_framework.py \
  --data all_camina_classes/data.yaml \
  --video test_video.mp4 \
  --epochs 100 \
  --models yolov5n yolov8n yolov10n yolo11n yolo12n \
  --ncnn
```

---

## 📋 Detailed Usage Examples

### Dataset Conversion

#### Convert SDL Dataset
```bash
python scripts/convert_sdl_to_yolo11.py \
  --sdl-dataset "datasets/SDL fine-tuned_v3-cyclist_cleaned" \
  --output "all_camina_classes"
```

**Expected Output:**
```
2025-08-26 17:26:16,391 - INFO - Starting SDL to YOLO11 conversion...
2025-08-26 17:26:17,197 - INFO - Split train: 1224 images, 1222 label files
2025-08-26 17:26:17,197 - INFO - Split val: 72 images, 72 label files
2025-08-26 17:26:17,242 - INFO - === Class Distribution ===
2025-08-26 17:26:17,242 - INFO - pedestrian: 7361 objects (59.9%)
2025-08-26 17:26:17,242 - INFO - cyclist: 1761 objects (14.3%)
2025-08-26 17:26:17,242 - INFO - car: 2116 objects (17.2%)
```

### SAM2 + CLIP Auto-Labeling

#### Basic Auto-Labeling
```bash
python scripts/sam2_clip_auto_labeling.py \
  --image-dir "datasets/new_urban_images" \
  --output-dir "sam2_clip_results" \
  --confidence 0.3
```

#### Advanced Auto-Labeling with Visualization
```bash
python scripts/sam2_clip_auto_labeling.py \
  --image-dir "datasets/urban_mobility_images" \
  --output-dir "labeled_results" \
  --device cuda \
  --sam2-checkpoint "path/to/sam2_checkpoint.pth" \
  --clip-model "ViT-B/32" \
  --confidence 0.4 \
  --visualize
```

### Model Training

#### Basic YOLO11n Training
```bash
python scripts/train_yolo11n.py \
  --data all_camina_classes/data.yaml \
  --epochs 100
```

#### Production Training with Export
```bash
python scripts/train_yolo11n.py \
  --data all_camina_classes/data.yaml \
  --model yolo11n.pt \
  --epochs 200 \
  --batch 32 \
  --imgsz 640 \
  --device cuda \
  --export \
  --project "camina_production"
```

#### Resume Training
```bash
python scripts/train_yolo11n.py \
  --data all_camina_classes/data.yaml \
  --resume \
  --epochs 50
```

### Model Comparison

#### Quick Comparison (2 models)
```bash
python scripts/model_comparison_framework.py \
  --data all_camina_classes/data.yaml \
  --epochs 25 \
  --models yolov8n yolo11n
```

#### Full Production Comparison
```bash
python scripts/model_comparison_framework.py \
  --data all_camina_classes/data.yaml \
  --video datasets/test_video_1hr.mp4 \
  --epochs 100 \
  --models yolov5n yolov8n yolov10n yolo11n yolo12n \
  --ncnn \
  > comparison_results.log 2>&1
```

### Raspberry Pi 5 Deployment

#### Optimize Single Model
```bash
python scripts/rpi5_deployment_optimizer.py \
  --model runs/train/exp/weights/best.pt \
  --output rpi5_deployment \
  --format ncnn
```

#### Complete Deployment Package
```bash
python scripts/rpi5_deployment_optimizer.py \
  --model runs/train/yolo11n_9class_*/weights/best.pt \
  --output production_deployment \
  --format all
```

**Deployment Package Contents:**
```
production_deployment/
├── ncnn_model/ (NCNN format)
├── model.onnx (ONNX format) 
├── model.tflite (TensorFlow Lite)
├── rpi5_inference.py (Inference script)
├── install.sh (Installation script)
├── requirements.txt
├── benchmark.py
└── README.md
```

### Performance Evaluation

#### Generate Comparison Report
```bash
python scripts/evaluation_logging_system.py \
  --action report \
  --db-path experiments.db \
  --output comparison_report.json
```

#### Export Results to CSV
```bash
python scripts/evaluation_logging_system.py \
  --action export \
  --output all_experiments.csv
```

#### Create Visualizations
```bash
python scripts/evaluation_logging_system.py \
  --action visualize \
  --output visualizations/
```

---

## 🍓 Raspberry Pi 5 Deployment

### Installation on RPi5

```bash
# On Raspberry Pi 5
cd production_deployment
chmod +x install.sh
./install.sh
```

### Run Inference

#### Camera Inference
```bash
# Activate environment
source camina_env/bin/activate

# Real-time camera detection
python3 rpi5_inference.py \
  --model ncnn_model \
  --format ncnn \
  --input 0
```

#### Video File Processing
```bash
python3 rpi5_inference.py \
  --model ncnn_model \
  --format ncnn \
  --input test_video.mp4 \
  --output results.mp4
```

#### Benchmark Performance
```bash
python3 benchmark.py \
  --model ncnn_model \
  --format ncnn \
  --images 200 \
  --output benchmark_results.json
```

### Expected RPi5 Performance

| Model | Format | FPS | Latency | Memory | Power |
|-------|--------|-----|---------|--------|-------|
| YOLO11n | NCNN | 15-20 | 50-67ms | 800MB | 6W |
| YOLO11n | ONNX | 12-18 | 56-83ms | 900MB | 6.5W |
| YOLO11n | TFLite | 10-15 | 67-100ms | 700MB | 5.5W |

---

## 📊 Results and Analysis

### Model Comparison Results

| Model | mAP@0.5 | Model Size (MB) | Video FPS | Real-World FPS | Training Time (hrs) |
|-------|---------|-----------------|-----------|----------------|-------------------|
| YOLOv5n | 0.xxx | xx.x | xx.x | xx.x | x.x |
| YOLOv8n | 0.xxx | xx.x | xx.x | xx.x | x.x |
| YOLOv10n | 0.xxx | xx.x | xx.x | xx.x | x.x |
| YOLO11n | 0.xxx | xx.x | xx.x | xx.x | x.x |
| YOLO12n | 0.xxx | xx.x | xx.x | xx.x | x.x |

### Per-Class Detection Performance

| Class | New | YOLOv5n | YOLOv8n | YOLOv10n | YOLO11n | YOLO12n | Samples |
|-------|-----|---------|---------|----------|---------|---------|---------|
| Pedestrian | ❌ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 7,361 |
| Cyclist | ❌ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 1,761 |
| E-scooter | ✅ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | TBD |
| SUV | ✅ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | TBD |
| Motorcycle | ❌ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 445 |
| Bus | ❌ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 309 |
| Delivery Van | ✅ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | TBD |
| Truck | ❌ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 297 |
| Car | ❌ | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 0.xxx | 2,116 |

---

## 🔧 Advanced Configuration

### Custom Training Parameters

```python
# In scripts/train_yolo11n.py, modify training_params:
self.training_params = {
    'epochs': 150,
    'batch': 32,
    'imgsz': 640,
    'lr0': 0.001,
    'weight_decay': 0.0005,
    'warmup_epochs': 3,
    'mosaic': 1.0,
    'mixup': 0.15,
    'copy_paste': 0.3,
    # ... more parameters
}
```

### SAM2 + CLIP Configuration

```python
# In scripts/sam2_clip_auto_labeling.py, modify target classes:
self.target_classes = {
    6: {
        'name': 'e-scooter',
        'prompts': [
            'an electric scooter',
            'a person riding an e-scooter',
            'electric kick scooter'
        ]
    },
    # Add custom classes...
}
```

### Raspberry Pi 5 Optimization

```python
# In scripts/rpi5_deployment_optimizer.py:
self.optimization_configs = {
    'ncnn': {
        'quantization': 'int8',
        'vulkan_compute': True,
        'thread_count': 4
    }
}
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Model Loading Errors
```bash
# If ultralytics not installed
pip install ultralytics>=8.0.0

# If YOLO model not found
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolo11n.pt
```

#### 2. CUDA Memory Issues
```bash
# Reduce batch size
python scripts/train_yolo11n.py --batch 8

# Or use CPU
python scripts/train_yolo11n.py --device cpu
```

#### 3. SAM2/CLIP Dependencies
```bash
# Install CLIP
pip install git+https://github.com/openai/CLIP.git

# For SAM2 (when available)
pip install segment-anything-2
```

#### 4. Raspberry Pi 5 Issues
```bash
# Increase GPU memory
sudo raspi-config -> Advanced Options -> Memory Split -> 128

# Install Vulkan drivers
sudo apt install mesa-vulkan-drivers
```

---

## 📁 Project Structure

```
custom_model_train/
├── all_camina_classes/           # YOLO11 dataset (9 classes)
│   ├── images/{train,val,test}/
│   ├── labels/{train,val,test}/
│   ├── data.yaml
│   └── classes.txt
├── datasets/                     # Original datasets
│   └── SDL fine-tuned_v3-cyclist_cleaned/
├── scripts/                      # Core pipeline scripts
│   ├── convert_sdl_to_yolo11.py
│   ├── sam2_clip_auto_labeling.py
│   ├── train_yolo11n.py
│   ├── model_comparison_framework.py
│   ├── rpi5_deployment_optimizer.py
│   └── evaluation_logging_system.py
├── configs/                      # Training configurations
├── logs/                         # Experiment logs
├── results/                      # Comparison results
├── runs/                         # Training outputs
├── visualizations/               # Analysis plots
├── experiments.db                # SQLite database
├── yolo11n.pt                    # Base model
└── README.md                     # This file
```

---

## 📚 References and Citations

- **YOLO11**: [Ultralytics YOLO11 Documentation](https://docs.ultralytics.com/)
- **SAM2**: [Segment Anything Model 2](https://github.com/facebookresearch/segment-anything-2)
- **CLIP**: [OpenAI CLIP](https://github.com/openai/CLIP)
- **Raspberry Pi 5**: [Official Documentation](https://www.raspberrypi.org/documentation/)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-class-detection`)
3. Commit changes (`git commit -am 'Add new urban mobility class'`)
4. Push to branch (`git push origin feature/new-class-detection`)
5. Create Pull Request

## 📄 License

MIT License - see main repository for details

## 🏆 CAMINAv2 Performance Goals

- **Accuracy**: >0.85 mAP@0.5 across all 9 classes
- **Speed**: >15 FPS on Raspberry Pi 5
- **Size**: <20MB model for edge deployment
- **Efficiency**: Best accuracy/speed/size trade-off
- **Real-world**: Robust performance in urban environments

