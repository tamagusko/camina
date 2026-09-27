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
    from camina.service.sensor_daemon import DaemonConfig

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
    from camina.service.compose import compose
    from camina.service.sensor_daemon import SensorDaemon

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
    from camina.service.compose import compose

    cfg = _make_cfg(tmp_path)

    def _exploding_detect_factory(**_kwargs):
        raise ValueError(f"Model classes ['person', 'WRONG'] do not match config {CLASSES}")

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
    from camina.service.compose import compose

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
    from camina.service.sensor_daemon import DaemonConfig

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


def test_daemon_config_defaults_to_canonical_model_at_640(tmp_path: Path) -> None:
    """Without explicit NCNN fields, the config points at the 9-class TRA 2026
    export and the size it was exported at (640), not the 6-class warm-up
    model at 480."""
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(
        "sensor_id: cam-yaml-02\napi_base_url: https://api.test\napi_token: t\n"
        "classes: [person, cyclist, car, e-scooter, SUV, motorcyclist, bus, "
        "delivery_van, truck]\n"
    )
    cfg = DaemonConfig.from_yaml(yaml_path)

    # Ultralytics only recognises an NCNN export by the ``_ncnn_model`` suffix.
    assert cfg.ncnn_model_path == Path("models/camina_v1_yolo11n_ncnn_model")
    assert cfg.imgsz == 640


_MINIMAL_YAML = (
    "sensor_id: cam-yaml-03\napi_base_url: https://api.test\napi_token: t\n"
    "classes: [person, cyclist, car, e-scooter, SUV, motorcyclist, bus, "
    "delivery_van, truck]\n"
)


def test_daemon_config_reads_the_screenline(tmp_path: Path) -> None:
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML + "screenline: [[0.65, 0.1], [0.65, 0.9]]\nmin_move: 2\n")
    cfg = DaemonConfig.from_yaml(yaml_path)

    assert cfg.screenline == ((0.65, 0.1), (0.65, 0.9))
    assert cfg.min_move == pytest.approx(2.0)


def test_daemon_config_counts_on_movement_by_default(tmp_path: Path) -> None:
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML)
    cfg = DaemonConfig.from_yaml(yaml_path)

    assert cfg.screenline is None and cfg.min_move == pytest.approx(1.0)


def test_compose_gives_the_detector_a_count_gate_from_config(tmp_path: Path) -> None:
    """The daemon always counts through a gate: static tracks never reach the counter."""
    from dataclasses import replace

    from camina.core.counting import CountGate, Screenline
    from camina.service.compose import compose

    cfg = replace(_make_cfg(tmp_path), screenline=((0.5, 0.0), (0.5, 1.0)), min_move=1.5)
    captured: dict = {}

    def _capturing_detect_factory(**kwargs):
        captured.update(kwargs)
        return lambda _f: []

    daemon = compose(
        cfg,
        ncnn_model_path=tmp_path / "the_ncnn_dir",
        camera_factory=_fake_camera_factory,
        detect_factory=_capturing_detect_factory,
    )
    try:
        gate = captured["gate"]
        assert isinstance(gate, CountGate)
        assert gate.screenline == Screenline((0.5, 0.0), (0.5, 1.0))
        assert gate.min_move == pytest.approx(1.5)
    finally:
        daemon._outbox.close()
        daemon._daily.close()
        daemon._http.close()


def test_daemon_config_reads_the_tracking_rules(tmp_path: Path) -> None:
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML + "max_occlusion_s: 3.5\nmin_class_hits: 4\nrelink: true\n")
    cfg = DaemonConfig.from_yaml(yaml_path)
    assert cfg.max_occlusion_s == pytest.approx(3.5) and cfg.min_class_hits == 4
    assert cfg.relink is True

    yaml_path.write_text(_MINIMAL_YAML)
    cfg = DaemonConfig.from_yaml(yaml_path)
    assert cfg.max_occlusion_s == pytest.approx(5.0) and cfg.min_class_hits == 3
    assert cfg.relink is False


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("min_class_hits: 0", "min_class_hits"),
        ("min_class_hits: -3", "min_class_hits"),
        ("min_class_hits: 21", "min_class_hits"),
        ("max_occlusion_s: 0", "max_occlusion_s"),
        ("max_occlusion_s: 600", "max_occlusion_s"),
        ('relink: "false"', "relink"),
        ('relink: "no"', "relink"),
    ],
)
def test_daemon_config_rejects_bad_tracking_rules(tmp_path: Path, line: str, key: str) -> None:
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML + line + "\n")
    with pytest.raises(ValueError, match=key):
        DaemonConfig.from_yaml(yaml_path)


def test_local_and_server_tracking_bounds_are_the_same() -> None:
    from pydantic import ValidationError

    from camina.core.tracking_rules import MAX_CLASS_HITS, MAX_OCCLUSION_S_LIMIT
    from camina.io.schemas import SensorConfig

    base = {
        "config_version": "v",
        "publish_interval_minutes": 15,
        "heartbeat_interval_minutes": 5,
        "frame_skip": 1,
        "min_track_hits": 3,
    }
    SensorConfig(**base, max_occlusion_s=MAX_OCCLUSION_S_LIMIT, min_class_hits=MAX_CLASS_HITS)
    with pytest.raises(ValidationError):
        SensorConfig(**base, max_occlusion_s=MAX_OCCLUSION_S_LIMIT + 0.1)
    with pytest.raises(ValidationError):
        SensorConfig(**base, min_class_hits=MAX_CLASS_HITS + 1)


def test_the_shipped_sensor_yaml_sets_the_tracking_rules() -> None:
    from camina.service.sensor_daemon import DaemonConfig

    cfg = DaemonConfig.from_yaml(Path(__file__).parents[1] / "configs" / "sensor.yaml")
    assert cfg.max_occlusion_s == pytest.approx(5.0) and cfg.min_class_hits == 3
    assert cfg.relink is False


def test_compose_passes_the_tracking_rules_and_a_gate_that_outlives_occlusion(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from camina.service.compose import compose

    cfg = replace(_make_cfg(tmp_path), max_occlusion_s=7.0, min_class_hits=5, relink=True)
    captured: dict = {}

    def _capturing_detect_factory(**kwargs):
        captured.update(kwargs)
        return lambda _f: []

    daemon = compose(
        cfg,
        ncnn_model_path=tmp_path / "the_ncnn_dir",
        camera_factory=_fake_camera_factory,
        detect_factory=_capturing_detect_factory,
    )
    try:
        assert captured["max_occlusion_s"] == pytest.approx(7.0)
        assert captured["min_class_hits"] == 5
        assert captured["relink"] is True
        assert captured["gate"].forget_after_s >= 7.0
    finally:
        daemon._outbox.close()
        daemon._daily.close()
        daemon._http.close()


def test_the_heartbeat_defaults_to_15_minutes_for_the_pilot(tmp_path: Path) -> None:
    """15 min keeps the free Neon database asleep between quarter-hours; the goal is 5 min."""
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML)
    assert DaemonConfig.from_yaml(yaml_path).heartbeat_interval_seconds == 900
    shipped = DaemonConfig.from_yaml(Path(__file__).parents[1] / "configs" / "sensor.yaml")
    assert shipped.heartbeat_interval_seconds == 900


# ---------- Speed ----------

_SPEED_YAML = """speed:
  line_a: [[0.30, 0.20], [0.30, 0.90]]
  line_b: [[0.70, 0.20], [0.70, 0.90]]
  distance_m: 18.5
"""


def test_speed_is_off_without_a_speed_block(tmp_path: Path) -> None:
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML)
    assert DaemonConfig.from_yaml(yaml_path).speed is None
    shipped = DaemonConfig.from_yaml(Path(__file__).parents[1] / "configs" / "sensor.yaml")
    assert shipped.speed is None


def test_daemon_config_reads_the_speed_lines(tmp_path: Path) -> None:
    from camina.core.counting import Screenline
    from camina.core.speed import MAX_KMH
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML + _SPEED_YAML)
    speed = DaemonConfig.from_yaml(yaml_path).speed

    assert speed is not None
    assert speed.line_a == Screenline((0.30, 0.20), (0.30, 0.90))
    assert speed.line_b == Screenline((0.70, 0.20), (0.70, 0.90))
    assert speed.distance_m == pytest.approx(18.5)
    assert speed.max_kmh == pytest.approx(MAX_KMH)

    yaml_path.write_text(_MINIMAL_YAML + _SPEED_YAML + "  max_kmh: 80\n")
    assert DaemonConfig.from_yaml(yaml_path).speed.max_kmh == pytest.approx(80.0)


def test_a_speed_block_without_a_distance_is_refused(tmp_path: Path) -> None:
    from camina.service.sensor_daemon import DaemonConfig

    yaml_path = tmp_path / "sensor.yaml"
    yaml_path.write_text(_MINIMAL_YAML + _SPEED_YAML.replace("  distance_m: 18.5\n", ""))
    with pytest.raises(KeyError, match="distance_m"):
        DaemonConfig.from_yaml(yaml_path)


@pytest.mark.parametrize("with_speed", [False, True])
def test_compose_gives_the_detector_a_speed_estimator_only_when_calibrated(
    tmp_path: Path, with_speed: bool
) -> None:
    from dataclasses import replace

    from camina.core.counting import Screenline
    from camina.core.speed import SpeedEstimator, SpeedLines
    from camina.service.compose import compose

    lines = SpeedLines(Screenline((0.3, 0.0), (0.3, 1.0)), Screenline((0.7, 0.0), (0.7, 1.0)), 20.0)
    cfg = replace(_make_cfg(tmp_path), speed=lines if with_speed else None)
    captured: dict = {}

    def _capturing_detect_factory(**kwargs):
        captured.update(kwargs)
        return lambda _f: []

    daemon = compose(
        cfg,
        ncnn_model_path=tmp_path / "the_ncnn_dir",
        camera_factory=_fake_camera_factory,
        detect_factory=_capturing_detect_factory,
    )
    try:
        if with_speed:
            assert isinstance(captured["speed"], SpeedEstimator)
            assert captured["speed"].lines == lines
            assert captured["speed"].forget_after_s >= cfg.max_occlusion_s
        else:
            assert captured["speed"] is None
    finally:
        daemon._outbox.close()
        daemon._daily.close()
        daemon._http.close()
