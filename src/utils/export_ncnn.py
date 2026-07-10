"""One-shot NCNN export script for the fine-tuned 9-class CAMINAv1 YOLO11 model.

Wraps Ultralytics' `model.export(format="ncnn")` with the guards the edge agent
(plan 01-01) depends on:

1. Idempotency — re-running with the same `--source` does not re-export an
   existing NCNN directory unless `--force` is passed. The Pi 5 NCNN export
   takes ~30 s and writes ~7 MB of model files.
2. imgsz contract — the requested `--imgsz` must match the size recorded in the
   weights' provenance sidecar (``models/<stem>.meta.yaml``). For a canonical
   model a mismatch FAILS; for a legacy model (or a missing/`unknown` size) it
   only WARNS, since the true training size cannot be verified. This carries one
   consistent inference size from training config -> export -> runtime
   (``configs/sensor.yaml:imgsz``, ``detect_track.py`` default).
3. Canonical taxonomy guard — the exported model's `names`, after alias mapping
   via ``custom_model_train/class_mapping.yaml``, must equal the canonical
   9-class list in ``configs/classes.yaml`` (the single source of truth). A
   mismatch prints a clear diff and exits non-zero before any bad model ships.
   The legacy 6-class deployed model fails this guard by design (it can express
   only 6 of 9 canonical classes) — see ``models/20250629_warmup_best.meta.yaml``.
4. Logging via `logging.getLogger(__name__)` — never `print`.

Usage::

    uv run python -m src.utils.export_ncnn \\
        --source models/<canonical_9class>.pt \\
        --imgsz 480 --half

Produces ``models/<stem>_ncnn_model/``. See ``docs/sensor_deployment.md §6`` for
the full deployment context and ``docs/training_plan.md`` for the taxonomy /
imgsz contract.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml
from ultralytics import YOLO


logger = logging.getLogger(__name__)


# In-code mirror of ``configs/classes.yaml`` for back-compat and quick reference.
# The export guard loads the YAML at runtime as the authority; a drift between
# the two is caught by ``tests/test_class_taxonomy.py``.
CAMINAV1_CLASSES: list[str] = [
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


# ---------- Public API ----------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the NCNN export CLI.

    Args:
        argv: Optional argv list (mainly for tests). When None, reads from
            ``sys.argv[1:]`` per argparse defaults.

    Returns:
        Process exit code: 0 on success or skipped re-export. Raises
        ``SystemExit`` (non-zero) on an imgsz-contract violation, a taxonomy
        mismatch, a missing source, or an argparse parse error.
    """
    args = _build_parser().parse_args(argv)

    source: Path = args.source
    out_dir: Path = args.out_dir
    target_dir = out_dir / f"{source.stem}_ncnn_model"

    if target_dir.exists() and not args.force:
        logger.info(
            "NCNN model already exists at %s; pass --force to re-export",
            target_dir,
        )
        return 0

    if not source.exists():
        logger.error("Source weights not found: %s", source)
        raise SystemExit(f"Source weights not found: {source}")

    # Guard the imgsz contract BEFORE the expensive export.
    _check_imgsz_contract(source, args.imgsz)

    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    logger.info(
        "Exporting NCNN model from %s (imgsz=%d, half=%s)",
        source, args.imgsz, args.half,
    )
    model = YOLO(str(source))
    export_path = model.export(format="ncnn", half=args.half, imgsz=args.imgsz)
    elapsed = time.monotonic() - started
    logger.info("NCNN export finished in %.1fs -> %s", elapsed, export_path)

    # Verify canonical taxonomy on the exported artefact. Reload to make sure we
    # are reading the on-disk model, not the in-memory PyTorch one.
    exported_model = YOLO(str(export_path))
    names_list = [exported_model.names[i] for i in sorted(exported_model.names.keys())]
    _verify_canonical_taxonomy(names_list)

    logger.info(
        "Class taxonomy verified: %d classes map onto CAMINAv1 canonical order",
        len(names_list),
    )
    return 0


# ---------- Taxonomy loading (decoupled: reads the same YAML SSOT) ----------


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


def _verify_canonical_taxonomy(names_list: Sequence[str]) -> None:
    """Assert ``names_list`` maps exactly onto the canonical taxonomy, in order.

    Args:
        names_list: The exported model's class names, in index order.

    Raises:
        SystemExit: with a clear diff (unmapped / missing / extra / misordered)
            when the mapped names are not exactly the canonical list.
    """
    canonical = load_canonical_classes()
    aliases = load_class_aliases()

    unmapped = [n for n in names_list if n not in aliases]
    if unmapped:
        raise SystemExit(
            f"Class mismatch. Unmapped name(s) {unmapped} — add them to "
            f"custom_model_train/class_mapping.yaml or fix the weights. "
            f"Canonical classes: {canonical}"
        )

    mapped = [aliases[n] for n in names_list]
    if mapped == canonical:
        return

    missing = [c for c in canonical if c not in mapped]
    extra = [c for c in mapped if c not in canonical]
    parts = [
        "Class mismatch.",
        f"Expected canonical {canonical};",
        f"got (after alias mapping) {mapped}.",
    ]
    if missing:
        parts.append(f"Missing canonical classes: {missing}.")
    if extra:
        parts.append(f"Unexpected classes: {extra}.")
    if not missing and not extra:
        parts.append("Classes present but in the wrong order.")
    raise SystemExit(" ".join(parts))


# ---------- imgsz contract ----------


def _load_model_meta(source: Path) -> Optional[Dict]:
    """Load the provenance sidecar ``<source-stem>.meta.yaml`` if present."""
    sidecar = source.with_suffix(".meta.yaml")
    if not sidecar.exists():
        return None
    with open(sidecar, "r") as f:
        return yaml.safe_load(f)


def _check_imgsz_contract(source: Path, requested: int) -> None:
    """Validate the requested imgsz against the weights' provenance sidecar.

    Args:
        source: Path to the ``.pt`` weights file.
        requested: The ``--imgsz`` value passed on the CLI.

    Raises:
        SystemExit: when a canonical model records a concrete imgsz that differs
            from ``requested``. Legacy weights, a missing sidecar, or an
            ``unknown`` recorded size only produce a warning.
    """
    meta = _load_model_meta(source)
    if meta is None:
        logger.warning(
            "No provenance sidecar (%s); cannot verify the imgsz contract for "
            "%s. Proceeding with imgsz=%d — add a sidecar for new weights.",
            source.with_suffix(".meta.yaml").name, source.name, requested,
        )
        return

    recorded = meta.get("imgsz")
    is_canonical = bool(meta.get("canonical", False))

    if recorded is None or recorded == "unknown" or not isinstance(recorded, int):
        logger.warning(
            "Sidecar for %s records imgsz=%r (unverified); proceeding with "
            "imgsz=%d.", source.name, recorded, requested,
        )
        return

    if recorded == requested:
        logger.info("imgsz contract satisfied: requested=%d matches sidecar.", requested)
        return

    if is_canonical:
        raise SystemExit(
            f"imgsz contract violation: --imgsz {requested} does not match the "
            f"sidecar's recorded imgsz {recorded} for canonical model "
            f"{source.name}. Export at the recorded deployment size, or update "
            f"the sidecar if the deployment contract truly changed."
        )

    logger.warning(
        "Legacy weights %s: sidecar imgsz=%d, requested=%d. Proceeding (warn "
        "only for legacy), but note the deployment runs at "
        "configs/sensor.yaml:imgsz.",
        source.name, recorded, requested,
    )


# ---------- Internal ----------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_ncnn",
        description="Export the fine-tuned CAMINAv1 YOLO11 model to NCNN format.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the .pt weights file (e.g. models/20250629_warmup_best.pt).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=480,
        help="Square inference size used at export time (default: 480).",
    )
    parser.add_argument(
        "--half",
        action="store_true",
        default=True,
        help="Export with FP16 weights (default: True; passes half=True to Ultralytics).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-export even if the target NCNN directory already exists.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("models"),
        help="Directory where the *_ncnn_model/ folder is placed (default: models/).",
    )
    return parser


__all__ = [
    "main",
    "CAMINAV1_CLASSES",
    "load_canonical_classes",
    "load_class_aliases",
]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(main())
