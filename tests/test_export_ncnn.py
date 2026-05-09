"""Unit tests for the NCNN export CLI (`src.utils.export_ncnn`).

The script is a thin wrapper around Ultralytics' `model.export(format="ncnn")`,
plus an idempotency guard, a class-name assertion against the 9-class CAMINAv1
list, and an argparse CLI surface. We exercise the surface here without
actually running an export (which would need GPU + several seconds).
"""
from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest


CAMINAV1_CLASSES = [
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


def test_module_is_importable_and_exposes_main() -> None:
    """`python -m src.utils.export_ncnn` requires the module to import cleanly."""
    mod = importlib.import_module("src.utils.export_ncnn")
    assert hasattr(mod, "main"), "export_ncnn must expose a main() entry point"
    assert mod.CAMINAV1_CLASSES == CAMINAV1_CLASSES


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Argparse `--help` must exit 0 with the documented flags listed."""
    mod = importlib.import_module("src.utils.export_ncnn")
    with pytest.raises(SystemExit) as exc:
        mod.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--source", "--imgsz", "--half", "--force", "--out-dir"):
        assert flag in out, f"missing flag in --help output: {flag}"


def test_missing_source_exits_two() -> None:
    """argparse exits 2 when a required arg is missing."""
    mod = importlib.import_module("src.utils.export_ncnn")
    with pytest.raises(SystemExit) as exc:
        mod.main([])
    assert exc.value.code == 2


def test_idempotent_when_target_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the NCNN model directory already exists and `--force` is absent,
    the script logs a skip message and exits 0 without invoking YOLO export."""
    mod = importlib.import_module("src.utils.export_ncnn")
    # Pre-create a fake source weight + target NCNN dir to simulate "already exported".
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    target_dir = tmp_path / "weights_ncnn_model"
    target_dir.mkdir()

    sentinel = MagicMock()
    monkeypatch.setattr(mod, "YOLO", sentinel)

    rc = mod.main(["--source", str(source), "--out-dir", str(tmp_path)])
    assert rc == 0
    sentinel.assert_not_called()


def test_class_mismatch_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the exported model's `names` does not equal CAMINAV1_CLASSES, the
    script exits non-zero so we never ship a wrong-taxonomy model."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")

    fake_model = MagicMock()
    fake_model.export.return_value = str(tmp_path / "weights_ncnn_model")
    fake_model.names = {0: "person", 1: "BAD_CLASS"}  # Only 2 entries, mismatch.
    fake_yolo = MagicMock(return_value=fake_model)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    with pytest.raises(SystemExit) as exc:
        mod.main(["--source", str(source), "--out-dir", str(tmp_path), "--force"])
    assert exc.value.code != 0
