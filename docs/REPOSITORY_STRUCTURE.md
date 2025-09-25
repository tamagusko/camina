# CAMINA Repository Structure

This document describes the newly reorganized CAMINA repository structure for academic research and professional development.

## 🎯 Key Improvements

### ✅ Clean Metrics Extraction
- **Removed estimated precision/recall** calculations that used random scaling factors
- **Only real AP@0.5 values** extracted directly from YOLO validation
- **Mathematically sound** metrics for academic publication
- **No values > 1.0** - all metrics are now accurate

### ✅ Professional Organization
- **Organized model storage**: `model/` directory for all trained models
- **Clean source separation**: `src/` for utilities, main scripts at root
- **Proper documentation**: Comprehensive docs in `docs/`
- **Academic-ready structure**: Professional codebase organization

## 📂 Directory Structure

```
camina/
├── README.md                           # Main project documentation
├── main.py                            # Main detection script
├── train_evaluate_yolo_models.py      # Academic training pipeline
├── extract_only_real_metrics.py       # Clean comprehensive metrics
├── extract_real_ap50_only.py          # Clean AP@0.5 only (recommended)
├── training_logger.py                 # Training logging utilities
│
├── model/                             # Trained models (NEW: organized structure)
│   ├── yolo_comparison/              # YOLO model comparison results
│   │   ├── YOLOv5n/                 # YOLOv5 nano training results
│   │   │   └── train/
│   │   │       └── weights/
│   │   │           └── best.pt      # Trained model weights
│   │   ├── YOLOv8n/                 # YOLOv8 nano training results
│   │   ├── YOLOv10n/                # YOLOv10 nano training results
│   │   └── YOLO11n/                 # YOLO11 nano training results
│   ├── yolo_base/                    # Base YOLO models
│   ├── yolo_world/                   # YOLO-World models
│   └── camina/                       # CAMINA-specific models
│
├── src/                              # Source code and utilities (REORGANIZED)
│   ├── config.py                     # Configuration management
│   ├── utils.py                      # General utilities
│   ├── io_utils.py                   # Input/output utilities
│   ├── cyclist_logic.py              # Cyclist detection logic
│   ├── escooter_logic.py             # E-scooter detection logic
│   ├── merger_nms.py                 # NMS merging logic
│   ├── detector_yolo11n.py           # YOLO11n detector
│   ├── detector_yolo_world.py        # YOLO-World detector
│   ├── model_optimization_ncnn.py    # NCNN optimization (moved from root)
│   ├── class_distribution_analysis.py # Dataset analysis (moved from root)
│   ├── generate_comprehensive_reports.py # Report generation (moved from root)
│   ├── generate_performance_visualizations.py # Visualization (moved from root)
│   ├── validate_training_setup.py    # Setup validation (moved from root)
│   ├── verify_installation.py        # Installation verification (moved from root)
│   ├── extract_real_perclass_metrics.py # LEGACY (deprecated - had estimates)
│   ├── training_logger_backup.py     # Backup training logger
│   ├── training_logger_fixed.py      # Fixed training logger
│   └── scripts/                      # Utility scripts
│
├── docs/                             # Complete documentation
│   ├── README.md                     # Documentation index
│   ├── REPOSITORY_STRUCTURE.md       # This file - structure guide
│   ├── METRICS_EXTRACTION.md         # Clean metrics guide
│   ├── quick_start.md                # Quick start guide
│   ├── user_guide.md                 # Complete usage guide
│   ├── configuration.md              # Advanced configuration
│   ├── training_guide.md             # Academic training
│   ├── run_comparison.md             # Model comparison guide (moved from root)
│   └── TROUBLESHOOTING.md            # Common issues and solutions
│
├── tests/                            # Test suite
│   ├── test_config.py                # Configuration tests
│   └── test_cyclist_logic.py         # Logic tests
│
├── data/                             # Input datasets
├── outputs/                          # Detection and training results
├── configs/                          # Configuration files
├── paper/                            # Academic paper drafts
└── archive/                          # Historical files
```

## 🔄 What Changed

### Moved Files

#### From Root to `src/`:
- `class_distribution_analysis.py` → `src/class_distribution_analysis.py`
- `extract_real_perclass_metrics.py` → `src/extract_real_perclass_metrics.py` (DEPRECATED)
- `generate_comprehensive_reports.py` → `src/generate_comprehensive_reports.py`
- `generate_performance_visualizations.py` → `src/generate_performance_visualizations.py`
- `model_optimization_ncnn.py` → `src/model_optimization_ncnn.py`
- `training_logger_backup.py` → `src/training_logger_backup.py`
- `training_logger_fixed.py` → `src/training_logger_fixed.py`
- `validate_training_setup.py` → `src/validate_training_setup.py`
- `verify_installation.py` → `src/verify_installation.py`

#### Directory Reorganization:
- `models/` → `model/` (cleaner naming)
- `run_comparison.md` → `docs/run_comparison.md`

#### Removed Old Directory:
- `models/` (replaced by `model/`)

### Stayed at Root (Main Execution Scripts):
- `main.py` - Main detection script
- `train_evaluate_yolo_models.py` - Academic training pipeline
- `extract_only_real_metrics.py` - Clean comprehensive metrics
- `extract_real_ap50_only.py` - Clean AP@0.5 metrics (NEW)
- `training_logger.py` - Current training logger

## 🎓 Academic Features

### Clean Metrics Scripts

#### `extract_real_ap50_only.py` (RECOMMENDED)
- ✅ **Only real AP@0.5 values** from YOLO validation
- ✅ **No estimated metrics** - mathematically sound
- ✅ **Publication-ready tables** for academic papers
- ✅ **No random scaling factors** - all values are real

#### `extract_only_real_metrics.py`
- ✅ **Comprehensive real metrics** from YOLO validation
- ✅ **Overall performance** (mAP@0.5, precision, recall)
- ✅ **Training results** from results.csv
- ✅ **Academic table format** ready for papers

#### `src/extract_real_perclass_metrics.py` (DEPRECATED)
- ❌ **Contains estimated values** with random scaling
- ❌ **Mathematically incorrect** - can produce values > 1.0
- ❌ **Not suitable for academic publication**
- 🔄 **Replaced by** `extract_real_ap50_only.py`

## 📊 Usage Examples

### Clean Academic Metrics
```bash
# Generate clean AP@0.5 table (recommended)
python extract_real_ap50_only.py
# → outputs/model_comparison/tables/table2_real_ap50_only.md

# Generate comprehensive metrics
python extract_only_real_metrics.py
# → outputs/model_comparison/tables/table2_real_validation_only.md

# DON'T USE (deprecated - has estimates):
# python src/extract_real_perclass_metrics.py
```

### Training Pipeline
```bash
# Academic training with proper model organization
python train_evaluate_yolo_models.py
# → Saves to model/yolo_comparison/[ModelName]/
```

### Utility Scripts (now in src/)
```bash
# Run auxiliary scripts from src/
python src/validate_training_setup.py
python src/verify_installation.py
python src/class_distribution_analysis.py
```

## 🔧 Path Updates

All scripts have been updated to use the new `model/` path:

### Before:
```python
models_dir = base_dir / "models" / "yolo_comparison"
```

### After:
```python
models_dir = base_dir / "model" / "yolo_comparison"
```

## 💡 Benefits of New Structure

### For Researchers:
- **Clean metrics** - no more estimated values
- **Professional organization** - easy to navigate
- **Academic-ready** - publication-quality outputs
- **Reproducible** - all metrics from real YOLO validation

### For Developers:
- **Clear separation** - main scripts vs utilities
- **Proper imports** - organized source code
- **Better maintenance** - logical file organization
- **Collaboration-friendly** - professional structure

### For Publications:
- **Mathematically sound** metrics
- **No random scaling** factors
- **Real validation** results only
- **Professional tables** ready for papers

## 🚀 Next Steps

1. **Use clean metrics**: Always use `extract_real_ap50_only.py`
2. **Update imports**: If you have custom scripts, update paths to `model/`
3. **Check documentation**: New structure documented in `docs/`
4. **Academic publishing**: Use generated tables for papers

---

**Note**: This reorganization ensures academic rigor and professional code organization. All metrics are now mathematically sound and suitable for publication.