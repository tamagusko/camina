# Dataset Details

## Complete Pipeline Dataset

**Source:** `outputs/mixed/` (from `./run.sh`)

### Overview
- **Images:** ~2,013 frame images from `data/images/`
- **Split:** Automatic 80/20 train/validation split
- **Format:** YOLOv11 compatible

### Features
- ✅ **Stage A (YOLO11l):** Traditional object detection
- ✅ **Stage B (YOLO-World):** Open-vocabulary detection
- ✅ **E-scooter spatial association:** person + e-scooter → combined bbox
- ✅ **Cyclist logic:** person + bicycle → cyclist
- ✅ **NMS with class priorities:** SUV > car, delivery_van > truck

### Classes (9 total)
```
0: person        # Stage A detection
1: cyclist       # Generated via spatial logic
2: car           # Stage A detection
3: motorcycle    # Stage A detection
4: bus           # Stage A detection
5: truck         # Stage A detection
6: e-scooter     # Stage B (YOLO-World)
7: SUV           # Stage B (YOLO-World)
8: delivery_van  # Stage B (YOLO-World)
```

### File Paths
- **Images:** `outputs/mixed/dataset_viz/images/`
- **Labels:** `outputs/mixed/yolo/`

---

## YOLO-World Only Dataset

**Source:** `outputs/imagenet_train/` + `outputs/imagenet_test/` (from `./run_imagenet.sh`)

### Overview
- **Train Images:** 1,223 images from `data/dataset_v4i_yolov11/train/`
- **Test Images:** 72 images from `data/dataset_v4i_yolov11/test/`
- **Split:** Pre-defined train/test split
- **Format:** YOLOv11 compatible

### Features
- ✅ **Stage B only:** YOLO-World open-vocabulary detection
- ✅ **NMS consolidation:** Basic overlap resolution
- ❌ **No spatial logic:** E-scooter and cyclist logic disabled
- ❌ **No Stage A:** Traditional detection disabled

### Classes (3 total)
```
6: e-scooter     # YOLO-World detection
7: SUV           # YOLO-World detection
8: delivery_van  # YOLO-World detection
```

### File Paths
- **Train Images:** `outputs/imagenet_train/dataset_viz/images/`
- **Train Labels:** `outputs/imagenet_train/yolo/`
- **Test Images:** `outputs/imagenet_test/dataset_viz/images/`
- **Test Labels:** `outputs/imagenet_test/yolo/`

---

## Output Structure

Both datasets are organized in YOLOv11 format:

```
roboflow_datasets/
├── camina-complete-pipeline/
│   ├── data.yaml                    # YOLOv11 configuration
│   ├── images/
│   │   ├── train/                   # 80% of images (auto-split)
│   │   └── val/                     # 20% of images (auto-split)
│   ├── labels/
│   │   ├── train/                   # Corresponding YOLO labels
│   │   └── val/                     # Corresponding YOLO labels
│   └── [report files...]
└── camina-yolo-world-detections/
    ├── data.yaml
    ├── images/
    │   ├── train/                   # 1,223 predefined train images
    │   └── test/                    # 72 predefined test images
    ├── labels/
    │   ├── train/                   # Corresponding YOLO labels
    │   └── test/                    # Corresponding YOLO labels
    └── [report files...]
```

## Feature Comparison

| Feature | Complete Pipeline | YOLO-World Only |
|---------|------------------|------------------|
| **Detection Stages** | Stage A + Stage B | Stage B only |
| **Image Source** | `data/images/` | `data/dataset_v4i_yolov11/` |
| **Total Classes** | 9 classes | 3 classes |
| **E-scooter Logic** | ✅ Enabled | ❌ Disabled |
| **Cyclist Logic** | ✅ Enabled | ❌ Disabled |
| **NMS Prioritization** | ✅ Full priority rules | ✅ Basic consolidation |
| **Data Split** | Auto 80/20 | Predefined train/test |
| **Traditional Objects** | ✅ person, car, etc. | ❌ YOLO-World only |
| **Specialized Objects** | ✅ e-scooter, SUV, delivery_van | ✅ e-scooter, SUV, delivery_van |

## Technical Specifications

### YOLO Format Labels
All labels use normalized coordinates (0.0-1.0):
```
class_id center_x center_y width height
```

### data.yaml Configuration
```yaml
path: /path/to/dataset
train: images/train
val: images/val  # or images/test
nc: 9  # (or 3 for YOLO-World only)
names: [person, cyclist, car, ...]
```

### Quality Metrics
- **Annotation coverage:** Percentage of images with valid labels
- **Instance density:** Average objects per image
- **Class distribution:** Frequency of each class
- **Split balance:** Train/validation size ratio