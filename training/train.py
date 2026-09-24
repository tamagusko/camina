"""Train a detector for one experiment: build its dataset, train, record everything.

    python -m training.train --experiment training/experiments/yolo26n_real.yaml

Runs in the GPU environment (``training/requirements.txt``). Output, per run:

    runs/datasets/<name>/          the assembled dataset and its manifest.json
    runs/train/<name>/             Ultralytics output; weights/best.pt
    runs/train/<name>/run.json     experiment, resolved parameters, git commit,
                                   library versions, GPU, dataset manifest

Then compare runs with ``python -m training.evaluate``.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from training.build_dataset import DEFAULT_HOLDOUT, build_dataset

logger = logging.getLogger(__name__)

RUNS = Path("runs")


@dataclass(frozen=True)
class Experiment:
    """What to train on, and with which parameters."""

    name: str
    params: dict
    real: Path
    synthetic: Path | None
    syn_fraction: float | None


def load_experiment(path: Path) -> Experiment:
    """Read an experiment file and merge its ``train`` overrides into its base config.

    Raises:
        ValueError: when an override names a parameter the base config lacks
            (a typo would otherwise be silently ignored).
    """
    exp = yaml.safe_load(path.read_text())
    params = yaml.safe_load(Path(exp["base"]).read_text())
    unknown = set(exp.get("train", {})) - set(params)
    if unknown:
        raise ValueError(f"{path}: unknown training parameter(s) {sorted(unknown)}")
    params |= exp.get("train", {})
    data = exp["data"]
    syn = data.get("synthetic")
    return Experiment(
        name=exp["name"],
        params=params,
        real=Path(data["real"]),
        synthetic=Path(syn) if syn else None,
        syn_fraction=data.get("syn_fraction"),
    )


def train(exp: Experiment) -> Path:
    """Build the dataset, train, and write ``run.json``; returns the run directory."""
    from ultralytics import YOLO, __version__

    if exp.synthetic is not None and not (exp.synthetic / "data.yaml").exists():
        raise FileNotFoundError(f"synthetic dataset not found: {exp.synthetic}/data.yaml")
    manifest = build_dataset(
        exp.real,
        RUNS / "datasets" / exp.name,
        DEFAULT_HOLDOUT,
        exp.synthetic,
        exp.syn_fraction,
        seed=exp.params.get("seed", 42),
    )
    params = dict(exp.params)
    model = YOLO(params.pop("model"))
    model.train(
        data=str(RUNS / "datasets" / exp.name / "data.yaml"),
        project=str((RUNS / "train").resolve()),
        name=exp.name,
        exist_ok=False,
        **params,
    )
    run = RUNS / "train" / exp.name
    (run / "run.json").write_text(json.dumps(_record(exp, manifest, __version__), indent=2))
    logger.info("Done: %s", run / "weights" / "best.pt")
    return run


def _record(exp: Experiment, manifest: dict, ultralytics_version: str) -> dict:
    import torch

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return {
        "experiment": exp.name,
        "params": exp.params,
        "git_commit": commit,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics_version,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "dataset": manifest,
    }


def main() -> None:
    """Train the experiment given on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--experiment", type=Path, required=True)
    train(load_experiment(ap.parse_args().experiment))


if __name__ == "__main__":
    main()
