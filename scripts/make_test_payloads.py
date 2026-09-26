#!/usr/bin/env python3
"""Generate deterministic, realistic sensor requests as newline-delimited JSON."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from camina.io.schemas import CountsPayload, DailyPayload, HeartbeatPayload  # noqa: E402
from camina.utils.taxonomy import load_canonical_classes  # noqa: E402

UTC = timezone.utc
DUBLIN = ZoneInfo("Europe/Dublin")
SENSOR_ID = "cam-dub-01"
CONFIG_VERSION = "sim-v1"
FW_VERSION = "0.2.0"
VEHICLE_CLASSES = {
    "cyclist",
    "e-scooter",
    "car",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
}
BASE_RATES = {
    "person": 4.0,
    "cyclist": 3.0,
    "car": 17.0,
    "e-scooter": 0.35,
    "SUV": 4.0,
    "motorcyclist": 0.25,
    "bus": 0.45,
    "delivery_van": 1.2,
    "truck": 0.25,
}


def _poisson(rng: random.Random, mean: float) -> int:
    """Draw a Poisson count without requiring NumPy."""
    if mean <= 0:
        return 0
    if mean < 30:
        threshold = math.exp(-mean)
        product = 1.0
        count = 0
        while product > threshold:
            count += 1
            product *= rng.random()
        return count - 1
    return max(0, round(rng.gauss(mean, math.sqrt(mean))))


def _traffic_factor(moment: datetime) -> float:
    moment = moment.astimezone(DUBLIN)
    hour = moment.hour + moment.minute / 60
    weekday = moment.weekday() < 5
    if not weekday:
        return 0.46 if 9 <= hour < 18 else 0.16
    if 7 <= hour < 10:
        return 2.6
    if 16 <= hour < 19:
        return 2.25
    if 10 <= hour < 16:
        return 1.05
    if 19 <= hour < 22:
        return 0.62
    return 0.12


def _split_direction(rng: random.Random, count: int, moment: datetime) -> tuple[int, int]:
    moment = moment.astimezone(DUBLIN)
    hour = moment.hour + moment.minute / 60
    if 6 <= hour < 11:
        probability_ab = 0.68
    elif 15 <= hour < 20:
        probability_ab = 0.34
    else:
        probability_ab = 0.53
    ab = sum(rng.random() < probability_ab for _ in range(count))
    return ab, count - ab


def _window_body(
    rng: random.Random, start: datetime, end: datetime, partial: bool
) -> dict[str, Any]:
    midpoint = start + (end - start) / 2
    factor = _traffic_factor(midpoint) * (8 / 15 if partial else 1)
    raw: dict[str, tuple[int, int]] = {}
    for road_user_class, rate in BASE_RATES.items():
        total = _poisson(rng, rate * factor)
        raw[road_user_class] = _split_direction(rng, total, midpoint)

    # Apply k_min to each direction cell first. Counts reflect only published
    # direction cells so AB + BA remains exact after privacy suppression.
    directional: dict[str, dict[str, int]] = {"AB": {}, "BA": {}}
    counts: dict[str, int] = {}
    for road_user_class, (ab, ba) in raw.items():
        if ab >= 5:
            directional["AB"][road_user_class] = ab
        if ba >= 5:
            directional["BA"][road_user_class] = ba
        published = directional["AB"].get(road_user_class, 0) + directional["BA"].get(
            road_user_class, 0
        )
        if published:
            counts[road_user_class] = published

    speeds: dict[str, float] = {}
    for road_user_class, count in counts.items():
        if road_user_class in VEHICLE_CLASSES and count >= 5:
            mean_speed = {
                "car": 31,
                "cyclist": 16,
                "e-scooter": 18,
                "SUV": 30,
                "motorcyclist": 35,
                "bus": 22,
                "delivery_van": 27,
                "truck": 24,
            }[road_user_class]
            speeds[road_user_class] = round(max(5.0, rng.gauss(mean_speed, 5.0)), 1)

    payload = CountsPayload(
        schema_version="1.1",
        sensor_id=SENSOR_ID,
        window_start=start,
        window_end=end,
        partial=partial,
        counts=counts,
        counts_by_direction=directional,
        avg_speed_kmh=speeds,
        config_version=CONFIG_VERSION,
        fw_version=FW_VERSION,
        produced_at=end,
    )
    return payload.model_dump(mode="json", exclude_none=True)


def generate_payloads(
    days: int = 7,
    seed: int = 0,
    start: datetime = datetime(2026, 9, 21, tzinfo=UTC),
) -> list[dict[str, Any]]:
    """Build endpoint/body records in simulated network-send order."""
    if days < 1:
        raise ValueError("days must be at least 1")
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    start = start.astimezone(UTC).replace(second=0, microsecond=0)
    rng = random.Random(seed)
    classes = load_canonical_classes()
    scheduled: list[tuple[datetime, int, str, dict[str, Any]]] = []
    sequence = 0
    totals = {name: 0 for name in classes}

    def queue(due: datetime, endpoint: str, body: dict[str, Any]) -> None:
        nonlocal sequence
        scheduled.append((due, sequence, endpoint, body))
        sequence += 1

    total_minutes = days * 24 * 60
    for minute in range(5, total_minutes + 1, 5):
        heartbeat_time = start + timedelta(minutes=minute)
        ts = heartbeat_time - timedelta(minutes=7) if minute == 11 * 60 + 5 else heartbeat_time
        heartbeat = HeartbeatPayload(
            sensor_id=SENSOR_ID,
            ts=ts,
            uptime_s=minute * 60,
            cpu_temp_c=round(48 + rng.random() * 9, 1),
            last_window_end=heartbeat_time.replace(minute=(heartbeat_time.minute // 15) * 15),
            config_version=CONFIG_VERSION,
            fw_version=FW_VERSION,
        )
        queue(heartbeat_time, "heartbeat", heartbeat.model_dump(mode="json", exclude_none=True))

    for window_index in range(days * 96):
        window_start = start + timedelta(minutes=window_index * 15)
        window_end = window_start + timedelta(minutes=15)
        # Simulate a restart at 14:07: only the remaining eight minutes are
        # counted before the next boundary, so that window is marked partial.
        partial = window_index == 14 * 4 + 0
        body = _window_body(rng, window_start, window_end, partial)
        for name, count in body["counts"].items():
            totals[name] += count
        queue(window_end, "counts", body)

        if window_end.hour == 0 and window_end.minute == 0:
            day = (window_end - timedelta(days=1)).date()
            daily_totals = {name: count for name, count in totals.items() if count >= 5}
            daily = DailyPayload(
                sensor_id=SENSOR_ID,
                day=day,
                totals=daily_totals,
                window_count=96,
                late=False,
                config_version=CONFIG_VERSION,
                fw_version=FW_VERSION,
                produced_at=window_end,
            )
            queue(window_end, "daily", daily.model_dump(mode="json", exclude_none=True))
            totals = {name: 0 for name in classes}

    # Queue a single 30-minute outage's requests and replay them at recovery.
    outage_start = start + timedelta(hours=12)
    outage_end = outage_start + timedelta(minutes=30)
    sent: list[tuple[datetime, int, str, dict[str, Any]]] = []
    for due, order, endpoint, body in sorted(scheduled, key=lambda item: (item[0], item[1])):
        send_time = outage_end if outage_start <= due < outage_end else due
        sent.append((send_time, order, endpoint, body))

    output = [
        {"endpoint": endpoint, "sent_at": send_time.isoformat(), "body": body}
        for send_time, _, endpoint, body in sorted(sent, key=lambda item: (item[0], item[1]))
    ]
    # One at-least-once resend after the original has been accepted.
    duplicate = next(record for record in output if record["endpoint"] == "counts")
    duplicate_time = datetime.fromisoformat(duplicate["sent_at"]) + timedelta(seconds=10)
    output.append({**duplicate, "sent_at": duplicate_time.isoformat()})
    output.sort(key=lambda record: record["sent_at"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--start", default="2026-09-21T00:00:00Z")
    parser.add_argument("--output", type=Path, default=Path("-"))
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    rows = generate_payloads(days=args.days, seed=args.seed, start=start)
    stream = sys.stdout if str(args.output) == "-" else args.output.open("w", encoding="utf-8")
    try:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
    finally:
        if stream is not sys.stdout:
            stream.close()


if __name__ == "__main__":
    main()
