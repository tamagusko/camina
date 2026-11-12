from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.make_test_payloads import generate_payloads
from scripts.replay_payloads import replay


def test_one_day_stream_is_deterministic_and_covers_all_endpoints() -> None:
    start = datetime(2026, 9, 21, tzinfo=timezone.utc)
    first = generate_payloads(days=1, seed=0, start=start)
    second = generate_payloads(days=1, seed=0, start=start)
    assert first == second
    assert sum(row["endpoint"] == "counts" for row in first) == 97  # one duplicate resend
    assert sum(row["endpoint"] == "heartbeat" for row in first) == 96
    assert sum(row["endpoint"] == "daily" for row in first) == 1
    assert any(row["body"].get("partial") for row in first if row["endpoint"] == "counts")
    assert any(
        row["endpoint"] == "heartbeat" and row["body"]["ts"] != row["sent_at"] for row in first
    )
    assert any(
        row["endpoint"] == "counts"
        and row["sent_at"].startswith("2026-09-21T12:30")
        and row["body"]["window_start"].startswith("2026-09-21T12:00")
        for row in first
    )


def test_edge_payloads_preserve_raw_direction_and_speed_values() -> None:
    rows = generate_payloads(days=1, seed=0)
    counts = [row["body"] for row in rows if row["endpoint"] == "counts"]
    small_cells: list[int] = []
    for body in counts:
        for direction in body["counts_by_direction"].values():
            small_cells.extend(value for value in direction.values() if 1 <= value <= 4)
        totals = dict.fromkeys(body["counts"], 0)
        for direction in body["counts_by_direction"].values():
            for name, value in direction.items():
                totals[name] = totals.get(name, 0) + value
        assert body["counts"] == totals
        assert set(body["avg_speed_kmh"]).issubset(
            {"cyclist", "e-scooter", "car", "SUV", "motorcyclist", "bus", "delivery_van", "truck"}
        )
    assert small_cells


def test_replay_uses_bearer_token_and_posts_in_file_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "payloads.jsonl"
    rows = [
        {"endpoint": "counts", "sent_at": "2026-01-01T00:00:00Z", "body": {"sensor_id": "s"}},
        {"endpoint": "heartbeat", "sent_at": "2026-01-01T00:05:00Z", "body": {"sensor_id": "s"}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    requests = []
    monkeypatch.setattr("scripts.replay_payloads.time.sleep", Mock())

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr("scripts.replay_payloads.urlopen", fake_urlopen)
    assert replay(path, "https://dashboard.example/", "secret-test-token", speed=60) == 0
    assert [request.full_url.rsplit("/", 1)[-1] for request, _ in requests] == [
        "counts",
        "heartbeat",
    ]
    assert all(
        request.get_header("Authorization") == "Bearer secret-test-token" for request, _ in requests
    )
