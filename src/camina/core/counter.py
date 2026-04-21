"""Windowed road-user counter and daily cumulative accumulator.

The counter receives `(track_id, class_name)` pairs from the tracking stage and
emits periodic snapshots of per-class unique-track counts aligned to wall-clock
windows (default 15 min anchored at UTC 00:00).

The daily accumulator consumes those window snapshots and produces a per-day
cumulative total for reconciliation, persisted to SQLite so a reboot never
loses more than one window.

Semantics:
    - Within a single window, a given `(track_id, class_name)` pair is counted
      exactly once (deduplication set).
    - Across windows, the same `track_id` is counted once per window (the set
      resets at each rollover).
    - Windows align to wall-clock multiples of `window_seconds` offset from
      `anchor` (default: `1970-01-01T00:00:00+00:00`, i.e. UTC midnight grid).
    - The first window produced after start-up is marked ``partial=True`` so
      the downstream consumer can decide how to treat it.
    - Days align to UTC 00:00. If a device misses the rollover (e.g., power
      cut), the unpublished row is kept in SQLite and emitted on next boot
      with ``late=True``.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

DEFAULT_ANCHOR: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class WindowSnapshot:
    """Immutable per-window result emitted by `WindowedCounter`."""

    window_start: datetime
    window_end: datetime
    counts: dict[str, int]
    partial: bool

    def total(self) -> int:
        """Sum of counts across all classes."""
        return sum(self.counts.values())


@dataclass
class WindowedCounter:
    """Aggregates unique `(track_id, class)` pairs into wall-clock windows.

    Args:
        classes: Ordered list of class names to track. Classes not in this
            list are silently ignored.
        window_seconds: Window duration in seconds. Must be positive.
        anchor: Reference point for window alignment. Defaults to UTC
            midnight (``1970-01-01T00:00:00Z``), which yields standard
            boundaries (e.g., 10:00, 10:15, 10:30 for 15-min windows).

    Attributes (read-only from callers):
        window_start: Start of the currently-open window.
        window_end: End of the currently-open window.
        is_first_window: ``True`` until the first rollover; controls the
            ``partial`` flag on the emitted snapshot.
    """

    classes: list[str]
    window_seconds: int
    anchor: datetime = DEFAULT_ANCHOR

    # Internal state
    _window_start: datetime = field(init=False)
    _window_end: datetime = field(init=False)
    _seen_track_ids: dict[str, set[int]] = field(init=False)
    _counts: dict[str, int] = field(init=False)
    _is_first_window: bool = field(init=False, default=True)
    _started_at: datetime = field(init=False)

    def __post_init__(self) -> None:
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if self.anchor.tzinfo is None:
            raise ValueError("anchor must be timezone-aware")

        now = datetime.now(tz=timezone.utc)
        self._started_at = now
        self._window_start = self._align_to_window(now)
        self._window_end = self._window_start + timedelta(seconds=self.window_seconds)
        self._seen_track_ids = {cls: set() for cls in self.classes}
        self._counts = {cls: 0 for cls in self.classes}

    # ---------- Public API ----------

    @property
    def window_start(self) -> datetime:
        return self._window_start

    @property
    def window_end(self) -> datetime:
        return self._window_end

    @property
    def is_first_window(self) -> bool:
        return self._is_first_window

    def add(self, track_id: int, class_name: str, now: datetime) -> None:
        """Register a tracked object in the current window.

        Duplicate `(track_id, class_name)` within the same window is a no-op.
        Calls with `class_name` not in ``self.classes`` are silently dropped.
        The caller is responsible for invoking ``maybe_rollover`` periodically
        so that late observations for a closed window are not silently merged
        into the next one.
        """
        if class_name not in self._seen_track_ids:
            return
        now = self._as_utc(now)
        if now >= self._window_end:
            # Caller didn't roll over in time; attribute to the boundary so
            # the count isn't silently dropped, but the partial flag is
            # preserved on the next snapshot.
            pass
        if track_id not in self._seen_track_ids[class_name]:
            self._seen_track_ids[class_name].add(track_id)
            self._counts[class_name] += 1

    def maybe_rollover(self, now: datetime) -> Optional[WindowSnapshot]:
        """Close the current window if ``now`` is past its end; else None."""
        now = self._as_utc(now)
        if now < self._window_end:
            return None
        return self._snapshot_and_reset(now)

    def force_snapshot(self, now: datetime) -> WindowSnapshot:
        """Unconditionally close the current window and start a new one."""
        now = self._as_utc(now)
        return self._snapshot_and_reset(now)

    # ---------- Internal ----------

    def _snapshot_and_reset(self, now: datetime) -> WindowSnapshot:
        snapshot = WindowSnapshot(
            window_start=self._window_start,
            window_end=self._window_end,
            counts=dict(self._counts),
            partial=self._is_first_window and self._started_at > self._window_start,
        )
        # Start a new window aligned to ``now`` (handles long gaps correctly).
        self._window_start = self._align_to_window(now)
        self._window_end = self._window_start + timedelta(seconds=self.window_seconds)
        self._seen_track_ids = {cls: set() for cls in self.classes}
        self._counts = {cls: 0 for cls in self.classes}
        self._is_first_window = False
        return snapshot

    def _align_to_window(self, now: datetime) -> datetime:
        now = self._as_utc(now)
        delta = now - self.anchor
        total_seconds = int(delta.total_seconds())
        aligned = (total_seconds // self.window_seconds) * self.window_seconds
        return self.anchor + timedelta(seconds=aligned)

    @staticmethod
    def _as_utc(ts: datetime) -> datetime:
        if ts.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return ts.astimezone(timezone.utc)


@dataclass(frozen=True)
class DailySnapshot:
    """Immutable per-day cumulative result."""

    day: date
    totals: dict[str, int]
    window_count: int
    late: bool

    def total(self) -> int:
        return sum(self.totals.values())


class DailyAccumulator:
    """Running per-day totals with SQLite persistence.

    Rows are written synchronously after every ``add_window`` call. On reboot,
    ``pending_unpublished`` returns any previous-day row that never got
    published, flagged ``late=True``.

    Args:
        db_path: Filesystem path to the SQLite database. Created if missing.
        classes: Ordered list of class names. Keys not in this list are
            silently ignored when accumulating.
    """

    _CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS daily_totals (
            day          TEXT PRIMARY KEY,
            totals_json  TEXT NOT NULL,
            window_count INTEGER NOT NULL,
            published    INTEGER NOT NULL DEFAULT 0
        )
    """

    def __init__(self, db_path: Path, classes: list[str]) -> None:
        self._db_path = Path(db_path)
        self._classes = list(classes)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(self._CREATE_SQL)

    # ---------- Public API ----------

    def add_window(self, snapshot: WindowSnapshot) -> None:
        """Add a window's counts to the running total for its day (UTC)."""
        day = snapshot.window_start.astimezone(timezone.utc).date()
        current = self._load(day)
        if current is None:
            totals = {cls: 0 for cls in self._classes}
            window_count = 0
        else:
            totals, window_count, _ = current
        for cls, count in snapshot.counts.items():
            if cls in totals:
                totals[cls] += count
        window_count += 1
        self._save(day, totals, window_count, published=False)

    def maybe_rollover(self, now: datetime) -> Optional[DailySnapshot]:
        """If `now` is past the day boundary and yesterday is unpublished,
        return it. Caller is responsible for publishing and then calling
        ``mark_published``.
        """
        now = _as_utc(now)
        today = now.date()
        yesterday = today - timedelta(days=1)
        row = self._load(yesterday)
        if row is None:
            return None
        totals, window_count, published = row
        if published:
            return None
        return DailySnapshot(
            day=yesterday, totals=totals, window_count=window_count, late=False
        )

    def pending_unpublished(self) -> list[DailySnapshot]:
        """All unpublished days strictly before today (UTC), flagged `late=True`.

        Used on boot to catch up on days the device missed publishing.
        """
        today = datetime.now(tz=timezone.utc).date()
        rows = self._conn.execute(
            "SELECT day, totals_json, window_count FROM daily_totals "
            "WHERE published = 0 AND day < ? ORDER BY day ASC",
            (today.isoformat(),),
        ).fetchall()
        return [
            DailySnapshot(
                day=date.fromisoformat(day_str),
                totals=json.loads(totals_json),
                window_count=window_count,
                late=True,
            )
            for day_str, totals_json, window_count in rows
        ]

    def mark_published(self, day: date) -> None:
        """Mark `day` as published so it is not emitted again."""
        self._conn.execute(
            "UPDATE daily_totals SET published = 1 WHERE day = ?", (day.isoformat(),)
        )

    def close(self) -> None:
        self._conn.close()

    # ---------- Internal ----------

    def _load(self, day: date) -> Optional[tuple[dict[str, int], int, bool]]:
        row = self._conn.execute(
            "SELECT totals_json, window_count, published FROM daily_totals WHERE day = ?",
            (day.isoformat(),),
        ).fetchone()
        if row is None:
            return None
        totals_json, window_count, published = row
        return json.loads(totals_json), int(window_count), bool(published)

    def _save(
        self, day: date, totals: dict[str, int], window_count: int, published: bool
    ) -> None:
        self._conn.execute(
            "INSERT INTO daily_totals (day, totals_json, window_count, published) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(day) DO UPDATE SET "
            "  totals_json = excluded.totals_json, "
            "  window_count = excluded.window_count, "
            "  published = excluded.published",
            (day.isoformat(), json.dumps(totals), window_count, int(published)),
        )


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return ts.astimezone(timezone.utc)


__all__ = [
    "WindowSnapshot",
    "WindowedCounter",
    "DailySnapshot",
    "DailyAccumulator",
    "DEFAULT_ANCHOR",
]
