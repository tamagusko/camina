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

## 6. Production detector/tracker wiring

`src/camina/service/sensor_daemon.py` intentionally accepts the detector
and tracker as callables so it can be exercised in CI without importing
OpenCV / Ultralytics. The production entry point wires them in. Example:

```python
from src.camina.core.tracker import Sort
from src.camina.service.sensor_daemon import DaemonConfig, SensorDaemon
from ultralytics import YOLO
import cv2

def frame_source():
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        yield frame
    cap.release()

def make_detect_and_track(model_path, classes):
    model = YOLO(model_path)
    tracker = Sort()
    class_names = {i: c for i, c in enumerate(classes)}

    def detect_and_track(frame):
        results = model.predict(frame, imgsz=640, conf=0.4, verbose=False)[0]
        dets = []
        for box in results.boxes:
            cls_id = int(box.cls.item())
            if cls_id not in class_names:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            dets.append([x1, y1, x2, y2, float(box.conf.item())])
        for tx1, ty1, tx2, ty2, tid in tracker.update(np.array(dets)) if dets else []:
            yield int(tid), class_names[cls_id]

    return detect_and_track
```

Compose and run:

```python
config = DaemonConfig.from_yaml(Path("/etc/camina/sensor.yaml"))
daemon = SensorDaemon(
    config=config,
    frame_source=frame_source(),
    detect_and_track=make_detect_and_track("yolo11n_ncnn", config.classes),
)
daemon.start()
```

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No events in admin UI | Wrong `api_base_url` / token | Re-provision; check `journalctl` for 401 / 404 |
| Interval change ignored | Old `config_version` still cached | Force refresh via admin "Republish config" |
| Outbox growing unbounded | Backend unreachable > 10 days | Check network; inspect `state.db.outbox.db` |
| Clock warnings in logs | NTP not syncing | `sudo timedatectl set-ntp true` |
| Daemon restart loop | Unrecoverable auth error | Rotate token; redeploy config |
