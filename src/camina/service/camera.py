"""picamera2-backed frame source for the production edge daemon.

EDGE-02 mandates direct RGB888 capture from the Pi Camera Module 3 via
``picamera2``. The OpenCV USB-camera path and OpenCV BGR colour conversion
are explicitly out of scope for the production camera; see EDGE-02 in
``.planning/REQUIREMENTS.md`` for the full rationale. The daemon's main
loop (``src.camina.service.sensor_daemon.SensorDaemon._main_loop``)
iterates the returned generator directly, so this module exposes a
generator function rather than a class.

picamera2 is a hard runtime dependency on the Pi but is intentionally absent
from the CI environment (importing it on a non-Linux host raises
``ImportError`` from libcamera). The ``compose`` factory therefore receives
the camera factory as an injection point so tests can substitute an in-memory
frame source without ever importing this module.
"""
from __future__ import annotations

import logging
from typing import Iterator

import numpy as np


logger = logging.getLogger(__name__)


# ---------- Public API ----------


def picamera2_frame_source(imgsz: int = 480) -> Iterator[np.ndarray]:
    """Yield RGB888 frames from the Pi Camera Module 3 via picamera2.

    Args:
        imgsz: Square capture size (e.g. 480). Must match the YOLO NCNN
            input shape configured in ``configs/sensor.yaml``.

    Yields:
        ``numpy.ndarray`` of shape ``(imgsz, imgsz, 3)``, dtype ``uint8``,
        RGB byte order. The downstream YOLO NCNN model accepts this layout
        directly — no colour conversion is required.

    Raises:
        RuntimeError: when ``picamera2``/``libcamera`` are not available
            (typically on non-Pi hosts). Use a file-based or fake frame
            source via the ``compose(..., camera_factory=...)`` injection
            point in CI and on developer macOS hosts.
    """
    try:
        from picamera2 import Picamera2  # noqa: WPS433 — runtime-only import
    except ImportError as e:  # pragma: no cover — Pi-only path
        raise RuntimeError(
            "picamera2 not available; install via apt on Pi OS Bookworm"
        ) from e

    picam2 = Picamera2()
    picam2.preview_configuration.main.size = (imgsz, imgsz)
    picam2.preview_configuration.main.format = "RGB888"
    picam2.preview_configuration.align()
    picam2.configure("preview")
    picam2.start()
    logger.info("picamera2 started at %dx%d RGB888", imgsz, imgsz)
    try:
        while True:
            yield picam2.capture_array()
    finally:
        picam2.stop()
        picam2.close()
        logger.info("picamera2 stopped")


__all__ = ["picamera2_frame_source"]
