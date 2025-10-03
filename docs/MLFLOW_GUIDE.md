# MLflow Integration Guide for CAMINA

Complete guide for using MLflow to track experiments, monitor dataset balance, and manage model training.

## 🚀 Quick Start

### Installation

```bash
# Install MLflow
pip install mlflow

# Verify installation
mlflow --version
```

### Basic Usage

```bash
# 1. Monitor dataset balance
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --min-threshold 300 \
    --target-threshold 500 \
    --mlflow

# 2. Train model with MLflow tracking
python tools/train_with_mlflow.py \
    --model YOLOv8n \
    --model-path yolov8n.pt \
    --data data/datasetV3_stratified/data.yaml \
    --epochs 150

# 3. View results in MLflow UI
mlflow ui
# Open http://localhost:5000 in your browser
```

## 📊 Dataset Balance Monitoring

### Purpose
Track instance counts across classes and ensure you meet collection targets (300 minimum, 500 target instances per class).

### Usage

```bash
# Basic monitoring
python tools/monitor_dataset_balance.py --dataset data/datasetV3_stratified

# With MLflow tracking
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --min-threshold 300 \
    --target-threshold 500 \
    --mlflow \
    --output reports/dataset_balance.json
```

### Output Example

```
📊 CAMINA DATASET BALANCE REPORT
======================================================================
Dataset: data/datasetV3_stratified
Generated: 2025-01-15T10:30:00

📁 Images:
   Train: 1467
   Val:   367
   Total: 1834

🎯 Total Instances: 13148

📋 Per-Class Instance Counts:
----------------------------------------------------------------------
   ✅ person          [██████████████████████████████] 6975/500 (1395.0%)
   ✅ cyclist         [████████████████████████████░░] 2012/500 ( 402.4%)
   ✅ car             [████████████████████████████░░] 2105/500 ( 421.0%)
   ✅ e_scooter       [████████████████████░░░░░░░░░░]  728/500 ( 145.6%)
   ⚠️  SUV            [███████████████░░░░░░░░░░░░░░░]  456/500 (  91.2%)
      └─ Need 44 more instances to reach target
   ⚠️  bus            [██████████████░░░░░░░░░░░░░░░░]  321/500 (  64.2%)
      └─ Need 179 more instances to reach target
   ⚠️  motorcyclist   [█████████████░░░░░░░░░░░░░░░░░]  307/500 (  61.4%)
      └─ Need 193 more instances to reach target
   ⚠️  truck          [████░░░░░░░░░░░░░░░░░░░░░░░░░░]  132/500 (  26.4%)
      └─ Need 368 more instances to reach target
   ⚠️  delivery_van   [███░░░░░░░░░░░░░░░░░░░░░░░░░░░]  112/500 (  22.4%)
      └─ Need 388 more instances to reach target

⚠️  CRITICAL: Classes below minimum threshold (300)
----------------------------------------------------------------------
   • delivery_van: 112 instances (need 188 more)
     Priority: HIGH - Add 188+ images with 'delivery_van'

💡 Recommendations:
----------------------------------------------------------------------
   1. HIGH PRIORITY: Focus on collecting images for:
      - delivery_van (188+ more needed)
   2. MEDIUM PRIORITY: Increase instances for:
      - truck (368 more for target)
      - motorcyclist (193 more for target)
      - bus (179 more for target)
```

### Integration in Workflow

```python
from tools.mlflow_tracker import CAMINAMLflowTracker, load_instance_counts_from_labels

# Track dataset after adding new images
tracker = CAMINAMLflowTracker()

with tracker.start_dataset_tracking("my_dataset", "data/my_dataset"):
    class_names = ["person", "cyclist", "car", ...]

    # Load counts
    train_counts = load_instance_counts_from_labels("data/train/labels", class_names)
    val_counts = load_instance_counts_from_labels("data/val/labels", class_names)
    total_counts = {name: train_counts[name] + val_counts[name] for name in class_names}

    # Log with thresholds
    warnings = tracker.log_instance_counts(total_counts, min_threshold=300, target_threshold=500)

    if warnings['classes_below_min']:
        print("⚠️ Action needed: Some classes below minimum")
```

## 🎯 Training with MLflow

### Single Model Training

```bash
# Train YOLOv8n with MLflow tracking
python tools/train_with_mlflow.py \
    --model YOLOv8n \
    --model-path yolov8n.pt \
    --data data/datasetV3_stratified/data.yaml \
    --epochs 150 \
    --batch 16 \
    --imgsz 640 \
    --device 0
```

### Multiple Model Training

```python
from tools.train_with_mlflow import YOLOTrainerWithMLflow

# Define models to train
models = [
    {"name": "YOLOv5n", "path": "yolov5n.pt"},
    {"name": "YOLOv8n", "path": "yolov8n.pt"},
    {"name": "YOLO11n", "path": "yolo11n.pt"}
]

# Train all models
trainer = YOLOTrainerWithMLflow(experiment_name="CAMINA_Urban_Mobility")
results = trainer.train_all_models(
    models_config=models,
    data_yaml="data/datasetV3_stratified/data.yaml",
    epochs=150,
    batch=16,
    device="0"
)
```

### What Gets Tracked

**Training Parameters:**
- Model architecture
- Epochs, batch size, image size
- Optimizer, learning rate
- Dataset information

**Metrics:**
- Overall: mAP@0.5, mAP@0.5:0.95, precision, recall
- Per-class: AP@0.5 for each of 9 classes
- Training curves (if available)

**Artifacts:**
- Best model weights (best.pt)
- Training plots (results.png, confusion_matrix.png, etc.)
- Configuration files
- Summary JSON

**Dataset Info:**
- Instance counts per class
- Train/val split
- Class distribution
- Balance warnings

## 🖥️ MLflow UI

### Starting the UI

```bash
# Start MLflow UI (from project root)
mlflow ui

# Or specify custom tracking directory
mlflow ui --backend-store-uri mlruns

# Custom port
mlflow ui --port 5001
```

### Viewing Experiments

1. **Open browser**: http://localhost:5000
2. **Select experiment**: "CAMINA_Urban_Mobility"
3. **Compare runs**: Select multiple runs and click "Compare"
4. **View metrics**: Click on any run to see detailed metrics
5. **Download artifacts**: Access model weights and plots

### Key Features

- **Run Comparison**: Side-by-side comparison of multiple training runs
- **Metric Visualization**: Interactive plots of training metrics
- **Parameter Search**: Filter runs by hyperparameters
- **Artifact Management**: Download models and plots
- **Tag Filtering**: Filter by dataset, model type, etc.

## 📈 Advanced Usage

### Custom Tracking

```python
from tools.mlflow_tracker import CAMINAMLflowTracker

tracker = CAMINAMLflowTracker(experiment_name="My_Experiment")

# Start custom run
with tracker.start_training_run("MyModel", "MyDataset"):

    # Log parameters
    tracker.log_training_params({
        "model": "YOLOv8n",
        "custom_param": "value"
    })

    # Log metrics (with steps for time-series)
    for epoch in range(100):
        tracker.log_training_metrics({
            "loss": loss_value,
            "accuracy": acc_value
        }, step=epoch)

    # Log per-class metrics
    tracker.log_per_class_metrics({
        "person": {"ap50": 0.65},
        "car": {"ap50": 0.70}
    })

    # Log edge deployment metrics
    tracker.log_edge_deployment_metrics("Raspberry_Pi_5", {
        "inference_time_ms": 65.46,
        "fps": 15.3
    })

    # Log artifacts
    tracker.log_model_artifacts("best.pt", ["plot.png", "config.yaml"])
```

### Querying Runs Programmatically

```python
import mlflow

# Get experiment
experiment = mlflow.get_experiment_by_name("CAMINA_Urban_Mobility")

# Search runs
runs = mlflow.search_runs(
    experiment_ids=[experiment.experiment_id],
    filter_string="metrics.map50 > 0.55",
    order_by=["metrics.map50 DESC"]
)

# Get best run
best_run = runs.iloc[0]
print(f"Best mAP@0.5: {best_run['metrics.map50']}")
print(f"Model: {best_run['params.model']}")
```

## 🔧 Integration with Existing Pipeline

### 1. Update Training Script

```python
# In your existing training script
from tools.mlflow_tracker import CAMINAMLflowTracker

# Initialize tracker
tracker = CAMINAMLflowTracker()

# Wrap training in MLflow run
with tracker.start_training_run(model_name, dataset_name):
    # Your existing training code
    model = YOLO(model_path)
    results = model.train(...)

    # Log metrics
    tracker.log_training_metrics({
        "map50": results.box.map50,
        "precision": results.box.p.mean()
    })

    tracker.log_model_artifacts(best_weights_path)
```

### 2. Add Dataset Monitoring

```bash
# Before training, check dataset balance
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --mlflow

# Review warnings and add more images if needed
# Then proceed with training
```

### 3. Track Edge Deployment

```python
# After deploying to Raspberry Pi
tracker = CAMINAMLflowTracker()

with tracker.start_training_run("YOLOv8n_deployment", "datasetV3"):
    # Run timing tests
    timing_results = run_raspberry_pi_tests()

    # Log results
    tracker.log_edge_deployment_metrics("Raspberry_Pi_5", {
        "inference_time_ms": timing_results['avg_time_ms'],
        "fps": timing_results['fps'],
        "model_size_mb": model_size
    })
```

## 📋 Best Practices

### 1. Dataset Collection Strategy

- **Monitor regularly**: Run balance check after each batch of new images
- **Priority order**: Focus on classes below minimum threshold first
- **Target 500+**: Aim for 500+ instances per class for robust training
- **Balance matters**: Keep imbalance ratio < 10x if possible

### 2. Experiment Organization

- **Use consistent naming**: `{model_name}_{dataset_version}_{date}`
- **Tag everything**: Use tags for easy filtering (model_type, dataset_version, etc.)
- **Log hyperparameters**: Always log training parameters for reproducibility
- **Save artifacts**: Include plots, configs, and best weights

### 3. Model Comparison

- **Compare apples to apples**: Same dataset, same hyperparameters
- **Track per-class**: Monitor per-class AP@0.5 to identify weak classes
- **Test on edge**: Always validate on target hardware (Raspberry Pi)
- **Document decisions**: Use run notes to explain why certain choices were made

## 🎯 Workflow Example

```bash
# 1. Check dataset balance before training
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --mlflow

# 2. If classes need more data, add images and re-check
# (Add images...)
python tools/monitor_dataset_balance.py \
    --dataset data/datasetV3_stratified \
    --mlflow

# 3. Once balanced, train models
python tools/train_with_mlflow.py \
    --model YOLOv8n \
    --model-path yolov8n.pt \
    --data data/datasetV3_stratified/data.yaml \
    --epochs 150

# 4. View results and compare
mlflow ui
# Open http://localhost:5000

# 5. Export best model and test on Raspberry Pi
# (Export and test...)

# 6. Log edge deployment metrics
# (Done automatically by edge testing scripts)
```

## 📚 Reference

### Class Names (CAMINA)
```python
class_names = [
    "person",        # 0
    "cyclist",       # 1
    "car",           # 2
    "e-scooter",     # 3
    "SUV",           # 4
    "motorcyclist",  # 5
    "bus",           # 6
    "delivery_van",  # 7
    "truck"          # 8
]
```

### Recommended Thresholds
- **Minimum**: 300 instances/class (for basic training)
- **Target**: 500 instances/class (for robust performance)
- **Ideal**: 1000+ instances/class (for production models)

### Tracked Metrics
- `map50`: mAP at IoU 0.5
- `map50_95`: mAP at IoU 0.5:0.95
- `precision`: Average precision across classes
- `recall`: Average recall across classes
- `ap50_{class_name}`: Per-class Average Precision at IoU 0.5
- `instances_{class_name}`: Instance count per class
- `percentage_{class_name}`: Percentage of total instances
- `{device}_inference_time_ms`: Inference time on edge device
- `{device}_fps`: Frames per second on edge device

---

For more information, see:
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [CAMINA Repository](https://github.com/tamagusko/camina)
