"""Unit tests for ``scripts/run_sensor.py``.

The script is the production entry point invoked by systemd on the Pi 5
(via ``deploy/systemd/camina-sensor.service``). It composes the daemon
from a YAML config and either starts the main loop or, with ``--dry-run``,
verifies wiring and exits 0 without touching real hardware.

We import the script as a module so we can call ``main(argv)`` directly
without spawning a subprocess.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_sensor.py"


def _load_run_sensor():
    """Import ``scripts/run_sensor.py`` as a module under a stable name."""
    spec = importlib.util.spec_from_file_location("run_sensor", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_sensor"] = mod
    spec.loader.exec_module(mod)
    return mod


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
""".replace("STATE_DB", str(tmp_path / "state.db")).replace(
        "NCNN", str(tmp_path / "fake_ncnn")
    )
    p = tmp_path / "sensor.yaml"
    p.write_text(yaml_text)
    return p


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Argparse ``--help`` exits 0 with both ``--config`` and ``--dry-run``."""
    mod = _load_run_sensor()
    with pytest.raises(SystemExit) as exc:
        mod.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--config" in out
    assert "--dry-run" in out


def test_dry_run_composes_without_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--dry-run`` constructs the daemon via compose() and exits 0 without
    invoking ``daemon.start()``."""
    mod = _load_run_sensor()

    fake_daemon = MagicMock()
    captured: dict = {}

    def _fake_compose(cfg, **kwargs):
        captured["cfg_sensor_id"] = cfg.sensor_id
        captured.update(kwargs)
        return fake_daemon

    monkeypatch.setattr(mod, "compose", _fake_compose)

    yaml_path = _make_yaml(tmp_path)
    rc = mod.main(["--config", str(yaml_path), "--dry-run"])
    assert rc == 0
    fake_daemon.start.assert_not_called()
    assert captured["cfg_sensor_id"] == "cam-test-01"
    assert captured["ncnn_model_path"] == Path(str(tmp_path / "fake_ncnn"))


def test_missing_config_exits_two(tmp_path: Path) -> None:
    """A non-existent ``--config`` path exits with code 2 and logs an error."""
    mod = _load_run_sensor()
    rc = mod.main(["--config", str(tmp_path / "nope.yaml")])
    assert rc == 2


def test_full_run_invokes_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ``--dry-run``, ``main`` calls ``daemon.start()`` once and
    returns 0."""
    mod = _load_run_sensor()
    fake_daemon = MagicMock()
    monkeypatch.setattr(mod, "compose", lambda *_a, **_kw: fake_daemon)
    yaml_path = _make_yaml(tmp_path)
    rc = mod.main(["--config", str(yaml_path)])
    assert rc == 0
    fake_daemon.start.assert_called_once()
