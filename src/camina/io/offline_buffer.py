"""SQLite-backed FIFO outbox for ingest messages.

Enqueues serialized payloads when the network / backend is unavailable, and
drains them in first-in-first-out order when a sender becomes available
again. Uses WAL mode so rows survive a power cut. Size-capped to avoid
runaway growth on long outages; oldest rows are dropped beyond the cap and
reflected in ``stats().dropped``.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Callable, Union


logger = logging.getLogger(__name__)


DEFAULT_MAX_ROWS = 10_000
DEFAULT_MAX_ATTEMPTS = 50


class SendOutcome(str, Enum):
    """Tri-state result a sender reports for one outbox item.

    ``SENT``  → delivered; delete the row.
    ``RETRY`` → transient failure (transport error / 5xx / 408/425/429); stop
                draining and preserve FIFO order so we retry later.
    ``DROP``  → permanent rejection (4xx other than 408/425/429); delete the
                row so a poison message cannot wedge the queue forever.
    """

    SENT = "sent"
    RETRY = "retry"
    DROP = "drop"


# Senders may return the tri-state enum or a legacy bool (True→SENT, False→RETRY).
SenderResult = Union[SendOutcome, bool]


def _normalize_outcome(result: SenderResult) -> SendOutcome:
    """Coerce a sender's return value into a :class:`SendOutcome`.

    Preserves backward compatibility with bool-returning senders.
    """
    if result is True:
        return SendOutcome.SENT
    if result is False:
        return SendOutcome.RETRY
    return SendOutcome(result)


@dataclass(frozen=True)
class OutboxItem:
    """A queued message awaiting delivery."""

    id: int
    endpoint: str
    payload: bytes
    enqueued_at: int
    attempts: int


@dataclass(frozen=True)
class OutboxStats:
    pending: int
    dropped: int
    oldest_enqueued_at: int | None
    poisoned: int = 0


class OfflineBuffer:
    """Thread-safe SQLite FIFO outbox.

    Args:
        db_path: Filesystem path to the SQLite database. Created if missing.
        max_rows: Maximum number of pending rows before drop-oldest kicks in.
    """

    _CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS outbox (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint    TEXT NOT NULL,
            payload     BLOB NOT NULL,
            enqueued_at INTEGER NOT NULL,
            attempts    INTEGER NOT NULL DEFAULT 0
        )
    """
    _INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_outbox_enqueued ON outbox(enqueued_at)"

    def __init__(self, db_path: Path, max_rows: int = DEFAULT_MAX_ROWS) -> None:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self._db_path, isolation_level=None, check_same_thread=False
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(self._CREATE_SQL)
        self._conn.execute(self._INDEX_SQL)
        self._max_rows = max_rows
        self._lock = Lock()
        self._dropped: int = 0
        self._poisoned: int = 0

    # ---------- Public API ----------

    def enqueue(self, endpoint: str, payload: bytes) -> int:
        """Add a message to the outbox. Returns the assigned row id.

        If the queue is at capacity, the oldest row is deleted first and
        ``stats().dropped`` is incremented.
        """
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes")
        now = int(time.time())
        with self._lock:
            self._drop_to_cap_locked(reserve=1)
            cursor = self._conn.execute(
                "INSERT INTO outbox (endpoint, payload, enqueued_at) VALUES (?, ?, ?)",
                (endpoint, payload, now),
            )
            return int(cursor.lastrowid)

    def drain(
        self,
        send_fn: Callable[[OutboxItem], SenderResult],
        max_items: int = 50,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> int:
        """Drain up to ``max_items`` from the queue in FIFO order.

        ``send_fn`` is called with each item and reports a :class:`SendOutcome`
        (a legacy ``bool`` is also accepted: ``True``→SENT, ``False``→RETRY):

        - ``SENT``  → the row is deleted and draining continues.
        - ``DROP``  → the row is a poison message (e.g. a permanent 4xx); it is
          deleted and ``stats().poisoned`` is incremented so it cannot wedge
          the FIFO forever. Draining continues.
        - ``RETRY`` → the row's ``attempts`` counter is incremented and draining
          stops, preserving FIFO order so we don't hammer a failing backend.

        Safety valve: any row whose ``attempts`` has reached ``max_attempts`` is
        dropped (counted as poisoned) before ``send_fn`` is called, so a row
        that keeps reporting RETRY cannot block the queue indefinitely.

        Returns the number of successfully sent items.
        """
        if max_items <= 0:
            return 0
        sent = 0
        with self._lock:
            rows = self._peek_locked(max_items)
            for item in rows:
                if item.attempts >= max_attempts:
                    self._delete_locked(item.id)
                    self._poisoned += 1
                    logger.warning(
                        "OfflineBuffer: dropping item %d (%s) after %d attempts "
                        "(safety valve; total poisoned=%d)",
                        item.id, item.endpoint, item.attempts, self._poisoned,
                    )
                    continue
                try:
                    outcome = _normalize_outcome(send_fn(item))
                except Exception:
                    logger.exception("send_fn raised on outbox item %d", item.id)
                    outcome = SendOutcome.RETRY
                if outcome is SendOutcome.SENT:
                    self._delete_locked(item.id)
                    sent += 1
                elif outcome is SendOutcome.DROP:
                    self._delete_locked(item.id)
                    self._poisoned += 1
                    logger.warning(
                        "OfflineBuffer: dropping poison item %d (%s) "
                        "(total poisoned=%d)",
                        item.id, item.endpoint, self._poisoned,
                    )
                else:  # RETRY
                    self._conn.execute(
                        "UPDATE outbox SET attempts = attempts + 1 WHERE id = ?",
                        (item.id,),
                    )
                    break
        return sent

    def peek(self, max_items: int = 1) -> list[OutboxItem]:
        """Return the oldest ``max_items`` rows without removing them."""
        with self._lock:
            return self._peek_locked(max_items)

    def stats(self) -> OutboxStats:
        with self._lock:
            pending = self._conn.execute(
                "SELECT COUNT(*) FROM outbox"
            ).fetchone()[0]
            oldest = self._conn.execute(
                "SELECT MIN(enqueued_at) FROM outbox"
            ).fetchone()[0]
        return OutboxStats(
            pending=int(pending),
            dropped=int(self._dropped),
            oldest_enqueued_at=oldest,
            poisoned=int(self._poisoned),
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------- Internal ----------

    def _peek_locked(self, max_items: int) -> list[OutboxItem]:
        rows = self._conn.execute(
            "SELECT id, endpoint, payload, enqueued_at, attempts FROM outbox "
            "ORDER BY id ASC LIMIT ?",
            (max_items,),
        ).fetchall()
        return [
            OutboxItem(
                id=int(r[0]),
                endpoint=str(r[1]),
                payload=bytes(r[2]),
                enqueued_at=int(r[3]),
                attempts=int(r[4]),
            )
            for r in rows
        ]

    def _delete_locked(self, row_id: int) -> None:
        self._conn.execute("DELETE FROM outbox WHERE id = ?", (row_id,))

    def _drop_to_cap_locked(self, reserve: int) -> None:
        """Ensure ``pending + reserve <= max_rows`` by deleting oldest rows."""
        pending = self._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        need_to_drop = pending + reserve - self._max_rows
        if need_to_drop <= 0:
            return
        self._conn.execute(
            "DELETE FROM outbox WHERE id IN "
            "(SELECT id FROM outbox ORDER BY id ASC LIMIT ?)",
            (need_to_drop,),
        )
        self._dropped += need_to_drop
        logger.warning(
            "OfflineBuffer: dropped %d oldest rows to enforce cap (total dropped=%d)",
            need_to_drop,
            self._dropped,
        )


__all__ = [
    "OfflineBuffer",
    "OutboxItem",
    "OutboxStats",
    "SendOutcome",
    "DEFAULT_MAX_ROWS",
    "DEFAULT_MAX_ATTEMPTS",
]
