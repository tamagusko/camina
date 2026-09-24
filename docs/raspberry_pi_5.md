# Raspberry Pi 5 setup

From a blank SD card to the sensor running as a service. The Pi runs a lightweight
profile — NCNN, NumPy, SciPy and a few small libraries (`requirements-pi.txt`,
~200 MB) — with no PyTorch and no Ultralytics.

> **Status:** these steps follow the code and were checked on a dev machine; they have
> not yet been run end to end on a Pi (`.planning/PLAN.md` S6). If a step fails, note
> what you saw and fix this page.

## What you need

- Raspberry Pi 5 (8 GB; 4 GB is enough) with the Active Cooler
- Camera Module 3 on the CSI connector
- Official 27 W USB-C power supply
- microSD card, 32 GB or more
- Wi-Fi or Ethernet that can reach the dashboard

## 1. Flash the OS

In Raspberry Pi Imager choose **Raspberry Pi OS Lite (64-bit)**, the current
**Trixie** release (Debian 13, Python 3.13). Under *Edit settings* set the hostname
(e.g. `camina-01`), a user, Wi-Fi, your timezone, and enable SSH.

Use Trixie, not Bookworm: `picamera2` comes from the OS and must share NumPy 2 with the
sensor; Bookworm ships NumPy 1.

## 2. Check the hardware

```bash
sudo apt update && sudo apt full-upgrade -y
rpicam-hello --list-cameras     # lists the camera (imx708 for Camera Module 3)
timedatectl                     # "System clock synchronized: yes"
vcgencmd measure_temp           # idle ~40–50 °C with the cooler
vcgencmd get_throttled          # throttled=0x0 (anything else: power or heat)
```

The clock must be synced: counts are grouped into 15-minute windows by wall-clock time.

## 3. Install

```bash
sudo apt install -y git python3-venv python3-picamera2
sudo adduser --system --group --home /opt/camina camina
sudo usermod -aG video camina                 # camera access
sudo -u camina git clone --branch dev https://github.com/tamagusko/camina.git /opt/camina
cd /opt/camina
sudo -u camina python3 -m venv --system-site-packages venv
sudo -u camina ./venv/bin/pip install --no-deps -r requirements-pi.txt
sudo -u camina ./venv/bin/python -c "import picamera2, ncnn, numpy; print('ok')"
```

- `--system-site-packages` lets the venv see `picamera2`, which is installed with apt.
- `--no-deps` is deliberate: the listed packages are the complete set the sensor
  needs, and skipping dependency resolution keeps out ~150 MB it never uses
  (OpenCV, matplotlib…). See the note in `requirements-pi.txt`.
- The clone is `dev`: this runtime reaches `main` once it has run on a Pi
  (`.planning/PLAN.md` S6). After that, clone `main`, the stable branch.

## 4. Configure

```bash
sudo install -m 0750 -o camina -g camina -d /etc/camina /var/lib/camina
sudo cp configs/sensor.yaml /etc/camina/sensor.yaml
sudo chown camina:camina /etc/camina/sensor.yaml && sudo chmod 640 /etc/camina/sensor.yaml
sudo nano /etc/camina/sensor.yaml
```

Set, at least:

| Key | Value |
|---|---|
| `sensor_id` | this unit's id, e.g. `cam-dub-01` |
| `api_base_url` | the dashboard's ingest URL, ending in `/api/ingest` |
| `api_token` | this unit's token (keep the file at `chmod 640`) |

The defaults already point at the right places: `state_db_path:
/var/lib/camina/state.db`, `ncnn_model_path:
/opt/camina/models/camina_v1_yolo11n_ncnn_model`, `imgsz: 640`. For the smaller FP16
model, set `ncnn_model_path` to `/opt/camina/models/camina_v1_yolo11n_fp16_ncnn_model`.

**Before the live dashboard exists** (`.planning/PLAN.md` S4–S5): to test the link, run
the dashboard on a laptop (`scripts/run_dashboard.sh`), set `api_base_url` to
`http://<laptop-ip>:3000/api/ingest` and `api_token` to the laptop's
`CAMINA_DEV_INGEST_TOKEN`. Mock mode accepts the posts but does not store them, so
nothing appears on the map yet.

## 5. Dry run

```bash
cd /opt/camina
sudo -u camina ./venv/bin/python scripts/run_sensor.py --config /etc/camina/sensor.yaml --dry-run
```

Expect `Loaded NCNN model … (9 classes, imgsz 640)` and `Dry run OK`.

## 6. Run as a service

```bash
sudo cp deploy/systemd/camina-sensor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camina-sensor
journalctl -u camina-sensor -f
```

Expect `Sensor daemon starting for cam-dub-01`. The service starts at boot, waits for
network and clock sync, and systemd restarts it if it stalls for 5 minutes.

## Update

```bash
cd /opt/camina
sudo -u camina git pull
sudo -u camina ./venv/bin/pip install --no-deps -r requirements-pi.txt
sudo systemctl restart camina-sensor
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `rpicam-hello` finds no camera | Reseat the ribbon cable (contacts facing the board), power off first |
| `ImportError: picamera2` in the venv | The venv was made without `--system-site-packages`; recreate it |
| NumPy "compiled using NumPy 1.x" error | Bookworm image; reflash with Trixie |
| Camera permission denied | `camina` not in the `video` group (step 3), then restart the service |
| `throttled=` not `0x0` | Use the 27 W supply; check the Active Cooler fan spins |
| Windows or timestamps wrong | `timedatectl` must show the clock synchronized |

To run the test suite on the Pi: `./venv/bin/pip install pytest` then
`./venv/bin/python -m pytest`. Export and Ultralytics-parity tests skip on this
profile, by design.
