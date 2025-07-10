# CAMINA Automatic Calibration System

The CAMINA system now includes automatic camera calibration using Depth Anything V2 for accurate speed measurements.

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
# Install calibration requirements
pip install -r requirements_calibration.txt

# Install Depth Anything V2
pip install git+https://github.com/DepthAnything/Depth-Anything-V2.git
```

### 2. Download Depth Model

```bash
# Create models directory
mkdir -p models

# Download Depth Anything V2 small model (recommended for Raspberry Pi)
wget https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth -O models/depth_anything_v2_vits.pth
```

### 3. Run Initial Calibration

```bash
# Run calibration script when installing camera
python scripts/calibrate_camera.py
```

## 📋 How It Works

### **Automatic Calibration Process**

1. **Depth Estimation**: Uses Depth Anything V2 to estimate real-world depth from camera images
2. **Ground Plane Analysis**: Analyzes the ground plane to calculate pixel-to-meter conversion
3. **Config Update**: Automatically updates `pixels_per_meter` in your config file
4. **Reference Storage**: Saves a reference frame for position change detection

### **Camera Position Monitoring**

- **Scheduled Checks**: Monitors camera position twice daily (6 AM and 6 PM)
- **Change Detection**: Uses structural similarity (SSIM) and perceptual hashing
- **Auto-Recalibration**: Prompts for recalibration when position changes detected
- **Fallback Options**: Manual calibration script available

## 🛠️ Configuration Options

Add these settings to your `main_config.yaml`:

```yaml
# Calibration settings
camera_alignment_hours: [6, 18]  # Hours to check camera position
calibration_threshold: 0.1       # Sensitivity for position change detection
```

## 📊 Calibration Files

The system creates these files in `data/calibration/`:

- `reference_frame.jpg` - Reference image for position comparison
- `reference_hash.txt` - Quick comparison hash
- `calibration_info.yaml` - Calibration metadata

## 🔧 Manual Calibration

If automatic calibration fails or you need to recalibrate manually:

```bash
# Run standalone calibration
python scripts/calibrate_camera.py

# Or use the interactive mode in the main app
# The system will prompt you during scheduled checks
```

## 📱 Raspberry Pi Optimization

For better performance on Raspberry Pi:

1. **Use the small model** (`vits`) - already configured as default
2. **CPU-only mode** - automatically detects and uses CPU when GPU unavailable
3. **Memory efficiency** - depth estimation runs only during calibration

## 🚨 Troubleshooting

### **Depth Model Not Found**
```bash
# Ensure model is downloaded to correct location
ls models/depth_anything_v2_vits.pth

# If missing, download manually:
wget https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth -O models/depth_anything_v2_vits.pth
```

### **Import Errors**
```bash
# Install missing dependencies
pip install scikit-image torch torchvision

# For Depth Anything V2
pip install git+https://github.com/DepthAnything/Depth-Anything-V2.git
```

### **Calibration Fails**
- Ensure good lighting conditions
- Make sure camera has clear view of ground/road
- Try different times of day for better depth estimation
- Check that camera is stable and not moving during calibration

## 📈 Expected Results

### **Typical Calibration Values**
- **Window cameras**: 8-15 pixels per meter
- **Street-level cameras**: 15-30 pixels per meter
- **High cameras**: 5-12 pixels per meter

### **Accuracy Expectations**
- **Speed measurements**: ±2-5 km/h typical accuracy
- **Position detection**: Detects movements >10cm typically
- **Recalibration frequency**: Usually not needed unless camera physically moved

## 🔄 Integration with Main System

The calibration system is fully integrated:

- **Automatic monitoring** during normal operation
- **Non-intrusive checks** - doesn't affect counting performance
- **Smart scheduling** - only checks during specified hours
- **User prompts** - asks permission before recalibrating
- **Fallback handling** - continues operation even if calibration unavailable

## 📞 Support

If you encounter issues:

1. Check the calibration log files in `data/calibration/`
2. Verify all dependencies are installed
3. Ensure camera permissions are granted
4. Try manual calibration script

For technical support, check the troubleshooting section or create an issue on GitHub.