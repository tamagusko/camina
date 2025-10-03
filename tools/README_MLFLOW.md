# MLflow Tools for CAMINA

Experiment tracking and dataset monitoring tools with MLflow integration.

Pure functional implementation without classes - simple, clear, and maintainable.

## 📦 Installation

```bash
pip install mlflow
```

## 🛠️ Tools Overview

### 1. `mlflow_tracker.py` - Core MLflow Integration
Core library providing pure functions for MLflow tracking in CAMINA pipeline.

**Features:**
- Experiment initialization and run management
- Metrics logging (overall and per-class)
- Artifact management
- Dataset instance count validation
- Edge deployment metrics

**Architecture:** Pure functional - no classes, no state management
**Functions:** 20+ specialized functions, each doing ONE thing clearly

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

**Architecture:** Pure functional - composed of small, focused functions

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

**Architecture:** Pure functional - clear data flow without classes

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
- [X] Classes below minimum (300): HIGH PRIORITY
- [!] Classes below target (500): Add more when possible
- [OK] Classes meeting target: Good to go!

### Step 2: Add More Images (if needed)

If classes are below thresholds:
1. Focus on classes marked [X] (below minimum) first
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
# [X] delivery_van: 112 instances (need 188 more for minimum)
# [!] truck: 132 instances (need 368 more for target)

# 2. Add more images with underrepresented classes
# (collect and label images...)

# 3. Re-check balance
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --mlflow

# Output shows:
# [OK] delivery_van: 315 instances (63% of target)
# [OK] truck: 510 instances (102% of target)

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
- Focus on [X] classes (below minimum) first
- Aim for [!] classes (below target) next
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

## 🏗️ Code Architecture

All MLflow tools follow **pure functional programming** principles:

### Design Principles
- **No classes** - Only pure functions
- **No state** - All data passed as parameters
- **Single responsibility** - Each function does ONE thing
- **Self-explanatory names** - `instance_counts_per_class` not `counts`
- **Clear data flow** - Function → Process → Return

### Example Function Signature
```python
def count_instances_from_label_files(
    labels_directory: Path,
    class_names: List[str]
) -> Dict[str, int]:
    """
    Count instances per class from YOLO label files.

    Args:
        labels_directory: Directory containing .txt label files
        class_names: Ordered list of class names

    Returns:
        Dictionary mapping class name to instance count
    """
```

### Benefits
- Easy to understand and modify
- Easy to test (pure functions)
- No hidden state or side effects
- Clear separation of concerns
- Minimal cognitive load

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

## 📚 Code Organization

### mlflow_tracker.py Structure
```
├── EXPERIMENT INITIALIZATION
│   └── initialize_mlflow_experiment()
├── RUN MANAGEMENT
│   ├── start_dataset_creation_run()
│   ├── start_model_training_run()
│   └── end_mlflow_run()
├── INSTANCE COUNTING
│   └── count_instances_from_label_files()
├── THRESHOLD CHECKING
│   └── categorize_classes_by_threshold()
├── STATISTICS CALCULATION
│   └── calculate_dataset_statistics()
├── MLFLOW LOGGING
│   ├── log_instance_counts_to_mlflow()
│   ├── log_training_parameters()
│   ├── log_training_metrics()
│   ├── log_per_class_performance()
│   ├── log_model_artifacts()
│   └── log_edge_deployment_performance()
└── UTILITY FUNCTIONS
    └── print_mlflow_ui_instructions()
```

### monitor_dataset_balance.py Structure
```
├── INSTANCE COUNTING
│   ├── count_dataset_instances()
│   └── count_dataset_images()
├── STATISTICS CALCULATION
│   └── calculate_instance_statistics()
├── THRESHOLD CATEGORIZATION
│   └── categorize_classes_by_thresholds()
├── PROGRESS CALCULATION
│   └── calculate_collection_progress()
├── ANALYSIS
│   └── analyze_dataset_balance()
├── REPORTING
│   ├── print_dataset_balance_report()
│   └── save_analysis_report()
└── MLFLOW INTEGRATION
    └── track_dataset_balance_with_mlflow()
```

### train_with_mlflow.py Structure
```
├── DATASET LOADING
│   ├── load_dataset_configuration()
│   └── extract_dataset_info()
├── TRAINING EXECUTION
│   └── train_yolo_model()
├── MODEL VALIDATION
│   └── validate_trained_model()
├── ARTIFACT COLLECTION
│   └── collect_training_artifacts()
├── TRAINING WITH MLFLOW
│   └── train_yolo_model_with_mlflow()
└── BATCH TRAINING
    └── train_multiple_yolo_models()
```

## 🎯 Current Dataset Status (Example)

Based on your current dataset:

| Class | Instances | Status | Action Needed |
|-------|-----------|--------|---------------|
| person | 6,975 | [OK] | None |
| cyclist | 2,012 | [OK] | None |
| car | 2,105 | [OK] | None |
| e-scooter | 728 | [OK] | None |
| SUV | 456 | [!] | +44 for target |
| motorcyclist | 307 | [OK] | None |
| bus | 321 | [!] | +179 for target |
| truck | 132 | [X] | +168 to minimum |
| delivery_van | 112 | [X] | +188 to minimum |

**Priority actions:**
1. HIGH: Add 188+ images with delivery_van
2. HIGH: Add 168+ images with truck
3. MEDIUM: Add 179+ images with bus
4. MEDIUM: Add 44+ images with SUV

---

**Code Style:** Pure functional programming - no classes, simple and clear

**Need help?** Check the inline documentation in each Python file
