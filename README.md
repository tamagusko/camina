# CAMINA – Citizen-led Automated Modal INfrastructure Analytics

**CAMINA** is a lightweight, privacy-compliant, edge-deployable system for monitoring urban mobility through object detection and tracking. It runs entirely on a Raspberry Pi and uses YOLO11 with our custom-trained **CAMINAv1** model and SORT tracking to accurately count people, cyclists, cars, and more—ideal for citizen science and low-cost infrastructure analytics.

---

## ✅ Features

* 🧠 **YOLO11-based detection** with custom **CAMINAv1** model
* 🚲 **Accurately counts** people, cyclists, cars, motorcycles, buses, trucks
* 🛰️ **LoRaWAN support** (optional, via Dragino RS485-LN)
* 🌙 **Low-light detection with IR floodlight**
* 🔁 **Auto-switching between normal and low-light modes** based on brightness
* 💤 **Motion-based activation** to reduce energy use
* 📷 **Camera alignment check** (twice daily, skips if motion is detected)
* 🔐 **Fully edge-processed** — no image/video storage or upload
* 📝 **Configurable logging** in clean, compact format
* 🛠️ **Modular design** with support for extensions like near-miss and accident detection
* ⚡ Optimized for **solar deployment**
* 🇪🇺 **GDPR-compliant** and privacy-first

---

## 📁 Directory Structure

```
camina/
├── main.py                         # Main entry point for running the counter
├── src/
│   ├── camina/                     # Camina package
│   │   ├── app.py                  # Main application logic
│   │   ├── core/
│   │   │   └── tracker.py          # SORT tracker implementation
│   │   └── utils/
│   │       ├── config.py           # Central configuration loader
│   │       └── display.py          # E-paper and OLED display utilities
│   ├── dev/                        # Development scripts (e.g., motion detection, camera checks)
│   │   ├── camera_position_check.py
│   │   ├── lowlight_counter.py
│   │   ├── motion_detector.py
│   │   └── plugged_counter.py
│   ├── utils/                      # General utilities (e.g., NCNN export)
│   │   ├── export_ncnn.py
│   │   ├── infer_image.py
│   │   └── oled_display.py
│   └── speed_estimation.py         # Speed estimation module
├── configs/                        # Configuration files
│   ├── classes.yaml                # Defines object classes for detection
│   └── main_config.yaml            # Main application configuration
├── models/                         # Trained YOLO models
├── data/                           # Logs and camera reference images
├── docs/                           # Project documentation
├── scripts/                        # Utility scripts (e.g., data processing, training)
├── custom_model_train/             # Custom model training datasets and scripts
└── tests/                          # Test files and data
```

---

## 🛠️ Hardware Requirements

### Minimum Requirements
* **Development**: Any computer with Python 3.8+
* **Production**: Raspberry Pi 4/5 (Pi 3 supported with reduced performance)
* **Camera**: Raspberry Pi Camera Module 3 (NoIR recommended for IR use)
* **Storage**: 16GB+ microSD card (Class 10 or UHS-1)

### Optional Hardware
* **LoRaWAN**: Dragino RS485-LN for remote data transmission
* **Display**: E-paper or OLED display for local monitoring
* **Power**: Solar panel + battery for off-grid deployment
* **IR Lighting**: 850nm IR floodlight for night operation

### Software Dependencies
* **Models**: CAMINAv1 (included) or base YOLO11n
* **Framework**: Ultralytics YOLO11, OpenCV, NumPy
* **Tracking**: SORT algorithm implementation
* **Configuration**: YAML-based configuration system

---

## 🔧 Installation

### Prerequisites
- Python 3.8+
- Conda or pip package manager
- Git

### Quick Start
```bash
# Clone the repository
git clone https://github.com/your-username/camina.git
cd camina

# Create conda environment
conda env create -f environment.yml
conda activate camina

# Or install with pip
pip install -r requirements.txt
```

### Models
The project includes the **CAMINAv1** custom model optimized for cyclist detection:
- **CAMINAv1 Model**: `models/20250629_warmup_best.pt` (included)
- **NCNN Export**: `models/20250629_warmup_best_ncnn_model/` (optimized for Raspberry Pi)

**Optional**: Download base YOLO11n weights for comparison:
```bash
mkdir -p models
wget -O models/yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
```

**Recommended**: Use the CAMINAv1 model for production as it provides superior cyclist detection accuracy.

---

## 🚀 Usage

The `main.py` script acts as a launcher for the appropriate counter application (for PC or Raspberry Pi).

To run the counter:

```bash
python main.py
```

The application will automatically load the configuration from `configs/main_config.yaml` and start the modal share counter.

Press `q` or `ESC` to exit the application window.

---

## 📝 Logging

* Enabled via `logging_enabled: true` in `configs/main_config.yaml`
* Uses CAMINAv1 model for accurate cyclist detection in logs
* Written to `data/YYYYMMDD-<LOCATION>-<CAMERA_ID>.log`
* Format:

  ```
  2025-05-03 06:00, CAMERA_ALIGNMENT, status:OK, similarity:0.923
  2025-05-03 06:05, NORMAL_LIGHT, person:1, bicycle:1, car:0, motorcycle:0, bus:0, truck:0
  ```

---

## ⚙️ Configuration

Modify `configs/main_config.yaml` to adjust system behavior:

```yaml
# Model settings (CAMINAv1 custom model)
ncnn_model_path: models/20250629_warmup_best_ncnn_model/ # Path to the CAMINAv1 NCNN model

# Camera settings
camera_source: tests/test.mov # Camera source (e.g., 0 for webcam, path to video file)
frame_width: 640              # Frame width for camera capture
frame_height: 480             # Frame height for camera capture
frame_skip: 5                 # Process every Nth frame to reduce load

# Inference settings
imgsz: 640                    # Image size for model inference
confidence_threshold: 0.65    # Confidence threshold for object detection
draw_bbox: true               # Whether to draw bounding boxes on the output frame

# Logging and metadata
location: UCD                 # Location of the deployment
camera_id: cam01              # Unique ID for the camera
logging_enabled: true         # Enable/disable logging of counts
log_interval_minutes: 5       # Interval in minutes for logging counts

# Display settings (for Raspberry Pi with E-paper display)
refresh_interval_seconds: 10  # How often to refresh the E-paper display

# SORT tracker settings
sort_max_age: 90              # Maximum number of frames to keep a track without new detections
sort_iou_threshold: 0.3       # IoU threshold for matching detections to existing tracks

# CAMINAv1 Model Information
# The custom CAMINAv1 model was trained on COCO 2017 dataset with enhanced cyclist detection
# It provides significantly better accuracy for cyclist detection compared to base YOLO11

# main.py specific settings (for motion detection, low light, and alignment checks)
LOW_LIGHT_CHECK_INTERVAL: 15  # Check for low light conditions every X minutes
LOW_LIGHT_THRESHOLD: 50       # Threshold for low light detection (average pixel value)
CAMERA_ALIGNMENT_HOURS: [6, 18] # Hours to run camera alignment check (e.g., 6 AM and 6 PM)
MOTION_SENSITIVITY: 500       # Motion detection sensitivity (area of the largest contour)
REFERENCE_FRAME_PATH: "data/img/reference_frame.jpg" # Reference frame for camera alignment check
ALIGNMENT_THRESHOLD: 0.9      # Threshold for camera alignment check (structural similarity index)
EMAIL_SENDER: "your_email@gmail.com" # Sender email for notifications
EMAIL_PASSWORD: "your_password" # Sender email password
EMAIL_RECIPIENT: "recipient_email@example.com" # Recipient email for notifications
EMAIL_SUBJECT: "Camera Alignment Alert" # Email subject for alignment alerts
EMAIL_BODY: "Camera may be misaligned. Please check." # Email body for alignment alerts
```
