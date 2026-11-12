"""picamera2-backed frame source for the production edge daemon.

EDGE-02 mandates direct RGB888 capture from the Pi Camera Module 3 via
``picamera2``. The OpenCV USB-camera path and OpenCV BGR colour conversion
are explicitly out of scope for the production camera; see EDGE-02 in
``.planning/REQUIREMENTS.md`` for the full rationale. The daemon's main
loop (``camina.service.sensor_daemon.SensorDaemon._main_loop``)
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
import time
from collections.abc import Iterator

import numpy as np

logger = logging.getLogger(__name__)


# ---------- Public API ----------


def picamera2_frame_source(imgsz: int = 480) -> Iterator[tuple[np.ndarray, float]]:
    """Yield RGB888 frames, with their capture times, from the Pi Camera Module 3.

    Args:
        imgsz: Square capture size (e.g. 480). Must match the YOLO NCNN
            input shape configured in ``configs/sensor.yaml``.

    Yields:
        ``(frame, t)``: ``frame`` is a ``numpy.ndarray`` of shape
        ``(imgsz, imgsz, 3)``, dtype ``uint8``, RGB byte order, which the YOLO
        NCNN model accepts directly (no colour conversion). ``t`` is the
        capture time in seconds from libcamera's ``SensorTimestamp`` (start of
        exposure, a monotonic clock), so the tracker and the speed lines see
        when a frame was taken, not when inference got to it. Without that
        metadata, ``time.monotonic()`` right after capture.

    Raises:
        RuntimeError: when ``picamera2``/``libcamera`` are not available
            (typically on non-Pi hosts). Use a file-based or fake frame
            source via the ``compose(..., camera_factory=...)`` injection
            point in CI and on developer macOS hosts.
    """
    try:
        from picamera2 import Picamera2
    except ImportError as e:  # pragma: no cover — Pi-only path
        raise RuntimeError("picamera2 not available; install via apt on Pi OS Bookworm") from e

    picam2 = Picamera2()
    picam2.preview_configuration.main.size = (imgsz, imgsz)
    picam2.preview_configuration.main.format = "RGB888"
    picam2.preview_configuration.align()
    picam2.configure("preview")
    picam2.start()
    logger.info("picamera2 started at %dx%d RGB888", imgsz, imgsz)
    try:
        while True:
            request = picam2.capture_request()
            try:
                frame = request.make_array("main")
                sensor_ns = request.get_metadata().get("SensorTimestamp")
            finally:
                request.release()
            yield frame, (sensor_ns / 1e9 if sensor_ns is not None else time.monotonic())
    finally:
        picam2.stop()
        picam2.close()
        logger.info("picamera2 stopped")


__all__ = ["picamera2_frame_source"]
