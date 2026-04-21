"""Unit tests for WindowedCounter."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.camina.core.counter import DEFAULT_ANCHOR, WindowedCounter, WindowSnapshot


CLASSES = ["person", "cyclist", "car", "e-scooter"]
UTC = timezone.utc


def _start_counter(start: datetime, window_seconds: int = 900) -> WindowedCounter:
    """Create a counter whose internal "started_at" is `start`."""
    with patch(
        "src.camina.core.counter.datetime",
        wraps=datetime,
    ) as dt:
        dt.now.return_value = start
        return WindowedCounter(
            classes=list(CLASSES),
            window_seconds=window_seconds,
            anchor=DEFAULT_ANCHOR,
        )


# ---------- Construction ----------


def test_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError):
        WindowedCounter(classes=CLASSES, window_seconds=0)


def test_rejects_naive_anchor() -> None:
    naive = datetime(2026, 1, 1, 0, 0, 0)
    with pytest.raises(ValueError):
        WindowedCounter(classes=CLASSES, window_seconds=60, anchor=naive)


def test_rejects_naive_timestamps_in_add() -> None:
    now = datetime(2026, 4, 21, 10, 5, 0, tzinfo=UTC)
    c = _start_counter(now)
    with pytest.raises(ValueError):
        c.add(1, "person", datetime(2026, 4, 21, 10, 6, 0))  # naive


# ---------- Window alignment ----------


def test_windows_align_to_wall_clock() -> None:
    # Starting at 10:07:30, a 15-min window should begin at 10:00:00.
    start = datetime(2026, 4, 21, 10, 7, 30, tzinfo=UTC)
    c = _start_counter(start)
    assert c.window_start == datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    assert c.window_end == datetime(2026, 4, 21, 10, 15, 0, tzinfo=UTC)


def test_5_second_window_alignment() -> None:
    start = datetime(2026, 4, 21, 10, 0, 7, tzinfo=UTC)
    c = _start_counter(start, window_seconds=5)
    assert c.window_start == datetime(2026, 4, 21, 10, 0, 5, tzinfo=UTC)


# ---------- Counting semantics ----------


def test_duplicate_track_id_in_window_counts_once() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    for _ in range(5):
        c.add(track_id=42, class_name="person", now=start + timedelta(seconds=1))
    snap = c.force_snapshot(start + timedelta(seconds=10))
    assert snap.counts["person"] == 1


def test_different_track_ids_in_window_each_count() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    for tid in (1, 2, 3):
        c.add(track_id=tid, class_name="cyclist", now=start + timedelta(seconds=1))
    snap = c.force_snapshot(start + timedelta(seconds=10))
    assert snap.counts["cyclist"] == 3


def test_same_track_id_across_windows_counts_per_window() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    c.add(track_id=7, class_name="car", now=start + timedelta(seconds=30))
    first = c.force_snapshot(start + timedelta(minutes=15))
    # New window: same track id should count again.
    c.add(track_id=7, class_name="car", now=start + timedelta(minutes=16))
    second = c.force_snapshot(start + timedelta(minutes=30))
    assert first.counts["car"] == 1
    assert second.counts["car"] == 1


def test_unknown_class_is_ignored() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    c.add(track_id=1, class_name="truck", now=start + timedelta(seconds=1))
    snap = c.force_snapshot(start + timedelta(seconds=2))
    assert "truck" not in snap.counts
    assert sum(snap.counts.values()) == 0


# ---------- Rollover ----------


def test_maybe_rollover_returns_none_before_boundary() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    assert c.maybe_rollover(start + timedelta(seconds=60)) is None


def test_maybe_rollover_fires_at_boundary() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    c.add(track_id=1, class_name="person", now=start + timedelta(seconds=30))
    snap = c.maybe_rollover(start + timedelta(minutes=15))
    assert isinstance(snap, WindowSnapshot)
    assert snap.counts["person"] == 1


def test_rollover_aligns_new_window_to_wall_clock_even_after_long_gap() -> None:
    # Start at 10:00, then jump forward 47 minutes — new window should start
    # at 10:45, not 10:47.
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    c.force_snapshot(start + timedelta(minutes=47))
    assert c.window_start == datetime(2026, 4, 21, 10, 45, 0, tzinfo=UTC)
    assert c.window_end == datetime(2026, 4, 21, 11, 0, 0, tzinfo=UTC)


# ---------- Partial flag ----------


def test_first_window_is_partial_when_started_mid_window() -> None:
    start = datetime(2026, 4, 21, 10, 7, 30, tzinfo=UTC)  # mid-window
    c = _start_counter(start)
    snap = c.force_snapshot(datetime(2026, 4, 21, 10, 15, 0, tzinfo=UTC))
    assert snap.partial is True


def test_first_window_not_partial_when_started_exactly_on_boundary() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    snap = c.force_snapshot(datetime(2026, 4, 21, 10, 15, 0, tzinfo=UTC))
    assert snap.partial is False


def test_second_window_never_partial() -> None:
    start = datetime(2026, 4, 21, 10, 7, 30, tzinfo=UTC)
    c = _start_counter(start)
    _ = c.force_snapshot(datetime(2026, 4, 21, 10, 15, 0, tzinfo=UTC))
    snap2 = c.force_snapshot(datetime(2026, 4, 21, 10, 30, 0, tzinfo=UTC))
    assert snap2.partial is False


# ---------- Snapshot immutability ----------


def test_snapshot_counts_are_not_shared_with_internal_state() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    c.add(track_id=1, class_name="person", now=start + timedelta(seconds=5))
    snap = c.force_snapshot(start + timedelta(seconds=10))
    # Mutating internal state (via a second window) must not affect the snap.
    c.add(track_id=2, class_name="person", now=start + timedelta(minutes=16))
    _ = c.force_snapshot(start + timedelta(minutes=30))
    assert snap.counts["person"] == 1


def test_snapshot_total_helper() -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    c = _start_counter(start)
    c.add(1, "person", start + timedelta(seconds=1))
    c.add(2, "cyclist", start + timedelta(seconds=2))
    c.add(3, "cyclist", start + timedelta(seconds=3))
    snap = c.force_snapshot(start + timedelta(seconds=10))
    assert snap.total() == 3
