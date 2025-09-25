# CAMINA Metrics Extraction Guide

This guide explains the clean, academically sound metrics extraction system in CAMINA, designed to provide only real validation metrics without any estimates or mathematical inaccuracies.

## 🎯 Key Principle: Real Metrics Only

**All metrics are extracted directly from YOLO validation - NO estimates, NO random scaling factors, NO values > 1.0**

## 📊 Available Scripts

### ✅ `extract_real_ap50_only.py` (RECOMMENDED)

The cleanest and most academically sound metrics extraction script.

**What it provides:**
- ✅ Real per-class AP@0.5 values from YOLO validation
- ✅ Overall performance metrics (mAP@0.5, mAP@0.5:0.95, precision, recall)
- ✅ Publication-ready markdown tables
- ✅ JSON output for programmatic access
- ✅ Statistical summaries

**What it does NOT provide:**
- ❌ No estimated per-class precision/recall
- ❌ No random scaling factors
- ❌ No mathematically incorrect values

#### Usage:
```bash
python extract_real_ap50_only.py
```

#### Output Files:
- `outputs/model_comparison/results/real_ap50_only.json` - Raw metrics
- `outputs/model_comparison/tables/table2_real_ap50_only.md` - Academic table

#### Sample Output Table:
```markdown
| Class | Instances | YOLO11n AP@0.5 | YOLOv10n AP@0.5 | YOLOv5n AP@0.5 | YOLOv8n AP@0.5 |
|-------|-----------|----------------|------------------|----------------|----------------|
| Person | 6,975 | 0.745 | 0.723 | 0.698 | 0.712 |
| Cyclist | 2,012 | 0.623 | 0.587 | 0.534 | 0.601 |
| Car | 2,105 | 0.834 | 0.821 | 0.798 | 0.819 |
...
```

### ✅ `extract_only_real_metrics.py` (COMPREHENSIVE)

Provides comprehensive metrics from both training logs and validation.

**What it provides:**
- ✅ Real per-class AP@0.5 from YOLO validation
- ✅ Training results from results.csv
- ✅ Overall validation metrics
- ✅ Academic table with comprehensive data

#### Usage:
```bash
python extract_only_real_metrics.py
```

#### Output Files:
- `outputs/model_comparison/results/real_metrics_only.json` - Raw metrics
- `outputs/model_comparison/tables/table2_real_validation_only.md` - Academic table

### ❌ `src/extract_real_perclass_metrics.py` (DEPRECATED)

**DO NOT USE** - Contains estimated values with mathematical inaccuracies.

**Problems with this script:**
- ❌ Uses random scaling factors: `np.random.uniform(0.9, 1.1)`
- ❌ Can produce precision/recall > 1.0 (mathematically impossible)
- ❌ Estimated values, not real validation metrics
- ❌ Not suitable for academic publication

**This script has been moved to `src/` and marked as deprecated.**

## 🔬 Technical Details

### What YOLO Actually Provides

#### Per-Class Metrics Available:
- ✅ **AP@0.5** (Average Precision at IoU=0.5) - Real per-class values
- ✅ **AP@0.5:0.95** (AP averaged over IoU thresholds) - Real per-class values

#### Overall Metrics Available:
- ✅ **Overall mAP@0.5** - Mean of all class AP@0.5 values
- ✅ **Overall mAP@0.5:0.95** - Mean of all class AP@0.5:0.95 values
- ✅ **Overall Precision** - Single value across all classes
- ✅ **Overall Recall** - Single value across all classes

#### What YOLO Does NOT Provide:
- ❌ **Per-class precision** - Only overall precision available
- ❌ **Per-class recall** - Only overall recall available
- ❌ **Per-class F1 scores** - Cannot be calculated without per-class precision/recall

### Why We Only Extract Real Values

1. **Academic Integrity**: Only use metrics that are actually computed by the model
2. **Mathematical Accuracy**: No estimated values that could be > 1.0
3. **Reproducibility**: Results can be verified by running YOLO validation
4. **Publication Quality**: Suitable for peer-reviewed academic papers

## 📈 Academic Usage

### For Research Papers

Use the clean metrics for academic publications:

```bash
# Generate publication-ready table
python extract_real_ap50_only.py

# Use the generated table:
# outputs/model_comparison/tables/table2_real_ap50_only.md
```

### Citation Note

When using these metrics in papers, you can state:

> "All performance metrics are extracted directly from YOLO validation results without estimation or scaling factors, ensuring mathematical accuracy and reproducibility."

## 🔍 Verification

### How to Verify Results

1. **Run YOLO validation manually**:
```bash
from ultralytics import YOLO
model = YOLO("model/yolo_comparison/YOLO11n/train/weights/best.pt")
results = model.val(data="data/datasetV3_stratified/data.yaml")
print(results.box.maps)  # Per-class AP@0.5 values
```

2. **Compare with our extraction**:
The values should match exactly.

### Common Verification Checks

✅ **All AP@0.5 values are ≤ 1.0**
✅ **Values match manual YOLO validation**
✅ **No random variation between runs**
✅ **Consistent with training logs**

## 📊 Output Format Comparison

### Clean Script Output (GOOD):
```json
{
  "YOLO11n": {
    "overall_metrics": {
      "map50": 0.687,
      "map50_95": 0.412,
      "precision": 0.734,
      "recall": 0.623
    },
    "class_wise_ap": {
      "Person": 0.745,
      "Cyclist": 0.623,
      "Car": 0.834
    }
  }
}
```

### Deprecated Script Output (BAD):
```json
{
  "YOLO11n": {
    "class_wise_precision": {
      "Person": 1.127,  // ❌ > 1.0 - mathematically impossible!
      "Cyclist": 0.943
    },
    "class_wise_recall": {
      "Person": 1.083,  // ❌ > 1.0 - mathematically impossible!
      "Cyclist": 0.891
    }
  }
}
```

## 🚀 Best Practices

### For Academic Research

1. **Always use** `extract_real_ap50_only.py`
2. **Document the source** of metrics (YOLO validation)
3. **Include validation command** in methodology
4. **Verify results** against manual validation

### For Model Comparison

1. **Focus on AP@0.5** - the most reliable per-class metric
2. **Use overall metrics** for precision/recall comparisons
3. **Include confidence intervals** if running multiple validation runs
4. **Document dataset** and validation methodology

### For Publication

1. **Use real metrics only** - no estimates
2. **State validation method** clearly
3. **Include model details** (epochs, dataset, etc.)
4. **Provide reproducibility information**

## ⚠️ Common Pitfalls to Avoid

1. **Don't estimate per-class precision/recall** - YOLO doesn't provide these
2. **Don't use random scaling factors** - mathematically unsound
3. **Don't mix training and validation metrics** - use validation for final results
4. **Don't trust metrics > 1.0** - indicates estimation errors

## 📚 Further Reading

- [YOLO Validation Documentation](https://docs.ultralytics.com/modes/val/)
- [AP Metrics Explanation](https://jonathan-hui.medium.com/map-mean-average-precision-for-object-detection-45c121a31173)
- [Model Evaluation Best Practices](https://paperswithcode.com/sota)

---

**Remember**: Academic integrity requires using only real, verifiable metrics. Our clean extraction ensures your research meets the highest standards.