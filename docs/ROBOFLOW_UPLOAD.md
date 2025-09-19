# Manual Roboflow Upload Guide

Step-by-step instructions for manually uploading CAMINA datasets to Roboflow.

## Prerequisites

1. **Prepared dataset** - Run `python prepared_data_roboflow.py` first
2. **Roboflow account** - Sign up at [roboflow.com](https://roboflow.com)
3. **Dataset folder** - Located in `roboflow_datasets/[dataset-name]/`

## Upload Process

### Step 1: Access Roboflow

1. Go to [roboflow.com](https://roboflow.com)
2. Sign in to your account
3. Navigate to your workspace

### Step 2: Create or Select Project

**For new project:**
1. Click "Create New Project"
2. Choose "Object Detection"
3. Set project name:
   - `camina-complete-pipeline` (for run.sh output)
   - `camina-yolo-world-detections` (for run_imagenet.sh output)

**For existing project:**
1. Click on your existing project
2. Navigate to "Dataset" tab

### Step 3: Upload Dataset

1. **Click "Upload"** → "Computer"
2. **Select folder:** Choose entire `roboflow_datasets/[dataset-name]/` folder
3. **Format:** Select "YOLOv11" or "YOLOv8" (both compatible)
4. **Upload mode:** Choose "Folder Upload"

### Step 4: Configure Dataset

1. **Verify classes** are correctly detected:
   ```
   Complete Pipeline: 9 classes (person, cyclist, car, ...)
   YOLO-World Only: 3 classes (e-scooter, SUV, delivery_van)
   ```

2. **Check splits** are properly recognized:
   ```
   Complete Pipeline: train/val split
   YOLO-World Only: train/test split
   ```

3. **Validate file counts** match your local dataset

### Step 5: Add Metadata

1. **Version name:**
   - `v1-complete-pipeline` (for run.sh)
   - `v1-yolo-world-detections` (for run_imagenet.sh)

2. **Version notes:** Copy from your dataset's `DATASET_REPORT.md`

3. **Tags:** Add relevant tags like:
   - `urban-mobility`
   - `camina-pipeline`
   - `yolo-world`
   - `multi-stage-detection`

### Step 6: Review and Confirm

1. **Preview samples** - Check annotations are correctly displayed
2. **Verify statistics** - Compare with your generated reports
3. **Review class mapping** - Ensure all classes are properly labeled
4. **Confirm upload** - Click "Create Version"

## Upload Configuration by Dataset

### Complete Pipeline Dataset

**Settings:**
- **Project Type:** Object Detection
- **Format:** YOLOv11
- **Classes:** 9 (all CAMINA classes)
- **Split:** train/val (80/20 automatic)
- **Features:** Multi-stage detection with spatial logic

**Description Template:**
```
CAMINA complete pipeline dataset with multi-stage detection.
Includes Stage A (YOLO11l) + Stage B (YOLO-World) with spatial
association logic for cyclist and e-scooter detection.
```

### YOLO-World Only Dataset

**Settings:**
- **Project Type:** Object Detection
- **Format:** YOLOv11
- **Classes:** 3 (e-scooter, SUV, delivery_van)
- **Split:** train/test (predefined)
- **Features:** YOLO-World open-vocabulary detection

**Description Template:**
```
CAMINA YOLO-World dataset focusing on specialized urban mobility
objects. Uses open-vocabulary detection for e-scooter, SUV, and
delivery van classification.
```

## Verification Checklist

After upload, verify:

- [ ] **File counts match** local dataset
- [ ] **All classes present** in class list
- [ ] **Sample annotations** display correctly
- [ ] **Split ratios** match expected percentages
- [ ] **Image quality** maintained after upload
- [ ] **Labels aligned** with bounding boxes

## Common Upload Issues

### File Format Problems
- **Solution:** Ensure YOLO format labels (normalized coordinates)
- **Check:** data.yaml has correct class names and paths

### Missing Files
- **Solution:** Verify all images have corresponding .txt label files
- **Check:** Run data preparation script again if files missing

### Class Mapping Errors
- **Solution:** Manually correct class names in Roboflow interface
- **Check:** Compare with generated class_distribution.csv

### Split Recognition Issues
- **Solution:** Upload train and val/test folders separately if needed
- **Check:** Ensure folder structure matches YOLOv11 format

## Post-Upload Actions

### 1. Generate Statistics
Use Roboflow's built-in analytics to:
- Compare class distributions
- Analyze annotation quality
- Review split balance

### 2. Download and Verify
- Download a sample to verify format consistency
- Compare with original dataset structure
- Test with YOLO training scripts

### 3. Share and Collaborate
- Set appropriate permissions
- Share with team members
- Document access credentials

## API Integration (Optional)

For automated uploads in the future, you can use the Roboflow Python SDK:

```python
from roboflow import Roboflow

rf = Roboflow(api_key="YOUR_API_KEY")
project = rf.workspace("workspace-name").project("project-name")
project.version(1).download("yolov11")
```

## Troubleshooting

### Upload Fails
1. Check internet connection
2. Verify file permissions
3. Try smaller batch uploads
4. Contact Roboflow support

### Wrong Format Detection
1. Ensure data.yaml is present and correct
2. Verify folder structure matches YOLOv11
3. Check label file formatting

### Missing Annotations
1. Verify label files exist for all images
2. Check label files are not empty
3. Validate YOLO coordinate format

## Support Resources

- **Roboflow Documentation:** [docs.roboflow.com](https://docs.roboflow.com)
- **Community Forum:** [community.roboflow.com](https://community.roboflow.com)
- **CAMINA Reports:** Use generated academic reports for reference
- **Format Validation:** Check data.yaml and label files locally first