"""Canonical CAMINAv1 taxonomy loader for the training toolchain.

Single source of truth for class names lives in ``configs/classes.yaml``; the
alias table (dataset / toolchain label name -> canonical name) lives in
``custom_model_train/class_mapping.yaml``. This module reads both and provides a
loader that FAILS LOUDLY on any unmapped or missing class, so a taxonomy
mismatch can never slip silently into a converted dataset, a training run, or a
metrics table.

Import from the sibling toolchain scripts as ``from class_taxonomy import ...``
(the ``scripts/`` directory is on ``sys.path`` when a script is run directly).
The deployment-side export guard (``src/utils/export_ncnn.py``) reads the same
two YAML files independently to stay decoupled from this training-only package.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)


class TaxonomyError(ValueError):
    """Raised when class names do not reconcile onto the canonical taxonomy."""


def _project_root() -> Path:
    """Return the repo root by walking up until ``configs/`` is found."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs" / "classes.yaml").exists():
            return parent
    raise TaxonomyError(
        "Could not locate configs/classes.yaml from "
        f"{Path(__file__).resolve()}; is the repo layout intact?"
    )


def canonical_classes_path() -> Path:
    return _project_root() / "configs" / "classes.yaml"


def class_mapping_path() -> Path:
    return _project_root() / "custom_model_train" / "class_mapping.yaml"


def load_canonical_classes(path: Optional[Path] = None) -> List[str]:
    """Load the canonical 9-class list, ordered by integer index.

    Args:
        path: Optional override for ``configs/classes.yaml`` (mainly for tests).

    Returns:
        Class names ordered by their integer index (index 0 first).

    Raises:
        TaxonomyError: if indices are not a contiguous ``0..n-1`` range or a
            name is duplicated.
    """
    path = path or canonical_classes_path()
    with open(path, "r") as f:
        raw: Dict[int, str] = {int(k): v for k, v in yaml.safe_load(f).items()}

    expected_indices = set(range(len(raw)))
    if set(raw.keys()) != expected_indices:
        raise TaxonomyError(
            f"{path} indices must be a contiguous 0..{len(raw) - 1} range, "
            f"got {sorted(raw.keys())}"
        )
    names = [raw[i] for i in range(len(raw))]
    if len(set(names)) != len(names):
        raise TaxonomyError(f"{path} contains duplicate class names: {names}")
    return names


def load_class_aliases(path: Optional[Path] = None) -> Dict[str, str]:
    """Load the label-name -> canonical-name alias table.

    Args:
        path: Optional override for ``class_mapping.yaml`` (mainly for tests).

    Returns:
        Mapping of every recognised label name to its canonical name.
    """
    path = path or class_mapping_path()
    with open(path, "r") as f:
        aliases: Dict[str, str] = dict(yaml.safe_load(f))
    return aliases


def resolve_to_canonical(
    model_names: Sequence[str],
    *,
    aliases: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Translate arbitrary label names to canonical names via the alias table.

    Args:
        model_names: Label names in their native order.
        aliases: Optional pre-loaded alias table.

    Returns:
        The canonical names, one per input, in the same order.

    Raises:
        TaxonomyError: if any name is absent from the alias table (never
            silently passed through).
    """
    aliases = aliases if aliases is not None else load_class_aliases()
    unmapped = [n for n in model_names if n not in aliases]
    if unmapped:
        raise TaxonomyError(
            f"Unmapped class name(s) {unmapped}; add them to "
            f"{class_mapping_path()} or fix the dataset labels. "
            f"Known names: {sorted(aliases)}"
        )
    return [aliases[n] for n in model_names]


def assert_canonical_taxonomy(
    model_names: Sequence[str],
    *,
    aliases: Optional[Dict[str, str]] = None,
    canonical: Optional[List[str]] = None,
) -> None:
    """Assert ``model_names`` maps exactly onto the canonical taxonomy, in order.

    Args:
        model_names: Names in model/dataset order.
        aliases: Optional pre-loaded alias table.
        canonical: Optional pre-loaded canonical class list.

    Raises:
        TaxonomyError: with a human-readable diff (missing / extra / misordered
            classes) when the mapped names are not exactly the canonical list.
    """
    canonical = canonical if canonical is not None else load_canonical_classes()
    mapped = resolve_to_canonical(model_names, aliases=aliases)
    if mapped == canonical:
        return

    missing = [c for c in canonical if c not in mapped]
    extra = [c for c in mapped if c not in canonical]
    detail = [
        f"expected {canonical}",
        f"got (after alias mapping) {mapped}",
    ]
    if missing:
        detail.append(f"missing canonical classes: {missing}")
    if extra:
        detail.append(f"unexpected classes: {extra}")
    if not missing and not extra:
        detail.append("classes present but in the wrong order")
    raise TaxonomyError("Taxonomy mismatch — " + "; ".join(detail))


__all__ = [
    "TaxonomyError",
    "load_canonical_classes",
    "load_class_aliases",
    "resolve_to_canonical",
    "assert_canonical_taxonomy",
    "canonical_classes_path",
    "class_mapping_path",
]
