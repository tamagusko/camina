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

You should now have:

```
~/datasets/coco/
├── annotations/
│   └── instances_train2017.json
└── train2017/
    └── *.jpg
```

---

### **2. 🧠 Prepare the Custom Dataset Script**

Use the `coco_to_cyclist.py` script you’ve been developing. This script:

* Reads COCO annotations
* Detects overlapping boxes (person+bicycle) → creates a `cyclist` box
* Saves YOLOv8-style datasets
* Produces 2,400 balanced images per class (2k train, 400 test)

Run it like this:

```
python coco_to_cyclist.py \
  --coco-dir ~/datasets/coco \
  --out-dir ~/datasets/cyclist_yolo11
```

After running, you'll have:

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

Here's the adjusted version using `pip install` directly instead of cloning:

---

### **3. 🔄 Install YOLOv11**

```
pip install git+https://github.com/YOLOv11/YOLOv11.git
```

---

### **4. ✅ Check Your `data.yaml`**

The script already creates this file, but confirm the contents:

```yaml
path: /full/path/to/datasets/cyclist_yolo11
train: images/train
val: images/test
nc: 6
names: [person, cyclist, car, motorcycle, bus, truck]
```

---

### **5. 🧪 Start Training with YOLOv11n**

Make sure `yolo11n.pt` is in the `models/` folder, or download if needed.

Then run training:

```
python train.py \
  --model models/yolo11n.pt \
  --data ~/datasets/cyclist_yolo11/data.yaml \
  --epochs 100 \
  --batch 16 \
  --imgsz 640 \
  --device 0 # --device mps for Mac
```

You can adjust `batch`, `epochs`, or `imgsz` depending on your system resources.

---

### **6. 🎯 Monitor and Evaluate**

Training outputs will be stored in `runs/train/exp*/`.

You can evaluate performance by checking:

```
tensorboard --logdir runs/train
```

---

### **7. 🧊 Export for Inference (e.g., NCNN or ONNX)**

After training (convert to edge devices):

```
python export.py --weights runs/train/exp/weights/best.pt --format ncnn
```
