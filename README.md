# CAMINA – Citizen-led Automated Modal INfrastructure Analytics

**CAMINA** is a lightweight, privacy-first, edge-deployable traffic-sensor network. A Raspberry Pi 5 is designed to run the fine-tuned 9-class YOLO11n detector (**CAMINAv1**, NCNN — the TRA 2026 model) with a custom Kalman + Hungarian tracker, aggregating counts into 15-minute windows **on-device** (no image or video ever stored or uploaded), and publishing them over HTTPS to a public dashboard that colour-codes Dublin streets by count and speed. Bringing CAMINAv1 to `main` is `.planning/PLAN.md` S1.

Research at UCD Spatial Dynamics Lab, funded by REALLOCATE (EU grant 101103924). Status and targets: `.planning/STATE.md` (M1 target 2026-12-31).

---

## How it works

```
Pi Camera 3 → YOLO11 NCNN → per-class Kalman/Hungarian tracker
   → WindowedCounter (15-min UTC windows) → DailyAccumulator (SQLite)
   → HttpsPublisher (+ SQLite offline outbox) → dashboard ingest API
   → Neon Postgres → Next.js public map (Dublin)
```

- **Transports:** Wi-Fi/HTTPS (primary). LoRaWAN via TTN exists as a tested prototype (20-byte schema-v2 binary uplink + webhook ingest, `docs/lora.md`) but is not deployed — optional in M2 (`.planning/PLAN.md` D1). Cellular works as HTTPS over a cellular bearer — the edge code is bearer-agnostic, no code change needed.
- **Privacy:** fully edge-processed, counts only; public UI never exposes sensor GPS; k-anonymity floor; right-to-erasure via DB cascade. GDPR-first by design.

## 📁 Directory structure

```
camina/
├── scripts/
│   ├── run_sensor.py           # Production entry point (edge daemon CLI)
│   ├── generate_mock_dublin.py # 8-sensor Dublin simulation fixtures
│   ├── calibrate_camera.py     # Camera calibration (pixels_per_meter)
│   ├── train/                  # Fine-tuning scripts + configs
│   └── data_processing/        # Dataset utilities
├── src/
│   ├── camina/
│   │   ├── core/               # WindowedCounter, DailyAccumulator, tracker
│   │   ├── io/                 # HttpClient, HttpsPublisher, OfflineBuffer, ConfigPoller
│   │   ├── service/            # SensorDaemon, camera, detect_track, compose
│   │   └── utils/              # Config loader, depth calibration
│   └── utils/                  # NCNN export CLI (export_ncnn.py)
├── configs/                    # sensor.yaml (daemon), classes.yaml, main_config.yaml
├── dashboard/                  # Next.js 16 dashboard (pnpm; see dashboard/)
├── deploy/systemd/             # camina-sensor.service unit
├── models/                     # Model weights + NCNN exports (6-class warm-up today; CAMINAv1 in PLAN.md S1)
├── custom_model_train/         # Training pipeline (labeling, training, evaluation)
├── docs/                       # Deployment, simulation, training/eval plans, protocol
├── tests/                      # pytest suite (edge)
├── archive/                    # Legacy code kept for reference (not maintained)
└── .planning/                  # Staged plan, project state, audit
```

## 🔧 Installation (edge)

Python 3.10+, [`uv`](https://docs.astral.sh/uv/) preferred:

```bash
git clone https://github.com/your-username/camina.git
cd camina
uv pip install -r requirements.txt   # or: pip install -r requirements.txt
uv run pytest                        # verify: all tests green
```

### Models

- `models/20250629_warmup_best.pt` (+ NCNN export `models/20250629_warmup_best_ncnn_model/`) is a 6-class warm-up model, not CAMINAv1. The 9-class CAMINAv1 NCNN export (TRA 2026) lives on `origin/TRA2026` until it is brought to `main` (`.planning/PLAN.md` S1).
- Re-export for Pi: `uv run python -m src.utils.export_ncnn --help` (validates the class taxonomy; see `docs/sensor_deployment.md`)
- Base YOLO11n for comparison: `wget -O models/yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`

## 🚀 Usage

Edge daemon (production):

```bash
uv run python scripts/run_sensor.py --config /etc/camina/sensor.yaml   # --dry-run to validate
```

Configuration lives in `configs/sensor.yaml` (sensor ID, API base URL, token, publish interval — dynamic settings are meant to hot-reload via the config poller; the server-side fix is pending, `.planning/PLAN.md` S3). Deployment via systemd: `deploy/systemd/camina-sensor.service`.

Dashboard (see `dashboard/`):

```bash
pnpm -C dashboard install
pnpm -C dashboard dev   # mock mode by default (CAMINA_DATA_SOURCE=live for live)
```

Simulation fixtures (8 Dublin sensors: UCD + city-centre corridor, LoRa/WiFi/cellular mix):

```bash
python scripts/generate_mock_dublin.py   # regenerates data/mock/dublin/; see docs/simulation.md
```

## 🧪 Tests

- Edge: `uv run pytest` (pytest)
- Dashboard: `pnpm -C dashboard exec vitest run` (unit incl. binding privacy-regression test) + Playwright e2e

## 📚 Documentation

- `docs/sensor_deployment.md` — Pi deployment + NCNN export
- `docs/simulation.md` — 8-sensor Dublin simulation mode
- `docs/training_plan.md` / `docs/evaluation_plan.md` — model retraining + per-class evaluation
- `docs/RECONCILIATION.md`, `docs/PROTOCOL.md` — data-integrity design
- `.planning/` — staged plan (`PLAN.md`), project state (`STATE.md`), 2026-09-15 audit
- `archive/` — legacy single-app counter and experiments (unmaintained, kept for reference)

## License

See `LICENSE`.
