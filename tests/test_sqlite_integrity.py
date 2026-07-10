"""Unit tests for the stdlib-only SQLite integrity check + quarantine (M9)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from src.camina.utils.sqlite_integrity import check_and_recover


def _make_healthy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.execute("INSERT INTO t (a) VALUES (1)")
    conn.commit()
    conn.close()


def test_healthy_db_passes(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_healthy_db(db)
    assert check_and_recover(db) is False
    assert db.exists()  # untouched


def test_missing_db_is_noop(tmp_path: Path) -> None:
    assert check_and_recover(tmp_path / "absent.db") is False


def test_corrupt_db_is_quarantined(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    db.write_bytes(b"this is definitely not a sqlite database" * 8)

    assert check_and_recover(db) is True
    # Original path is cleared so the caller can recreate fresh.
    assert not db.exists()
    quarantined = list(tmp_path.glob("state.db.corrupt.*"))
    assert len(quarantined) == 1


def test_truncated_header_is_quarantined(tmp_path: Path) -> None:
    """A valid DB truncated mid-header (e.g. power cut) is corrupt."""
    db = tmp_path / "state.db"
    _make_healthy_db(db)
    # Keep only the first few bytes of the SQLite header -> unreadable.
    db.write_bytes(db.read_bytes()[:12])

    assert check_and_recover(db) is True
    assert not db.exists()
    assert len(list(tmp_path.glob("state.db.corrupt.*"))) == 1


def test_recreate_after_quarantine_succeeds(tmp_path: Path) -> None:
    """After quarantine the caller can open a fresh DB at the same path."""
    db = tmp_path / "state.db"
    db.write_bytes(b"garbage" * 100)
    assert check_and_recover(db) is True

    _make_healthy_db(db)  # recreate
    assert check_and_recover(db) is False
