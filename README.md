# CAMINA

**CAMINA** (Counting Active Mobility In Neighbourhood Areas) is a lightweight, edge-based citizen science tool for counting pedestrians, cyclists, and vehicles using a camera and a Raspberry Pi 3.

This project enables participatory sensing and supports communities in understanding mobility patterns in public spaces.

---

## Features

* 🚲 Counts people, bicycles, motorcycles, cars, buses, and trucks
* 📏 Estimates vehicle speed using object tracking
* ⚠️ Detects near misses and potential collisions based on trajectory analysis
* 🖥️ Operates entirely on a Raspberry Pi 3 or 4 (edge-computing device)
* ☀️ Optimized for solar-powered, off-grid deployment
* 🌙 Automatically switches between day and low-light (IR) modes based on ambient brightness (every 10 minutes, configurable)
* 🌐 Optional LoRaWAN integration for remote data transmission
* 🔐 All processing occurs locally — no images or videos are stored or transmitted
* ✅ Designed in compliance with **GDPR** and privacy-by-design principles

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

## List of Equipment

### 🔧 Core Components

* **Raspberry Pi 3 Model B+** or **Raspberry Pi 4 (recommended)**
* **Raspberry Pi Camera Module 3 NoIR** – for visible and infrared imaging
* **MicroSD Card** (16GB or larger, Class 10 or UHS-1)

### 🔌 Power and Deployment

* **5V Power Supply** (2.5A for Pi 3, 3A USB-C for Pi 4)
* **USB Power Bank or battery** 
* **Solar Panel** (optional; 10–20W with charge controller and battery for off-grid)

### 🌙 Night and Low-Light Support *(plugged-in mode only)*

* **850nm IR Floodlight** – for night illumination of street scenes

### 🌐 Connectivity and Transmission

* **USB Wi-Fi Adapter** (for Raspberry Pi 3)

### 🧪 Optional Sensor

* **SenseCAP S2102** – PM2.5 air quality sensor
* **Dragino RS485-LN** – LoRaWAN module for remote log transmission over RS485
