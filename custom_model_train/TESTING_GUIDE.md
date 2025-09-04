# CAMINA Pipeline Testing Guide

This guide provides step-by-step instructions for testing and running the complete CAMINA dataset expansion pipeline.

## 🚀 Quick Start

### 1. Prerequisites Check

First, run the quick validation script to ensure everything is set up correctly:

```bash
# Make scripts executable
chmod +x run_tests.sh
chmod +x run_camina_pipeline.py

# Run quick validation
./run_tests.sh
```

**Expected Output:**
```
🧪 CAMINA PIPELINE QUICK TEST SUITE
✅ Python Dependencies Check PASSED
✅ Directory Structure Check PASSED  
✅ Script Files Check PASSED
✅ Script Syntax Validation PASSED
✅ SDL Dataset Check PASSED
✅ Pipeline Runner Quick Test PASSED
✅ Configuration File Check PASSED

📊 All tests passed! (7/7)
🚀 Pipeline is ready to run!
```

### 2. Run Pipeline Tests Only

To run comprehensive tests without full training:

```bash
python3 run_camina_pipeline.py --mode test --verbose
```

### 3. Run Quick Pipeline Test

For rapid development/testing with minimal resources:

```bash
python3 run_camina_pipeline.py --quick --verbose
```

### 4. Run Full Pipeline

For complete pipeline execution with training and comparison:

```bash
python3 run_camina_pipeline.py --mode full --config pipeline_config.yaml
```

---

## 📋 Detailed Testing Scenarios

### Scenario 1: First-Time Setup Validation

**Purpose**: Verify that the environment is correctly configured

```bash
# 1. Check system requirements
./run_tests.sh

# 2. Test individual components
python3 run_camina_pipeline.py --mode test --verbose

# 3. Check results
ls -la pipeline_results/
cat pipeline_results/*/pipeline_report.json
```

**What to expect:**
- All dependency checks pass
- Dataset structure is validated
- Script syntax is correct
- Configuration files are valid

### Scenario 2: Quick Development Testing

**Purpose**: Fast iteration during development

```bash
# Run with minimal resources
python3 run_camina_pipeline.py \
  --quick \
  --no-cleanup \
  --verbose \
  --output-dir quick_test_results
```

**Configuration for quick testing:**
- Training epochs: 1-3
- Batch size: 2-4  
- Models: Only YOLO11n
- No video benchmarking
- CPU-only mode

### Scenario 3: Model Comparison Testing

**Purpose**: Compare multiple YOLO models performance

```bash
# Edit pipeline_config.yaml to include desired models
python3 run_camina_pipeline.py \
  --config pipeline_config.yaml \
  --mode full \
  --verbose
```

**Expected outputs:**
- Training results for each model
- Comparison metrics (mAP, FPS, size)
- Performance visualizations
- Deployment packages

### Scenario 4: Production Readiness Testing

**Purpose**: Full validation before production deployment

```bash
# Full pipeline with all optimizations
python3 run_camina_pipeline.py \
  --mode full \
  --config pipeline_config.yaml \
  --output-dir production_test \
  --verbose > full_test.log 2>&1

# Monitor progress
tail -f full_test.log
```

**What gets tested:**
- Complete dataset conversion (6→9 classes)
- Full model training (100+ epochs)
- Multi-model comparison 
- SAM2+CLIP auto-labeling
- Raspberry Pi 5 deployment optimization
- Comprehensive performance metrics

---

## 🔧 Configuration Options

### Basic Configuration (`pipeline_config.yaml`)

```yaml
pipeline:
  epochs: 50              # Training epochs
  batch_size: 16         # Batch size
  device: "auto"         # auto, cpu, cuda, mps
  models_to_compare:     # Models to benchmark
    - "yolov8n"
    - "yolo11n"
  cleanup_after_test: false

testing:
  quick_test_epochs: 3   # For --quick mode
  run_memory_profiling: true
  validate_outputs: true
```

### Command Line Options

```bash
# Basic usage
python3 run_camina_pipeline.py [OPTIONS]

# Options:
--mode {full,test,pipeline}   # Execution mode
--config CONFIG_FILE          # Custom configuration
--quick                      # Fast testing mode  
--no-cleanup                 # Keep temporary files
--output-dir DIR             # Results directory
--verbose                    # Detailed logging
```

### Environment Variables

```bash
# Optional environment configuration
export CUDA_VISIBLE_DEVICES=0    # GPU selection
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128  # Memory management
export YOLO_VERBOSE=False        # Reduce YOLO logging
```

---

## 📊 Understanding Test Results

### Test Report Structure

After running tests, check the generated report:

```bash
# View main report
cat pipeline_results/*/pipeline_report.json

# Key sections:
# - pipeline_info: Timing and configuration
# - summary: Pass/fail statistics  
# - pipeline_steps: Individual step results
# - test_results: Test outcomes
# - recommendations: Next steps
```

### Success Indicators

**✅ All Tests Pass:**
```json
{
  "summary": {
    "pipeline_steps_passed": 6,
    "pipeline_steps_total": 6,
    "tests_passed": 8,
    "tests_total": 8,
    "overall_success": true
  }
}
```

**❌ Some Tests Fail:**
```json
{
  "summary": {
    "overall_success": false
  },
  "recommendations": [
    "Some pipeline steps failed. Check individual step logs for details."
  ]
}
```

### Performance Metrics

Check these key metrics in your results:

```bash
# Dataset conversion statistics
grep "Class Distribution" pipeline_logs/*/dataset_conversion.log

# Training performance
ls runs/train/*/weights/
cat runs/train/*/results.csv

# Model comparison results  
cat results/model_comparison_*/model_comparison_summary.csv

# Deployment optimization
ls */ncnn_model/
cat */README.md
```

---

## 🐛 Troubleshooting

### Common Issues and Solutions

#### 1. Dependency Errors
```bash
# Error: ModuleNotFoundError: No module named 'ultralytics'
pip install ultralytics opencv-python numpy pandas matplotlib seaborn torch torchvision

# For CLIP (optional)
pip install git+https://github.com/openai/CLIP.git
```

#### 2. CUDA Memory Issues  
```bash
# Reduce batch size
python3 run_camina_pipeline.py --quick  # Uses batch_size=2

# Or edit pipeline_config.yaml:
testing:
  test_batch_size: 1
pipeline:
  batch_size: 8
```

#### 3. Dataset Not Found
```bash
# Check dataset location
ls -la "datasets/SDL fine-tuned_v3-cyclist_cleaned/"

# Update path in config
pipeline:
  sdl_dataset_path: "your/actual/path/to/SDL dataset"
```

#### 4. Training Fails
```bash
# Check training logs
cat pipeline_logs/*/training_test.log
cat runs/train/*/train_log.txt

# Common fixes:
# - Use CPU if GPU issues: --config with device: "cpu"
# - Reduce batch size: batch_size: 4
# - Check disk space: df -h
```

#### 5. Script Permission Errors
```bash
# Fix permissions
chmod +x run_tests.sh
chmod +x run_camina_pipeline.py
chmod +x scripts/*.py
```

### Debug Mode

For detailed debugging:

```bash
# Maximum verbosity
python3 run_camina_pipeline.py \
  --mode test \
  --verbose \
  --no-cleanup \
  --output-dir debug_results

# Check individual logs
ls pipeline_logs/*/
tail -f pipeline_logs/*/*.log
```

### Memory Monitoring

Monitor resource usage during testing:

```bash
# Run in one terminal
python3 run_camina_pipeline.py --mode full --verbose

# Monitor in another terminal  
watch -n 2 'nvidia-smi && echo "---" && free -h && echo "---" && df -h'
```

---

## 📈 Performance Expectations

### Expected Test Times

| Test Type | Duration | Resource Usage |
|-----------|----------|----------------|
| Quick validation (`./run_tests.sh`) | 30 seconds | Minimal |
| Test mode (`--mode test`) | 2-5 minutes | Low CPU |
| Quick pipeline (`--quick`) | 10-30 minutes | 1-2GB RAM |
| Full pipeline | 2-6 hours | 4-8GB RAM, GPU |

### Expected Outputs

After successful testing, you should have:

```
pipeline_results/
└── camina_run_YYYYMMDD_HHMMSS/
    ├── pipeline_report.json     # Main results
    └── ...

pipeline_logs/
└── camina_run_YYYYMMDD_HHMMSS/
    ├── dataset_conversion.log
    ├── training_test.log
    ├── auto_labeling_test.log
    └── ...

all_camina_classes/              # Converted dataset
├── data.yaml
├── classes.txt  
└── images/labels/...

runs/train/                      # Training results
deployment_*/                    # Deployment packages
results/                         # Comparison results
```

---

## 🎯 Next Steps After Testing

### 1. If All Tests Pass ✅

```bash
# Ready for production training
python3 scripts/train_yolo11n.py \
  --data all_camina_classes/data.yaml \
  --epochs 200 \
  --batch 16 \
  --device cuda

# Run full model comparison
python3 scripts/model_comparison_framework.py \
  --epochs 100 \
  --models yolov5n yolov8n yolo11n
```

### 2. If Some Tests Fail ❌

1. **Review logs**: Check `pipeline_logs/` for specific errors
2. **Check requirements**: Ensure all dependencies are installed  
3. **Validate data**: Confirm SDL dataset is correctly placed
4. **Resource limits**: Try `--quick` mode first
5. **Report issues**: Use the error logs to troubleshoot

### 3. Customize for Your Needs

```bash
# Edit configuration
cp pipeline_config.yaml my_config.yaml
# ... customize settings ...

# Run with custom config
python3 run_camina_pipeline.py --config my_config.yaml
```

---

## 📞 Getting Help

### Log Analysis

Check these files for troubleshooting:
- `pipeline_logs/*/pipeline_report.json` - Overall results
- `pipeline_logs/*/*.log` - Individual step logs  
- `runs/train/*/` - Training outputs
- `*.log` files - Command outputs

### Issue Reporting

When reporting issues, include:
1. **Command used**: Full command line
2. **Error logs**: Relevant log files
3. **Environment**: OS, Python version, GPU info
4. **Configuration**: Your `pipeline_config.yaml`

This comprehensive testing framework ensures your CAMINA pipeline is robust and ready for production deployment! 🚀