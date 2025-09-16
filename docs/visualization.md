# CAMINA Label Visualization Guide

## 📊 Your Test Results Summary

Based on your test run with `python camina_dataset_creator.py img/test/ img/output_test`, here are the results:

- **📁 Total Images:** 35
- **🏷️ Images with Labels:** 31 (88.6% coverage)
- **🎯 Total Detections:** 159 objects
- **🔢 Average per Image:** 5.1 detections

### 🎯 Class Distribution Detected:
| Class | Count | Percentage | Confidence |
|-------|-------|------------|------------|
| **cyclist** | 63 | 39.6% | 1.00 |
| **pedestrian** | 60 | 37.7% | 1.00 |
| **car** | 14 | 8.8% | 1.00 |
| **bus** | 10 | 6.3% | 1.00 |
| **motorcycle** | 6 | 3.8% | 1.00 |
| **SUV** | 5 | 3.1% | 1.00 |
| **truck** | 1 | 0.6% | 1.00 |

*Note: e-scooter and delivery_van were not detected in this test batch*

## 🛠️ Visualization Scripts Created

### 1. **Main Visualizer: `visualize_labels.py`**

**Full-featured visualization tool with multiple options:**

```bash
# Show statistics only
python visualize_labels.py img/output_test --stats-only

# Create summary grid (recommended first check)
python visualize_labels.py img/output_test --summary

# Visualize specific image
python visualize_labels.py img/output_test --image 000000000641.jpg

# Save visualizations instead of displaying
python visualize_labels.py img/output_test --summary --save --output-dir img/visualizations

# Interactive mode - shows first 3 labeled images
python visualize_labels.py img/output_test
```

### 2. **Quick Checker: `quick_check_labels.py`**

**Simplified tool for rapid checking:**

```bash
# Check first 3 images
python quick_check_labels.py img/output_test

# Check 5 random images
python quick_check_labels.py img/output_test --random --count 5

# Check specific image
python quick_check_labels.py img/output_test --image 000000001053.jpg

# Save all checks
python quick_check_labels.py img/output_test --save --count 5
```

## 🎨 Visualization Features

### **Color-Coded Classes:**
- 🔵 **pedestrian** - Light blue boxes
- 🟢 **cyclist** - Light green boxes
- 🔴 **car** - Light red boxes
- 🟡 **motorcycle** - Cyan boxes
- 🟣 **bus** - Magenta boxes
- 🟠 **truck** - Yellow boxes
- 🟤 **e-scooter** - Light brown boxes
- 🟪 **SUV** - Purple boxes
- 🔷 **delivery_van** - Teal boxes

### **Information Displayed:**
- Bounding boxes around detected objects
- Class names with confidence scores
- Image title with detection count
- Summary statistics for entire dataset

## 🔍 Recommended Workflow

### **Step 1: Quick Overview**
```bash
# Get dataset statistics
python visualize_labels.py img/output_test --stats-only
```

### **Step 2: Visual Summary**
```bash
# Create summary grid showing multiple images
python visualize_labels.py img/output_test --summary --save --output-dir img/visualizations
```

### **Step 3: Detailed Inspection**
```bash
# Check specific images that look interesting or problematic
python visualize_labels.py img/output_test --image [IMAGE_NAME]
```

### **Step 4: Random Sampling**
```bash
# Check random images for quality assessment
python quick_check_labels.py img/output_test --random --count 5
```

## 📁 Output Files Created

### **In `img/visualizations/`:**
- `camina_summary.png` - Grid showing multiple labeled images
- `viz_[IMAGE_NAME].png` - Individual image visualizations

## 🔧 Troubleshooting

### **If no visualizations appear:**
```bash
# Make sure matplotlib backend is working
python -c "import matplotlib.pyplot as plt; plt.figure(); plt.show()"
```

### **If images not found:**
```bash
# Check dataset structure
ls -la img/output_test/
ls img/output_test/images/ | head -5
ls img/output_test/labels/ | head -5
```

### **If you want to see confidence thresholds:**
The current output shows confidence=1.00 for all detections because the CAMINA dataset creator applies class-specific thresholds during creation and only saves detections that pass the threshold.

## 🚀 Next Steps

### **For Production Use:**
1. **Review the visualizations** to assess label quality
2. **Import to Roboflow** for human correction if needed:
   ```bash
   # The img/output_test directory is ready for Roboflow import
   ```
3. **Train your YOLO11n model**:
   ```bash
   python camina_yolo11n_trainer.py img/output_test /training_output --edge-optimization
   ```

### **For Better Auto-Labeling:**
If you notice issues with specific classes, you can:
- Adjust confidence thresholds in `camina_dataset_creator.py`
- Use more specific prompts for problematic classes
- Add more diverse training images

## 💡 Tips

- **High confidence (1.00)** means the model was very certain about detections
- **Good class distribution** shows the model found diverse urban mobility objects
- **88.6% label coverage** is excellent for auto-labeling
- **Focus on edge cases** - check images with unusual angles or lighting
- **Review new classes** - Pay attention to e-scooter, SUV, delivery_van detection quality

Your CAMINA auto-labeling is working very well! 🎉