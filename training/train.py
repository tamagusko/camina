"""Train a detector for one experiment: build its dataset, train, record everything.

Two modes:

- **dev** (default): train on train, validate on val every epoch, early-stop, keep the
  best epoch. Use it to compare experiments (``python -m training.evaluate``).
- **final** (``--final``): once an experiment is chosen, retrain it on train + val for
  the dev run's best number of epochs, with validation off; the test split stays
  untouched, so its score is still honest. This is the model to put on the Pi.

    python -m training.train --experiment training/experiments/yolo26n_tra2026.yaml
    python -m training.train --experiment training/experiments/yolo26n_tra2026.yaml --final

Runs in the GPU environment (``training/requirements.txt``). Output, per run:

    runs/datasets/<name>[_final]/        the assembled dataset and its manifest.json
    runs/train/<name>[_final]/           Ultralytics output; weights/best.pt
    runs/train/<name>[_final]/run.json   mode, parameters, best epoch (dev), git commit,
                                         library versions, GPU, dataset manifest

Then compare runs with ``python -m training.evaluate``.
"""

from __future__ import annotations

import argparse
import csv
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


def final_params(params: dict, dev: dict) -> dict:
    """Parameters for final training: the dev run's best epoch count, validation off.

    Raises:
        ValueError: when the dev run was trained with other parameters (its best
            epoch would not transfer).
    """
    if dev["params"] != params:
        raise ValueError("the dev run used other parameters; re-run it in dev mode first")
    return params | {"epochs": dev["best_epoch"], "val": False}


def train(exp: Experiment, final: bool = False) -> Path:
    """Build the dataset, train, and write ``run.json``; returns the run directory."""
    from ultralytics import YOLO, __version__

    if exp.synthetic is not None and not (exp.synthetic / "data.yaml").exists():
        raise FileNotFoundError(f"synthetic dataset not found: {exp.synthetic}/data.yaml")
    name, params, val_fraction = exp.name, dict(exp.params), 0.1
    if final:
        dev = json.loads((RUNS / "train" / exp.name / "run.json").read_text())
        name, params, val_fraction = f"{exp.name}_final", final_params(params, dev), 0.0
    manifest = build_dataset(
        exp.real,
        RUNS / "datasets" / name,
        DEFAULT_HOLDOUT,
        exp.synthetic,
        exp.syn_fraction,
        seed=exp.params.get("seed", 42),
        val_fraction=val_fraction,
    )
    model = YOLO(params.pop("model"))
    model.train(
        data=str(RUNS / "datasets" / name / "data.yaml"),
        project=str((RUNS / "train").resolve()),
        name=name,
        exist_ok=False,
        **params,
    )
    run = RUNS / "train" / name
    record = _record(exp, manifest, __version__) | {"mode": "final" if final else "dev"}
    if not final:
        record["best_epoch"] = best_epoch(run / "results.csv")
    (run / "run.json").write_text(json.dumps(record, indent=2))
    logger.info("Done: %s", run / "weights" / "best.pt")
    return run


def best_epoch(results_csv: Path) -> int:
    """The epoch best.pt comes from: the first with the highest mAP50-95.

    That is Ultralytics' fitness for detection (8.4); the saved weights no longer
    record the epoch, so it is read from the per-epoch ``results.csv``.
    """
    rows = list(csv.DictReader(results_csv.read_text().splitlines()))
    scores = [float(r["metrics/mAP50-95(B)"]) for r in rows]
    return int(rows[scores.index(max(scores))]["epoch"])


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
    ap.add_argument("--final", action="store_true", help="train + val, dev run's best epochs")
    args = ap.parse_args()
    train(load_experiment(args.experiment), final=args.final)


if __name__ == "__main__":
    main()
