"""Unit tests for HttpClient and HttpsPublisher (mocked transport)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from camina.core.counter import DailySnapshot, WindowSnapshot
from camina.io.http_client import HttpClient, RetryPolicy
from camina.io.https_publisher import HttpsPublisher
from camina.io.offline_buffer import OfflineBuffer
from camina.io.schemas import CountsPayload, HeartbeatPayload

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
    with (
        HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c,
        pytest.raises(httpx.HTTPStatusError),
    ):
        c.request("POST", "/v1/sensors/1/counts", content=b"{}")


def test_client_does_not_retry_on_400() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(400, text="bad payload")

    transport = httpx.MockTransport(handler)
    with (
        HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c,
        pytest.raises(httpx.HTTPStatusError),
    ):
        c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert len(attempts) == 1


def test_client_does_not_retry_on_401() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(401, text="bad token")

    transport = httpx.MockTransport(handler)
    with (
        HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c,
        pytest.raises(httpx.HTTPStatusError),
    ):
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
        avg_speed_kmh={"person": 4.0, "cyclist": 12.0, "car": 28.0},
    )

    assert result.delivered is True
    assert result.enqueued is False
    assert result.latest_config_version == "v2"
    assert received[-1]["sensor_id"] == "cam-01"
    assert received[-1]["schema_version"] == "1.0"
    assert "counts_by_direction" not in received[-1]
    assert received[-1]["counts"] == {"person": 5, "cyclist": 2, "car": 10}
    assert received[-1]["avg_speed_kmh"] == {
        "person": 4.0,
        "cyclist": 12.0,
        "car": 28.0,
    }
    client.close()


def test_publisher_emits_directional_schema_version(outbox: OfflineBuffer) -> None:
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    client = HttpClient(
        "https://api.test", token="t", retry=_fast_retry(), transport=httpx.MockTransport(handler)
    )
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)
    publisher.post_counts(
        snapshot=WindowSnapshot(
            window_start=datetime(2026, 4, 21, 10, tzinfo=UTC),
            window_end=datetime(2026, 4, 21, 10, 15, tzinfo=UTC),
            counts={"car": 7, "person": 7},
            partial=False,
            counts_by_direction={"AB": {"car": 3, "person": 2}, "BA": {"car": 4, "person": 5}},
        ),
        config_version="v1",
        fw_version="0.2.0",
    )
    assert received[0]["schema_version"] == "1.1"
    assert received[0]["counts"] == {"car": 7, "person": 7}
    assert received[0]["counts_by_direction"] == {
        "AB": {"car": 3, "person": 2},
        "BA": {"car": 4, "person": 5},
    }
    client.close()


def test_counts_payload_direction_contract_and_legacy_version() -> None:
    shared = {
        "sensor_id": "cam-01",
        "window_start": datetime(2026, 4, 21, 10, tzinfo=UTC),
        "window_end": datetime(2026, 4, 21, 10, 15, tzinfo=UTC),
        "partial": False,
        "counts": {"car": 3},
        "config_version": "v1",
        "fw_version": "0.2.0",
    }
    legacy = CountsPayload(**shared)
    assert legacy.schema_version == "1.0"
    assert "counts_by_direction" not in legacy.model_dump(exclude_none=True)

    directional = CountsPayload(**shared, counts_by_direction={"AB": {"car": 1}, "BA": {"car": 2}})
    assert directional.schema_version == "1.1"

    with pytest.raises(ValueError, match="sum"):
        CountsPayload(**shared, counts_by_direction={"AB": {"car": 1}})
    with pytest.raises(ValueError):
        CountsPayload(**shared, counts_by_direction={"CA": {"car": 3}})


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


def test_publisher_buffers_200_response_with_ok_false(outbox: OfflineBuffer) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "latest_config_version": "v1"})

    client = HttpClient(
        "https://api.test",
        token="t",
        retry=_fast_retry(),
        transport=httpx.MockTransport(handler),
    )
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)
    try:
        result = publisher.post_counts(
            snapshot=_window({"person": 1, "cyclist": 0, "car": 0}),
            config_version="v1",
            fw_version="0.2.0",
        )

        assert result.delivered is False
        assert result.enqueued is True
        assert outbox.stats().pending == 1
    finally:
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
    person_values = [r["counts"].get("person", 0) for r in state["received"]]
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
        totals={"person": 100, "cyclist": 50, "car": 200, "e-scooter": 4},
        window_count=96,
        late=True,
    )
    result = publisher.post_daily(snap, config_version="v1", fw_version="0.2.0")

    assert result.delivered is True
    assert payloads[-1]["day"] == "2026-04-21"
    assert payloads[-1]["late"] is True
    assert payloads[-1]["totals"]["person"] == 100
    assert payloads[-1]["totals"]["e-scooter"] == 4
    client.close()


def test_publisher_counts_path_has_no_v1_prefix(outbox: OfflineBuffer) -> None:
    """F1: request path is `/sensors/{id}/counts` (base_url already carries
    `/api/ingest`); the stale `/v1` segment is gone."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    publisher.post_counts(
        snapshot=_window({"person": 1, "cyclist": 0, "car": 0}),
        config_version="v1",
        fw_version="0.2.0",
    )
    assert seen["path"] == "/sensors/cam-01/counts"
    assert "/v1/" not in seen["path"]
    client.close()


def test_failed_heartbeat_is_not_enqueued(outbox: OfflineBuffer) -> None:
    """F4: a heartbeat that fails to send is never buffered (zero replay value)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    hb = HeartbeatPayload(sensor_id="cam-01", uptime_s=10, config_version="v1", fw_version="0.2.0")
    result = publisher.post_heartbeat(hb)

    assert result.delivered is False
    assert result.buffered is False
    assert result.enqueued is False
    assert outbox.stats().pending == 0
    client.close()


def test_heartbeat_outbox_fields_must_be_nonnegative() -> None:
    shared = {
        "sensor_id": "cam-01",
        "uptime_s": 10,
        "config_version": "v1",
        "fw_version": "0.2.0",
    }
    hb = HeartbeatPayload(**shared, outbox_depth=12, outbox_dropped_total=3)
    assert hb.outbox_depth == 12
    assert hb.outbox_dropped_total == 3

    with pytest.raises(ValueError):
        HeartbeatPayload(**shared, outbox_depth=-1)
    with pytest.raises(ValueError):
        HeartbeatPayload(**shared, outbox_dropped_total=-1)
    with pytest.raises(ValueError):
        HeartbeatPayload(**shared, outbox_depth=1.5)


def test_outbox_item_4xx_is_dropped_as_poison(outbox: OfflineBuffer) -> None:
    """F3: a permanently-rejected (4xx) buffered item is dropped, not retried."""
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad payload")

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    drained = publisher.drain_outbox()
    assert drained == 0
    assert outbox.stats().pending == 0  # poison row removed, no longer wedges FIFO
    assert outbox.stats().poisoned == 1
    client.close()


def test_outbox_item_5xx_is_retried_not_dropped(outbox: OfflineBuffer) -> None:
    """F3: a transient (5xx) failure keeps the buffered item for later retry."""
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    drained = publisher.drain_outbox()
    assert drained == 0
    assert outbox.stats().pending == 1  # kept for retry
    assert outbox.stats().poisoned == 0
    client.close()


def test_outbox_item_is_retained_when_response_ok_is_false(outbox: OfflineBuffer) -> None:
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "latest_config_version": "v1"})

    client = HttpClient(
        "https://api.test",
        token="t",
        retry=_fast_retry(),
        transport=httpx.MockTransport(handler),
    )
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)
    try:
        assert publisher.drain_outbox() == 0
        assert outbox.stats().pending == 1
        assert outbox.peek(1)[0].attempts == 1
    finally:
        client.close()


def test_outbox_transport_error_does_not_charge_attempt(outbox: OfflineBuffer) -> None:
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = HttpClient(
        "https://api.test", token="t", retry=_fast_retry(), transport=httpx.MockTransport(handler)
    )
    publisher = HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)

    assert publisher.drain_outbox() == 0
    assert outbox.stats().pending == 1
    assert outbox.peek(1)[0].attempts == 0
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


def _skew_publisher(outbox: OfflineBuffer, responses: list[httpx.Response]) -> HttpsPublisher:
    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = HttpClient(
        "https://api.test", token="t", retry=_fast_retry(), transport=httpx.MockTransport(handler)
    )
    return HttpsPublisher(sensor_id="cam-01", http_client=client, outbox=outbox)


def test_outbox_item_rejected_for_clock_skew_is_kept_and_flagged(outbox: OfflineBuffer) -> None:
    """A 422 timestamp_in_future means the device clock runs fast, not a bad row."""
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')
    publisher = _skew_publisher(
        outbox,
        [
            httpx.Response(422, json={"error": "timestamp_in_future"}),
            httpx.Response(200, json={"ok": True, "latest_config_version": "v1"}),
        ],
    )

    assert publisher.drain_outbox() == 0
    assert outbox.stats().pending == 1
    assert outbox.stats().poisoned == 0
    assert outbox.peek(1)[0].attempts == 0
    assert publisher.clock_skew is True

    assert publisher.drain_outbox() == 1
    assert outbox.stats().pending == 0
    assert publisher.clock_skew is False


def test_outbox_item_too_old_is_dropped(outbox: OfflineBuffer) -> None:
    """A 422 timestamp_too_old can never be accepted; it is dropped as before."""
    outbox.enqueue("counts", b'{"sensor_id":"cam-01"}')
    publisher = _skew_publisher(outbox, [httpx.Response(422, json={"error": "timestamp_too_old"})])

    assert publisher.drain_outbox() == 0
    assert outbox.stats().pending == 0
    assert outbox.stats().poisoned == 1
    assert publisher.clock_skew is False


def test_fresh_counts_rejected_for_clock_skew_stay_buffered(outbox: OfflineBuffer) -> None:
    skew = httpx.Response(422, json={"error": "timestamp_in_future"})
    publisher = _skew_publisher(outbox, [skew, skew])

    result = publisher.post_counts(_window({"car": 3}), config_version="v1", fw_version="0.1.0")
    assert result.buffered is True
    assert publisher.drain_outbox() == 0
    assert outbox.stats().pending == 1
    assert publisher.clock_skew is True
