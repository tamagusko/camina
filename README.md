# CAMINA – Citizen-led Automated Modal INfrastructure Analytics

## 📋 Overview
CAMINA is a lightweight, privacy-compliant, edge-deployable system for counting and analyzing urban mobility using object detection and tracking. Designed to run on a Raspberry Pi with a camera, CAMINA uses YOLOv8 and SORT to detect and count modal share categories such as pedestrians, bicycles, and vehicles.

## ✅ Features
- 🧠 YOLOv8n-based object detection
- 🚲 Counts people, bicycles, cars, motorcycles, buses, and trucks
- 📏 Measures vehicle speeds (future extension)
- ⚠️ Detects near misses and potential accidents based on object trajectories (planned)
- 🖥️ Runs entirely on a Raspberry Pi 3/4/5
- ⚡ Optimized for solar-powered deployment
- 🌙 Low light detection using IR (plugged-in mode only)
- 🔄 Switches between normal and low-light mode every 10 minutes (configurable)
- 🔐 Processes everything on the edge — **no images or videos are transmitted or stored**
- 🛰️ Optional LoRaWAN module for data offload
- ✅ Fully compliant with **GDPR** and privacy-by-design principles

## 📁 Directory Structure
```
camina/
├── main.py                    # Auto mode switching and log orchestration
├── src/
│   ├── count.py               # Normal light mode
│   ├── lowlight_counter.py    # Low-light mode (IR)
│   ├── config.py              # Camera/location config
│   ├── sort.py                # Object tracking
│   ├── camera_position_check.py    # [dev] Camera alignment helper
│   ├── near_misses_detect.py       # [dev] Detect close encounters
│   ├── accident_detect.py          # [dev] Detect collisions
├── models/                    # Pre-trained YOLOv8n model weights
├── data/                      # Data and logs
├── docs/                      # Documentation
```

## 🛠️ Requirements
- Python 3.8+
- Raspberry Pi 3/4/5 (Linux/macOS compatible for testing)
- Raspberry Pi Camera Module 3 NoIR

## 🔧 Installation
```bash
conda env create -f environment.yml
conda activate camina
```
Download YOLOv8n model weights:
```bash
mkdir -p models && wget -O models/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

## 🚀 Usage
Start the main loop (auto-switching between modes):
```bash
python main.py
```

To manually run a specific mode:
```bash
python src/count.py           # Normal light mode
python src/lowlight_counter.py  # Low light mode
```

Press `q` or `ESC` to stop.

## 📝 Logging
- Enabled by setting `LOGGING_ENABLED = True` in `src/config.py`
- Logs saved every N minutes (configurable via `LOG_INTERVAL_MINUTES`)
- Format: `data/YYYYMMDD-<LOCATION>-<CAMERA_ID>.log`
```
2025-05-03 01:55, NORMAL_LIGHT, person:0, bicycle:0, car:0, motorcycle:0, bus:0, truck:0
```

## 📌 Configuration
Edit `src/config.py`:
```python
LOCATION = "dublin"
CAMERA_ID = "cam01"
LOGGING_ENABLED = True
LOG_INTERVAL_MINUTES = 5
LOW_LIGHT_CHECK_INTERVAL = 600  # Check every 10 minutes
```
