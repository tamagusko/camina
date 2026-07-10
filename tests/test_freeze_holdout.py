"""Tests for the frozen held-out set builder (``freeze_holdout.py``).

Verifies that the same seed over the same pooled files produces the same
``manifest_sha256`` (determinism), that re-running is idempotent, and that the
selected pairs are materialised into the ``test`` split with no split overlap.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Dict

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module() -> ModuleType:
    path = REPO_ROOT / "custom_model_train" / "scripts" / "freeze_holdout.py"
    spec = importlib.util.spec_from_file_location("freeze_holdout", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fh = _load_module()


def _make_dataset(root: Path) -> Path:
    """Build a deterministic multi-stratum synthetic YOLO dataset."""
    for split in ("train", "val", "test"):
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)
    # 10 person-only + 10 car+cyclist images across train/val -> two strata.
    for i in range(10):
        stem = f"p{i:03d}"
        (root / "images" / "train" / f"{stem}.jpg").write_bytes(f"img-{stem}".encode())
        (root / "labels" / "train" / f"{stem}.txt").write_text("0 0.5 0.5 0.1 0.2\n")
    for i in range(10):
        stem = f"cc{i:03d}"
        split = "train" if i < 5 else "val"
        (root / "images" / split / f"{stem}.jpg").write_bytes(f"img-{stem}".encode())
        (root / "labels" / split / f"{stem}.txt").write_text(
            "2 0.5 0.5 0.3 0.3\n1 0.4 0.4 0.2 0.2\n"
        )
    data_yaml = root / "data.yaml"
    with open(data_yaml, "w") as f:
        yaml.safe_dump(
            {"path": str(root), "train": "images/train", "val": "images/val", "test": "images/test"},
            f,
        )
    return data_yaml


def _stems_in(dir_path: Path) -> set:
    return {p.stem for p in dir_path.glob("*.jpg")}


def test_same_seed_same_manifest_hash(tmp_path: Path) -> None:
    """Two independent fixtures, same seed -> identical manifest hash."""
    ds_a = _make_dataset(tmp_path / "a")
    ds_b = _make_dataset(tmp_path / "b")

    man_a: Dict[str, object] = fh.freeze_holdout(ds_a, frac=0.15, seed=42)
    man_b: Dict[str, object] = fh.freeze_holdout(ds_b, frac=0.15, seed=42)

    assert man_a["manifest_sha256"] == man_b["manifest_sha256"]
    assert man_a["num_test"] == man_b["num_test"]
    assert man_a["num_pool"] == 20
    # round(0.15*10) per stratum = 2 + 2 = 4 held out.
    assert man_a["num_test"] == 4


def test_different_seed_may_differ_but_size_holds(tmp_path: Path) -> None:
    ds_a = _make_dataset(tmp_path / "a")
    ds_b = _make_dataset(tmp_path / "b")
    man_a = fh.freeze_holdout(ds_a, frac=0.15, seed=1)
    man_b = fh.freeze_holdout(ds_b, frac=0.15, seed=2)
    assert man_a["num_test"] == man_b["num_test"] == 4


def test_idempotent_rerun(tmp_path: Path) -> None:
    """Re-running on the same dataset (test already carved) is a no-op hash-wise."""
    ds = _make_dataset(tmp_path / "a")
    first = fh.freeze_holdout(ds, frac=0.15, seed=42)
    second = fh.freeze_holdout(ds, frac=0.15, seed=42)
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert second["num_test"] == 4


def test_materialised_and_no_overlap(tmp_path: Path) -> None:
    ds = _make_dataset(tmp_path / "a")
    manifest = fh.freeze_holdout(ds, frac=0.15, seed=42)
    root = tmp_path / "a"

    test_stems = _stems_in(root / "images" / "test")
    assert len(test_stems) == manifest["num_test"]
    # No filename appears in more than one split.
    train_stems = _stems_in(root / "images" / "train")
    val_stems = _stems_in(root / "images" / "val")
    assert test_stems.isdisjoint(train_stems)
    assert test_stems.isdisjoint(val_stems)
    # Every record uses dataset-root-relative paths and has an image hash.
    for rec in manifest["test_files"]:  # type: ignore[attr-defined]
        assert rec["image"].startswith("images/test/")
        assert not Path(rec["image"]).is_absolute()
        assert len(rec["image_sha256"]) == 64
