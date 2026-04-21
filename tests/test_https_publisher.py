"""Unit tests for HttpClient and HttpsPublisher (mocked transport)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import httpx
import pytest

from src.camina.core.counter import DailySnapshot, WindowSnapshot
from src.camina.io.http_client import HttpClient, RetryPolicy
from src.camina.io.https_publisher import HttpsPublisher
from src.camina.io.offline_buffer import OfflineBuffer


UTC = timezone.utc
CLASSES = ["person", "cyclist", "car"]


# ---------- Helpers ----------


def _fast_retry() -> RetryPolicy:
    return RetryPolicy(max_attempts=3, base_delay_s=0.0, max_delay_s=0.0, jitter=0.0)


def _window(
    counts: dict[str, int],
    start: datetime = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC),
    partial: bool = False,
) -> WindowSnapshot:
    return WindowSnapshot(
        window_start=start,
        window_end=start + timedelta(minutes=15),
        counts=counts,
        partial=partial,
    )


@pytest.fixture()
def outbox(tmp_path: Path) -> Iterator[OfflineBuffer]:
    b = OfflineBuffer(db_path=tmp_path / "out.db", max_rows=100)
    try:
        yield b
    finally:
        b.close()


# ---------- HttpClient ----------


def test_client_returns_success_without_retry() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        response = c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert response.status_code == 200
    assert len(calls) == 1


def test_client_retries_on_500_then_succeeds() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        response = c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert response.status_code == 200
    assert len(attempts) == 2


def test_client_raises_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="still down")

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        with pytest.raises(httpx.HTTPStatusError):
            c.request("POST", "/v1/sensors/1/counts", content=b"{}")


def test_client_does_not_retry_on_400() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(400, text="bad payload")

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        with pytest.raises(httpx.HTTPStatusError):
            c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert len(attempts) == 1


def test_client_does_not_retry_on_401() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(401, text="bad token")

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        with pytest.raises(httpx.HTTPStatusError):
            c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert len(attempts) == 1


def test_client_retries_on_connect_error() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            raise httpx.ConnectError("no route")
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        response = c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert response.status_code == 200
    assert len(attempts) == 3


def test_client_sends_bearer_header() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="abc", retry=_fast_retry(), transport=transport) as c:
        c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert seen_headers["authorization"] == "Bearer abc"


# ---------- HttpsPublisher ----------


def test_publisher_posts_counts_successfully(outbox: OfflineBuffer) -> None:
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v2"})

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    result = publisher.post_counts(
        snapshot=_window({"person": 5, "cyclist": 2, "car": 10}),
        config_version="v1",
        fw_version="0.2.0",
    )

    assert result.delivered is True
    assert result.enqueued is False
    assert result.latest_config_version == "v2"
    assert received[-1]["sensor_id"] == "cam-01"
    assert received[-1]["counts"] == {"person": 5, "cyclist": 2, "car": 10}
    client.close()


def test_publisher_enqueues_when_backend_down(outbox: OfflineBuffer) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    result = publisher.post_counts(
        snapshot=_window({"person": 1, "cyclist": 0, "car": 0}),
        config_version="v1",
        fw_version="0.2.0",
    )

    assert result.delivered is False
    assert result.enqueued is True
    assert outbox.stats().pending == 1
    client.close()


def test_publisher_drains_outbox_on_next_success(outbox: OfflineBuffer) -> None:
    state = {"down": True, "received": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["down"]:
            return httpx.Response(503)
        state["received"].append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    # First two calls fail and buffer.
    for n in (1, 2):
        publisher.post_counts(
            snapshot=_window({"person": n, "cyclist": 0, "car": 0}),
            config_version="v1",
            fw_version="0.2.0",
        )
    assert outbox.stats().pending == 2

    # Backend recovers; next call should succeed AND drain the earlier two.
    state["down"] = False
    result = publisher.post_counts(
        snapshot=_window({"person": 99, "cyclist": 0, "car": 0}),
        config_version="v1",
        fw_version="0.2.0",
    )
    assert result.delivered is True
    assert outbox.stats().pending == 0
    # Server saw: the two buffered payloads (person=1, then person=2), then the fresh (person=99).
    person_values = [r["counts"]["person"] for r in state["received"]]
    assert person_values == [1, 2, 99]
    client.close()


def test_publisher_posts_daily(outbox: OfflineBuffer) -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    snap = DailySnapshot(
        day=date(2026, 4, 21),
        totals={"person": 100, "cyclist": 50, "car": 200},
        window_count=96,
        late=True,
    )
    result = publisher.post_daily(snap, config_version="v1", fw_version="0.2.0")

    assert result.delivered is True
    assert payloads[-1]["day"] == "2026-04-21"
    assert payloads[-1]["late"] is True
    assert payloads[-1]["totals"]["person"] == 100
    client.close()


def test_publisher_drain_outbox_explicit_call(outbox: OfflineBuffer) -> None:
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    drained = publisher.drain_outbox()
    assert drained == 2
    assert outbox.stats().pending == 0
    client.close()
