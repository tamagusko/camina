"""Integration test: SensorDaemon composes end-to-end against a mock backend."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

import httpx
import pytest

from src.camina.io.http_client import HttpClient, RetryPolicy
from src.camina.io.https_publisher import HttpsPublisher
from src.camina.io.offline_buffer import OfflineBuffer
from src.camina.io.config_poller import ConfigPoller
from src.camina.core.counter import WindowedCounter, WindowSnapshot
from src.camina.service import sensor_daemon as sd
from src.camina.service.sensor_daemon import DaemonConfig, SensorDaemon


CLASSES = ["person", "cyclist", "car"]
UTC = timezone.utc


def _make_daemon(tmp_path: Path, transport: httpx.MockTransport) -> SensorDaemon:
    """Build a SensorDaemon with an empty frame source and a mock-backed
    publisher that shares the daemon's real outbox + daily accumulator."""
    cfg = DaemonConfig(
        sensor_id="cam-01",
        api_base_url="https://api.test",
        api_token="t",
        state_db_path=tmp_path / "state.db",
        classes=list(CLASSES),
        fw_version="0.2.0",
        publish_interval_seconds=900,
        heartbeat_interval_seconds=300,
    )
    daemon = SensorDaemon(
        config=cfg, frame_source=iter([]), detect_and_track=lambda _f: []
    )
    client = HttpClient(
        "https://api.test",
        token="t",
        retry=RetryPolicy(max_attempts=2, base_delay_s=0.0, max_delay_s=0.0, jitter=0.0),
        transport=transport,
    )
    daemon._publisher = HttpsPublisher(
        sensor_id="cam-01", http_client=client, outbox=daemon._outbox
    )
    daemon._test_client = client  # type: ignore[attr-defined]
    return daemon


def test_windowed_counter_feeds_publisher_end_to_end(tmp_path: Path) -> None:
    """Counts produced by WindowedCounter arrive at the backend via HttpsPublisher."""
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    outbox = OfflineBuffer(db_path=tmp_path / "out.db", max_rows=100)
    client = HttpClient(
        "https://api.test",
        token="t",
        retry=RetryPolicy(max_attempts=2, base_delay_s=0.0, max_delay_s=0.0, jitter=0.0),
        transport=transport,
    )
    pub = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)
    counter = WindowedCounter(classes=list(CLASSES), window_seconds=60)

    # Simulate three tracked detections in the first window.
    start = counter.window_start
    inside = start
    for tid, cls in [(1, "person"), (2, "cyclist"), (3, "person")]:
        counter.add(track_id=tid, class_name=cls, now=inside)

    # Roll over: force the window boundary.
    snap = counter.force_snapshot(start.replace(minute=(start.minute + 1) % 60))
    result = pub.post_counts(snap, config_version="v1", fw_version="0.2.0")
    assert result.delivered is True
    assert len(received) == 1
    body = received[0]
    assert body["sensor_id"] == "cam-01"
    assert body["counts"]["person"] == 2
    assert body["counts"]["cyclist"] == 1

    outbox.close()
    client.close()


def test_config_poller_reconfigures_counter(tmp_path: Path) -> None:
    """When backend advertises a new config_version, the counter's window changes."""

    # First GET returns a config with a 30 s window (we start at 60 s).
    new_config = {
        "config_version": "v2",
        "publish_interval_minutes": 1,      # 1 min = 60 s — unchanged for simplicity
        "heartbeat_interval_minutes": 5,
        "daily_publish_time_utc": "00:00",
        "detection_zone": None,
        "frame_skip": 5,
        "min_track_hits": 3,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=new_config)

    transport = httpx.MockTransport(handler)
    client = HttpClient(
        "https://api.test",
        token="t",
        retry=RetryPolicy(max_attempts=2, base_delay_s=0.0, max_delay_s=0.0, jitter=0.0),
        transport=transport,
    )

    applied: list = []
    poller = ConfigPoller(
        sensor_id="cam-01",
        http_client=client,
        current_version="v1",
        apply=applied.append,
    )
    changed = poller.check("v2")
    assert changed is True
    assert poller.current_version == "v2"
    assert applied[0].config_version == "v2"
    client.close()


def test_daily_publish_buffered_marks_published_no_retry_storm(tmp_path: Path) -> None:
    """F2: on a network failure the daily payload is buffered exactly once and
    then marked published, so ``maybe_rollover`` stops re-emitting it."""
    transport = httpx.MockTransport(lambda _r: httpx.Response(503))
    daemon = _make_daemon(tmp_path, transport)
    try:
        # Seed an unpublished daily row for "yesterday".
        yesterday_window = WindowSnapshot(
            window_start=datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC),
            window_end=datetime(2026, 4, 21, 10, 15, 0, tzinfo=UTC),
            counts={"person": 3, "cyclist": 0, "car": 0},
            partial=False,
        )
        daemon._daily.add_window(yesterday_window)

        now = datetime(2026, 4, 22, 0, 5, 0, tzinfo=UTC)
        snap = daemon._daily.maybe_rollover(now)
        assert snap is not None

        daemon._publish_daily(snap)
        # Backend down → buffered exactly once.
        assert daemon._outbox.stats().pending == 1
        # Marked published despite delivered=False → not re-emitted next frame.
        assert daemon._daily.maybe_rollover(now) is None
        # Next loop iteration: still None, no duplicate enqueue.
        assert daemon._daily.maybe_rollover(now) is None
        assert daemon._outbox.stats().pending == 1
    finally:
        daemon._test_client.close()  # type: ignore[attr-defined]
        daemon.stop()


def test_stop_flushes_open_window(tmp_path: Path) -> None:
    """F5: graceful stop snapshots the open window (marked partial) and feeds
    both the publisher and the daily accumulator before closing state."""
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": ""})

    daemon = _make_daemon(tmp_path, httpx.MockTransport(handler))

    recorded: list[WindowSnapshot] = []
    orig_add = daemon._daily.add_window

    def _spy(snap: WindowSnapshot) -> None:
        recorded.append(snap)
        orig_add(snap)

    daemon._daily.add_window = _spy  # type: ignore[method-assign]

    now = datetime.now(tz=UTC)
    daemon._counter.add(track_id=1, class_name="person", now=now)
    daemon._counter.add(track_id=2, class_name="cyclist", now=now)

    daemon.stop()  # flush happens before state is closed

    assert len(received) == 1
    assert received[0]["partial"] is True
    assert received[0]["counts"]["person"] == 1
    assert received[0]["counts"]["cyclist"] == 1
    assert len(recorded) == 1
    assert recorded[0].counts["person"] == 1
    daemon._test_client.close()  # type: ignore[attr-defined]


def test_stop_skips_empty_open_window(tmp_path: Path) -> None:
    """F5: an empty open window (zero counts) is not published on stop."""
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": ""})

    daemon = _make_daemon(tmp_path, httpx.MockTransport(handler))
    daemon.stop()  # no counts added → nothing published
    assert received == []
    daemon._test_client.close()  # type: ignore[attr-defined]


def test_daemon_wires_fast_fail_inline_retry(tmp_path: Path) -> None:
    """F6: the daemon's in-loop HttpClient uses the fast-fail policy so an
    outage cannot stall the detection loop (the outbox owns durable retries)."""
    daemon = _make_daemon(
        tmp_path,
        httpx.MockTransport(lambda _r: httpx.Response(200, json={"ok": True, "latest_config_version": ""})),
    )
    try:
        assert daemon._http._retry is sd._INLINE_RETRY
        assert sd._INLINE_RETRY.max_attempts == 2
        assert sd._INLINE_RETRY.max_delay_s < RetryPolicy().max_delay_s
    finally:
        daemon._test_client.close()  # type: ignore[attr-defined]
        daemon.stop()
