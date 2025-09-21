# CAMINA Configuration Guide

Complete reference for configuring CAMINA's detection pipeline and optimization settings.

## Configuration File Structure

Main configuration: `configs/config.yaml`

```yaml
detection_stages:     # Two-stage detection pipeline
cyclist_detection:    # Spatial association logic
nms_consolidation:    # Priority-based suppression
text_prompts:         # YOLO-World prompts
performance:          # Hardware optimization
paths:               # Model and data paths
logging:             # Output and debugging
```

## Detection Stages

### Stage A: Base Detection (YOLO11n)
```yaml
detection_stages:
  stage_a:
    model_path: models/yolo_base/yolo11n.pt
    confidence_threshold: 0.25    # Detection confidence minimum
    iou_threshold: 0.45          # NMS IoU threshold
    max_detections: 300          # Maximum detections per image
    classes: [0, 2, 3, 4, 5]     # person, car, motorcycle, bus, truck
```

### Stage B: Specialized Detection (YOLO-World)
```yaml
detection_stages:
  stage_b:
    model_path: models/yolo_world/yolov8s-world.pt
    confidence_threshold: 0.35    # Higher threshold for specialized objects
    iou_threshold: 0.45
    max_detections: 300
    classes: [6, 7, 8]           # e-scooter, SUV, delivery_van
```

## Cyclist Detection Logic

### Basic Configuration
```yaml
cyclist_detection:
  enabled: true
  iou_threshold: 0.20           # Person-bicycle overlap requirement
  spatial_margin: 5             # Pixel margin for spatial proximity
  min_person_confidence: 0.30   # Minimum person detection confidence
  min_bicycle_confidence: 0.25  # Minimum bicycle detection confidence
  max_distance: 50              # Maximum pixel distance between person/bicycle
```

### Advanced Parameters
```yaml
cyclist_detection:
  geometric_validation: true    # Enable geometric constraint checking
  aspect_ratio_check: true      # Validate person aspect ratio
  min_person_height: 0.05      # Minimum person bbox height (normalized)
  max_person_width: 0.8        # Maximum person bbox width (normalized)
  bicycle_size_validation: true # Check bicycle dimensions
```

## NMS Consolidation

### Priority System
```yaml
nms_consolidation:
  enabled: true
  iou_threshold: 0.35           # IoU threshold for suppression
  class_priority: [6, 7, 8, 1, 0, 2, 3, 4, 5]  # YOLO-World classes first
  deterministic_tie_breaking: true               # Consistent results
  confidence_weighting: 0.1     # Weight confidence in tie-breaking
```

### Class Priority Explanation
```yaml
# Priority order (higher priority suppresses lower):
# 6: e-scooter     (highest priority)
# 7: SUV
# 8: delivery_van
# 1: cyclist       (spatial logic result)
# 0: person        (Stage A)
# 2: car
# 3: motorcycle
# 4: bus
# 5: truck         (lowest priority)
```

## Text Prompts (YOLO-World)

### Default Prompts
```yaml
text_prompts:
  e_scooter: "A person on an e-scooter. A person on an electric scooter."
  suv: "An SUV. A pickup truck. A large SUV."
  delivery_van: "A delivery van. A delivery truck."
```

### Enhanced Prompts for Better Detection
```yaml
text_prompts:
  e_scooter: |
    A person riding an electric scooter. E-scooter rider. Person on electric scooter.
    Electric scooter with rider. Scooter user. E-scooter in urban environment.

  suv: |
    A sport utility vehicle. SUV on road. Large passenger vehicle. Pickup truck.
    Off-road vehicle. Family SUV. Large SUV. Crossover vehicle.

  delivery_van: |
    A delivery van. Commercial delivery vehicle. Delivery truck. Package delivery van.
    Courier van. Logistics vehicle. Commercial van. Freight delivery vehicle.
```

## Performance Optimization

### Hardware Settings
```yaml
performance:
  device: auto                  # 'auto', 'cuda', 'cpu', 'mps'
  batch_size: 16               # Adjust based on GPU memory
  memory_cleanup_interval: 100  # Clean GPU memory every N images
  max_workers: 8               # Parallel processing threads
  use_tensorrt: false          # TensorRT optimization (advanced)
```

### Memory Management
```yaml
performance:
  # For 12GB+ GPU
  batch_size: 32
  memory_cleanup_interval: 200

  # For 8GB GPU
  batch_size: 16
  memory_cleanup_interval: 100

  # For 6GB GPU
  batch_size: 8
  memory_cleanup_interval: 50

  # For 4GB GPU
  batch_size: 4
  memory_cleanup_interval: 25
```

### Quality vs Speed Trade-offs
```yaml
performance:
  # High Quality (slower)
  quality_mode: high
  confidence_threshold_stage_a: 0.20
  confidence_threshold_stage_b: 0.30
  batch_size: 8

  # Balanced (default)
  quality_mode: balanced
  confidence_threshold_stage_a: 0.25
  confidence_threshold_stage_b: 0.35
  batch_size: 16

  # High Speed (faster)
  quality_mode: speed
  confidence_threshold_stage_a: 0.35
  confidence_threshold_stage_b: 0.45
  batch_size: 32
```

## Path Configuration

### Model Paths
```yaml
paths:
  models:
    yolo_base: models/yolo_base/
    yolo_world: models/yolo_world/
    camina: models/camina/

  data:
    input: data/input/
    output: outputs/
    cache: cache/

  configs:
    base: configs/
    custom: configs/custom/
```

### Automatic Model Download
```yaml
model_download:
  auto_download: true
  cache_directory: models/cache/
  verify_checksum: true
  fallback_urls:
    yolo11n: "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
    yolov8s_world: "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s-world.pt"
```

## Logging and Output

### Logging Configuration
```yaml
logging:
  level: INFO                   # DEBUG, INFO, WARNING, ERROR
  console_output: true          # Print to console
  file_output: true            # Save to log file
  log_file: logs/camina.log    # Log file path
  performance_logging: true    # Log timing information
  detection_logging: false    # Log individual detections (verbose)
```

### Output Settings
```yaml
output:
  formats: [yolo, visualization] # Output formats to generate
  visualization:
    enabled: true
    bbox_thickness: 2
    font_size: 0.5
    colors:                     # Class-specific colors
      person: [255, 0, 0]       # Red
      cyclist: [0, 255, 0]      # Green
      car: [0, 0, 255]         # Blue
      e_scooter: [255, 255, 0] # Yellow

  compression:
    enabled: false              # Compress output files
    format: zip                # zip, tar.gz
```

## Environment-Specific Configurations

### Development Environment
```yaml
# configs/dev_config.yaml
detection_stages:
  stage_a:
    confidence_threshold: 0.20  # Lower threshold for testing
  stage_b:
    confidence_threshold: 0.30

logging:
  level: DEBUG
  detection_logging: true       # Verbose logging for debugging

performance:
  batch_size: 4                # Smaller batches for development
```

### Production Environment
```yaml
# configs/prod_config.yaml
detection_stages:
  stage_a:
    confidence_threshold: 0.30  # Higher threshold for production
  stage_b:
    confidence_threshold: 0.40

logging:
  level: INFO
  detection_logging: false     # Minimal logging for performance

performance:
  batch_size: 32              # Larger batches for throughput
  memory_cleanup_interval: 200
```

### Research Environment
```yaml
# configs/research_config.yaml
detection_stages:
  stage_a:
    confidence_threshold: 0.15  # Very low threshold for research
  stage_b:
    confidence_threshold: 0.25

cyclist_detection:
  enabled: true
  experimental_features: true  # Enable experimental algorithms

logging:
  level: DEBUG
  performance_logging: true
  export_detections: true     # Export all detection data
```

## Use Case Specific Configurations

### Traffic Monitoring
```yaml
# Focus on vehicles, less on pedestrians
detection_stages:
  stage_a:
    confidence_threshold: 0.35
    classes: [2, 3, 4, 5]      # cars, motorcycles, buses, trucks
  stage_b:
    confidence_threshold: 0.30  # SUVs and delivery vans

cyclist_detection:
  enabled: false              # Skip cyclist logic for pure vehicle detection
```

### Pedestrian Safety Analysis
```yaml
# Focus on people and cyclists
detection_stages:
  stage_a:
    confidence_threshold: 0.20  # Lower threshold for people
    classes: [0]               # person only
  stage_b:
    confidence_threshold: 0.35

cyclist_detection:
  enabled: true
  min_person_confidence: 0.15  # Very sensitive to people
```

### Micro-mobility Research
```yaml
# Focus on e-scooters and cyclists
detection_stages:
  stage_a:
    confidence_threshold: 0.25
  stage_b:
    confidence_threshold: 0.25  # Lower threshold for e-scooters

text_prompts:
  e_scooter: |
    Electric scooter rider. Person on e-scooter. E-scooter user.
    Electric kick scooter. Micro-mobility device user.

cyclist_detection:
  enabled: true
  iou_threshold: 0.15         # More sensitive spatial association
```

## Validation and Testing

### Configuration Validation
```yaml
validation:
  enabled: true
  strict_mode: false          # Fail on warnings
  check_model_paths: true     # Verify model files exist
  check_gpu_memory: true      # Validate GPU memory requirements
  test_sample: true           # Run test detection on sample image
```

### A/B Testing Configuration
```yaml
ab_testing:
  enabled: false
  variant_a: configs/config_v1.yaml
  variant_b: configs/config_v2.yaml
  sample_ratio: 0.1           # Fraction of images for testing
  metrics_comparison: true    # Compare detection metrics
```

## Advanced Features

### Ensemble Detection
```yaml
ensemble:
  enabled: false
  models:
    - models/yolo_base/yolo11n.pt
    - models/yolo_base/yolo11s.pt
  fusion_method: weighted_average
  weights: [0.6, 0.4]
```

### Adaptive Thresholds
```yaml
adaptive_thresholds:
  enabled: false
  method: dynamic            # dynamic, confidence_based
  adaptation_rate: 0.1       # How quickly to adapt
  min_threshold: 0.15        # Minimum confidence threshold
  max_threshold: 0.60        # Maximum confidence threshold
```

### Custom Preprocessing
```yaml
preprocessing:
  resize_method: letterbox    # letterbox, stretch, crop
  normalization: imagenet    # imagenet, custom
  augmentation:
    enabled: false
    methods: [flip, rotate, brightness]
```

## Configuration Best Practices

1. **Start with defaults** and adjust incrementally
2. **Test on small samples** before full processing
3. **Monitor GPU memory** usage during batch processing
4. **Document configuration changes** for reproducibility
5. **Use environment-specific configs** for different deployment scenarios
6. **Validate configurations** before production use
7. **Keep backup configs** for known working setups