"""Unit tests for OfflineBuffer."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

import pytest

from src.camina.io.offline_buffer import OfflineBuffer, OutboxItem, SendOutcome


@pytest.fixture()
def buf(tmp_path: Path) -> Iterator[OfflineBuffer]:
    b = OfflineBuffer(db_path=tmp_path / "state.db", max_rows=100)
    try:
        yield b
    finally:
        b.close()


# ---------- Enqueue / peek ----------


def test_enqueue_assigns_monotonic_ids(buf: OfflineBuffer) -> None:
    id1 = buf.enqueue("counts", b'{"n":1}')
    id2 = buf.enqueue("counts", b'{"n":2}')
    assert id2 > id1


def test_enqueue_rejects_non_bytes(buf: OfflineBuffer) -> None:
    with pytest.raises(TypeError):
        buf.enqueue("counts", "not bytes")  # type: ignore[arg-type]


def test_peek_returns_fifo_order(buf: OfflineBuffer) -> None:
    for n in range(5):
        buf.enqueue("counts", f'{{"n":{n}}}'.encode())
    items = buf.peek(max_items=3)
    payloads = [item.payload for item in items]
    assert payloads == [b'{"n":0}', b'{"n":1}', b'{"n":2}']


# ---------- Drain ----------


def test_drain_removes_sent_rows(buf: OfflineBuffer) -> None:
    for n in range(4):
        buf.enqueue("counts", str(n).encode())

    sent: list[OutboxItem] = []

    def sender(item: OutboxItem) -> bool:
        sent.append(item)
        return True

    count = buf.drain(sender, max_items=4)
    assert count == 4
    assert buf.stats().pending == 0
    assert [item.payload for item in sent] == [b"0", b"1", b"2", b"3"]


def test_drain_stops_on_first_failure(buf: OfflineBuffer) -> None:
    for n in range(5):
        buf.enqueue("counts", str(n).encode())

    calls: list[int] = []

    def sender(item: OutboxItem) -> bool:
        calls.append(item.id)
        return item.id < 3  # fail on id >= 3 (row 3 is the 3rd enqueued)

    sent = buf.drain(sender, max_items=5)
    # Sent the first two successfully (ids 1 and 2), then failed on id 3 and stopped.
    assert sent == 2
    assert len(calls) == 3
    assert buf.stats().pending == 3


def test_drain_increments_attempts_on_failure(buf: OfflineBuffer) -> None:
    buf.enqueue("counts", b"x")

    def always_fail(_: OutboxItem) -> bool:
        return False

    buf.drain(always_fail)
    [item] = buf.peek(1)
    assert item.attempts == 1

    buf.drain(always_fail)
    [item] = buf.peek(1)
    assert item.attempts == 2


def test_drain_handles_sender_exception(buf: OfflineBuffer) -> None:
    buf.enqueue("counts", b"x")

    def broken(_: OutboxItem) -> bool:
        raise RuntimeError("network exploded")

    sent = buf.drain(broken)
    assert sent == 0
    assert buf.stats().pending == 1


def test_drain_respects_max_items(buf: OfflineBuffer) -> None:
    for n in range(10):
        buf.enqueue("counts", str(n).encode())

    def ok(_: OutboxItem) -> bool:
        return True

    sent = buf.drain(ok, max_items=3)
    assert sent == 3
    assert buf.stats().pending == 7


# ---------- Poison-message handling (tri-state outcomes) ----------


def test_drain_drops_poison_and_continues(buf: OfflineBuffer) -> None:
    for n in range(3):
        buf.enqueue("counts", str(n).encode())

    def sender(item: OutboxItem) -> SendOutcome:
        # Middle row (id 2) is a poison message; the others deliver.
        return SendOutcome.DROP if item.id == 2 else SendOutcome.SENT

    sent = buf.drain(sender, max_items=3)
    assert sent == 2
    assert buf.stats().pending == 0
    assert buf.stats().poisoned == 1


def test_drain_retry_preserves_fifo_order(buf: OfflineBuffer) -> None:
    for n in range(3):
        buf.enqueue("counts", str(n).encode())

    def sender(_: OutboxItem) -> SendOutcome:
        return SendOutcome.RETRY

    sent = buf.drain(sender, max_items=3)
    assert sent == 0
    assert buf.stats().pending == 3  # nothing lost on transient failure
    [head] = buf.peek(1)
    assert head.payload == b"0"      # order preserved
    assert head.attempts == 1        # only the head was charged an attempt


def test_drain_safety_valve_drops_after_max_attempts(buf: OfflineBuffer) -> None:
    buf.enqueue("counts", b"x")

    def retry(_: OutboxItem) -> SendOutcome:
        return SendOutcome.RETRY

    # Three RETRY drains bump attempts to 3 without dropping the row.
    for _ in range(3):
        buf.drain(retry, max_attempts=3)
    assert buf.stats().pending == 1
    assert buf.peek(1)[0].attempts == 3

    # The next drain trips the safety valve and drops it as poisoned.
    buf.drain(retry, max_attempts=3)
    assert buf.stats().pending == 0
    assert buf.stats().poisoned == 1


def test_drain_legacy_bool_sender_still_works(buf: OfflineBuffer) -> None:
    """Bool-returning senders remain valid: True→SENT, False→RETRY."""
    for n in range(2):
        buf.enqueue("counts", str(n).encode())

    assert buf.drain(lambda _i: True, max_items=2) == 2
    assert buf.stats().pending == 0
    assert buf.stats().poisoned == 0


# ---------- Size cap ----------


def test_cap_drops_oldest_when_exceeded(tmp_path: Path) -> None:
    b = OfflineBuffer(db_path=tmp_path / "s.db", max_rows=3)
    b.enqueue("counts", b"A")
    b.enqueue("counts", b"B")
    b.enqueue("counts", b"C")
    # This one pushes us over → drops "A".
    b.enqueue("counts", b"D")
    items = b.peek(max_items=10)
    assert [i.payload for i in items] == [b"B", b"C", b"D"]
    assert b.stats().dropped == 1
    b.close()


def test_cap_drops_multiple_when_far_over(tmp_path: Path) -> None:
    b = OfflineBuffer(db_path=tmp_path / "s.db", max_rows=2)
    for c in (b"A", b"B", b"C", b"D", b"E"):
        b.enqueue("counts", c)
    items = b.peek(max_items=10)
    assert [i.payload for i in items] == [b"D", b"E"]
    assert b.stats().dropped == 3
    b.close()


# ---------- Persistence across reopen ----------


def test_rows_survive_reopen(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    b1 = OfflineBuffer(db_path=path, max_rows=100)
    b1.enqueue("counts", b"persist me")
    b1.close()

    b2 = OfflineBuffer(db_path=path, max_rows=100)
    items = b2.peek(max_items=1)
    assert items[0].payload == b"persist me"
    b2.close()


# ---------- Concurrency ----------


def test_concurrent_enqueue_is_safe(tmp_path: Path) -> None:
    b = OfflineBuffer(db_path=tmp_path / "s.db", max_rows=1000)
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda n: b.enqueue("counts", str(n).encode()), range(200)))
        assert b.stats().pending == 200
    finally:
        b.close()


# ---------- Stats ----------


def test_stats_reflect_state(buf: OfflineBuffer) -> None:
    s0 = buf.stats()
    assert s0.pending == 0
    assert s0.dropped == 0
    assert s0.oldest_enqueued_at is None

    buf.enqueue("counts", b"a")
    buf.enqueue("counts", b"b")
    s1 = buf.stats()
    assert s1.pending == 2
    assert s1.oldest_enqueued_at is not None
