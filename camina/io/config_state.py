"""Persist the server config the daemon last applied, next to ``state.db``.

The daemon restores it on start, so a reboot keeps the server's settings and
its ``config_version`` before the first successful connection.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import ValidationError

from camina.io.schemas import SensorConfig

logger = logging.getLogger(__name__)


def config_state_path(state_db_path: Path) -> Path:
    """``state.db`` -> ``state.config.json`` in the same directory."""
    return state_db_path.with_suffix(".config.json")


def load_config_state(path: Path) -> SensorConfig | None:
    """The saved config, or ``None`` on first boot or when the file is unreadable."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Cannot read saved config %s (%s); starting without it", path, exc)
        return None
    try:
        return SensorConfig.model_validate_json(raw)
    except ValidationError as exc:
        logger.warning("Ignoring invalid saved config %s: %s", path, exc)
        return None


def save_config_state(path: Path, config: SensorConfig) -> None:
    """Write atomically: a crash leaves the old file or the new one, never half."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(config.model_dump_json(), encoding="utf-8")
    os.replace(tmp, path)
    logger.info("Persisted config version %s to %s", config.config_version, path)


__all__ = ["config_state_path", "load_config_state", "save_config_state"]
