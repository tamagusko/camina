"""The daemon persists the applied server config and restores it on start.

Fields this firmware cannot apply are rejected with a logged reason, never
silently ignored (plan S3).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from camina.io.schemas import SensorConfig
from camina.service.sensor_daemon import DaemonConfig, SensorDaemon

CLASSES = ["person", "cyclist", "car"]


def _config(**overrides: object) -> SensorConfig:
    data: dict[str, object] = {
        "config_version": "v2",
        "publish_interval_minutes": 5,
        "heartbeat_interval_minutes": 2,
        "daily_publish_time_utc": "00:00",
        "detection_zone": None,
        "frame_skip": 1,
        "min_track_hits": 3,
    }
    data.update(overrides)
    return SensorConfig.model_validate(data)


class _Detector:
    """Stand-in for the detect_and_track closure with its tracker handle."""

    def __init__(self) -> None:
        self.tracker = SimpleNamespace(min_hits=3)

    def __call__(self, _frame: object) -> list:
        return []


def _daemon(tmp_path: Path, detector: object | None = None) -> SensorDaemon:
    cfg = DaemonConfig(
        sensor_id="cam-01",
        api_base_url="https://api.test",
        api_token="t",
        state_db_path=tmp_path / "state.db",
        classes=list(CLASSES),
        fw_version="0.2.0",
    )
    return SensorDaemon(
        config=cfg, frame_source=iter([]), detect_and_track=detector or (lambda _f: [])
    )


def _apply(daemon: SensorDaemon, config: SensorConfig) -> None:
    """What ConfigPoller.check does after a successful fetch."""
    daemon._apply_config(config)
    daemon._persist_config(config.config_version)


def test_applied_config_survives_a_restart(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)
    _apply(daemon, _config(min_track_hits=4))
    daemon.stop()

    state = json.loads((tmp_path / "state.config.json").read_text())
    assert state["config_version"] == "v2"
    assert state["min_track_hits"] == 4

    detector = _Detector()
    restarted = _daemon(tmp_path, detector)
    try:
        assert restarted._poller.current_version == "v2"
        assert restarted._counter.window_seconds == 300
        assert restarted._config.heartbeat_interval_seconds == 120
        assert detector.tracker.min_hits == 4
    finally:
        restarted.stop()


def test_first_boot_has_no_version(tmp_path: Path) -> None:
    daemon = _daemon(tmp_path)
    try:
        assert daemon._poller.current_version == ""
    finally:
        daemon.stop()


def test_corrupt_state_is_ignored_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "state.config.json").write_text("{not json")
    with caplog.at_level(logging.WARNING):
        daemon = _daemon(tmp_path)
    try:
        assert daemon._poller.current_version == ""
        assert "saved config" in caplog.text
    finally:
        daemon.stop()


def test_min_track_hits_is_applied_to_the_tracker(tmp_path: Path) -> None:
    detector = _Detector()
    daemon = _daemon(tmp_path, detector)
    try:
        daemon._apply_config(_config(min_track_hits=6))
        assert detector.tracker.min_hits == 6
    finally:
        daemon.stop()


def test_unsupported_fields_are_rejected_with_a_reason(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    daemon = _daemon(tmp_path)
    try:
        with caplog.at_level(logging.WARNING):
            daemon._apply_config(
                _config(
                    frame_skip=5,
                    detection_zone={"type": "polygon", "points": []},
                    daily_publish_time_utc="02:00",
                )
            )
        assert "frame_skip=5 rejected" in caplog.text
        assert "daily_publish_time_utc=02:00 rejected" in caplog.text
        assert "detection_zone rejected" in caplog.text
        assert "min_track_hits=3 not applied" in caplog.text  # plain lambda: no tracker
        # The supported fields still apply.
        assert daemon._counter.window_seconds == 300

        caplog.clear()
        with caplog.at_level(logging.WARNING):
            daemon._apply_config(_config())
        assert "rejected" not in caplog.text
    finally:
        daemon.stop()
