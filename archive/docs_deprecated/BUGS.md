# CAMINA Known Issues and Bugs

## 🐞 Current Issues

### 1. Cyclist vs E-scooter Ambiguity
**Status**: Partially mitigated with priority system
- **Description**: E-scooter riders can be incorrectly detected as cyclists by Stage A when person+bicycle pairs exist nearby
- **Current Mitigation**: E-scooter detections suppress overlapping cyclist detections (IoU ≥ 0.35)
- **Workaround**: Adjust e-scooter confidence thresholds or refine text prompts for better discrimination
- **Impact**: Low - most cases handled by priority system

### 2. Small Object Detection Limits
**Status**: Configuration dependent
- **Description**: Very small mobility objects (distant or low-resolution) may be missed
- **Workaround**: Lower confidence thresholds or adjust `min_bbox_area` setting
- **Configuration**: Set `min_bbox_area: 0.005` for smaller objects
- **Impact**: Medium - affects detection completeness in wide-area surveillance

### 3. GPU Memory Fragmentation
**Status**: Monitored with automatic mitigation
- **Description**: Long-running processing can lead to GPU memory fragmentation
- **Current Mitigation**: Dynamic batch sizing and memory cleanup intervals
- **Workaround**: Restart processing periodically for very large datasets
- **Impact**: Low - handled by memory management system

## ✅ Resolved Issues

### 1. Cyclist Misclassification (RESOLVED v2.0)
- **Previous Issue**: Cyclists misclassified as motorcycles by base YOLO models
- **Solution**: Implemented geometric cyclist detection logic (person+bicycle pairing)
- **Result**: High-precision cyclist detection with >90% accuracy

### 2. Base YOLO11 Class Limitations (RESOLVED v2.0)
- **Previous Issue**: YOLO11 lacks e-scooter, SUV, delivery_van classes
- **Solution**: Hybrid architecture with YOLO-World for new classes
- **Result**: Complete 9-class urban mobility detection

### 3. Detection Conflicts (RESOLVED v2.0)
- **Previous Issue**: Overlapping detections from multiple models caused confusion
- **Solution**: Priority-based NMS consolidation with deterministic tie-breaking
- **Result**: Clean, consistent detection output

## 🔍 Monitoring and Reporting

### How to Report Issues
1. Check this list for known issues first
2. Enable verbose logging: `python main.py --verbose`
3. Include configuration file and sample images
4. Describe expected vs actual behavior
5. Include system specifications (GPU, memory, etc.)

### Performance Monitoring
```bash
# Monitor GPU usage during processing
watch -n 1 nvidia-smi

# Check memory usage patterns
python main.py --verbose --images_dir data/test 2>&1 | grep -i memory

# Validate detection consistency
python main.py --validate_only --config configs/config.yaml
```

## 🛠️ Troubleshooting Tips

### For Cyclist Detection Issues
```yaml
# Adjust cyclist detection sensitivity
cyclist_detection:
  iou_threshold: 0.15    # Lower = more permissive matching
  spatial_margin_px: 10  # Higher = more tolerance for positioning
```

### For E-scooter Detection Issues
```yaml
# Refine e-scooter prompts for better accuracy
text_prompts:
  e-scooter:
    - "electric scooter with person"
    - "person riding electric scooter"
    - "standing person on scooter platform"
```

### For Memory Issues
```yaml
# Reduce memory usage
performance:
  batch_size_base: 8
  max_batch_size: 16
  memory_threshold: 0.70
```

---

**Last Updated**: Current as of v2.0.0
**Next Review**: Monitor issue reports and user feedback
