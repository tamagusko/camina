"""Unit tests for DailyAccumulator."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.camina.core.counter import (
    DailyAccumulator,
    DailySnapshot,
    WindowSnapshot,
)


CLASSES = ["person", "cyclist", "car"]
UTC = timezone.utc


@pytest.fixture()
def acc(tmp_path: Path) -> DailyAccumulator:
    a = DailyAccumulator(db_path=tmp_path / "state.db", classes=list(CLASSES))
    yield a
    a.close()


def _snap(start: datetime, counts: dict[str, int]) -> WindowSnapshot:
    return WindowSnapshot(
        window_start=start,
        window_end=start + timedelta(minutes=15),
        counts=counts,
        partial=False,
    )


# ---------- Accumulation ----------


def test_add_window_creates_row(acc: DailyAccumulator) -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    acc.add_window(_snap(start, {"person": 10, "cyclist": 5, "car": 20}))
    snap = acc.maybe_rollover(datetime(2026, 4, 22, 0, 1, 0, tzinfo=UTC))
    assert snap is not None
    assert snap.day == date(2026, 4, 21)
    assert snap.totals == {"person": 10, "cyclist": 5, "car": 20}
    assert snap.window_count == 1
    assert snap.late is False


def test_multiple_windows_accumulate(acc: DailyAccumulator) -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    acc.add_window(_snap(start, {"person": 1, "cyclist": 0, "car": 2}))
    acc.add_window(_snap(start + timedelta(minutes=15), {"person": 3, "cyclist": 2, "car": 0}))
    acc.add_window(_snap(start + timedelta(minutes=30), {"person": 4, "cyclist": 1, "car": 7}))
    snap = acc.maybe_rollover(datetime(2026, 4, 22, 0, 0, 1, tzinfo=UTC))
    assert snap is not None
    assert snap.totals == {"person": 8, "cyclist": 3, "car": 9}
    assert snap.window_count == 3


def test_unknown_class_ignored(acc: DailyAccumulator) -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    acc.add_window(_snap(start, {"person": 1, "truck": 99}))
    snap = acc.maybe_rollover(datetime(2026, 4, 22, 0, 0, 1, tzinfo=UTC))
    assert snap is not None
    assert "truck" not in snap.totals
    assert snap.totals["person"] == 1


# ---------- Rollover ----------


def test_rollover_returns_none_before_boundary(acc: DailyAccumulator) -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    acc.add_window(_snap(start, {"person": 1, "cyclist": 0, "car": 0}))
    # Same UTC day — no rollover.
    assert acc.maybe_rollover(datetime(2026, 4, 21, 23, 59, 0, tzinfo=UTC)) is None


def test_rollover_fires_once_after_boundary(acc: DailyAccumulator) -> None:
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    acc.add_window(_snap(start, {"person": 1, "cyclist": 0, "car": 0}))
    now = datetime(2026, 4, 22, 0, 0, 30, tzinfo=UTC)
    first = acc.maybe_rollover(now)
    assert first is not None
    acc.mark_published(first.day)
    assert acc.maybe_rollover(now) is None


# ---------- Late publication after restart ----------


def test_pending_unpublished_on_boot(tmp_path: Path) -> None:
    db = tmp_path / "state.db"

    # Simulate a session that writes a day-old row and does NOT mark it published.
    acc1 = DailyAccumulator(db_path=db, classes=list(CLASSES))
    old_day = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
    acc1.add_window(_snap(old_day, {"person": 4, "cyclist": 2, "car": 1}))
    acc1.close()

    # Next boot — simulate current time two days later.
    fake_now = datetime(2026, 4, 22, 8, 0, 0, tzinfo=UTC)

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now if tz else fake_now.replace(tzinfo=None)

    with patch("src.camina.core.counter.datetime", _FakeDT):
        acc2 = DailyAccumulator(db_path=db, classes=list(CLASSES))
        pending = acc2.pending_unpublished()
        acc2.close()

    assert len(pending) == 1
    late = pending[0]
    assert late.day == date(2026, 4, 20)
    assert late.late is True
    assert late.totals == {"person": 4, "cyclist": 2, "car": 1}


def test_published_row_is_not_returned_as_pending(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    acc1 = DailyAccumulator(db_path=db, classes=list(CLASSES))
    acc1.add_window(
        _snap(datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC), {"person": 1, "cyclist": 0, "car": 0})
    )
    acc1.mark_published(date(2026, 4, 20))
    acc1.close()

    acc2 = DailyAccumulator(db_path=db, classes=list(CLASSES))
    assert acc2.pending_unpublished() == []
    acc2.close()


# ---------- Crash recovery ----------


def test_totals_survive_reopen(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    acc1 = DailyAccumulator(db_path=db, classes=list(CLASSES))
    start = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
    acc1.add_window(_snap(start, {"person": 5, "cyclist": 2, "car": 7}))
    acc1.close()

    acc2 = DailyAccumulator(db_path=db, classes=list(CLASSES))
    snap = acc2.maybe_rollover(datetime(2026, 4, 22, 0, 0, 1, tzinfo=UTC))
    acc2.close()

    assert snap is not None
    assert snap.totals == {"person": 5, "cyclist": 2, "car": 7}
    assert snap.window_count == 1


# ---------- Snapshot helpers ----------


def test_snapshot_total_helper() -> None:
    snap = DailySnapshot(
        day=date(2026, 4, 21),
        totals={"person": 5, "cyclist": 2, "car": 7},
        window_count=3,
        late=False,
    )
    assert snap.total() == 14
