"""One-shot NCNN export script for the fine-tuned 9-class CAMINAv1 YOLO11 model.

Wraps Ultralytics' `model.export(format="ncnn")` with three guards that the
edge agent (plan 01-01) depends on:

1. Idempotency — re-running with the same `--source` does not re-export an
   existing NCNN directory unless `--force` is passed. The Pi 5 NCNN export
   takes ~30 s and writes ~7 MB of model files; we don't want to repeat it
   every time `docs/sensor_deployment.md §6` is followed.
2. Class-name assertion — the exported model's `names` attribute must equal
   the canonical 9-class CAMINAv1 list, in order. A mismatch means the wrong
   weights file was passed (e.g. base `yolo11n.pt` instead of the fine-tuned
   `models/20250629_warmup_best.pt`); we exit non-zero before any bad model
   ships to a sensor.
3. Logging via `logging.getLogger(__name__)` — never `print`. The script is
   invoked manually from the deployment runbook, but is also called from CI
   smoke checks; both prefer structured log lines.

Usage::

    uv run python -m src.utils.export_ncnn \\
        --source models/20250629_warmup_best.pt \\
        --imgsz 480 --half

Produces ``models/20250629_warmup_best_ncnn_model/``. See
``docs/sensor_deployment.md §6`` for the full deployment context.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Optional, Sequence

from ultralytics import YOLO


logger = logging.getLogger(__name__)


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
        Process exit code: 0 on success or skipped re-export, non-zero on
        class-name mismatch or argparse parse error (raises SystemExit).
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

    # Verify class taxonomy on the exported artefact. Reload to make sure we
    # are reading the on-disk model, not the in-memory PyTorch one.
    exported_model = YOLO(str(export_path))
    names_list = [exported_model.names[i] for i in sorted(exported_model.names.keys())]
    if names_list != CAMINAV1_CLASSES:
        raise SystemExit(
            f"Class mismatch. Expected {CAMINAV1_CLASSES}, got {names_list}"
        )

    logger.info(
        "Class taxonomy verified: %d classes match CAMINAv1 in order",
        len(CAMINAV1_CLASSES),
    )
    return 0


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


__all__ = ["main", "CAMINAV1_CLASSES"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(main())
