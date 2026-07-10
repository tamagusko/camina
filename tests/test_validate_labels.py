"""Tests for the data-time YOLO label validator (``validate_labels.py``).

Covers a passing synthetic dataset plus each violation class the validator
must reject: bad ``data.yaml`` names, out-of-range class-id, out-of-range
coordinate, and an unparseable label line.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Dict, List

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL: List[str] = [
    "person", "cyclist", "car", "e-scooter", "SUV",
    "motorcyclist", "bus", "delivery_van", "truck",
]


def _load_module() -> ModuleType:
    path = REPO_ROOT / "custom_model_train" / "scripts" / "validate_labels.py"
    spec = importlib.util.spec_from_file_location("validate_labels", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vl = _load_module()


def _make_dataset(
    root: Path,
    labels: Dict[str, str],
    names: object = None,
) -> Path:
    """Materialise a tiny YOLO dataset; return its data.yaml path."""
    (root / "images" / "train").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "train").mkdir(parents=True, exist_ok=True)
    for stem, content in labels.items():
        (root / "images" / "train" / f"{stem}.jpg").write_bytes(b"fakejpg")
        (root / "labels" / "train" / f"{stem}.txt").write_text(content)
    if names is None:
        names = {i: n for i, n in enumerate(CANONICAL)}
    data_yaml = root / "data.yaml"
    with open(data_yaml, "w") as f:
        yaml.safe_dump({"path": str(root), "train": "images/train", "nc": 9, "names": names}, f)
    return data_yaml


def test_valid_dataset_passes(tmp_path: Path) -> None:
    data_yaml = _make_dataset(
        tmp_path,
        {
            "a": "0 0.5 0.5 0.1 0.2\n1 0.4 0.4 0.2 0.2\n",
            "b": "2 0.5 0.5 0.3 0.3\n",
            "c": "",  # empty background image is valid
        },
    )
    counts, num_files = vl.validate_dataset(data_yaml, splits=["train"])
    assert num_files == 3
    assert counts[0] == 1 and counts[1] == 1 and counts[2] == 1
    assert sum(counts.values()) == 3
    # CLI entry point returns 0 on success.
    import sys

    sys.argv = ["validate_labels.py", "--data", str(data_yaml), "--splits", "train"]
    assert vl.main() == 0


def test_non_canonical_names_rejected(tmp_path: Path) -> None:
    bad_names = {i: n for i, n in enumerate(CANONICAL)}
    bad_names[0] = "pedestrian_typo"  # not in the alias table
    data_yaml = _make_dataset(tmp_path, {"a": "0 0.5 0.5 0.1 0.2\n"}, names=bad_names)
    with pytest.raises(vl.LabelValidationError):
        vl.validate_dataset(data_yaml, splits=["train"])


def test_class_id_out_of_range_rejected(tmp_path: Path) -> None:
    data_yaml = _make_dataset(tmp_path, {"a": "9 0.5 0.5 0.1 0.2\n"})
    with pytest.raises(vl.LabelValidationError, match="out of range"):
        vl.validate_dataset(data_yaml, splits=["train"])


def test_coord_out_of_range_rejected(tmp_path: Path) -> None:
    data_yaml = _make_dataset(tmp_path, {"a": "0 0.5 1.5 0.1 0.2\n"})
    with pytest.raises(vl.LabelValidationError, match="out of range"):
        vl.validate_dataset(data_yaml, splits=["train"])


def test_unparseable_line_rejected(tmp_path: Path) -> None:
    data_yaml = _make_dataset(tmp_path, {"a": "0 0.5 0.5 0.1\n"})  # only 4 fields
    with pytest.raises(vl.LabelValidationError, match="expected 5 fields"):
        vl.validate_dataset(data_yaml, splits=["train"])


def test_non_integer_class_id_rejected(tmp_path: Path) -> None:
    data_yaml = _make_dataset(tmp_path, {"a": "car 0.5 0.5 0.1 0.2\n"})
    with pytest.raises(vl.LabelValidationError, match="not an integer"):
        vl.validate_dataset(data_yaml, splits=["train"])
