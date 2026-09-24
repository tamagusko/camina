# CAMINA

**Citizen-led Automated Modal INfrastructure Analytics** — a privacy-first traffic sensor.
A Raspberry Pi counts nine road-user classes on-device and publishes only the counts to a
public map of Dublin. No image or video is stored or uploaded.

Research prototype, UCD Spatial Dynamics Lab. No unit is deployed on a street yet; the plan
is in [`.planning/PLAN.md`](.planning/PLAN.md), current status in
[`.planning/STATE.md`](.planning/STATE.md).

## How it works

```
Pi camera → YOLO11n (NCNN) → tracker → count gate → 15-min counts → HTTPS → dashboard
```

- **Detector:** the 9-class YOLO11n from the TRA 2026 paper, as NCNN (FP32 and FP16) in
  [`models/`](models/), provenance in each folder's `PROVENANCE.md`.
- **Tracker:** one SORT tracker for all classes; a track's class is its majority vote.
- **Count gate:** each track is counted once, when it crosses a screenline (with direction)
  or has moved far enough. Parked cars and street furniture never count.
- **Privacy:** counts only; the public map never shows sensor locations; counts below 5
  are suppressed.

## Detected classes

| ID | Class | Description |
|---|---|---|
| 0 | Person | Individual persons |
| 1 | Cyclist | People on bicycles |
| 2 | Car | Standard passenger cars |
| 3 | E-scooter | Electric scooters |
| 4 | SUV | Sport utility vehicles |
| 5 | Motorcyclist | People on motorcycles |
| 6 | Bus | Public buses |
| 7 | Delivery Van | Delivery vehicles |
| 8 | Truck | Large trucks |

IDs are the published order, fixed in [`configs/classes.yaml`](configs/classes.yaml).

## Quick start

```bash
git clone https://github.com/tamagusko/camina.git && cd camina
uv venv && uv pip install -r requirements.txt
.venv/bin/python -m pytest

# See what the sensor sees and counts, on a test video
.venv/bin/python scripts/view_detections.py --video videos/test.mov --out /tmp/out.mp4 \
    --screenline 0.65 0.15 0.65 0.72 --play

# Dashboard with mock data (Node 20.11+) → http://localhost:3000/dublin
scripts/run_dashboard.sh
```

On a Raspberry Pi 5: [docs/raspberry_pi_5.md](docs/raspberry_pi_5.md).

## Repository

| Path | Contents |
|---|---|
| `camina/` | The sensor: detector, tracker, count gate, counters, publisher (`python -m camina`) |
| `dashboard/` | Next.js map and ingest API |
| `training/` | Dataset, training and NCNN export |
| `models/` | CAMINAv1 NCNN models |
| `configs/` | Classes and per-device sensor config |
| `videos/` | Test videos |
| `scripts/` | Viewer, dashboard runner, mock data generator |
| `deploy/` | systemd unit |
| `docs/` | Pi setup, ingest protocol, operations, mock mode |

## License

- **Code:** [MIT](LICENSE).
- **Models:** [AGPL-3.0](models/LICENSE) — everything in `models/`. They were trained and
  exported with [Ultralytics YOLO](https://github.com/ultralytics/ultralytics), which is
  AGPL-3.0 and declares that licence for the models it produces (stated in each export's
  `metadata.yaml`). The sensor runs them with `ncnn` and does not use Ultralytics; training
  and export do.
