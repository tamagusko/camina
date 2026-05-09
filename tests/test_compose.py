"""Unit tests for the SensorDaemon compose factory.

The factory wires ``DaemonConfig`` + a camera frame source + a YOLO/tracker
``detect_and_track`` callable into the existing ``SensorDaemon``. To avoid
loading picamera2 / Ultralytics in CI, both are passed in as factory
callables and replaced with fakes here.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


CLASSES = [
    "person",
    "cyclist",
    "car",
    "e-scooter",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
]


def _make_cfg(tmp_path: Path):
    from src.camina.service.sensor_daemon import DaemonConfig

    return DaemonConfig(
        sensor_id="cam-test-01",
        api_base_url="https://api.test",
        api_token="t",
        state_db_path=tmp_path / "state.db",
        classes=list(CLASSES),
        fw_version="0.0.0",
        publish_interval_seconds=900,
        heartbeat_interval_seconds=300,
    )


def _fake_camera_factory(imgsz: int):
    """Yield a single deterministic frame, then stop."""
    yield np.zeros((imgsz, imgsz, 3), dtype=np.uint8)


def _fake_detect_factory(**_kwargs):
    """Build a no-op detect_and_track that yields nothing per frame."""

    def _f(_frame):
        return []

    return _f


def test_compose_returns_configured_daemon(tmp_path: Path) -> None:
    """Compose returns a SensorDaemon whose internal counter knows the 9
    classes and whose frame source is iterable (not a callable)."""
    from src.camina.service.compose import compose
    from src.camina.service.sensor_daemon import SensorDaemon

    cfg = _make_cfg(tmp_path)
    daemon = compose(
        cfg,
        ncnn_model_path=tmp_path / "fake_ncnn",
        imgsz=480,
        conf=0.3,
        camera_factory=_fake_camera_factory,
        detect_factory=_fake_detect_factory,
    )
    try:
        assert isinstance(daemon, SensorDaemon)
        assert daemon._counter.classes == cfg.classes
        # frame_source is iterated directly by the daemon; must be an iterable,
        # not a callable.
        frames = list(daemon._frame_source)
        assert len(frames) == 1
        assert frames[0].shape == (480, 480, 3)
        assert frames[0].dtype == np.uint8
    finally:
        # Close opened sqlite handles + http client to keep the test sandbox tidy.
        daemon._outbox.close()
        daemon._daily.close()
        daemon._http.close()


def test_compose_propagates_class_mismatch(tmp_path: Path) -> None:
    """If the detect-factory raises ValueError on class-name mismatch, compose
    surfaces it (no swallowing)."""
    from src.camina.service.compose import compose

    cfg = _make_cfg(tmp_path)

    def _exploding_detect_factory(**_kwargs):
        raise ValueError(
            "Model classes ['person', 'WRONG'] do not match config "
            f"{CLASSES}"
        )

    with pytest.raises(ValueError, match="Model classes"):
        compose(
            cfg,
            ncnn_model_path=tmp_path / "fake_ncnn",
            camera_factory=_fake_camera_factory,
            detect_factory=_exploding_detect_factory,
        )


def test_compose_passes_through_tunables(tmp_path: Path) -> None:
    """The detect_factory receives the imgsz/conf/classes/ncnn_model_path
    arguments verbatim, so production code can rely on the wiring."""
    from src.camina.service.compose import compose

    cfg = _make_cfg(tmp_path)
    captured: dict = {}

    def _capturing_detect_factory(**kwargs):
        captured.update(kwargs)
        return lambda _f: []

    daemon = compose(
        cfg,
        ncnn_model_path=tmp_path / "the_ncnn_dir",
        imgsz=320,
        conf=0.42,
        camera_factory=_fake_camera_factory,
        detect_factory=_capturing_detect_factory,
    )
    try:
        assert captured["ncnn_model_path"] == tmp_path / "the_ncnn_dir"
        assert captured["classes"] == CLASSES
        assert captured["imgsz"] == 320
        assert captured["conf"] == pytest.approx(0.42)
    finally:
        daemon._outbox.close()
        daemon._daily.close()
        daemon._http.close()


def test_daemon_config_from_yaml_reads_ncnn_fields(tmp_path: Path) -> None:
    """``DaemonConfig.from_yaml`` reads the new NCNN fields with sensible
    defaults, leaving the existing required fields untouched."""
    from src.camina.service.sensor_daemon import DaemonConfig

    yaml_text = """
sensor_id: cam-yaml-01
api_base_url: https://api.test
api_token: t
state_db_path: /tmp/state.db
classes:
  - person
  - cyclist
  - car
  - e-scooter
  - SUV
  - motorcyclist
  - bus
  - delivery_van
  - truck
fw_version: 1.2.3
ncnn_model_path: /opt/camina/models/CAMINAv1_ncnn_model
imgsz: 480
conf_threshold: 0.4
"""
    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(yaml_text)
    cfg = DaemonConfig.from_yaml(yaml_path)

    assert cfg.sensor_id == "cam-yaml-01"
    assert cfg.classes == CLASSES
    assert cfg.ncnn_model_path == Path("/opt/camina/models/CAMINAv1_ncnn_model")
    assert cfg.imgsz == 480
    assert cfg.conf_threshold == pytest.approx(0.4)
