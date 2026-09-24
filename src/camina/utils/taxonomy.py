"""Class taxonomy loaders: the canonical class list and the label alias table.

Lives in the daemon's helper layer so the sensor can read the taxonomy without
importing ``src.utils.export_ncnn`` (which imports Ultralytics and PyTorch).
The export CLI re-exports these functions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml


def _project_root() -> Path:
    """Return the repo root by walking up until ``configs/classes.yaml`` exists."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs" / "classes.yaml").exists():
            return parent
    raise SystemExit(
        "Could not locate configs/classes.yaml; is the repo layout intact?"
    )


def load_canonical_classes() -> List[str]:
    """Load the canonical class list from ``configs/classes.yaml``, index order."""
    path = _project_root() / "configs" / "classes.yaml"
    with open(path, "r") as f:
        raw: Dict[int, str] = {int(k): v for k, v in yaml.safe_load(f).items()}
    return [raw[i] for i in sorted(raw.keys())]


def load_class_aliases() -> Dict[str, str]:
    """Load the label-name -> canonical-name alias table."""
    path = _project_root() / "custom_model_train" / "class_mapping.yaml"
    with open(path, "r") as f:
        return dict(yaml.safe_load(f))


__all__ = ["load_canonical_classes", "load_class_aliases"]
