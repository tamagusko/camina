Here’s a clean and minimal `README.md` tailored to your CAMINA project:
# CAMINA

**CAMINA** (Counting Active Mobility In Neighbourhood Areas) is a lightweight, edge-based citizen science tool for counting pedestrians, cyclists, and vehicles using a camera and a Raspberry Pi 3.

This project enables participatory sensing and supports communities in understanding mobility patterns in public spaces.

---

## Features

- 🧠 YOLOv8n-based object detection
- 🚲 Counts people, bicycles, cars, motorcycles, buses, and trucks
- 📏 Measures vehicle speeds using visual tracking
- ⚠️ Detects near misses and potential accidents based on object trajectories
- 🖥️ Runs entirely on a Raspberry Pi 3 (optimized for solar-powered deployment)
- 📊 Outputs real-time modal share counts
- 🔐 Processes everything on the edge — **no images or videos are transmitted**
- ✅ Fully compliant with **GDPR** and privacy-by-design principles

---

## Requirements

- Python 3.10
- Conda (recommended for Mac development)
- Raspberry Pi 3 (for edge deployment)

---

## Setup (Mac)

```bash
conda create -n camina python=3.10
conda activate camina
pip install torch torchvision ultralytics opencv-python
````

---

## Running

```bash
python src/camina_counter.py
```

Press `q` to exit the viewer.

---

## Directory Structure

```
camina/
├── src/
│   └── solar_counter.py
├── data/
├── notebooks/
├── environment.yml
├── README.md
└── .gitignore
```
