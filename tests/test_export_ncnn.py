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


@pytest.fixture(autouse=True)
def _smoke_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fakes write placeholder bytes, so stub the runtime smoke test."""
    mod = importlib.import_module("src.utils.export_ncnn")
    monkeypatch.setattr(mod, "smoke_test", lambda model_dir: None)


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

    rc = mod.main(["--source", str(source), "--out-dir", str(tmp_path), "--no-half"])
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

    fake_yolo, _ = _fake_yolo(["person", "BAD_CLASS"])  # Only 2 entries, mismatch.
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    with pytest.raises(SystemExit) as exc:
        mod.main(["--source", str(source), "--out-dir", str(tmp_path), "--force"])
    assert exc.value.code != 0


# ---------- FP16 export path (Pi 4 / storage-halved deployment) ----------

# The TRA 2026 weights export their names alphabetically. `detect_track.py`
# remaps them onto the canonical order BY NAME (S1), so the export guard must
# accept this order too — otherwise the shipped model cannot be re-exported.
TRA2026_MODEL_NAMES = [
    "SUV",
    "bus",
    "car",
    "cyclist",
    "delivery_van",
    "e-scooter",
    "motorcycle",
    "person",
    "truck",
]


def _fake_yolo(names: list[str]):
    """A YOLO stand-in that writes ``<weights-dir>/<stem>_ncnn_model/``.

    That is where Ultralytics puts an NCNN export — next to the weights file it
    loaded, not in any output directory we ask for. Reproducing that here is what
    makes the "FP16 must not clobber FP32" test meaningful.

    Returns ``(fake_yolo_class, fake_model)``.
    """
    fake_model = MagicMock()
    fake_model.names = dict(enumerate(names))
    loaded: dict[str, Path] = {}

    def _load(path, *args, **kwargs):
        loaded["path"] = Path(path)
        return fake_model

    def _export(**kwargs):
        src = loaded["path"]
        produced = src.parent / f"{src.stem}_ncnn_model"
        produced.mkdir(parents=True, exist_ok=True)
        (produced / "model.ncnn.bin").write_bytes(b"\x00")
        (produced / "model.ncnn.param").write_text("7767517\n")
        return str(produced)

    fake_model.export.side_effect = _export
    return MagicMock(side_effect=_load), fake_model


def test_no_half_exports_fp32(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--no-half` must be expressible so the FP32 reference model stays reproducible."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    fake_yolo, fake_model = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    rc = mod.main(["--source", str(source), "--out-dir", str(tmp_path), "--no-half"])

    assert rc == 0
    assert fake_model.export.call_args.kwargs["half"] is False


def test_half_is_the_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FP16 is the deployment default; it halves the .bin for the Pi."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    fake_yolo, fake_model = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    rc = mod.main(["--source", str(source), "--out-dir", str(tmp_path)])

    assert rc == 0
    assert fake_model.export.call_args.kwargs["half"] is True


def test_default_imgsz_is_the_deployment_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The export default must be the 640 contract enforced by detect_track.py."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    fake_yolo, fake_model = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    mod.main(["--source", str(source), "--out-dir", str(tmp_path)])

    assert fake_model.export.call_args.kwargs["imgsz"] == 640


def test_fp16_lands_beside_the_fp32_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An FP16 export must not overwrite the FP32 model; both ship side by side."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    fp32_dir = tmp_path / "weights_ncnn_model"
    fp32_dir.mkdir()
    (fp32_dir / "model.ncnn.bin").write_bytes(b"fp32-sentinel")

    fake_yolo, _ = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    rc = mod.main(["--source", str(source), "--out-dir", str(tmp_path), "--half"])

    assert rc == 0
    fp16_dir = tmp_path / "weights_fp16_ncnn_model"
    assert fp16_dir.is_dir(), "FP16 export must go to its own *_fp16_ncnn_model dir"
    assert (fp32_dir / "model.ncnn.bin").read_bytes() == b"fp32-sentinel"


def test_alphabetical_export_order_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shipped TRA 2026 name order must pass the guard: the runtime remaps by name."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    fake_yolo, _ = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    rc = mod.main(["--source", str(source), "--out-dir", str(tmp_path), "--force"])

    assert rc == 0


# ---------- Runtime smoke test and TorchScript sources (2026-09-24) ----------

def test_a_model_that_crashes_at_runtime_fails_the_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Size and taxonomy checks passed on models that segfault; only running them catches it."""
    mod = importlib.import_module("src.utils.export_ncnn")
    source = tmp_path / "weights.pt"
    source.write_bytes(b"")
    fake_yolo, _ = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    def crash(model_dir):
        raise RuntimeError("NCNN forward pass crashed (signal 11)")

    monkeypatch.setattr(mod, "smoke_test", crash)

    with pytest.raises(SystemExit, match="crashed"):
        mod.main(["--source", str(source), "--out-dir", str(tmp_path)])


def _torchscript(tmp_path: Path, imgsz: int = 640) -> Path:
    import json
    import zipfile

    ts = tmp_path / "best.torchscript"
    meta = {"imgsz": [imgsz, imgsz], "names": {str(i): n for i, n in enumerate(TRA2026_MODEL_NAMES)},
            "args": {"batch": 1, "half": False}}
    with zipfile.ZipFile(ts, "w") as z:
        z.writestr("best/extra/config.txt", json.dumps(meta))
    return ts


def test_torchscript_source_requires_an_explicit_pnnx(tmp_path: Path) -> None:
    """pnnx releases are not interchangeable, so there is no silent default."""
    mod = importlib.import_module("src.utils.export_ncnn")

    with pytest.raises(SystemExit, match="--pnnx"):
        mod.main(["--source", str(_torchscript(tmp_path)), "--out-dir", str(tmp_path)])


def test_torchscript_source_enforces_its_embedded_imgsz(tmp_path: Path) -> None:
    mod = importlib.import_module("src.utils.export_ncnn")
    ts = _torchscript(tmp_path, imgsz=640)

    with pytest.raises(SystemExit, match="imgsz"):
        mod.main(["--source", str(ts), "--out-dir", str(tmp_path), "--pnnx", "/opt/pnnx", "--imgsz", "480"])


def test_torchscript_source_exports_through_pnnx_not_ultralytics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = importlib.import_module("src.utils.export_ncnn")
    ts = _torchscript(tmp_path)
    seen = {}

    def fake_export(source, target_dir, *, imgsz, half, pnnx):
        seen.update(source=source, target=target_dir, imgsz=imgsz, half=half, pnnx=pnnx)
        target_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "export_torchscript", fake_export)
    fake_yolo, fake_model = _fake_yolo(TRA2026_MODEL_NAMES)
    monkeypatch.setattr(mod, "YOLO", fake_yolo)

    rc = mod.main(["--source", str(ts), "--out-dir", str(tmp_path), "--pnnx", "/opt/pnnx"])

    assert rc == 0
    assert seen["target"] == tmp_path / "best_fp16_ncnn_model"
    assert (seen["imgsz"], seen["half"], seen["pnnx"]) == (640, True, Path("/opt/pnnx"))
    fake_model.export.assert_not_called()
