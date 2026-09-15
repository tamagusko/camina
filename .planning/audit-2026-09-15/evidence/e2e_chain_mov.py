"""Throwaway end-to-end chain probe for the CAMINA audit (scratch only).

Run from the repo root with the scratch venv:
    PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python <scratch>/e2e_chain.py

Establishes which links of camera -> detect -> track -> count -> daily ->
outbox -> publish -> config-poll -> LoRa encode actually connect. Never touches
the network: the HTTP backend is an httpx.MockTransport that mimics the
dashboard counts route response (echoes the payload's config_version).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path("/home/tamagusko/repos/camina")
SCRATCH = Path(__file__).resolve().parent
OUT = SCRATCH / "e2e_out"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO))

results: dict[str, dict] = {}


def record(link: str, ok: bool, detail: str) -> None:
    results[link] = {"ok": ok, "detail": detail}
    print(f"[{'OK ' if ok else 'BRK'}] {link}: {detail}")


# ---------------------------------------------------------------- config
from src.camina.service.sensor_daemon import DaemonConfig  # noqa: E402

cfg = DaemonConfig.from_yaml(REPO / "configs" / "sensor.yaml")
record("L0 config load", True, f"sensor_id={cfg.sensor_id} classes={len(cfg.classes)} imgsz={cfg.imgsz} ncnn={cfg.ncnn_model_path}")
record("L0b ncnn path exists on dev host", Path(cfg.ncnn_model_path).exists(), str(cfg.ncnn_model_path))

# ---------------------------------------------------------------- camera
from src.camina.service.camera import picamera2_frame_source  # noqa: E402

try:
    next(picamera2_frame_source(cfg.imgsz))
    record("L1 camera capture (picamera2)", True, "frame captured")
except Exception as e:  # expected on x86
    record("L1 camera capture (picamera2)", False, f"{type(e).__name__}: {e}")

# ---------------------------------------------------------------- production detector wiring
from src.camina.service.detect_track import make_detect_and_track  # noqa: E402

for model_dir in ["models/20250629_warmup_best_ncnn_model", "models/yolo11n_ncnn_model", "models/20250629_warmup_best.pt"]:
    try:
        make_detect_and_track(REPO / model_dir, classes=cfg.classes, imgsz=cfg.imgsz, conf=cfg.conf_threshold)
        record(f"L2 make_detect_and_track({model_dir})", True, "closure built")
    except Exception as e:
        record(f"L2 make_detect_and_track({model_dir})", False, f"{type(e).__name__}: {str(e)[:300]}")

# ---------------------------------------------------------------- workaround chain with legacy model
import cv2  # noqa: E402
import httpx  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from ultralytics import YOLO  # noqa: E402

from src.camina.core.counter import DailyAccumulator, WindowedCounter  # noqa: E402
from src.camina.core.tracker import Sort  # noqa: E402
from src.camina.io.config_poller import ConfigPoller  # noqa: E402
from src.camina.io.http_client import HttpClient, RetryPolicy  # noqa: E402
from src.camina.io.https_publisher import HttpsPublisher  # noqa: E402
from src.camina.io.lora_codec import pack, pack_b64, unpack  # noqa: E402
from src.camina.io.offline_buffer import OfflineBuffer  # noqa: E402
from src.camina.io.schemas import HeartbeatPayload  # noqa: E402

aliases = yaml.safe_load((REPO / "custom_model_train" / "class_mapping.yaml").read_text())

bench = {}
for fmt, path in [("pt", "models/20250629_warmup_best.pt"), ("ncnn", "models/20250629_warmup_best_ncnn_model")]:
    try:
        m = YOLO(str(REPO / path), task="detect")
        imgs = sorted((REPO / "custom_model_train" / "test_images").glob("*.jpg"))
        lat = []
        det_total = 0
        for i, p in enumerate(imgs):
            t0 = time.perf_counter()
            r = m(str(p), verbose=False, imgsz=480, conf=cfg.conf_threshold)[0]
            if i > 0:
                lat.append(time.perf_counter() - t0)
            det_total += len(r.boxes)
        bench[fmt] = {"names": m.names, "images": len(imgs), "detections": det_total,
                      "mean_latency_ms_x86": round(1000 * float(np.mean(lat)), 1) if lat else None}
        record(f"L2b raw YOLO inference ({fmt}) on test_images", True, json.dumps(bench[fmt]))
    except Exception as e:
        record(f"L2b raw YOLO inference ({fmt})", False, f"{type(e).__name__}: {str(e)[:300]}")
        traceback.print_exc()

model = YOLO(str(REPO / "models/20250629_warmup_best.pt"), task="detect")
legacy_to_canon = {i: aliases[n] for i, n in model.names.items()}
trackers = {c: Sort() for c in cfg.classes}

cap = cv2.VideoCapture(str(REPO / "tests" / "test.mov"))
counter = WindowedCounter(classes=cfg.classes, window_seconds=900)
frames, yielded, tracked_pairs = 0, 0, set()
# Synthetic clock inside the currently open window so a rollover can be forced.
t_frame = counter.window_start + timedelta(seconds=1)
while frames < 600:
    ok, frame = cap.read()
    if not ok:
        break
    frames += 1
    r = model(frame, verbose=False, imgsz=480, conf=cfg.conf_threshold)[0]
    per = {c: [] for c in cfg.classes}
    for cls_i, conf, box in zip(r.boxes.cls.cpu().numpy().astype(int), r.boxes.conf.cpu().numpy(), r.boxes.xyxy.cpu().numpy()):
        per[legacy_to_canon[int(cls_i)]].append([*box.tolist(), float(conf)])
    for c, dets in per.items():
        arr = np.asarray(dets, dtype=float) if dets else np.empty((0, 5))
        for row in trackers[c].update(arr):
            tid = f"{c}-{int(row[4])}"
            counter.add(track_id=tid, class_name=c, now=t_frame)
            tracked_pairs.add(tid)
            yielded += 1
cap.release()
record("L3 tracking (Sort per class) on test_video.mp4", yielded > 0,
       f"frames={frames} track_yields={yielded} unique_tracks={len(tracked_pairs)}")

snap = counter.maybe_rollover(counter.window_end + timedelta(seconds=1))
record("L4 WindowedCounter rollover", snap is not None and snap.total() > 0,
       f"counts={snap.counts if snap else None} partial={snap.partial if snap else None}")

daily = DailyAccumulator(db_path=OUT / "state.db", classes=cfg.classes)
daily.add_window(snap)
dsnap = daily.maybe_rollover(snap.window_start + timedelta(days=1))
record("L5 DailyAccumulator add+rollover", dsnap is not None, f"{dsnap}")

# Mock backend mimicking dashboard counts/daily/heartbeat route response + config route.
captured: list[dict] = []
server_state = {"fail": False}


def handler(req: httpx.Request) -> httpx.Response:
    if server_state["fail"]:
        raise httpx.ConnectError("simulated outage", request=req)
    if req.method == "GET" and req.url.path.endswith("/config"):
        captured.append({"path": req.url.path, "method": "GET"})
        return httpx.Response(200, json={"config_version": "v2", "publish_interval_minutes": 15,
                                         "heartbeat_interval_minutes": 5, "daily_publish_time_utc": "00:00",
                                         "detection_zone": None, "frame_skip": 5, "min_track_hits": 3})
    body = json.loads(req.content)
    captured.append({"path": req.url.path, "method": req.method, "headers": {k: v for k, v in req.headers.items() if k.lower() in ("authorization", "idempotency-key", "content-type")}, "body": body})
    # dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts:47 echoes payload config_version
    return httpx.Response(200, json={"ok": True, "latest_config_version": body.get("config_version")})


client = HttpClient(cfg.api_base_url, token="tok", retry=RetryPolicy(max_attempts=1, base_delay_s=0, max_delay_s=0, jitter=0),
                    transport=httpx.MockTransport(handler))
outbox = OfflineBuffer(db_path=OUT / "outbox.db", max_rows=100)
pub = HttpsPublisher(sensor_id=cfg.sensor_id, http_client=client, outbox=outbox)
applied = []
poller = ConfigPoller(sensor_id=cfg.sensor_id, http_client=client, current_version="", apply=applied.append)

res = pub.post_counts(snap, config_version=poller.current_version, fw_version=cfg.fw_version)
if res.latest_config_version:
    poller.check(res.latest_config_version)
record("L6 HTTPS publish counts (mock transport)", res.delivered, f"url={captured[0]['path'] if captured else None} latest_config_version={res.latest_config_version!r}")
res_d = pub.post_daily(dsnap, config_version=poller.current_version, fw_version=cfg.fw_version)
hb = HeartbeatPayload(sensor_id=cfg.sensor_id, uptime_s=10, cpu_temp_c=None, last_window_end=snap.window_end,
                      config_version=poller.current_version, fw_version=cfg.fw_version)
res_h = pub.post_heartbeat(hb)
record("L6b publish daily + heartbeat", res_d.delivered and res_h.delivered, f"daily={res_d.delivered} hb={res_h.delivered}")
record("L7 ConfigPoller triggered by server response", len(applied) > 0,
       f"applied={len(applied)}; server echoes client config_version so latest==current -> never fetches /config")

server_state["fail"] = True
res_off = pub.post_counts(snap, config_version="", fw_version=cfg.fw_version)
stats_off = outbox.stats()
server_state["fail"] = False
res_back = pub.post_counts(snap, config_version="", fw_version=cfg.fw_version)
record("L8 offline buffer enqueue + drain", res_off.buffered and outbox.stats().pending == 0,
       f"buffered={res_off.buffered} pending_during_outage={stats_off.pending} pending_after={outbox.stats().pending}")

# LoRa encode from the same snapshot.
epoch = int(snap.window_start.timestamp())
try:
    pack(cfg.sensor_id, epoch, snap.counts)
    record("L9 LoRa pack with configured sensor_id", True, cfg.sensor_id)
except Exception as e:
    record("L9 LoRa pack with configured sensor_id", False, f"{type(e).__name__}: {e}")
b64 = pack_b64("D01", epoch, snap.counts)
rt = unpack(pack("D01", epoch, snap.counts))
record("L9b LoRa pack/unpack roundtrip with 'D01'", rt.counts == {c: snap.counts.get(c, 0) for c in rt.counts}, f"b64={b64} len={len(b64)}")
record("L9c LoRa encoder called from daemon", False, "no import of src.camina.io.lora_codec outside tests (see grep)")

(OUT / "captured_requests.json").write_text(json.dumps(captured, indent=1, default=str))
(OUT / "lora_frame.json").write_text(json.dumps({"b64": b64, "epoch": epoch, "counts": snap.counts}))
(OUT / "results.json").write_text(json.dumps({"results": results, "bench": {k: {**v, "names": {str(a): b for a, b in v["names"].items()}} for k, v in bench.items()}}, indent=1, default=str))
daily.close(); outbox.close(); client.close()
print("done")
