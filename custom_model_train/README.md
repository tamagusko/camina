## 🚀 Step-by-Step: Fine-tune YOLOv11n with a Custom COCO-Based Dataset

---

### **1. 🔻 Download COCO 2017 Dataset (Train Only)**

```
mkdir -p ~/datasets/coco
cd ~/datasets/coco

# Download images
wget http://images.cocodataset.org/zips/train2017.zip
unzip train2017.zip

# Download annotations
wget http://images.cocodataset.org/annotations/annotations_trainval2017.zip
unzip annotations_trainval2017.zip
```

Your folder should look like this:

```
~/datasets/coco/
├── annotations/
│   └── instances_train2017.json
└── train2017/
    └── *.jpg
```

---

### **2. 🧠 Prepare the Custom Dataset with Synthetic Cyclist Class**

Use the updated `coco_to_cyclist.py` script:

* Reads COCO annotations
* Synthesizes `cyclist` from overlapping `person ∩ bicycle` boxes (IoU ≥ 0.3)
* Uses the *combined bounding box* of both objects
* Normalizes annotations to YOLO format
* Outputs a balanced dataset

Run it like this:

```
python coco_to_cyclist.py \
  --coco-dir ~/datasets/coco \
  --out-dir ~/datasets/cyclist_yolo11 \
  --iou 0.3
```

After running, you’ll have:

```
~/datasets/cyclist_yolo11/
├── images/
│   ├── train/
│   └── test/
├── labels/
│   ├── train/
│   └── test/
└── data.yaml
```

---

### **3. 🧪 Validate Your Labels (Optional)**

You can visually inspect a few sample images using:

```
python validate_yolo_labels.py \
  --dataset-dir ~/datasets/cyclist_yolo11 \
  --filter-class 1  # show only images containing cyclists (class 1)
```

This opens each image and draws all bounding boxes, filtering to show only images that contain a given class.

---

### **4. 🔄 Install YOLOv11**

Install YOLOv11 directly:

```
pip install git+https://github.com/YOLOv11/YOLOv11.git
```

---

### **5. ✅ Check Your `data.yaml`**

Ensure the file looks like this:

```yaml
path: /full/path/to/datasets/cyclist_yolo11
train: images/train
val: images/test
nc: 6
names: [person, cyclist, car, motorcycle, bus, truck]
```

---

### **6. 🚀 Start Training with YOLOv11n**

Ensure `yolo11n.pt` is available in `models/` or provide the correct path.

```
python train.py \
  --model models/yolo11n.pt \
  --data ~/datasets/cyclist_yolo11/data.yaml \
  --epochs 100 \
  --batch 16 \
  --imgsz 640 \
  --device 0  # or --device mps for Mac M1/M2
```

---

### **7. 📊 Monitor and Evaluate**

Monitor training with:

```
tensorboard --logdir runs/train
```

You’ll find training outputs in:

```
runs/train/exp/
```

---

### **8. 🧊 Export for Inference (e.g., NCNN or ONNX)**

After training, export to edge formats:

```
python export.py --weights runs/train/exp/weights/best.pt --format ncnn
```

