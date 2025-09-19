# Troubleshooting Guide

Common issues and solutions for CAMINA data preparation.

## Path and File Issues

### "Path does not exist" Error

**Problem:** Script can't find input directories

**Solutions:**
1. **Verify pipeline completion:**
   ```bash
   # Check if run.sh completed
   ls outputs/mixed/yolo/

   # Check if run_imagenet.sh completed
   ls outputs/imagenet_train/yolo/
   ls outputs/imagenet_test/yolo/
   ```

2. **Check expected paths:**
   ```bash
   # Complete pipeline paths
   ls outputs/mixed/dataset_viz/images/
   ls outputs/mixed/yolo/

   # YOLO-World only paths
   ls outputs/imagenet_train/dataset_viz/images/
   ls outputs/imagenet_train/yolo/
   ```

3. **Run pipelines if missing:**
   ```bash
   ./run.sh                    # For complete pipeline
   ./run_imagenet.sh          # For YOLO-World only
   ```

### Empty Output Folders

**Problem:** Directories exist but contain no files

**Causes & Solutions:**

1. **Pipeline failed silently:**
   ```bash
   # Check logs for errors
   python main.py --images_dir data/images --output_dir outputs/test --config configs/config.yaml --verbose
   ```

2. **No detections found:**
   - Verify input images are valid
   - Check detection confidence thresholds
   - Review model loading errors

3. **Permission issues:**
   ```bash
   # Fix permissions
   chmod -R 755 outputs/
   ```

### Missing Label Files

**Problem:** Images exist but no corresponding .txt labels

**Solutions:**

1. **Check YOLO format generation:**
   ```bash
   # Verify labels were created
   ls outputs/mixed/yolo/ | head -5
   ```

2. **Validate label content:**
   ```bash
   # Check if labels have content
   head outputs/mixed/yolo/[filename].txt
   ```

3. **Re-run with verbose output:**
   ```bash
   python main.py --verbose
   ```

## Script Execution Issues

### Python Import Errors

**Problem:** Cannot import modules or dependencies

**Solutions:**

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Check Python version:**
   ```bash
   python --version  # Should be 3.8+
   ```

3. **Verify file location:**
   ```bash
   ls prepared_data_roboflow.py
   ```

### Configuration Errors

**Problem:** Script fails during configuration validation

**Solutions:**

1. **Check dataset type:**
   - Use `"single"` for run.sh output
   - Use `"split"` for run_imagenet.sh output

2. **Verify paths in script:**
   ```python
   # Edit paths if different
   images_dir="your/custom/path/to/images"
   labels_dir="your/custom/path/to/labels"
   ```

3. **Test configuration:**
   ```bash
   python -c "
   from prepared_data_roboflow import PrepareConfig
   config = PrepareConfig(
       dataset_name='test',
       dataset_type='single',
       images_dir='outputs/mixed/dataset_viz/images',
       labels_dir='outputs/mixed/yolo'
   )
   print('Config OK')
   "
   ```

## Data Quality Issues

### Annotation Coverage Too Low

**Problem:** Less than 80% of images have annotations

**Causes & Solutions:**

1. **Detection thresholds too high:**
   - Lower confidence thresholds in config.yaml
   - Review NMS settings

2. **No objects in images:**
   - Expected for some datasets
   - Review detection statistics

3. **Label file corruption:**
   ```bash
   # Find empty label files
   find outputs/mixed/yolo/ -name "*.txt" -empty
   ```

### Class Imbalance

**Problem:** One class dominates the dataset (>70%)

**Solutions:**

1. **Review detection settings:**
   - Check class-specific confidence thresholds
   - Verify NMS prioritization rules

2. **Expected behavior:**
   - Some imbalance is normal for urban datasets
   - Person/car typically most frequent

3. **Data augmentation:**
   - Consider balancing during training
   - Use weighted loss functions

### Inconsistent Splits

**Problem:** Train/val splits seem unbalanced

**Solutions:**

1. **Automatic splitting (run.sh):**
   - Script uses 80/20 split automatically
   - Random but deterministic ordering

2. **Predefined splits (run_imagenet.sh):**
   - Uses original dataset train/test structure
   - No modification of splits

3. **Custom splitting:**
   ```python
   # Modify split ratio in script
   split_idx = int(len(valid_pairs) * 0.9)  # 90/10 split
   ```

## Report Generation Issues

### Missing Report Files

**Problem:** Some report files not generated

**Solutions:**

1. **Check script completion:**
   ```bash
   # Verify all report files exist
   ls roboflow_datasets/[dataset-name]/
   ```

2. **Re-run preparation:**
   ```bash
   python prepared_data_roboflow.py
   ```

3. **Check disk space:**
   ```bash
   df -h  # Verify sufficient space
   ```

### CSV File Errors

**Problem:** CSV files malformed or empty

**Solutions:**

1. **Check label files:**
   ```bash
   # Verify labels have valid content
   head -5 outputs/mixed/yolo/*.txt
   ```

2. **Validate CSV format:**
   ```bash
   # Check CSV structure
   head roboflow_datasets/[dataset]/class_distribution.csv
   ```

## Upload-Related Issues

### Large Dataset Size

**Problem:** Dataset too large for upload

**Solutions:**

1. **Split upload:**
   - Upload train and val separately
   - Use batch upload methods

2. **Compress images:**
   - Reduce image quality if acceptable
   - Remove unnecessary files

3. **Subset creation:**
   ```bash
   # Create smaller test dataset
   mkdir subset_test
   cp outputs/mixed/yolo/*.txt subset_test/ | head -100
   ```

### Format Validation Errors

**Problem:** Roboflow rejects dataset format

**Solutions:**

1. **Check data.yaml:**
   ```bash
   cat roboflow_datasets/[dataset]/data.yaml
   ```

2. **Validate YOLO labels:**
   ```bash
   # Check coordinate ranges (should be 0.0-1.0)
   python -c "
   with open('roboflow_datasets/[dataset]/labels/train/[file].txt') as f:
       for line in f:
           parts = line.strip().split()
           coords = [float(x) for x in parts[1:]]
           print('Coords:', coords)
           assert all(0.0 <= x <= 1.0 for x in coords)
   "
   ```

3. **Test with YOLO tools:**
   ```bash
   # Validate with official YOLO tools
   yolo val data=roboflow_datasets/[dataset]/data.yaml
   ```

## Performance Issues

### Slow Processing

**Problem:** Script takes very long time

**Solutions:**

1. **Reduce dataset size:**
   ```bash
   # Test with smaller subset first
   mkdir test_subset
   cp outputs/mixed/yolo/*.txt test_subset/ | head -10
   ```

2. **Check system resources:**
   ```bash
   htop  # Monitor CPU and memory usage
   ```

3. **Optimize file operations:**
   - Use SSD storage if available
   - Close other applications

### Memory Issues

**Problem:** Script runs out of memory

**Solutions:**

1. **Process in batches:**
   - Modify script to process smaller chunks
   - Clear variables between operations

2. **Increase system memory:**
   - Close other applications
   - Use swap file if needed

## Getting Help

### Debug Information

When reporting issues, include:

1. **System information:**
   ```bash
   python --version
   uname -a
   df -h
   ```

2. **Dataset statistics:**
   ```bash
   ls -la outputs/mixed/yolo/ | wc -l
   ls -la outputs/mixed/dataset_viz/images/ | wc -l
   ```

3. **Error messages:**
   - Full traceback from Python
   - Any log file contents

### Log Files

Enable verbose logging:
```bash
python prepared_data_roboflow.py 2>&1 | tee preparation.log
```

### Contact Support

- **GitHub Issues:** Create issue with debug information
- **Documentation:** Check generated reports for dataset-specific details
- **Community:** Share anonymized statistics for help

## Prevention Tips

1. **Always run pipelines completely** before data preparation
2. **Check file permissions** in output directories
3. **Verify disk space** before processing large datasets
4. **Test with small subset** before full processing
5. **Keep backups** of working configurations
6. **Review logs** for warnings during pipeline execution