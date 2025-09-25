#!/bin/bash

# CAMINA E-Scooter Dataset Pipeline Script
# Process diverse e-scooter images and generate preview visualizations

echo "🛴 Starting CAMINA E-Scooter Dataset Pipeline..."
echo "📁 Processing $(ls "data/e-scooter rider dataset/diverse/" | wc -l) diverse e-scooter images"
echo "💾 Output directory: outputs/escooter"
echo ""

# Step 1: Run the complete pipeline
echo "⚡ Step 1: Running CAMINA detection pipeline on e-scooter dataset..."
source venv/bin/activate && python main.py --images_dir "data/e-scooter rider dataset/diverse/" --output_dir outputs/escooter --config configs/config.yaml --verbose

if [ $? -ne 0 ]; then
    echo "❌ Pipeline failed. Exiting."
    exit 1
fi

echo ""
echo "✅ Pipeline completed successfully!"
echo ""

# Step 2: Setup visualization structure
echo "📋 Step 2: Setting up visualization structure..."
mkdir -p outputs/escooter/dataset_viz/images outputs/escooter/dataset_viz/labels outputs/escooter/previews

# Copy files for visualization
echo "📄 Copying images and labels for visualization..."
cp "data/e-scooter rider dataset/diverse/"* outputs/escooter/dataset_viz/images/
cp outputs/escooter/yolo/* outputs/escooter/dataset_viz/labels/

echo ""
echo "🎨 Step 3: Generating preview images for all detections..."
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/escooter/dataset_viz --continuous --save --output-dir outputs/escooter/previews --method matplotlib

if [ $? -ne 0 ]; then
    echo "❌ Preview generation failed. Exiting."
    exit 1
fi

echo ""
echo "📊 Step 4: Generating summary visualization..."
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/escooter/dataset_viz --summary --save --output-dir outputs/escooter/previews

if [ $? -ne 0 ]; then
    echo "❌ Summary generation failed. Exiting."
    exit 1
fi

echo ""
echo "🎉 All tasks completed successfully!"
echo ""
echo "📁 Results saved in:"
echo "   • COCO annotations: outputs/escooter/coco/"
echo "   • YOLO labels: outputs/escooter/yolo/"
echo "   • Summary stats: outputs/escooter/summary/"
echo "   • Preview images: outputs/escooter/previews/"
echo ""
echo "🔍 Pipeline features used:"
echo "   ✅ E-scooter spatial association (person + e-scooter → combined bbox)"
echo "   ✅ SUV priority over car in overlaps"
echo "   ✅ Delivery_van priority over truck in overlaps"
echo "   ✅ Cyclist logic (person + bicycle → cyclist)"
echo "   ✅ NMS consolidation with class priorities"
echo ""
echo "🛴 E-scooter dataset analysis:"
echo "   • Dataset: 600 diverse e-scooter rider images"
echo "   • Selection method: CLIP embeddings + K-means clustering"
echo "   • Focus: Representative diversity for e-scooter detection"
echo ""
echo "📈 Check outputs/escooter/previews/camina_summary.png for overview!"