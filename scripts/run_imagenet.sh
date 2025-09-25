#!/bin/bash

# CAMINA YOLO-World Only Pipeline for dataset_v4i_yolov11
# Runs Stage B (YOLO-World) only on existing dataset with labels

echo "🚀 Starting CAMINA YOLO-World Pipeline on dataset_v4i_yolov11..."
echo "📁 Dataset: data/dataset_v4i_yolov11/"
echo "🏷️  Train set: $(ls data/dataset_v4i_yolov11/train/images/ | wc -l) images"
echo "🏷️  Test set: $(ls data/dataset_v4i_yolov11/test/images/ | wc -l) images"
echo "⚡ Running Stage B (YOLO-World) only for e-scooter, SUV, delivery_van detection"
echo ""

# Create output directories
echo "📁 Creating output directories..."
mkdir -p outputs/imagenet_train outputs/imagenet_test

# Process train set
echo "🔥 Processing TRAIN SET (1223 images)..."
echo "Running YOLO-World detection on train images..."
source venv/bin/activate && python main.py --images_dir data/dataset_v4i_yolov11/train/images --output_dir outputs/imagenet_train --config configs/config.yaml --verbose

if [ $? -ne 0 ]; then
    echo "❌ Train set processing failed. Exiting."
    exit 1
fi

echo ""
echo "✅ Train set completed!"
echo ""

# Process test set
echo "🔥 Processing TEST SET (72 images)..."
echo "Running YOLO-World detection on test images..."
source venv/bin/activate && python main.py --images_dir data/dataset_v4i_yolov11/test/images --output_dir outputs/imagenet_test --config configs/config.yaml --verbose

if [ $? -ne 0 ]; then
    echo "❌ Test set processing failed. Exiting."
    exit 1
fi

echo ""
echo "✅ Test set completed!"
echo ""

# Generate visualizations for train set
echo "🎨 Generating preview images for TRAIN SET..."
mkdir -p outputs/imagenet_train/dataset_viz/images outputs/imagenet_train/dataset_viz/labels outputs/imagenet_train/previews
cp data/dataset_v4i_yolov11/train/images/* outputs/imagenet_train/dataset_viz/images/
cp outputs/imagenet_train/yolo/* outputs/imagenet_train/dataset_viz/labels/

source venv/bin/activate && python src/scripts/visualize_labels.py outputs/imagenet_train/dataset_viz --summary --save --output-dir outputs/imagenet_train/previews

# Generate sample previews (first 20 images to avoid too many files)
echo "🖼️  Generating sample preview images (first 20)..."
source venv/bin/activate && python -c "
import os
from pathlib import Path
import subprocess

# Get first 20 image files
viz_dir = Path('outputs/imagenet_train/dataset_viz')
image_files = sorted(list(viz_dir.glob('images/*')))[:20]

for img_file in image_files:
    img_name = img_file.stem
    label_file = viz_dir / 'labels' / f'{img_name}.txt'
    if label_file.exists():
        subprocess.run([
            'python', 'src/scripts/visualize_labels.py',
            str(viz_dir), '--image', img_name,
            '--save', '--output-dir', 'outputs/imagenet_train/previews',
            '--method', 'matplotlib'
        ])
"

echo ""
echo "🎨 Generating preview images for TEST SET..."
mkdir -p outputs/imagenet_test/dataset_viz/images outputs/imagenet_test/dataset_viz/labels outputs/imagenet_test/previews
cp data/dataset_v4i_yolov11/test/images/* outputs/imagenet_test/dataset_viz/images/
cp outputs/imagenet_test/yolo/* outputs/imagenet_test/dataset_viz/labels/

source venv/bin/activate && python src/scripts/visualize_labels.py outputs/imagenet_test/dataset_viz --summary --save --output-dir outputs/imagenet_test/previews

# Generate all test previews (only 72 images)
echo "🖼️  Generating all test preview images..."
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/imagenet_test/dataset_viz --continuous --save --output-dir outputs/imagenet_test/previews --method matplotlib

echo ""
echo "🎉 YOLO-World pipeline completed successfully!"
echo ""
echo "📁 Results saved in:"
echo "   📊 TRAIN SET:"
echo "      • COCO annotations: outputs/imagenet_train/coco/"
echo "      • YOLO labels: outputs/imagenet_train/yolo/"
echo "      • Summary stats: outputs/imagenet_train/summary/"
echo "      • Preview images: outputs/imagenet_train/previews/"
echo "      • Summary visualization: outputs/imagenet_train/previews/camina_summary.png"
echo ""
echo "   📊 TEST SET:"
echo "      • COCO annotations: outputs/imagenet_test/coco/"
echo "      • YOLO labels: outputs/imagenet_test/yolo/"
echo "      • Summary stats: outputs/imagenet_test/summary/"
echo "      • Preview images: outputs/imagenet_test/previews/"
echo "      • Summary visualization: outputs/imagenet_test/previews/camina_summary.png"
echo ""
echo "🔍 YOLO-World detections for:"
echo "   ✅ e-scooter (class 6)"
echo "   ✅ SUV (class 7)"
echo "   ✅ delivery_van (class 8)"
echo ""
echo "📈 Check summary visualizations for detection overview!"