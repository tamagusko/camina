"""Tests for training experiment configs.

An experiment names its data (real, optionally synthetic) and may override the
base training config; everything else comes from the base, so two experiments
that differ only in data are trained identically.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from training.train import load_experiment

REPO = Path(__file__).resolve().parents[1]


def _write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data))
    return path


def test_an_experiment_inherits_the_base_and_applies_overrides(tmp_path: Path) -> None:
    base = _write(tmp_path / "base.yaml", {"model": "yolo26n.pt", "epochs": 200, "batch": 32})
    exp = _write(
        tmp_path / "exp.yaml",
        {"name": "quick", "base": str(base), "data": {"real": "r"}, "train": {"epochs": 3}},
    )

    e = load_experiment(exp)

    assert e.name == "quick"
    assert e.params == {"model": "yolo26n.pt", "epochs": 3, "batch": 32}
    assert e.real == Path("r") and e.synthetic is None and e.syn_fraction is None


def test_an_override_the_base_does_not_know_is_rejected(tmp_path: Path) -> None:
    base = _write(tmp_path / "base.yaml", {"epochs": 200})
    exp = _write(
        tmp_path / "exp.yaml",
        {"name": "x", "base": str(base), "data": {"real": "r"}, "train": {"epoch": 3}},
    )

    with pytest.raises(ValueError, match="epoch"):
        load_experiment(exp)


def test_the_two_committed_experiments_differ_only_in_data() -> None:
    real = load_experiment(REPO / "training/experiments/yolo26n_tra2026.yaml")
    syn = load_experiment(REPO / "training/experiments/yolo26n_tra2026_synthetic.yaml")

    assert real.params == syn.params
    assert real.real == syn.real
    assert real.synthetic is None and syn.synthetic is not None
