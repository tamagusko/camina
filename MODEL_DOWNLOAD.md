# Model Files Download Guide

The CAMINA hybrid detection system requires the following model files that are not included in the repository due to size constraints:

## Required Model Files

### 1. YOLO11n (Primary Model)
- **File**: `yolo11n.pt` (~5.6MB)
- **Download**: Automatically downloaded by Ultralytics on first run
- **Alternative**: https://github.com/ultralytics/ultralytics/releases

### 2. YOLO-World (Secondary Model)
- **File**: `yolov8l-world.pt` (~95MB)
- **Download**: Automatically downloaded by Ultralytics on first run
- **Alternative**: https://github.com/AILab-CVC/YOLO-World/releases

### 3. Grounding DINO (Alternative Secondary Model)
- **File**: `groundingdino_swint_ogc.pth` (~693MB)
- **Download**: https://github.com/IDEA-Research/GroundingDINO/releases
- **Direct Link**: https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

## Quick Setup

1. **Activate environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the system** (models will auto-download):
   ```bash
   python dataset_creator.py input_images/ output_dataset/ --verbose
   ```

## Manual Download (Optional)

If you prefer to download models manually:

```bash
# Download Grounding DINO
wget https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

# YOLO models will be downloaded automatically on first use
```

## Configuration

The hybrid system uses:
- **YOLO11n** for COCO classes (pedestrian, car, motorcycle, bus, truck)
- **YOLO-World** for new classes (cyclist, e-scooter, SUV, delivery_van)

Change the secondary model in `dataset_creator_config.json`:
```json
{
  "hybrid_config": {
    "secondary_model": "yolo_world"  // or "grounding_dino"
  }
}
```

## Performance

- **YOLO11n + YOLO-World**: ~5.5 images/second (RTX 3060)
- **YOLO11n + Grounding DINO**: ~3.2 images/second (RTX 3060)

Both configurations achieve excellent 9-class urban mobility detection.