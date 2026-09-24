# CAMINA

**Citizen-led Automated Modal INfrastructure Analytics** — a privacy-first traffic sensor.
A Raspberry Pi counts nine road-user classes on-device and publishes only the counts to a
public map of Dublin. No image or video is stored or uploaded.

Research prototype, UCD Spatial Dynamics Lab. No unit is deployed on a street yet; the plan
is in [`.planning/PLAN.md`](.planning/PLAN.md), current status in
[`.planning/STATE.md`](.planning/STATE.md).

## How it works

```
Pi camera → YOLO11n (NCNN) → tracker → 15-min counts → HTTPS → dashboard
```

- **Detector:** the 9-class YOLO11n from the TRA 2026 paper (classes below). FP32 and FP16
  NCNN exports in [`models/`](models/), provenance in each folder's `PROVENANCE.md`.
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

Edge (Python 3.10+):

```bash
git clone https://github.com/tamagusko/camina.git && cd camina
uv venv && uv pip install -r requirements.txt pytest
uv run pytest
```

Running the sensor on a Raspberry Pi 5: [docs/raspberry_pi_5.md](docs/raspberry_pi_5.md).

Dashboard, with mock data (Node 20.11+):

```bash
scripts/run_dashboard.sh    # → http://localhost:3000/dublin
```

## Repository

| Path | Contents |
|---|---|
| `src/camina/` | Edge daemon: tracker, counters, offline buffer, publisher |
| `dashboard/` | Next.js dashboard and ingest API |
| `models/` | CAMINAv1 NCNN models |
| `custom_model_train/` | Training pipeline |
| `configs/` | Sensor and class configuration |
| `deploy/` | systemd unit |
| `docs/` | Deployment, protocol, simulation, training |

## Docs

- [Raspberry Pi 5 setup](docs/raspberry_pi_5.md) and [sensor deployment details](docs/sensor_deployment.md)
- [Simulation mode](docs/simulation.md)
- [Training](docs/training_plan.md) and [evaluation](docs/evaluation_plan.md)
- [Contributing and branches](CONTRIBUTING.md)

## License

- **Code:** [MIT](LICENSE).
- **Models:** [AGPL-3.0](models/LICENSE) — everything in `models/`, plus
  `custom_model_train/yolo11n.pt`. They were trained and exported with
  [Ultralytics YOLO](https://github.com/ultralytics/ultralytics), which is AGPL-3.0 and declares
  that licence for the models it produces (stated in each NCNN export's `metadata.yaml`).

The edge software loads these models through the `ultralytics` package, so a distributed build
of the sensor software must comply with AGPL-3.0. The dashboard does not use Ultralytics.
