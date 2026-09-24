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

`sensor.yaml` contains the per-device `api_token` — restrict it to `chmod 640`,
owned by the `camina` service user, so it isn't world-readable:

```bash
sudo chmod 640 /etc/camina/sensor.yaml
sudo chown camina:camina /etc/camina/sensor.yaml
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

The current CAMINAv1 export (TRA 2026 YOLO11n, 640×640) is committed at
`models/camina_v1_yolo11n_ncnn_model/` (provenance in its `PROVENANCE.md`),
so no export step is needed for it. After a retrain, export the new weights:

```bash
uv run python -m src.utils.export_ncnn \
    --source models/<date>_caminav1_best.pt \
    --imgsz 640 --half
```

Produces `models/<date>_caminav1_best_fp16_ncnn_model/`. Re-run only after
retraining CAMINAv1 (the script is idempotent — it skips re-exporting an
existing target directory unless you pass `--force`). The export verifies
that the model's class taxonomy maps onto the canonical 9-class list and
exits non-zero on mismatch, so a base `yolo11n.pt` slipped in by mistake
will fail loudly instead of shipping wrong-taxonomy counts. Export *order*
is not checked: `detect_track.py` remaps model index -> canonical index by
name, which is how the alphabetically-ordered TRA 2026 export is consumed.

### Precision: FP16 or FP32

`--half` (the default) writes FP16 weights to `<stem>_fp16_ncnn_model/`;
`--no-half` writes FP32 to `<stem>_ncnn_model/`. The two directories are
siblings, so both precisions can be built from the same weights and kept
side by side — the FP16 export never overwrites the FP32 reference.

FP16 halves the `.bin` (measured on `yolo11n.pt` at 640: **10.57 MB ->
5.35 MB**), which cuts load time and memory traffic on any Pi. What it does
for *speed* depends on the board:

| Board | Core | FP16 arithmetic | Expect from FP16 |
|---|---|---|---|
| Pi 5 | Cortex-A76 (ARMv8.2-A) | native | smaller model; NCNN already runs FP16 math on this core even from an FP32 file, so the speed gain is usually small |
| Pi 4 | Cortex-A72 (ARMv8.0-A) | **none** | smaller model and less memory traffic only; arithmetic stays FP32 |

Treat FP16 as a size/memory win that is free to take, not as a speed fix.
Neither precision changes detection accuracy meaningfully; **input size
does** — do not drop below the 640 export contract without re-validating
(see `docs/evaluation_plan.md`).

Both precisions of the current model are committed:
`models/camina_v1_yolo11n_ncnn_model/` (FP32) and
`models/camina_v1_yolo11n_fp16_ncnn_model/` (FP16, detection parity in its
`PROVENANCE.md`). Point `configs/sensor.yaml::ncnn_model_path` at whichever
directory you deployed.

**pnnx version matters.** Every export ends with a forward pass in a child
process; a build that crashes there fails the export. The pnnx bundled with the
installed Ultralytics produces such builds for this model, so a `.torchscript`
source must name its converter explicitly (`--pnnx`, release 20250924
validated):

```bash
uv run python -m src.utils.export_ncnn \
    --source camina_v1_yolo11n.torchscript --pnnx <pnnx-20250924>/pnnx
```

Copy the exported directory to the Pi at the path referenced by
`configs/sensor.yaml::ncnn_model_path` (default
`/opt/camina/models/camina_v1_yolo11n_ncnn_model`). The daemon refuses to
start if `configs/sensor.yaml::imgsz` differs from the export size recorded in
the model's `metadata.yaml`.

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

### Service supervision (Type=notify + watchdog)

`camina-sensor.service` runs as `Type=notify` with `WatchdogSec=300`. The
daemon signals `READY=1` once start-up completes (threads up, state opened)
and emits `WATCHDOG=1` keep-alives from its main loop roughly every 60 s. If
the detection loop wedges (camera stall, GIL-locked worker) and no keep-alive
arrives within 300 s, systemd restarts the unit. The unit is also ordered
`After=time-sync.target` so a pre-NTP boot cannot publish clock-skewed
window timestamps.

### State-DB corruption recovery

On start-up the daemon runs `PRAGMA integrity_check` on both state databases
(`state.db` and `state.db.outbox.db`) before opening them. A file corrupted by
an unclean power-off is moved aside to `<name>.corrupt.<epoch>` and recreated
fresh — a bad buffer logs an `ERROR` and self-heals instead of crash-looping
the service. Inspect any `*.corrupt.*` files under `/var/lib/camina` if counts
appear to reset unexpectedly.

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
| Service restarts every ~5 min | Main loop stalled; watchdog fired | Check `journalctl` for a wedged camera/detector; `WatchdogSec=300` restarts a stuck loop by design |
| `*.corrupt.*` file in `/var/lib/camina` | Corrupt state DB quarantined on boot | Expected self-heal after an unclean power-off; remove the quarantined file once inspected |
