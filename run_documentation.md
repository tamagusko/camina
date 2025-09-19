# CAMINA Complete Pipeline Commands

## Overview
Complete pipeline to process all images in `data/images` (2013 images) and generate preview visualizations.

## Step 1: Run the Complete Pipeline
```bash
source venv/bin/activate && python main.py --images_dir data/images --output_dir outputs/mixed --config configs/config.yaml --verbose
```

## Step 2: Generate All Preview Images
```bash
# Create visualization dataset structure
mkdir -p outputs/mixed/dataset_viz/images outputs/mixed/dataset_viz/labels outputs/mixed/previews

# Copy images and labels for visualization
cp data/images/* outputs/mixed/dataset_viz/images/
cp outputs/mixed/yolo/* outputs/mixed/dataset_viz/labels/

# Generate preview images for all detections
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/mixed/dataset_viz --continuous --save --output-dir outputs/mixed/previews --method matplotlib

# Generate summary visualization
source venv/bin/activate && python src/scripts/visualize_labels.py outputs/mixed/dataset_viz --summary --save --output-dir outputs/mixed/previews
```

## Combined Single Command
```bash
source venv/bin/activate && python main.py --images_dir data/images --output_dir outputs/mixed --config configs/config.yaml --verbose && mkdir -p outputs/mixed/dataset_viz/images outputs/mixed/dataset_viz/labels outputs/mixed/previews && cp data/images/* outputs/mixed/dataset_viz/images/ && cp outputs/mixed/yolo/* outputs/mixed/dataset_viz/labels/ && python src/scripts/visualize_labels.py outputs/mixed/dataset_viz --continuous --save --output-dir outputs/mixed/previews --method matplotlib && python src/scripts/visualize_labels.py outputs/mixed/dataset_viz --summary --save --output-dir outputs/mixed/previews
```

## Pipeline Features
This pipeline includes all implemented features:

- ✅ **E-scooter spatial association**: person + e-scooter → combined bbox
- ✅ **SUV priority over car** in overlapping detections
- ✅ **Delivery_van priority over truck** in overlapping detections
- ✅ **Cyclist logic**: person + bicycle → cyclist detection
- ✅ **NMS consolidation** with proper class priorities: `[6, 7, 8, 1, 0, 2, 3, 4, 5]`

## Expected Outputs
- **COCO format annotations**: `outputs/mixed/coco/`
- **YOLO format labels**: `outputs/mixed/yolo/`
- **Summary statistics**: `outputs/mixed/summary/`
- **Individual preview images**: `outputs/mixed/previews/viz_*.png`
- **Summary visualization**: `outputs/mixed/previews/camina_summary.png`

## Dataset Info
- **Total images**: 2,013 frame images from `data/images/`
- **Expected processing time**: ~10-15 minutes (depending on hardware)
- **Target hardware**: RTX 3060 12GB VRAM + 32GB RAM