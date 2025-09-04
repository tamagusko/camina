# **CAMINA Dataset Expansion: 9-Class Urban Mobility Detection Pipeline (YOLO11 Format)**

You are an expert computer vision researcher specializing in YOLO11 architecture, DINOv3 implementation, urban mobility monitoring, object detection, and edge device optimization. Your task is to implement a complete dataset expansion pipeline for multimodal transportation monitoring using YOLO11 format specifications.

## **Objective**

Expand the existing CAMINA dataset from 6 classes to 9 classes using DINOv3-assisted semi-automated labeling, targeting YOLO11n deployment on Raspberry Pi 5 for urban mobility monitoring.

## **Current State vs Target State**

**Current Classes (6):**

- person → **pedestrian** (rename)
- **cyclist** (manually labelled class)
- car
- motorcycle
- bus
- truck

**Target Classes (9):**

- pedestrian (class_id: 0)
- cyclist (class_id: 1)
- car (class_id: 2)
- motorcycle (class_id: 3)
- bus (class_id: 4)
- truck (class_id: 5)
- **e-scooter** (class_id: 6) (new)
- **SUV** (class_id: 7) (new)
- **delivery van** (class_id: 8) (new)

## **Available Resources**

- Base YOLO11 model with existing classes (person, cyclist, car, motorcycle, bus, truck)
- SDL fine-tuned_v3-cyclist_cleaned dataset (images with people+bicycles, 30% overlap, manually cleaned from false positives) with the new cyclist class.
- DINOv3 model for feature extraction and object localization

## **YOLO11 Format Specifications**

### **Dataset Structure**

all_camina_classes/

├── images/

│  ├── train/

│  ├── val/

│  └── test/

├── labels/

│  ├── train/

│  ├── val/

│  └── test/

├── data.yaml

└── classes.txt

### **YOLO11 data.yaml Configuration**

\# Dataset configuration for YOLO11

path: ./all_camina_classes # dataset root dir

train: images/train # train images (relative to 'path')

val: images/val # val images (relative to 'path')

test: images/test # test images (relative to 'path')

\# Classes

names:

 0: pedestrian

 1: cyclist

 2: car

 3: motorcycle

 4: bus

 5: truck

 6: e-scooter

 7: SUV

 8: delivery_van

\# Number of classes

nc: 9

### **YOLO11 Label Format**

Each .txt file contains annotations in YOLO11 format:

class_id center_x center_y width height

- All coordinates normalized to [0, 1]
- center_x, center_y: bounding box center coordinates
- width, height: bounding box dimensions

## **Implementation Pipeline**

### **1. SDL Dataset Analysis & YOLO11 Conversion**

- Convert existing SDL dataset to YOLO11 format
- Remap class IDs according to new 9-class schema
- Validate annotation format compliance
- Generate dataset statistics and class distribution reports

### **2. DINOv3 Semi-Automated Pipeline (YOLO11 Compatible)**

\# Expected pipeline structure

def dinov2_yolo11_pipeline():

  \# DINOv3 feature extraction

  \# Object localization with confidence scores

  \# YOLO11 format annotation generation

  \# Batch processing for efficiency

- Configure DINOv3 for robust feature extraction
- Generate YOLO11-format annotations for new classes
- Create confidence-based filtering for automated suggestions
- Output bounding boxes in normalized YOLO11 coordinates

### **3. Manual Verification Protocol (YOLO11 Format)**

- Implement annotation tools compatible with YOLO11 format
- Create validation scripts for annotation consistency
- Establish quality control metrics for new classes
- Generate inter-annotator agreement analysis

### **4. Additional Data Collection (YOLO11 Ready)**

- Collect images with metadata for YOLO11 training
- Maintain aspect ratio and resolution standards
- Implement automated YOLO11 format conversion
- Ensure train/val/test split consistency

### **5. YOLO11 Dataset Organization**

all_camina_classes/

├── images/

│  ├── train/ (70%)

│  ├── val/ (20%)

│  └── test/ (10%)

├── labels/

│  ├── train/

│  ├── val/

│  └── test/

├── data.yaml (YOLO11 config)

└── README.md

### **6. Quality Assurance (YOLO11 Specific)**

- Validate YOLO11 annotation format compliance
- Check normalized coordinate ranges [0, 1]
- Verify class ID consistency across splits
- Implement YOLO11-compatible augmentation testing

### **7. YOLO11n Training Pipeline**

\# YOLO11n training configuration

model = YOLO('yolo11n.pt') # load pretrained model

results = model.train(

  data='./all_camina_classes/data.yaml',

  epochs=100,

  imgsz=640,

  device='cpu', # Raspberry Pi 5 optimization

  batch=16,

  workers=4,

  patience=10,

  save_period=10,

  project='camina_expansion',

  name='yolo11n_9classes'

)

### **8. Edge Deployment Optimization (Raspberry Pi 5)**

- Model quantization for YOLO11n
- TensorRT optimization (if available)
- Memory usage optimization
- Inference speed benchmarking

## **YOLO11 Specific Deliverables**

1. **YOLO11-formatted dataset** with proper data.yaml configuration
2. **DINOv3 → YOLO11 conversion pipeline** with automated annotation generation
3. **YOLO11n training scripts** optimized for 9-class detection
4. **Raspberry Pi 5 deployment package** with optimized inference
5. **Validation metrics** using YOLO11's built-in evaluation tools

## **YOLO11 Training Command Structure**

\# Training

yolo train model=yolo11n.pt data=./all_camina_classes/data.yaml epochs=100 imgsz=640

\# Validation 

yolo val model=./runs/detect/train/weights/best.pt data=./all_camina_classes/data.yaml

\# Inference

yolo predict model=./runs/detect/train/weights/best.pt source=./test_images

## **Constraints & YOLO11 Requirements**

- Maintain YOLO11 format standards throughout pipeline
- Ensure compatibility with Raspberry Pi 5 deployment
- Optimize for YOLO11n's lightweight architecture
- Follow YOLO11's data augmentation and training best practices
- Implement YOLO11's built-in metrics and visualization tools

Implement this pipeline systematically using YOLO11's native format and training procedures, ensuring seamless integration with the YOLO11 ecosystem while maintaining CAMINA methodology standards.

FINAL EXPERIMENT:

I'll want to compare YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n, and YOLO12n.

The data I want to compare is:

Model

mAP@0.5

Model Size (MB)

Video FPS

Real-World FPS

Training Time (hrs)

I'll first test the models on a 1-hour video to ensure the same environment and input, and then I'll run real-world tests. The models will run on a Raspberry Pi 5 8GB using the ncnn format.

Also, for all models, I'll need:

Per-Class Detection Performance (mAP@0.5)

Class

New

YOLOv5n

YOLOv8n

YOLOv10n

YOLO11n

YOLO12n

Samples

Pedestrian

Cyclist

E-scooter

SUV

Motorcycle

Bus

Delivery Van

Truck

So, save these results in a log for each run so you can compare them later.
