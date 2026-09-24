#!/usr/bin/env python3
"""Benchmark CAMINAv1 on the dev host: inference-only and detect+track.

This is a sanity check on a desktop CPU, not a thermal or Pi benchmark — x86
SIMD is not ARM NEON, so the numbers do not predict Raspberry Pi FPS. Use it
to catch pipeline regressions and to compare configurations on one machine.

Usage:
    uv run python scripts/bench_host.py --video tests/test.mov --frames 300
    uv run python scripts/bench_host.py --images custom_model_train/test_images
"""
from __future__ import annotations

import argparse
import json
import logging
import platform
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

# Run from a clone without installing: make the repo root importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger(__name__)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


def _summarise(name: str, times_ms: list[float]) -> dict:
    return {
        "stage": name,
        "frames": len(times_ms),
        "mean_ms": round(statistics.fmean(times_ms), 2),
        "p50_ms": round(_percentile(times_ms, 50), 2),
        "p95_ms": round(_percentile(times_ms, 95), 2),
        "fps_mean": round(1000.0 / statistics.fmean(times_ms), 2),
    }


def _frames_from_video(path: Path, limit: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    frames = []
    while len(frames) < limit:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        raise SystemExit(f"No frames read from {path}")
    return frames


def _frames_from_images(directory: Path, limit: int) -> list[np.ndarray]:
    paths = sorted(
        p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )[:limit]
    frames = [cv2.imread(str(p)) for p in paths]
    if not frames:
        raise SystemExit(f"No images found in {directory}")
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="models/camina_v1_yolo11n_ncnn_model")
    parser.add_argument("--video", type=Path)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.3)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--json", type=Path, help="write the report here")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.video and not args.images:
        args.video = Path("tests/test.mov")

    from ultralytics import YOLO

    from src.camina.service.detect_track import make_detect_and_track
    from src.camina.utils.config import load_classes

    classes = [v for _, v in sorted(load_classes().items())]
    frames = (
        _frames_from_video(args.video, args.frames)
        if args.video
        else _frames_from_images(args.images, args.frames)
    )
    logger.info("loaded %d frames at imgsz=%d", len(frames), args.imgsz)

    # Stage 1: inference only.
    model = YOLO(args.model, task="detect")
    for frame in frames[: args.warmup]:
        model(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)

    infer_ms, detections = [], Counter()
    for frame in frames:
        start = time.perf_counter()
        result = model(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
        infer_ms.append((time.perf_counter() - start) * 1000.0)
        for cls_idx in result.boxes.cls:
            detections[result.names[int(cls_idx)]] += 1

    # Stage 2: inference + per-class Kalman/Hungarian tracking, as the daemon runs it.
    detect_and_track = make_detect_and_track(
        ncnn_model_path=args.model, classes=classes, imgsz=args.imgsz, conf=args.conf
    )
    track_ms, tracks = [], set()
    for frame in frames:
        start = time.perf_counter()
        emitted = list(detect_and_track(frame))
        track_ms.append((time.perf_counter() - start) * 1000.0)
        tracks.update(track_id for track_id, _ in emitted)

    report = {
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "cpu_count": len(__import__("os").sched_getaffinity(0)),
            "python": platform.python_version(),
        },
        "config": {
            "model": str(args.model),
            "imgsz": args.imgsz,
            "conf": args.conf,
            "source": str(args.video or args.images),
        },
        "stages": [_summarise("inference", infer_ms), _summarise("detect+track", track_ms)],
        "detections_by_class": dict(detections.most_common()),
        "unique_tracks": len(tracks),
    }

    for stage in report["stages"]:
        logger.info(
            "%-13s mean %6.2f ms  p50 %6.2f  p95 %6.2f  -> %5.2f FPS",
            stage["stage"], stage["mean_ms"], stage["p50_ms"], stage["p95_ms"], stage["fps_mean"],
        )
    logger.info("detections: %s", report["detections_by_class"])
    logger.info("unique tracks: %d", report["unique_tracks"])
    logger.info("NOTE: desktop x86 numbers; they do not predict Raspberry Pi FPS.")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        logger.info("wrote %s", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
