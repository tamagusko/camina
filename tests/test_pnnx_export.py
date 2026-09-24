"""Unit tests for `training.pnnx_export` (TorchScript -> NCNN via pnnx, runtime smoke test).

Why this module exists: the 9-class CAMINAv1 weights survive only as the
TorchScript intermediate on `origin/TRA2026` (no `.pt`), and pnnx releases are
not interchangeable — the pnnx bundled with the installed Ultralytics emits a
graph that segfaults inside NCNN's forward pass, while pnnx 20250924
reproduces the shipped FP32 export byte for byte (2026-09-24).
"""

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

from training import pnnx_export

TRA2026_METADATA = {
    "description": "Ultralytics YOLO11n model trained on datasetV3_stratified",
    "date": "2025-09-25T22:03:35.355222",
    "version": "8.3.200",
    "stride": 32,
    "task": "detect",
    "batch": 1,
    "imgsz": [640, 640],
    "names": {
        "0": "SUV",
        "1": "bus",
        "2": "car",
        "3": "cyclist",
        "4": "delivery_van",
        "5": "e-scooter",
        "6": "motorcycle",
        "7": "person",
        "8": "truck",
    },
    "args": {"batch": 1, "half": False},
}


def _fake_torchscript(path: Path, metadata: dict = TRA2026_METADATA) -> Path:
    """A zip laid out like an Ultralytics TorchScript file (metadata in extra/config.txt)."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("best/extra/config.txt", json.dumps(metadata))
        z.writestr("best/data.pkl", b"")
    return path


def _fake_pnnx(returncode: int = 0):
    """Stand-in for subprocess.run that writes the ncnn files pnnx would write."""
    calls: list[list[str]] = []

    def run(cmd, **kwargs):
        calls.append(list(cmd))
        if returncode == 0:
            args = dict(a.split("=", 1) for a in cmd[2:] if "=" in a)
            Path(args["ncnnparam"]).write_text("7767517\n")
            Path(args["ncnnbin"]).write_bytes(b"\x00" * 8)
        return subprocess.CompletedProcess(cmd, returncode, "", "pnnx log")

    return run, calls


# ---------- read_torchscript_metadata ----------


def test_reads_the_metadata_ultralytics_embeds(tmp_path: Path) -> None:
    meta = pnnx_export.read_torchscript_metadata(_fake_torchscript(tmp_path / "best.torchscript"))

    assert meta["imgsz"] == [640, 640]
    assert meta["names"]["6"] == "motorcycle"


def test_a_torchscript_without_metadata_is_rejected(tmp_path: Path) -> None:
    bare = tmp_path / "bare.torchscript"
    with zipfile.ZipFile(bare, "w") as z:
        z.writestr("bare/data.pkl", b"")

    with pytest.raises(ValueError, match=r"config\.txt"):
        pnnx_export.read_torchscript_metadata(bare)


# ---------- export_torchscript ----------


def test_fp16_export_passes_fp16_and_the_input_shape_to_pnnx(tmp_path: Path) -> None:
    ts = _fake_torchscript(tmp_path / "best.torchscript")
    run, calls = _fake_pnnx()

    pnnx_export.export_torchscript(
        ts,
        tmp_path / "out_fp16_ncnn_model",
        imgsz=640,
        half=True,
        pnnx=Path("/opt/pnnx"),
        runner=run,
    )

    cmd = calls[0]
    assert cmd[0] == "/opt/pnnx" and cmd[1] == str(ts)
    assert "fp16=1" in cmd
    assert "inputshape=[1,3,640,640]" in cmd


def test_metadata_records_half_and_integer_class_keys(tmp_path: Path) -> None:
    ts = _fake_torchscript(tmp_path / "best.torchscript")
    run, _ = _fake_pnnx()
    target = tmp_path / "out_fp16_ncnn_model"

    pnnx_export.export_torchscript(
        ts, target, imgsz=640, half=True, pnnx=Path("/opt/pnnx"), runner=run
    )

    meta = yaml.safe_load((target / "metadata.yaml").read_text())
    assert meta["args"]["half"] is True
    assert meta["names"][6] == "motorcycle"  # int keys, as Ultralytics writes them
    assert meta["date"] == TRA2026_METADATA["date"]  # provenance survives
    assert sorted(p.name for p in target.iterdir()) == [
        "metadata.yaml",
        "model.ncnn.bin",
        "model.ncnn.param",
    ]


def test_pnnx_failure_is_raised_not_swallowed(tmp_path: Path) -> None:
    ts = _fake_torchscript(tmp_path / "best.torchscript")
    run, _ = _fake_pnnx(returncode=1)

    with pytest.raises(RuntimeError, match="pnnx"):
        pnnx_export.export_torchscript(
            ts, tmp_path / "x_ncnn_model", imgsz=640, half=True, pnnx=Path("/opt/pnnx"), runner=run
        )


# ---------- smoke_test ----------


def _model_dir(tmp_path: Path) -> Path:
    d = tmp_path / "m_ncnn_model"
    d.mkdir()
    (d / "metadata.yaml").write_text(yaml.safe_dump({"imgsz": [640, 640]}))
    return d


def test_smoke_test_catches_a_segfaulting_model(tmp_path: Path) -> None:
    def segfault(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, -11, "", "")

    with pytest.raises(RuntimeError, match="crash"):
        pnnx_export.smoke_test(_model_dir(tmp_path), runner=segfault)


def test_smoke_test_rejects_non_finite_output(tmp_path: Path) -> None:
    def nan_output(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 3, "ret=0 shape=(13, 8400) finite=False", "")

    with pytest.raises(RuntimeError, match="finite=False"):
        pnnx_export.smoke_test(_model_dir(tmp_path), runner=nan_output)


def test_smoke_test_passes_a_healthy_model(tmp_path: Path) -> None:
    seen = {}

    def ok(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "ret=0 shape=(13, 8400) finite=True", "")

    pnnx_export.smoke_test(_model_dir(tmp_path), runner=ok)

    assert "640" in seen["cmd"][-1], "smoke input size must come from metadata.yaml"
