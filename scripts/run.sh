#!/bin/bash

# CAMINA Complete Pipeline Script
# Process all images in data/images and generate preview visualizations

echo "🚀 Starting CAMINA Complete Pipeline..."
echo "📁 Processing $(ls data/images | wc -l) images from data/images/"
echo "💾 Output directory: outputs/mixed"
echo ""

# Step 1: Run the complete pipeline
echo "⚡ Step 1: Running CAMINA detection pipeline..."
source venv/bin/activate && python main.py --images_dir data/images --output_dir outputs/mixed --config configs/config.yaml --verbose

if [ $? -ne 0 ]; then
    echo "❌ Pipeline failed. Exiting."
    exit 1
fi

echo ""
echo "✅ Pipeline completed successfully!"
echo ""

# Step 2: Setup visualization structure
echo "📋 Step 2: Setting up visualization structure..."
mkdir -p outputs/mixed/dataset_viz/images outputs/mixed/dataset_viz/labels outputs/mixed/previews

# Copy files for visualization
echo "📄 Copying images and labels for visualization..."
cp data/images/* outputs/mixed/dataset_viz/images/
cp outputs/mixed/yolo/* outputs/mixed/dataset_viz/labels/

echo ""
echo "🎨 Step 3: Generating preview images for all detections..."
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/mixed/dataset_viz --continuous --save --output-dir outputs/mixed/previews --method matplotlib

if [ $? -ne 0 ]; then
    echo "❌ Preview generation failed. Exiting."
    exit 1
fi

echo ""
echo "📊 Step 4: Generating summary visualization..."
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/mixed/dataset_viz --summary --save --output-dir outputs/mixed/previews

if [ $? -ne 0 ]; then
    echo "❌ Summary generation failed. Exiting."
    exit 1
fi

echo ""
echo "🎉 All tasks completed successfully!"
echo ""
echo "📁 Results saved in:"
echo "   • COCO annotations: outputs/mixed/coco/"
echo "   • YOLO labels: outputs/mixed/yolo/"
echo "   • Summary stats: outputs/mixed/summary/"
echo "   • Preview images: outputs/mixed/previews/"
echo ""
echo "🔍 Pipeline features used:"
echo "   ✅ E-scooter spatial association (person + e-scooter → combined bbox)"
echo "   ✅ SUV priority over car in overlaps"
echo "   ✅ Delivery_van priority over truck in overlaps"
echo "   ✅ Cyclist logic (person + bicycle → cyclist)"
echo "   ✅ NMS consolidation with class priorities"
echo ""
echo "📈 Check outputs/mixed/previews/camina_summary.png for overview!"