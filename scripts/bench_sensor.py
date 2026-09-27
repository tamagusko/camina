#!/usr/bin/env python3
"""Measure end-to-end sensor detection throughput and host telemetry.

Run on a Pi with the camera, or replay a video with ``--video``. The report
contains hardware samples at start, middle, and end. ``throttled`` is the
integer bitmask printed in hexadecimal in the Markdown report; zero is the
pass state. On a laptop, unavailable hardware readings are recorded as null.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import deque
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from camina.core.counting import CountGate, Screenline
from camina.service.camera import picamera2_frame_source
from camina.service.detect_track import make_detect_and_track
from camina.service.sensor_daemon import DaemonConfig
from camina.utils.hardware import read_cpu_temp, read_process_rss_mb, read_throttled

logger = logging.getLogger(__name__)
_FPS_MINIMUM = 5.0


def read_hardware() -> dict[str, float | int | None]:
    """Read current hardware telemetry, returning None for unsupported values."""
    return {
        "cpu_temp_c": read_cpu_temp(),
        "rss_mb": read_process_rss_mb(),
        "throttled": read_throttled(),
    }


def summarize_benchmark(
    frame_times: list[float],
    telemetry_samples: list[dict[str, Any]],
    duration_s: float,
) -> dict[str, Any]:
    """Create the machine-readable benchmark result from elapsed frame times."""
    elapsed = max(duration_s, 0.0)
    instantaneous = 0.0
    if len(frame_times) >= 2:
        delta = frame_times[-1] - frame_times[-2]
        instantaneous = 1 / delta if delta > 0 else 0.0
    elif len(frame_times) == 1 and frame_times[0] > 0:
        instantaneous = 1 / frame_times[0]
    recent = [stamp for stamp in frame_times if stamp >= max(0.0, elapsed - 60.0)]
    rolling_span = min(60.0, elapsed)
    rolling = len(recent) / rolling_span if rolling_span > 0 else 0.0
    fps_samples: list[dict[str, float]] = []
    recent_frames: deque[float] = deque()
    for index, stamp in enumerate(frame_times):
        previous = frame_times[index - 1] if index else None
        delta = stamp - previous if previous is not None else 0.0
        current_instant = 1 / delta if delta > 0 else 0.0
        recent_frames.append(stamp)
        while recent_frames and recent_frames[0] < stamp - 60.0:
            recent_frames.popleft()
        sample_span = min(60.0, stamp)
        current_rolling = len(recent_frames) / sample_span if sample_span > 0 else 0.0
        fps_samples.append(
            {
                "elapsed_s": round(stamp, 3),
                "instantaneous": round(current_instant, 3),
                "rolling_1m": round(current_rolling, 3),
            }
        )
    throttle_values = [sample.get("throttled") for sample in telemetry_samples]
    passed = (
        instantaneous >= _FPS_MINIMUM
        and rolling >= _FPS_MINIMUM
        and len(throttle_values) == 3
        and all(value == 0 for value in throttle_values)
    )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "duration_s": round(elapsed, 3),
        "frames_processed": len(frame_times),
        "fps": {
            "instantaneous": round(instantaneous, 3),
            "rolling_1m": round(rolling, 3),
        },
        "fps_samples": fps_samples,
        "hardware_samples": telemetry_samples,
        "pass_criteria": {
            "fps_minimum": _FPS_MINIMUM,
            "throttled_required": 0,
            "fps_pass": instantaneous >= _FPS_MINIMUM and rolling >= _FPS_MINIMUM,
            "throttled_pass": len(throttle_values) == 3
            and all(value == 0 for value in throttle_values),
            "passed": passed,
        },
    }


def run_benchmark(
    frames: Iterable[Any],
    detect: Callable[[Any], Iterable[Any]],
    duration_s: float,
    telemetry: Callable[[], dict[str, float | int | None]] = read_hardware,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run the supplied frame/detector pipeline for up to ``duration_s``.

    The injectable frame source, detector, telemetry, and clock make this
    function testable without camera hardware, sysfs, or ``vcgencmd``.
    """
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    started = clock()
    telemetry_samples: list[dict[str, Any]] = []

    def sample(phase: str) -> None:
        telemetry_samples.append(
            {"phase": phase, "elapsed_s": round(clock() - started, 3), **telemetry()}
        )

    sample("start")
    middle_sampled = False
    frame_times: list[float] = []
    source = iter(frames)
    while clock() - started < duration_s:
        try:
            item = next(source)
        except StopIteration:
            break
        # The Pi camera yields (frame, capture time), as the daemon expects.
        frame, t = item if isinstance(item, tuple) else (item, None)
        tuple(detect(frame) if t is None else detect(frame, t))
        completed = clock() - started
        frame_times.append(completed)
        if not middle_sampled and completed >= duration_s / 2:
            sample("middle")
            middle_sampled = True
    elapsed = max(0.0, clock() - started)
    if not middle_sampled:
        sample("middle")
    sample("end")
    return summarize_benchmark(frame_times, telemetry_samples, elapsed)


def write_reports(report: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown reports using ``out`` as the shared basename."""
    base = out.with_suffix("") if out.suffix.lower() in {".json", ".md"} else out
    json_path = base.with_suffix(".json")
    markdown_path = base.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = []
    for sample in report["hardware_samples"]:
        throttled = sample["throttled"]
        throttle_text = "unavailable" if throttled is None else f"0x{throttled:x}"
        temp = "unavailable" if sample["cpu_temp_c"] is None else f"{sample['cpu_temp_c']:.1f} °C"
        rss = "unavailable" if sample["rss_mb"] is None else f"{sample['rss_mb']:.2f} MiB"
        rows.append(f"| {sample['phase']} | {temp} | {rss} | {throttle_text} |")
    fps = report["fps"]
    criteria = report["pass_criteria"]
    status = "PASS" if criteria["passed"] else "FAIL"
    markdown = "\n".join(
        [
            "# Sensor pipeline bench report",
            "",
            f"- Created: {report['created_at']}",
            f"- Duration: {report['duration_s']} s",
            f"- Frames processed: {report['frames_processed']}",
            f"- FPS: instantaneous {fps['instantaneous']}, 1-minute rolling {fps['rolling_1m']}",
            f"- Per-frame FPS samples: {len(report['fps_samples'])} (recorded in JSON)",
            f"- Pass criteria: {status} (FPS >= 5 and throttled == 0x0 at all samples)",
            "",
            "## Hardware samples",
            "",
            "| Phase | CPU temperature | Process RSS | vcgencmd get_throttled |",
            "|---|---:|---:|---:|",
            *rows,
            "",
            "Unavailable hardware readings are recorded as null in JSON.",
            "",
        ]
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return json_path, markdown_path


def _video_frames(path: Path) -> Iterable[Any]:
    """Loop an OpenCV video file as frames until the consumer stops."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open video: {path}")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(f"Video contains no readable frames: {path}")
            yield frame
    finally:
        capture.release()


def _pipeline(config_path: Path) -> tuple[Iterable[Any], Callable[[Any], Iterable[Any]]]:
    config = DaemonConfig.from_yaml(config_path)
    gate = CountGate(
        screenline=Screenline(*config.screenline) if config.screenline else None,
        min_move=config.min_move,
        forget_after_s=2 * config.max_occlusion_s,
    )
    detector = make_detect_and_track(
        ncnn_model_path=config.ncnn_model_path,
        classes=config.classes,
        imgsz=config.imgsz,
        conf=config.conf_threshold,
        gate=gate,
        max_occlusion_s=config.max_occlusion_s,
        min_class_hits=config.min_class_hits,
        relink=config.relink,
    )
    return picamera2_frame_source(config.imgsz), detector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--video", type=Path, help="loop a video file instead of reading the Pi camera"
    )
    parser.add_argument(
        "--duration", type=float, default=1800, help="bench duration in seconds (default: 1800)"
    )
    parser.add_argument("--config", type=Path, default=Path("configs/sensor.yaml"))
    parser.add_argument("--out", type=Path, required=True, help="report basename or .json/.md path")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    frames, detector = _pipeline(args.config)
    if args.video is not None:
        frames = _video_frames(args.video)
    report = run_benchmark(frames, detector, args.duration)
    json_path, markdown_path = write_reports(report, args.out)
    logger.info(
        "Wrote bench reports: %s and %s (criteria: %s)",
        json_path,
        markdown_path,
        report["pass_criteria"]["passed"],
    )
    return 0 if report["pass_criteria"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
