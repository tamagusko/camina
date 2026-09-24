"""Build a ready-to-start ``SensorDaemon`` from its config.

Camera and detector are passed in as factories, so tests (and machines
without a Pi camera) substitute fakes without importing ``picamera2``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import numpy as np

from camina.core.counting import CountGate, Screenline
from camina.service.camera import picamera2_frame_source
from camina.service.detect_track import make_detect_and_track
from camina.service.sensor_daemon import DaemonConfig, SensorDaemon

logger = logging.getLogger(__name__)


# ---------- Public API ----------


def compose(
    cfg: DaemonConfig,
    ncnn_model_path: Path,
    imgsz: int = 640,
    conf: float = 0.3,
    *,
    camera_factory: Callable[[int], Iterator[np.ndarray]] = picamera2_frame_source,
    detect_factory: Callable[
        ..., Callable[[np.ndarray], Iterable[tuple[str, str]]]
    ] = make_detect_and_track,
) -> SensorDaemon:
    """Compose a production ``SensorDaemon`` from config + NCNN model.

    Args:
        cfg: Parsed ``DaemonConfig`` (see ``DaemonConfig.from_yaml``).
        ncnn_model_path: Directory holding the exported NCNN model
            (``models/<stem>_ncnn_model/`` from ``training.export_ncnn``).
        imgsz: Square inference size used by both YOLO and the camera.
            Must equal the value used at NCNN export time.
        conf: Confidence threshold below which detections are dropped
            before the tracker.
        camera_factory: Callable building the frame-source iterable. The
            default ``picamera2_frame_source`` is Pi-only; CI tests inject
            in-memory generators.
        detect_factory: Callable building the ``detect_and_track`` closure.
            Receives ``ncnn_model_path``, ``classes``, ``imgsz``, ``conf`` and
            ``gate`` (a ``CountGate`` built from ``cfg``) as kwargs. CI tests
            inject a no-op returning ``[]`` per frame.

    Returns:
        A configured ``SensorDaemon``. The caller is responsible for
        invoking ``.start()`` (or ``.stop()`` for cleanup in tests).
    """
    logger.info(
        "Composing daemon for sensor_id=%s with ncnn=%s imgsz=%d conf=%.2f",
        cfg.sensor_id,
        ncnn_model_path,
        imgsz,
        conf,
    )
    frame_source = camera_factory(imgsz)
    detect_and_track = detect_factory(
        ncnn_model_path=ncnn_model_path,
        classes=cfg.classes,
        imgsz=imgsz,
        conf=conf,
        gate=CountGate(
            screenline=Screenline(*cfg.screenline) if cfg.screenline else None,
            min_move=cfg.min_move,
        ),
    )
    return SensorDaemon(
        config=cfg,
        frame_source=frame_source,
        detect_and_track=detect_and_track,
    )


__all__ = ["compose"]
