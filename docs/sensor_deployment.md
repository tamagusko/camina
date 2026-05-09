# Sensor Deployment (RPi5)

Reproducible steps to bring a fresh Raspberry Pi 5 online as a CAMINA edge
sensor. The daemon implements plan 01 (HTTPS ingest, windowed counting,
offline buffer, remote config).

## 1. Prerequisites

- Raspberry Pi 5 (8 GB) running Raspberry Pi OS Bookworm 64-bit.
- Camera connected via CSI or USB (tested with Camera Module 3 and
  standard USB webcams).
- Network (Ethernet or Wi-Fi) reachable to the CAMINA API host.
- NTP enabled (`timedatectl` should show `NTP service: active`).

## 2. Install

```bash
sudo adduser --system --group --home /opt/camina camina
sudo -u camina git clone https://github.com/tamagusko/camina.git /opt/camina
cd /opt/camina
sudo -u camina python3 -m venv venv
sudo -u camina ./venv/bin/pip install -r requirements.txt
```

## 3. Provision

Per-device secrets and identifiers. Replace placeholders from the admin UI.

```bash
sudo install -m 0750 -o camina -g camina -d /etc/camina /var/lib/camina
sudo -u camina cp configs/sensor.yaml /etc/camina/sensor.yaml
sudo -u camina sed -i \
    -e 's/^sensor_id:.*/sensor_id: cam-dub-01/' \
    -e "s|^api_base_url:.*|api_base_url: https://camina.ucd.ie/api/ingest|" \
    -e 's/^api_token:.*/api_token: <paste-from-admin-ui>/' \
    -e 's|^state_db_path:.*|state_db_path: /var/lib/camina/state.db|' \
    /etc/camina/sensor.yaml
```

## 4. Enable the service

```bash
sudo cp deploy/systemd/camina-sensor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now camina-sensor.service
journalctl -u camina-sensor.service -f
```

Expected first-boot log lines:

    Sensor daemon starting for cam-dub-01
    Applied new config version <hash> to sensor cam-dub-01
    HTTPS POST /v1/sensors/cam-dub-01/heartbeat -> 200

## 5. Verify from the admin UI

Within a minute of starting the service, the sensor should:

- Appear in `/admin/sensors` with a green "online" badge.
- Receive a heartbeat record visible in the sensor detail page.
- Accept an interval change from the admin form and reflect the new
  `config_version` in its next heartbeat within one publish interval.

## 6. NCNN model export

The edge daemon runs the fine-tuned 9-class CAMINAv1 model via NCNN (the
ARM64-friendly inference backend). Export once on any host that has the
`.pt` weights and Ultralytics installed; the resulting directory is what
the daemon loads at startup.

```bash
uv run python -m src.utils.export_ncnn \
    --source models/20250629_warmup_best.pt \
    --imgsz 480 --half
```

Produces `models/20250629_warmup_best_ncnn_model/`. Re-run only after
retraining CAMINAv1 (the script is idempotent — it skips re-exporting an
existing target directory unless you pass `--force`). The export verifies
that the model's class taxonomy matches the canonical 9-class list and
exits non-zero on mismatch, so a base `yolo11n.pt` slipped in by mistake
will fail loudly instead of shipping wrong-taxonomy counts.

Copy the exported directory to the Pi at the path referenced by
`configs/sensor.yaml::ncnn_model_path` (default
`/opt/camina/models/20250629_warmup_best_ncnn_model`).

## 7. Running the daemon

The production entry point is `scripts/run_sensor.py`. It composes the
picamera2 RGB888 frame source, the fine-tuned 9-class CAMINAv1 NCNN
detector, and the existing custom Kalman+Hungarian tracker into the
`SensorDaemon` and starts the main loop.

```bash
# Manual smoke (no systemd) — composes the daemon, verifies wiring, exits 0.
uv run python scripts/run_sensor.py --config configs/sensor.yaml --dry-run

# Full run
uv run python scripts/run_sensor.py --config configs/sensor.yaml
```

The systemd unit in `deploy/systemd/camina-sensor.service` continues to
invoke `python -m src.camina.service.sensor_daemon --config /etc/camina/sensor.yaml`
for backwards compatibility; both entry points now delegate to the same
`compose()` factory in `src/camina/service/compose.py`, so they cannot
diverge.

### macOS / non-Pi development

`picamera2` is Pi-only (it depends on `libcamera`). On a Mac dev host the
daemon's main loop will fail at `picam2 = Picamera2()` with a
`RuntimeError`. For local development:

- Use `--dry-run` to verify the wiring graph, NCNN model loading, and
  YAML parsing without ever capturing a frame.
- For full inference smoke runs with a video file, swap in a custom
  camera factory via `src.camina.service.compose.compose(...,
  camera_factory=...)`. Plan 01-02 lands a `bench_sensor.py` driver
  that demonstrates this pattern with `cv2.VideoCapture` against a
  test clip.

## Troubleshooting (appendix)

This appendix sits outside the numbered sequence so future plans (01-02
benchmark §8/§9/§9b, 01-03 USB SSD §10, 01-04 48-h soak §11) can append
without renumbering.

| Symptom | Likely cause | Fix |
|---|---|---|
| No events in admin UI | Wrong `api_base_url` / token | Re-provision; check `journalctl` for 401 / 404 |
| Interval change ignored | Old `config_version` still cached | Force refresh via admin "Republish config" |
| Outbox growing unbounded | Backend unreachable > 10 days | Check network; inspect `state.db.outbox.db` |
| Clock warnings in logs | NTP not syncing | `sudo timedatectl set-ntp true` |
| Daemon restart loop | Unrecoverable auth error | Rotate token; redeploy config |
| `--dry-run` works on Mac, full run does not | picamera2 unavailable on macOS | Expected; see §7 dev notes — use `--dry-run` or inject a video-file camera factory |
| Class mismatch on startup | Wrong `.pt` weights exported | Re-run `src.utils.export_ncnn` against the fine-tuned `models/20250629_warmup_best.pt` |
