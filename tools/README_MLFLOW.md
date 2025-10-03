# MLflow Tools for CAMINA

Experiment tracking and dataset monitoring tools with MLflow integration.

## 📦 Installation

```bash
pip install mlflow
```

## 🛠️ Tools Overview

### 1. `mlflow_tracker.py` - Core MLflow Integration
Core library for MLflow tracking in CAMINA pipeline.

**Features:**
- Experiment tracking
- Metrics logging (overall and per-class)
- Artifact management
- Dataset instance count validation
- Edge deployment metrics

### 2. `monitor_dataset_balance.py` - Dataset Balance Monitor
Track instance counts and ensure dataset balance meets requirements.

**Usage:**
```bash
# Basic monitoring
python tools/monitor_dataset_balance.py --dataset data/datasetV3_stratified

# With MLflow tracking
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --min-threshold 300 \
    --target-threshold 500 \
    --mlflow
```

**Output:**
- Visual progress bars for each class
- Warnings for classes below thresholds
- Prioritized recommendations for data collection
- JSON report with complete statistics
- MLflow tracking (optional)

### 3. `train_with_mlflow.py` - Training with MLflow
Wrapper for YOLO training with automatic MLflow tracking.

**Usage:**
```bash
# Train single model
python tools/train_with_mlflow.py \
    --model YOLOv8n \
    --model-path yolov8n.pt \
    --data data/datasetV3_stratified/data.yaml \
    --epochs 150 \
    --batch 16
```

**Tracks:**
- Training hyperparameters
- Overall metrics (mAP@0.5, precision, recall)
- Per-class AP@0.5 for all 9 classes
- Model artifacts (weights, plots, configs)
- Dataset instance counts

## 🚀 Quick Start

### Step 1: Monitor Your Dataset

```bash
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --min-threshold 300 \
    --target-threshold 500 \
    --mlflow
```

**Check output for:**
- ⚠️ Classes below minimum (300): HIGH PRIORITY
- ⚡ Classes below target (500): Add more when possible
- ✅ Classes meeting target: Good to go!

### Step 2: Add More Images (if needed)

If classes are below thresholds:
1. Focus on classes marked ⚠️ (below minimum) first
2. Use autolabeling or manual annotation
3. Re-run monitoring to verify progress

### Step 3: Train Models

```bash
python tools/train_with_mlflow.py \
    --model YOLOv8n \
    --model-path yolov8n.pt \
    --data data/datasetV3_stratified/data.yaml \
    --epochs 150
```

### Step 4: View Results

```bash
mlflow ui
# Open http://localhost:5000
```

## 📊 Key Thresholds

For CAMINA urban mobility detection:

| Threshold | Instances/Class | Purpose |
|-----------|----------------|---------|
| **Minimum** | 300 | Basic training capability |
| **Target** | 500 | Robust performance |
| **Ideal** | 1000+ | Production-ready models |

## 🎯 Workflow Example

```bash
# 1. Check current dataset balance
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --mlflow

# Output shows:
# ⚠️ delivery_van: 112 instances (need 188 more for minimum)
# ⚡ truck: 132 instances (need 368 more for target)

# 2. Add more images with underrepresented classes
# (collect and label images...)

# 3. Re-check balance
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --mlflow

# Output shows:
# ✅ delivery_van: 315 instances (63% of target)
# ✅ truck: 510 instances (102% of target)

# 4. Train when all classes meet minimum
python tools/train_with_mlflow.py \
    --model YOLOv8n \
    --model-path yolov8n.pt \
    --data data/datasetV3_stratified/data.yaml \
    --epochs 150

# 5. Compare results in MLflow UI
mlflow ui
```

## 🔍 What Gets Tracked

### Dataset Monitoring
- Total instances per class
- Percentage distribution
- Imbalance ratio
- Classes below thresholds
- Collection progress (% of target)

### Model Training
- **Parameters**: Model type, epochs, batch size, learning rate, etc.
- **Metrics**: mAP@0.5, precision, recall (overall + per-class)
- **Artifacts**: Best weights, training plots, configs
- **Dataset**: Instance counts, class distribution, split info

### Edge Deployment
- Inference time (ms)
- FPS
- Model size (MB)
- Device specifications

## 📈 Viewing in MLflow UI

### Compare Runs
1. Select multiple runs (checkbox)
2. Click "Compare"
3. View side-by-side metrics and parameters

### Search and Filter
```
# Filter by performance
metrics.map50 > 0.55

# Filter by model
params.model = 'YOLOv8n'

# Filter by dataset
tags.dataset_name = 'datasetV3_stratified'
```

### Download Artifacts
1. Click on a run
2. Scroll to "Artifacts"
3. Download model weights, plots, or configs

## 💡 Best Practices

### 1. Monitor Before Every Training
Always check dataset balance before training:
```bash
python tools/monitor_dataset_balance.py --dataset <path> --mlflow
```

### 2. Track Everything
Use `--mlflow` flag to maintain history of all experiments

### 3. Prioritize Data Collection
- Focus on ⚠️ classes (below minimum) first
- Aim for ⚡ classes (below target) next
- Maintain balance (keep imbalance ratio < 10x)

### 4. Use Consistent Naming
- Datasets: `datasetV{version}_{description}`
- Models: `{Architecture}{size}` (e.g., YOLOv8n)
- Experiments: Descriptive names with dates

### 5. Document Decisions
Use MLflow run notes to explain:
- Why certain hyperparameters were chosen
- Data collection decisions
- Model selection reasoning

## 🐛 Troubleshooting

### MLflow not found
```bash
pip install mlflow
```

### Port already in use
```bash
mlflow ui --port 5001
```

### Tracking URI issues
MLflow stores data in `mlruns/` by default. To change:
```bash
export MLFLOW_TRACKING_URI=file:///path/to/mlruns
```

### Can't see recent runs
Refresh your browser (F5) in MLflow UI

## 📚 More Information

- Full guide: `docs/MLFLOW_GUIDE.md`
- MLflow docs: https://mlflow.org/docs/latest/
- CAMINA repo: https://github.com/tamagusko/camina

## 🎯 Current Dataset Status (Example)

Based on your current dataset:

| Class | Instances | Status | Action Needed |
|-------|-----------|--------|---------------|
| person | 6,975 | ✅ | None |
| cyclist | 2,012 | ✅ | None |
| car | 2,105 | ✅ | None |
| e-scooter | 728 | ✅ | None |
| SUV | 456 | ⚡ | +44 for target |
| motorcyclist | 307 | ✅ | None |
| bus | 321 | ⚡ | +179 for target |
| truck | 132 | ⚠️ | +168 to minimum |
| delivery_van | 112 | ⚠️ | +188 to minimum |

**Priority actions:**
1. 🔴 HIGH: Add 188+ images with delivery_van
2. 🔴 HIGH: Add 168+ images with truck
3. 🟡 MEDIUM: Add 179+ images with bus
4. 🟡 MEDIUM: Add 44+ images with SUV

---

**Need help?** Check the full guide in `docs/MLFLOW_GUIDE.md`
