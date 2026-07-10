"""SQLite integrity check + corruption quarantine (stdlib-only).

Runs ``PRAGMA integrity_check`` on a state database before it is opened. If the
file is corrupt (a truncated write after a power cut, a garbage file, etc.) it
is moved aside to ``<name>.corrupt.<epoch>`` so the caller can recreate a fresh
database rather than crash the daemon over an unreadable buffer.

Constraint: this module is **stdlib-only** and must not import ``core/`` or
``io/`` (recorded in ``.planning/STATE.md`` — ``utils/`` stays dependency-free
so it can be reused from any layer without cycles).
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Union


logger = logging.getLogger(__name__)

# WAL/SHM sidecars share the base name; quarantine them alongside the main file
# so a fresh reopen does not resurrect a stale write-ahead log.
_SIDECAR_SUFFIXES = ("-wal", "-shm")


def check_and_recover(db_path: Union[str, Path]) -> bool:
    """Verify a SQLite database and quarantine it if corrupt.

    Args:
        db_path: Path to the SQLite database to check.

    Returns:
        ``True`` if the database was found corrupt and quarantined (recovery
        happened; the caller should recreate a fresh database). ``False`` if
        the database is healthy or does not exist yet.

    Never raises — a corrupt buffer must not crash the daemon on boot.
    """
    path = Path(db_path)
    if not path.exists():
        return False

    if _integrity_ok(path):
        return False

    logger.error(
        "SQLite integrity check failed for %s; quarantining and recreating", path
    )
    _quarantine(path)
    return True


def _integrity_ok(path: Path) -> bool:
    """Return ``True`` iff ``PRAGMA integrity_check`` reports ``ok``.

    A file that is not a database at all raises ``sqlite3.DatabaseError`` on the
    pragma; that is treated as corruption (returns ``False``).
    """
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    return bool(row) and row[0] == "ok"


def _quarantine(path: Path) -> None:
    """Move the corrupt database (and any WAL/SHM sidecars) aside."""
    suffix = f".corrupt.{int(time.time())}"
    targets = [path] + [Path(f"{path}{s}") for s in _SIDECAR_SUFFIXES]
    for target in targets:
        if not target.exists():
            continue
        try:
            target.rename(Path(f"{target}{suffix}"))
        except OSError:
            logger.exception("Failed to quarantine %s", target)


__all__ = ["check_and_recover"]
