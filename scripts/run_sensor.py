"""Production entry point for the CAMINA edge sensor daemon.

Composes the fine-tuned 9-class CAMINAv1 YOLO11 NCNN detector + custom
Kalman+Hungarian tracker + SensorDaemon, and runs the main loop. Invoked
by ``deploy/systemd/camina-sensor.service`` on the Raspberry Pi 5; also
runnable manually for smoke checks.

Usage::

    # Manual smoke (compose + verify wiring, then exit)
    uv run python scripts/run_sensor.py --config configs/sensor.yaml --dry-run

    # Full run
    uv run python scripts/run_sensor.py --config configs/sensor.yaml

The systemd unit currently invokes
``python -m src.camina.service.sensor_daemon --config /etc/camina/sensor.yaml``;
both entry points delegate to ``src.camina.service.compose.compose`` so they
stay behaviourally identical (plan 01-01 Task 3).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

# Ensure the repo root is on sys.path so ``from src.camina...`` resolves when
# the script is invoked directly (e.g. ``uv run python scripts/run_sensor.py``)
# rather than via ``python -m``. The systemd unit uses the module form and
# does not need this bootstrap, but the documented manual smoke-test command
# does. Insert at index 0 so we win over any conflicting installed package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.camina.service.compose import compose  # noqa: E402
from src.camina.service.sensor_daemon import DaemonConfig  # noqa: E402


logger = logging.getLogger(__name__)


# ---------- Public API ----------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the production sensor daemon.

    Args:
        argv: Optional argv list (mainly for tests). When ``None``, argparse
            reads from ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 on clean shutdown or successful dry-run, 2 if
        the YAML config does not exist. Other failure modes (e.g. NCNN
        class-name mismatch) raise.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv)

    if not args.config.exists():
        logger.error("Config file not found: %s", args.config)
        return 2

    cfg = DaemonConfig.from_yaml(args.config)
    daemon = compose(
        cfg,
        ncnn_model_path=cfg.ncnn_model_path,
        imgsz=cfg.imgsz,
        conf=cfg.conf_threshold,
    )
    if args.dry_run:
        logger.info(
            "Dry run OK: daemon composed for sensor_id=%s", cfg.sensor_id
        )
        return 0

    daemon.start()
    return 0


# ---------- Internal ----------


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CAMINA edge sensor daemon")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to configs/sensor.yaml (or the per-device override "
             "installed at /etc/camina/sensor.yaml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compose the daemon and exit without entering the main loop. "
             "Use this for CI smoke checks and post-install verification.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
