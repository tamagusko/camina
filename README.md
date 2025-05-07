# CAMINA – Citizen-led Automated Modal INfrastructure Analytics

**CAMINA** is a lightweight, privacy-compliant, edge-deployable system for monitoring urban mobility through object detection and tracking. It runs entirely on a Raspberry Pi and uses YOLOv8 and SORT to count people, bicycles, cars, and more—ideal for citizen science and low-cost infrastructure analytics.

---

## ✅ Features

* 🧠 **YOLO11n-based detection**
* 🚲 **Counts** people, bicycles, cars, motorcycles, buses, trucks
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
├── main.py                         # Main loop: motion → alignment → light mode switching
├── src/
│   ├── count.py                    # YOLOv8 + SORT modal counter (day)
│   ├── lowlight_counter.py         # CLAHE-enhanced low-light counter (IR mode)
│   ├── motion_detector.py          # Motion detection logic
│   ├── camera_position_check.py    # Camera misalignment detection
│   ├── accident_detect.py          # [dev] Accident detection
│   ├── near_misses_detect.py       # [dev] Near-miss detection
│   ├── sort.py                     # SORT tracker
│   └── config.py                   # Central configuration
├── models/                         # YOLOv8 weights
├── data/                           # Logs and camera reference
├── docs/                           # Project docs
```

---

## 🛠️ Requirements

* Python 3.8+
* Raspberry Pi 3 / 4 / 5
* Raspberry Pi Camera Module 3 (NoIR recommended for IR use)
* Optional: Dragino RS485-LN for LoRaWAN

---

## 🔧 Installation

```bash
conda env create -f environment.yml
conda activate camina
```

Download YOLOv8n weights:

```bash
mkdir -p models
wget -O models/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

---

## 🚀 Usage

Start main loop (handles motion, alignment, and light mode switching):

```bash
python main.py
```

Run directly in a specific mode (e.g. testing):

```bash
python src/count.py             # Normal light mode
python src/lowlight_counter.py # Low-light mode
```

Press `q` or `ESC` to exit.

---

## 📝 Logging

* Enabled via `LOGGING_ENABLED = True` in `src/config.py`
* Written to `data/YYYYMMDD-<LOCATION>-<CAMERA_ID>.log`
* Format:

  ```
  2025-05-03 06:00, CAMERA_ALIGNMENT, status:OK, similarity:0.923
  2025-05-03 06:05, NORMAL_LIGHT, person:1, bicycle:1, car:0, motorcycle:0, bus:0, truck:0
  ```

---

## ⚙️ Configuration

Modify `src/config.py` to adjust system behavior:

```python
# Site info
LOCATION = "dublin"
CAMERA_ID = "cam01"

# Logging
LOGGING_ENABLED = True
LOG_INTERVAL_MINUTES = 5

# Brightness-based switching
LOW_LIGHT_THRESHOLD = 40
LOW_LIGHT_CHECK_INTERVAL = 10  # Minutes

# Motion detection
MOTION_CHECK_INTERVAL = 1  # Seconds
MOTION_THRESHOLD = 500000
STILL_THRESHOLD = 5  # Seconds

# Camera alignment check
CAMERA_ALIGNMENT_HOURS = [6, 14]  # 6am and 2pm
CAMERA_CHECK_SIMILARITY_THRESHOLD = 0.85
CAMERA_REFERENCE_IMAGE = "data/camera_reference.jpg"
```
