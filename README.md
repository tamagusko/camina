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
- 🌙 Detects ambient brightness to switch between day and low-light modes every 10 minutes (configurable)
- 🗂 Logs results to a daily file: `data/YYYYMMDD-location-camera.log`
- 📈 Saves modal counts and low-light status every minute
- ⚙️ Configurable via `config.py` (location, camera ID, light-check interval)
- 🔐 Processes everything on the edge — **no images or videos are transmitted or stored**
- ✅ Fully compliant with **GDPR** and privacy-by-design principles

---

## Modes

- `solar_counter.py`: Edge-efficient modal share counting (daylight)
- `solar_lowlight_counter.py`: CLAHE-enhanced detection for low-light or IR scenes
- `plugged_counter.py`: Full-feature mode with speed and near-miss detection
- `camina_run.py`: Smart launcher that automatically chooses between daylight or low-light mode and re-checks based on config

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
pip install -r requirements.txt
```

Or, using the provided environment:

```bash
conda env create -f environment.yml
conda activate camina
```

---

## Running

```bash
python camina_run.py  # Auto-selects normal or low-light mode, updates every N min
```

You can also run a specific mode:

```bash
python src/solar_counter.py
python src/solar_lowlight_counter.py
python src/plugged_counter.py
```

Press `q` to exit the viewer.

---

## Directory Structure

```
camina/
├── src/
│   ├── solar_counter.py
│   ├── solar_lowlight_counter.py
│   ├── plugged_counter.py
│   ├── sort.py
├── camina_run.py
├── config.py
├── data/
├── notebooks/
├── environment.yml
├── README.md
└── .gitignore
```
