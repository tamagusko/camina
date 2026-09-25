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


# ---------- final mode ----------


def test_final_training_uses_the_dev_runs_best_epoch_and_no_validation() -> None:
    from training.train import final_params

    params = {"epochs": 200, "patience": 40, "batch": 32}
    dev = {"params": params, "best_epoch": 102}

    final = final_params(params, dev)

    assert final["epochs"] == 102 and final["val"] is False
    assert final["batch"] == 32
    assert params["epochs"] == 200  # the experiment's own params are not modified


def test_final_training_refuses_a_dev_run_with_other_parameters() -> None:
    from training.train import final_params

    with pytest.raises(ValueError, match="dev run"):
        final_params(
            {"epochs": 200, "batch": 32}, {"params": {"epochs": 200, "batch": 16}, "best_epoch": 90}
        )


def test_best_epoch_is_the_first_epoch_with_the_highest_map50_95(tmp_path: Path) -> None:
    """Ultralytics keeps best.pt at the first epoch of highest mAP50-95; the saved
    weights no longer say which epoch that was, so results.csv is read instead."""
    from training.train import best_epoch

    csv = tmp_path / "results.csv"
    csv.write_text(
        "epoch,metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "1,0.30,0.20\n2,0.60,0.41\n3,0.70,0.40\n4,0.55,0.41\n"
    )

    assert best_epoch(csv) == 2
