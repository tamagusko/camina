# CAMINA

**CAMINA** (Counting Active Mobility In Neighbourhood Areas) is a lightweight, edge-based citizen science tool for counting pedestrians, cyclists, and vehicles using a camera and a Raspberry Pi.

This project enables participatory sensing and supports communities in understanding mobility patterns in public spaces.

---

## Features

- 🚲 Counts people, bicycles, motorcycles, cars, buses, and trucks
- 📏 Estimates vehicle speed using object tracking
- ⚠️ Detects near misses and potential collisions based on trajectory analysis
- 🖥️ Operates entirely on a Raspberry Pi 3 or 4 (edge-computing device)
- ☀️ Optimized for solar-powered, off-grid deployment
- 🌙 Automatically switches between day and low-light (IR) modes based on ambient brightness (every 10 minutes, configurable)
- 📷 Uses the **Raspberry Pi Camera Module 3 NoIR** with 850nm IR floodlight (plugged-in mode)
- 🌐 Optional LoRaWAN integration using **Dragino RS485-LN** for remote data transmission
- 🧪 Optional integration of **sds011** for PM2.5 and PM10 environmental sensing
- 🔐 All processing occurs locally — no images or videos are stored or transmitted
- ✅ Designed in compliance with **GDPR** and privacy-by-design principles

---

## Modes

- `solar_counter.py`: Efficient modal share counting (daylight)
- `solar_lowlight_counter.py`: CLAHE-enhanced detection for low-light or IR scenes
- `plugged_counter.py`: Full-feature mode with speed and near-miss detection
- `camina_run.py`: Smart launcher that automatically switches modes and manages logging

---

## Requirements

- Python 3.10
- Conda (recommended for Mac/Linux development)
- Raspberry Pi 3 or 4 with compatible power supply

---

## Setup

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
python camina_run.py  # Auto-switches between modes based on ambient light
```

Or run specific modes manually:

```bash
python src/solar_counter.py
python src/solar_lowlight_counter.py
python src/plugged_counter.py
```

---

## Directory Structure

```
camina/
├── src/
│   ├── solar_counter.py
│   ├── solar_lowlight_counter.py (test)
│   ├── plugged_counter.py (test)
│   ├── camera_position_check.py (dev)
│   ├── near_misses_detect.py (dev)
│   ├── accident_detect.py (dev)
│   ├── sort.py
├── camina_run.py  # Main script to run the project
├── config.py  # Configuration file for the project
├── data/  # directory for storing log files
├── notebooks/  # Jupyter notebooks testing and prototyping
```
