#!/usr/bin/env python3
"""Data-time label validator for a YOLO 9-class CAMINAv1 dataset (gap G2).

Walks a YOLO dataset described by a ``data.yaml`` and asserts, before any
training run, that:

  * ``data.yaml:names`` resolves exactly onto the canonical 9-class taxonomy
    (via ``class_taxonomy``; single source of truth ``configs/classes.yaml``);
  * every label file parses (each line is ``class cx cy w h``);
  * every class-id is an integer in ``[0, 8]``;
  * every coordinate is a float in ``[0, 1]``.

The interactive ``scripts/data_processing/validate_yolo_labels.py`` viewer does
none of these bound checks and needs a display; this is the headless CI guard.
The export guard (``src/utils/export_ncnn.py``) only covers export time.

Exit code ``0`` on success (with per-class box-count summary), ``1`` on any
violation (with a per-file error report).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import yaml

# Ensure the sibling taxonomy loader resolves whether this module is run
# directly (sys.path[0] == scripts dir) or imported by file path in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from class_taxonomy import (  # noqa: E402
    TaxonomyError,
    assert_canonical_taxonomy,
    load_canonical_classes,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NUM_CLASSES = 9
DEFAULT_SPLITS = ("train", "val", "test")


class LabelValidationError(ValueError):
    """Raised when a dataset fails the data-time label guard."""


def _names_in_order(names: object) -> List[str]:
    """Normalise a ``data.yaml:names`` field (dict or list) to index order."""
    if isinstance(names, dict):
        indices = sorted(int(k) for k in names.keys())
        if indices != list(range(len(indices))):
            raise LabelValidationError(
                f"data.yaml:names indices must be a contiguous 0..N-1 range, got {indices}"
            )
        return [str(names[i]) for i in indices]
    if isinstance(names, (list, tuple)):
        return [str(n) for n in names]
    raise LabelValidationError(f"data.yaml:names must be a dict or list, got {type(names).__name__}")


def validate_data_yaml_names(data_yaml: Path) -> List[str]:
    """Assert ``data.yaml:names`` maps exactly onto the canonical taxonomy.

    Returns:
        The canonical class list (index order).

    Raises:
        LabelValidationError: if names are missing or do not reconcile.
    """
    with open(data_yaml, "r") as f:
        config = yaml.safe_load(f) or {}
    if "names" not in config:
        raise LabelValidationError(f"{data_yaml} has no 'names' field")
    names = _names_in_order(config["names"])
    try:
        assert_canonical_taxonomy(names)
    except TaxonomyError as exc:
        raise LabelValidationError(f"{data_yaml}: {exc}") from exc
    return load_canonical_classes()


def _validate_label_line(line: str) -> Tuple[int, str]:
    """Validate one ``class cx cy w h`` line.

    Returns:
        ``(class_id, "")`` when valid, else ``(-1, reason)``.
    """
    parts = line.split()
    if len(parts) != 5:
        return -1, f"expected 5 fields, got {len(parts)}: {line!r}"
    try:
        class_id = int(parts[0])
    except ValueError:
        return -1, f"class-id is not an integer: {parts[0]!r}"
    if not 0 <= class_id < NUM_CLASSES:
        return -1, f"class-id {class_id} out of range [0, {NUM_CLASSES - 1}]"
    for name, raw in zip(("cx", "cy", "w", "h"), parts[1:5]):
        try:
            value = float(raw)
        except ValueError:
            return -1, f"coordinate {name} is not a float: {raw!r}"
        if not 0.0 <= value <= 1.0:
            return -1, f"coordinate {name}={value} out of range [0, 1]"
    return class_id, ""


def validate_label_file(label_file: Path) -> Tuple[Dict[int, int], List[str]]:
    """Validate a single label file.

    Returns:
        ``(box_counts_by_class, errors)`` — ``errors`` empty when the file is
        clean (an empty file is a valid background image).
    """
    box_counts: Dict[int, int] = {}
    errors: List[str] = []
    with open(label_file, "r") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            class_id, reason = _validate_label_line(line)
            if class_id < 0:
                errors.append(f"line {lineno}: {reason}")
            else:
                box_counts[class_id] = box_counts.get(class_id, 0) + 1
    return box_counts, errors


def validate_dataset(
    data_yaml: Path,
    splits: Sequence[str] = DEFAULT_SPLITS,
) -> Tuple[Dict[int, int], int]:
    """Validate every label file in the dataset's present splits.

    Args:
        data_yaml: Path to the dataset ``data.yaml``.
        splits: Split names to validate (skipped silently if absent).

    Returns:
        ``(total_box_counts_by_class, num_label_files)``.

    Raises:
        LabelValidationError: on names mismatch or any per-file violation.
    """
    canonical = validate_data_yaml_names(data_yaml)
    dataset_root = data_yaml.parent

    total_counts: Dict[int, int] = {i: 0 for i in range(NUM_CLASSES)}
    num_files = 0
    file_errors: Dict[str, List[str]] = {}

    for split in splits:
        label_dir = dataset_root / "labels" / split
        if not label_dir.is_dir():
            continue
        for label_file in sorted(label_dir.glob("*.txt")):
            if label_file.name.endswith(".cache"):
                continue
            num_files += 1
            counts, errors = validate_label_file(label_file)
            if errors:
                rel = label_file.relative_to(dataset_root)
                file_errors[str(rel)] = errors
            for class_id, count in counts.items():
                total_counts[class_id] += count

    if file_errors:
        lines = [f"{len(file_errors)} label file(s) failed validation:"]
        for rel, errors in sorted(file_errors.items()):
            lines.append(f"  {rel}")
            lines.extend(f"    - {err}" for err in errors)
        raise LabelValidationError("\n".join(lines))

    logger.info("Label validation PASSED — %d label files, names == canonical", num_files)
    logger.info("Per-class box counts:")
    for idx, name in enumerate(canonical):
        logger.info("  %d %-13s %d", idx, name, total_counts[idx])
    return total_counts, num_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Headless YOLO 9-class label validator (data-time taxonomy + bounds guard).",
    )
    parser.add_argument(
        "--data",
        required=True,
        type=Path,
        help="Path to the dataset data.yaml.",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=list(DEFAULT_SPLITS),
        help=f"Splits to validate (default: {' '.join(DEFAULT_SPLITS)}).",
    )
    args = parser.parse_args()

    try:
        validate_dataset(args.data, splits=args.splits)
    except (LabelValidationError, FileNotFoundError) as exc:
        logger.error("Label validation FAILED:\n%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
