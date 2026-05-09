"""Production composition factory for the SensorDaemon.

Wires the picamera2 frame source + YOLO NCNN detector + custom Kalman
tracker + ``DaemonConfig`` into a ready-to-start ``SensorDaemon``. Both the
camera and the detector/tracker stage are accepted as factory callables so
CI and developer macOS hosts can substitute fakes without ever importing
``picamera2`` or ``ultralytics``.

Used from two entry points:

- ``scripts/run_sensor.py`` — the production CLI (plan 01-01 Task 3).
- ``src.camina.service.sensor_daemon.main`` — preserved for the existing
  systemd unit (``deploy/systemd/camina-sensor.service``); both paths
  resolve to the same composition logic to avoid divergence.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable, Iterator

import numpy as np

from src.camina.service.camera import picamera2_frame_source
from src.camina.service.detect_track import make_detect_and_track
from src.camina.service.sensor_daemon import DaemonConfig, SensorDaemon


logger = logging.getLogger(__name__)


# ---------- Public API ----------


def compose(
    cfg: DaemonConfig,
    ncnn_model_path: Path,
    imgsz: int = 480,
    conf: float = 0.3,
    *,
    camera_factory: Callable[[int], Iterator[np.ndarray]] = picamera2_frame_source,
    detect_factory: Callable[..., Callable[[np.ndarray], Iterable[tuple[str, str]]]] = make_detect_and_track,
) -> SensorDaemon:
    """Compose a production ``SensorDaemon`` from config + NCNN model.

    Args:
        cfg: Parsed ``DaemonConfig`` (see ``DaemonConfig.from_yaml``).
        ncnn_model_path: Directory holding the exported NCNN model
            (``models/<stem>_ncnn_model/`` from ``src.utils.export_ncnn``).
        imgsz: Square inference size used by both YOLO and the camera.
            Must equal the value used at NCNN export time.
        conf: Confidence threshold below which detections are dropped
            before the tracker.
        camera_factory: Callable building the frame-source iterable. The
            default ``picamera2_frame_source`` is Pi-only; CI tests inject
            in-memory generators.
        detect_factory: Callable building the ``detect_and_track`` closure.
            Receives ``ncnn_model_path``, ``classes``, ``imgsz``, ``conf``
            as kwargs. CI tests inject a no-op returning ``[]`` per frame.

    Returns:
        A configured ``SensorDaemon``. The caller is responsible for
        invoking ``.start()`` (or ``.stop()`` for cleanup in tests).
    """
    logger.info(
        "Composing daemon for sensor_id=%s with ncnn=%s imgsz=%d conf=%.2f",
        cfg.sensor_id, ncnn_model_path, imgsz, conf,
    )
    frame_source = camera_factory(imgsz)
    detect_and_track = detect_factory(
        ncnn_model_path=ncnn_model_path,
        classes=cfg.classes,
        imgsz=imgsz,
        conf=conf,
    )
    return SensorDaemon(
        config=cfg,
        frame_source=frame_source,
        detect_and_track=detect_and_track,
    )


__all__ = ["compose"]
