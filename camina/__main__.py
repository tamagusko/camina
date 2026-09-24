"""Run the sensor: ``python -m camina --config /etc/camina/sensor.yaml [--dry-run]``.

``--dry-run`` builds everything (config, model, camera, publisher) and exits
without entering the main loop: the post-install check in
``docs/raspberry_pi_5.md``. The systemd unit runs the same command without it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from camina.service.compose import compose
from camina.service.sensor_daemon import DaemonConfig

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Compose the daemon from ``--config`` and run it.

    Returns:
        0 on clean shutdown or a successful dry run, 2 if the config file is
        missing. Wiring errors (e.g. a model/class mismatch) raise.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(prog="python -m camina", description="CAMINA sensor")
    parser.add_argument("--config", type=Path, required=True, help="sensor.yaml")
    parser.add_argument(
        "--dry-run", action="store_true", help="compose everything, then exit without running"
    )
    args = parser.parse_args(argv)

    if not args.config.exists():
        logger.error("Config file not found: %s", args.config)
        return 2
    cfg = DaemonConfig.from_yaml(args.config)
    daemon = compose(
        cfg, ncnn_model_path=cfg.ncnn_model_path, imgsz=cfg.imgsz, conf=cfg.conf_threshold
    )
    if args.dry_run:
        logger.info("Dry run OK: daemon composed for sensor_id=%s", cfg.sensor_id)
        return 0
    daemon.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
