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

- **Detector:** the 9-class YOLO11n from the TRA 2026 paper — person, cyclist, car,
  e-scooter, SUV, motorcyclist, bus, delivery van, truck. FP32 and FP16 NCNN exports in
  [`models/`](models/), provenance in each folder's `PROVENANCE.md`.
- **Privacy:** counts only; the public map never shows sensor locations; counts below 5
  are suppressed.

## Quick start

Edge (Python 3.10+):

```bash
git clone https://github.com/tamagusko/camina.git && cd camina
uv venv && uv pip install -r requirements.txt pytest
uv run pytest
```

Running the daemon on a Pi: [docs/sensor_deployment.md](docs/sensor_deployment.md).

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

- [Deploying a sensor](docs/sensor_deployment.md)
- [Simulation mode](docs/simulation.md)
- [Training](docs/training_plan.md) and [evaluation](docs/evaluation_plan.md)
- [Contributing and branches](CONTRIBUTING.md)

## License

Code: [MIT](LICENSE). The models in `models/` were trained and exported with
Ultralytics YOLO and carry its AGPL-3.0 licence (see each `metadata.yaml`).
