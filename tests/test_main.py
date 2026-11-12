"""Tests for the sensor entry point, ``python -m camina``.

``main(argv)`` is called directly; ``compose`` is replaced so no model,
camera or network is touched.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from camina import __main__ as entry


@pytest.fixture(autouse=True)
def _restore_camina_log_level():
    """``main`` sets the ``camina`` logger level; keep it from leaking into other tests."""
    import logging

    camina_logger = logging.getLogger("camina")
    level = camina_logger.level
    yield
    camina_logger.setLevel(level)


def _make_yaml(tmp_path: Path) -> Path:
    """Write a minimal valid sensor.yaml the daemon can parse."""
    yaml_text = """
sensor_id: cam-test-01
api_base_url: https://api.test
api_token: t
state_db_path: STATE_DB
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
fw_version: 0.0.0
ncnn_model_path: NCNN
imgsz: 480
conf_threshold: 0.3
""".replace("STATE_DB", str(tmp_path / "state.db")).replace("NCNN", str(tmp_path / "fake_ncnn"))
    p = tmp_path / "sensor.yaml"
    p.write_text(yaml_text)
    return p


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Argparse ``--help`` exits 0 with both ``--config`` and ``--dry-run``."""
    with pytest.raises(SystemExit) as exc:
        entry.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--config" in out
    assert "--dry-run" in out


def test_dry_run_composes_without_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--dry-run`` constructs the daemon via compose() and exits 0 without
    invoking ``daemon.start()``."""

    fake_daemon = MagicMock()
    captured: dict = {}

    def _fake_compose(cfg, **kwargs):
        captured["cfg_sensor_id"] = cfg.sensor_id
        captured.update(kwargs)
        return fake_daemon

    monkeypatch.setattr(entry, "compose", _fake_compose)

    yaml_path = _make_yaml(tmp_path)
    rc = entry.main(["--config", str(yaml_path), "--dry-run"])
    assert rc == 0
    fake_daemon.start.assert_not_called()
    fake_daemon.stop.assert_called_once()
    assert captured["cfg_sensor_id"] == "cam-test-01"
    assert captured["ncnn_model_path"] == Path(str(tmp_path / "fake_ncnn"))


def test_missing_config_exits_two(tmp_path: Path) -> None:
    """A non-existent ``--config`` path exits with code 2 and logs an error."""
    rc = entry.main(["--config", str(tmp_path / "nope.yaml")])
    assert rc == 2


def test_log_level_sets_the_camina_loggers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--log-level DEBUG`` shows the per-road-user speed lines a calibration
    session needs; the default stays INFO."""
    import logging

    camina_logger = logging.getLogger("camina")
    monkeypatch.setattr(entry, "compose", lambda *_a, **_kw: MagicMock())
    yaml_path = _make_yaml(tmp_path)

    assert entry.main(["--config", str(yaml_path), "--dry-run", "--log-level", "DEBUG"]) == 0
    assert camina_logger.level == logging.DEBUG
    assert entry.main(["--config", str(yaml_path), "--dry-run"]) == 0
    assert camina_logger.level == logging.INFO


def test_full_run_invokes_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``--dry-run``, ``main`` calls ``daemon.start()`` once and
    returns 0."""
    fake_daemon = MagicMock()
    monkeypatch.setattr(entry, "compose", lambda *_a, **_kw: fake_daemon)
    yaml_path = _make_yaml(tmp_path)
    rc = entry.main(["--config", str(yaml_path)])
    assert rc == 0
    fake_daemon.start.assert_called_once()
