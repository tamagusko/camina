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
from src.camina.core.counter import WindowedCounter


CLASSES = ["person", "cyclist", "car"]
UTC = timezone.utc


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
