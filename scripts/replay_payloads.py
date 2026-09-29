#!/usr/bin/env python3
"""Replay a generated JSONL sensor stream to a dashboard ingest API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def replay(path: Path, base_url: str, token: str, speed: float = 1.0) -> int:
    """POST records in file order; return the number of non-2xx responses."""
    if speed <= 0:
        raise ValueError("speed must be positive")
    previous: datetime | None = None
    failures = 0
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                endpoint = record["endpoint"]
                if endpoint not in {"counts", "daily", "heartbeat"}:
                    raise ValueError(f"unsupported endpoint {endpoint!r}")
                body = record["body"]
                sent_at = datetime.fromisoformat(record["sent_at"].replace("Z", "+00:00"))
                sensor_id = body["sensor_id"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid JSONL record on line {line_number}: {exc}") from exc

            if previous is not None:
                delay = max(0.0, (sent_at - previous).total_seconds()) / speed
                if delay:
                    time.sleep(delay)
            previous = sent_at

            url = (
                f"{base_url.rstrip('/')}/api/ingest/sensors/{quote(sensor_id, safe='')}/{endpoint}"
            )
            request = Request(
                url,
                data=json.dumps(body, separators=(",", ":")).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
            except HTTPError as exc:
                status = exc.code
            except URLError as exc:
                status = 0
                print(f"{endpoint}: network error: {exc.reason}", file=sys.stderr)
            print(f"{endpoint}: HTTP {status}")
            failures += status < 200 or status >= 300
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payloads", type=Path, help="JSONL payload file")
    parser.add_argument("base_url", help="dashboard base URL, e.g. https://camina.example")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="replay time multiplier (e.g. 60 compresses 1h to 1m)",
    )
    args = parser.parse_args()
    token = os.environ.get("CAMINA_SENSOR_TOKEN")
    if not token:
        parser.error("CAMINA_SENSOR_TOKEN must be set in the environment")
    try:
        failures = replay(args.payloads, args.base_url, token, speed=args.speed)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
