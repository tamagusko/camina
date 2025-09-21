# CAMINA User Guide

Comprehensive guide for using CAMINA's urban mobility detection system.

## Overview

CAMINA (Computer-Aided Mobility Investigation and Analysis) is a hybrid object detection system specifically designed for urban mobility analysis. It combines multiple YOLO models with specialized logic to detect pedestrians, cyclists, vehicles, and micro-mobility devices.

## Detection Architecture

### Three-Stage Pipeline

1. **Stage A**: Base object detection (YOLO11n)
   - Classes: person, car, motorcycle, bus, truck
   - High-speed general object detection

2. **Cyclist Logic**: Spatial association algorithm
   - Combines person + bicycle detections → cyclist
   - IoU threshold: 0.20, spatial margin: 5px

3. **Stage B**: Specialized detection (YOLO-World)
   - Classes: e-scooter, SUV, delivery_van
   - Open-vocabulary detection for specialized objects

4. **NMS Consolidation**: Priority-based suppression
   - YOLO-World classes suppress overlapping Stage A detections
   - Configurable priority order: `[6, 7, 8, 1, 0, 2, 3, 4, 5]`

## Command Line Interface

### Basic Commands

```bash
# Single image
python main.py --input image.jpg

# Multiple images
python main.py --input folder/ --batch

# Video processing
python main.py --input video.mp4

# Custom output location
python main.py --input data/ --output results/ --batch
```

### Advanced Options

```bash
# Custom configuration
python main.py --config custom_config.yaml --input data/

# Specific output formats
python main.py --input data/ --format yolo --viz --batch

# Performance options
python main.py --input data/ --batch_size 8 --cleanup_interval 50
```

## Configuration Guide

### Main Configuration File: `configs/config.yaml`

#### Detection Stages
```yaml
detection_stages:
  stage_a:
    model_path: models/yolo_base/yolo11n.pt
    confidence_threshold: 0.25
    iou_threshold: 0.45
    max_detections: 300

  stage_b:
    model_path: models/yolo_world/yolov8s-world.pt
    confidence_threshold: 0.35
    iou_threshold: 0.45
    max_detections: 300
```

#### Cyclist Detection
```yaml
cyclist_detection:
  enabled: true
  iou_threshold: 0.20        # Person-bicycle overlap requirement
  spatial_margin: 5          # Pixel margin for spatial checks
  min_person_confidence: 0.3 # Minimum person detection confidence
  min_bicycle_confidence: 0.25 # Minimum bicycle detection confidence
```

#### NMS Consolidation
```yaml
nms_consolidation:
  enabled: true
  iou_threshold: 0.35
  class_priority: [6, 7, 8, 1, 0, 2, 3, 4, 5]  # YOLO-World first
  deterministic_tie_breaking: true
```

#### Text Prompts (YOLO-World)
```yaml
text_prompts:
  e_scooter: "A person on an e-scooter. A person on an electric scooter."
  suv: "An SUV. A pickup truck. A large SUV."
  delivery_van: "A delivery van. A delivery truck."
```

#### Performance Settings
```yaml
performance:
  device: auto               # 'auto', 'cuda', 'cpu'
  batch_size: 16            # Adjust based on GPU memory
  memory_cleanup_interval: 100 # Clean up every N images
  min_bbox_area: 0.01       # Minimum bounding box area
```

## Output Formats

### Directory Structure
```
output_folder/
├── detections/              # YOLO format labels (.txt files)
├── dataset_viz/            # Visualized images with bounding boxes
│   └── images/            # Visual detection results
├── yolo/                   # Raw detection outputs
│   ├── stage_a/           # YOLO11n outputs
│   ├── stage_b/           # YOLO-World outputs
│   └── consolidated/      # Final consolidated results
└── performance_report.json # Processing statistics
```

### YOLO Format Labels
Each detection file contains normalized coordinates:
```
class_id center_x center_y width height confidence
0 0.5 0.3 0.2 0.4 0.85
1 0.7 0.6 0.15 0.25 0.92
```

### Class Mapping
```
0: person      5: truck
1: cyclist     6: e-scooter
2: car         7: SUV
3: motorcycle  8: delivery_van
4: bus
```

## Performance Optimization

### GPU Memory Management
```yaml
performance:
  batch_size: 8              # Reduce for low memory GPUs
  memory_cleanup_interval: 50 # More frequent cleanup
```

### Speed Optimization
```yaml
detection_stages:
  stage_a:
    confidence_threshold: 0.35  # Higher threshold = fewer detections
  stage_b:
    confidence_threshold: 0.45  # Skip low-confidence detections
```

### Quality vs Speed Trade-offs
- **High Quality**: Lower thresholds, smaller batch sizes
- **High Speed**: Higher thresholds, larger batch sizes
- **Balanced**: Default settings (recommended)

## Use Cases

### Traffic Monitoring
```yaml
# Optimize for vehicle detection
detection_stages:
  stage_a:
    confidence_threshold: 0.3
cyclist_detection:
  enabled: false  # Skip cyclist logic for pure vehicle monitoring
```

### Pedestrian Safety Analysis
```yaml
# Optimize for person and cyclist detection
detection_stages:
  stage_a:
    confidence_threshold: 0.2  # Lower threshold for people
cyclist_detection:
  enabled: true
  min_person_confidence: 0.25
```

### Micro-mobility Research
```yaml
# Focus on e-scooters and cyclists
detection_stages:
  stage_b:
    confidence_threshold: 0.3  # Lower threshold for e-scooters
cyclist_detection:
  enabled: true
```

## Troubleshooting

### Common Issues

#### No Detections Found
**Symptoms**: Empty output files, no visualizations
**Solutions**:
1. Lower confidence thresholds
2. Check input image quality
3. Verify model files are present
4. Check GPU memory availability

#### Cyclist Misclassification
**Symptoms**: Cyclists detected as motorcycles or missing
**Solutions**:
1. Enable cyclist detection logic
2. Adjust IoU and spatial margin thresholds
3. Review person/bicycle confidence thresholds

#### GPU Memory Errors
**Symptoms**: CUDA out of memory errors
**Solutions**:
1. Reduce batch size
2. Increase memory cleanup frequency
3. Use CPU mode for testing

#### Slow Processing
**Symptoms**: Very slow inference times
**Solutions**:
1. Increase batch size (if memory allows)
2. Raise confidence thresholds
3. Disable visualization generation
4. Use smaller model variants

### Performance Monitoring

Check `performance_report.json` for:
- Processing times per image
- Memory usage statistics
- Detection counts per class
- Model loading times

## Best Practices

### Image Quality
- **Resolution**: 640x640 minimum, higher for better small object detection
- **Format**: JPG, PNG supported
- **Quality**: Well-lit, minimal motion blur

### Batch Processing
- Use `--batch` flag for multiple images
- Monitor GPU memory usage
- Adjust batch size based on image resolution

### Configuration Tuning
- Start with default settings
- Adjust thresholds incrementally
- Test on representative sample first
- Document configuration changes

### Output Management
- Use descriptive output folder names
- Archive important results
- Monitor disk space for large datasets

## Integration Examples

### Python Script Integration
```python
from main import process_images

results = process_images(
    input_path="data/images/",
    output_path="results/",
    config_path="configs/config.yaml",
    batch_mode=True
)
```

### Shell Script Automation
```bash
#!/bin/bash
for dataset in data/*/; do
    python main.py --input "$dataset" --output "results/$(basename "$dataset")" --batch
done
```

## Advanced Features

### Custom Class Priority
Modify NMS priority for specific use cases:
```yaml
nms_consolidation:
  class_priority: [1, 6, 0, 7, 8, 2, 3, 4, 5]  # Prioritize cyclists and e-scooters
```

### Dynamic Thresholds
Implement confidence threshold adaptation:
```yaml
detection_stages:
  stage_a:
    adaptive_threshold: true
    min_confidence: 0.2
    max_confidence: 0.5
```

### Custom Text Prompts
Enhance YOLO-World detection with custom prompts:
```yaml
text_prompts:
  e_scooter: "A person riding an electric scooter. E-scooter rider. Scooter user."
  custom_vehicle: "A delivery truck. Food delivery vehicle. Commercial van."
```