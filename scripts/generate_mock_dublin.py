"""Generate deterministic mock Dublin data for dashboard dev.

Outputs JSON fixtures under ``data/mock/dublin/`` that mirror the database
schema defined in ``plan/02-dashboard-vercel.md`` §8. The dashboard reads them
directly when ``DATA_SOURCE=mock`` and ignores the database, or they can be
loaded into Postgres via the (future) ``scripts/seed_mock.py`` when the
dashboard is live.

Ten sensors are placed on ten real Dublin streets with 7 days of 15-min
windows, plausible diurnal patterns, heartbeats, and daily rollups.

Usage:
    python scripts/generate_mock_dublin.py
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


SEED = 20260421
CITY = "dublin"
DAYS = 7
WINDOW_MINUTES = 15
HEARTBEAT_MINUTES = 5

CLASSES = [
    "person",
    "cyclist",
    "car",
    "e-scooter",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
]

# Ten real Dublin streets. Each LineString is a compact 2-4 point approximation
# of the segment covered by a single sensor (for visualization only — precise
# OSM geometry will come from the admin draw tool in production).
STREETS: list[dict] = [
    {
        "id": "dame-st",
        "display_name": "Dame Street",
        "osm_way_ids": [4254127],
        "coords": [[-6.2672, 53.3438], [-6.2617, 53.3440]],
    },
    {
        "id": "grafton-st",
        "display_name": "Grafton Street",
        "osm_way_ids": [4254128],
        "coords": [[-6.2601, 53.3415], [-6.2594, 53.3440]],
    },
    {
        "id": "oconnell-st-upper",
        "display_name": "O'Connell Street Upper",
        "osm_way_ids": [4254129],
        "coords": [[-6.2619, 53.3523], [-6.2612, 53.3493]],
    },
    {
        "id": "oconnell-st-lower",
        "display_name": "O'Connell Street Lower",
        "osm_way_ids": [4254130],
        "coords": [[-6.2612, 53.3493], [-6.2605, 53.3466]],
    },
    {
        "id": "parnell-st",
        "display_name": "Parnell Street",
        "osm_way_ids": [4254131],
        "coords": [[-6.2645, 53.3524], [-6.2590, 53.3526]],
    },
    {
        "id": "thomas-st",
        "display_name": "Thomas Street",
        "osm_way_ids": [4254132],
        "coords": [[-6.2810, 53.3433], [-6.2732, 53.3430]],
    },
    {
        "id": "south-great-georges-st",
        "display_name": "South Great George's Street",
        "osm_way_ids": [4254133],
        "coords": [[-6.2650, 53.3421], [-6.2648, 53.3395]],
    },
    {
        "id": "camden-st",
        "display_name": "Camden Street",
        "osm_way_ids": [4254134],
        "coords": [[-6.2656, 53.3365], [-6.2653, 53.3326]],
    },
    {
        "id": "baggot-st-lower",
        "display_name": "Baggot Street Lower",
        "osm_way_ids": [4254135],
        "coords": [[-6.2516, 53.3368], [-6.2458, 53.3354]],
    },
    {
        "id": "pearse-st",
        "display_name": "Pearse Street",
        "osm_way_ids": [4254136],
        "coords": [[-6.2544, 53.3437], [-6.2444, 53.3433]],
    },
]


def _midpoint(coords: list[list[float]]) -> tuple[float, float]:
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return lon, lat


def _bbox(coords: list[list[float]]) -> dict:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.0005
    return {
        "type": "Polygon",
        "coordinates": [[
            [min(lons) - pad, min(lats) - pad],
            [max(lons) + pad, min(lats) - pad],
            [max(lons) + pad, max(lats) + pad],
            [min(lons) - pad, max(lats) + pad],
            [min(lons) - pad, min(lats) - pad],
        ]],
    }


# Per-class baseline activity profile (counts per 15-min window at peak).
# Chosen to loosely match observed urban-mobility patterns in a European city
# centre. These are MOCK values for UI demo purposes only.
PEAK_BASELINE: dict[str, int] = {
    "person": 120,
    "cyclist": 35,
    "car": 80,
    "e-scooter": 18,
    "SUV": 22,
    "motorcyclist": 6,
    "bus": 8,
    "delivery_van": 12,
    "truck": 4,
}

# Per-class speed profile (km/h, rough averages).
SPEED_BASELINE: dict[str, float] = {
    "person": 4.2,
    "cyclist": 17.5,
    "car": 28.0,
    "e-scooter": 14.0,
    "SUV": 27.0,
    "motorcyclist": 32.0,
    "bus": 18.0,
    "delivery_van": 24.0,
    "truck": 20.0,
}


def _diurnal_factor(hour: float) -> float:
    """0.1-1.0 factor shaped by typical urban diurnal mobility pattern."""
    morning = 0.9 * math.exp(-((hour - 8.5) ** 2) / 4)
    evening = 1.0 * math.exp(-((hour - 17.5) ** 2) / 5)
    midday = 0.45 * math.exp(-((hour - 13.0) ** 2) / 10)
    night_floor = 0.08 if 0 <= hour < 6 else 0.12
    return max(night_floor, morning + evening + midday)


def _weekday_factor(weekday: int) -> float:
    return 1.0 if weekday < 5 else 0.7


def _sensor_character(idx: int) -> dict[str, float]:
    """Per-sensor modality weights — gives each sensor a distinct mix."""
    rng = random.Random(SEED + idx)
    return {cls: rng.uniform(0.55, 1.45) for cls in CLASSES}


def generate() -> dict:
    rng = random.Random(SEED)

    # ------- streets (public) -------
    streets = []
    for s in STREETS:
        streets.append({
            "id": s["id"],
            "display_name": s["display_name"],
            "osm_way_ids": s["osm_way_ids"],
            "geom": {
                "type": "MultiLineString",
                "coordinates": [s["coords"]],
            },
            "bbox": _bbox(s["coords"]),
            "city": CITY,
            "active": True,
        })

    # ------- sensors (admin-only) -------
    sensors = []
    coverage = []
    start_date = date(2026, 4, 15)
    for i, street in enumerate(STREETS):
        lon, lat = _midpoint(street["coords"])
        sensor_id = f"cam-dub-{i + 1:02d}"
        sensors.append({
            "id": sensor_id,
            "display_name": f"Dublin #{i + 1} ({street['display_name']})",
            "latitude": lat,
            "longitude": lon,
            "install_date": start_date.isoformat(),
            "active": True,
            "config_json": {
                "publish_interval_minutes": 15,
                "heartbeat_interval_minutes": 5,
                "frame_skip": 5,
                "daily_publish_time_utc": "00:00",
                "min_track_hits": 3,
            },
            "config_version": f"mock-v1-{i:02x}",
            "last_heartbeat": None,    # filled in heartbeat fixture
            "fw_version": "0.2.0",
            "notes": "MOCK data — generated by scripts/generate_mock_dublin.py",
        })
        coverage.append({"sensor_id": sensor_id, "street_id": street["id"], "weight": 1.0})

    # ------- readings (time-series) -------
    readings = []
    end = datetime(2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc)
    start = end - timedelta(days=DAYS)
    windows = int((end - start).total_seconds() // (WINDOW_MINUTES * 60))

    for sensor_idx, sensor in enumerate(sensors):
        character = _sensor_character(sensor_idx)
        for w in range(windows):
            window_start = start + timedelta(minutes=WINDOW_MINUTES * w)
            hour = window_start.hour + window_start.minute / 60.0
            time_factor = _diurnal_factor(hour) * _weekday_factor(window_start.weekday())
            for cls in CLASSES:
                peak = PEAK_BASELINE[cls]
                mean = peak * time_factor * character[cls]
                count = max(0, int(rng.gauss(mean, max(mean * 0.3, 1.5))))
                speed = SPEED_BASELINE[cls] * rng.uniform(0.85, 1.15) if count > 0 else None
                if count > 0:
                    readings.append({
                        "sensor_id": sensor["id"],
                        "window_start": window_start.isoformat(),
                        "window_end": (window_start + timedelta(minutes=WINDOW_MINUTES)).isoformat(),
                        "class_name": cls,
                        "count": count,
                        "avg_speed_kmh": round(speed, 1) if speed else None,
                        "partial": False,
                    })

    # ------- heartbeats (last 24 h only, to keep file small) -------
    heartbeats = []
    hb_start = end - timedelta(hours=24)
    hb_windows = int(24 * 60 / HEARTBEAT_MINUTES)
    for sensor in sensors:
        for h in range(hb_windows):
            ts = hb_start + timedelta(minutes=HEARTBEAT_MINUTES * h)
            heartbeats.append({
                "sensor_id": sensor["id"],
                "ts": ts.isoformat(),
                "uptime_s": int(3600 * 24 * 3 + HEARTBEAT_MINUTES * 60 * h),
                "cpu_temp_c": round(rng.uniform(45.0, 58.0), 1),
                "last_window_end": (
                    ts.replace(second=0, microsecond=0)
                    - timedelta(minutes=ts.minute % WINDOW_MINUTES)
                ).isoformat(),
                "config_version": sensor["config_version"],
            })
    # Update sensors.last_heartbeat to match
    for sensor in sensors:
        latest = max(
            (hb["ts"] for hb in heartbeats if hb["sensor_id"] == sensor["id"]),
            default=None,
        )
        sensor["last_heartbeat"] = latest

    # ------- daily rollups (per sensor, for the 7 days) -------
    daily = []
    for sensor in sensors:
        for day_offset in range(DAYS):
            day = (start + timedelta(days=day_offset)).date()
            day_readings = [
                r for r in readings
                if r["sensor_id"] == sensor["id"]
                and r["window_start"].startswith(day.isoformat())
            ]
            totals: dict[str, int] = {cls: 0 for cls in CLASSES}
            for r in day_readings:
                totals[r["class_name"]] += r["count"]
            daily.append({
                "sensor_id": sensor["id"],
                "day": day.isoformat(),
                "totals_json": totals,
                "window_count": len({r["window_start"] for r in day_readings}),
                "late": False,
                "reconciled": True,
            })

    return {
        "streets": streets,
        "sensors": sensors,
        "sensor_street_coverage": coverage,
        "sensor_readings": readings,
        "sensor_heartbeats": heartbeats,
        "sensor_daily_totals": daily,
        "meta": {
            "generated_by": "scripts/generate_mock_dublin.py",
            "seed": SEED,
            "city": CITY,
            "days": DAYS,
            "window_minutes": WINDOW_MINUTES,
            "sensor_count": len(sensors),
            "street_count": len(streets),
            "reading_count": len(readings),
        },
    }


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "data" / "mock" / "dublin"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = generate()

    # Write each table to its own file for clarity.
    for key, value in data.items():
        path = out_dir / f"{key}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
        print(f"wrote {path.relative_to(out_dir.parent.parent.parent)} "
              f"({len(value) if isinstance(value, list) else 'meta'})")

    # Also write a single combined GeoJSON for quick map preview.
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "street_id": s["id"],
                    "display_name": s["display_name"],
                },
                "geometry": s["geom"],
            }
            for s in data["streets"]
        ],
    }
    geo_path = out_dir / "streets.geojson"
    with geo_path.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
    print(f"wrote {geo_path.relative_to(out_dir.parent.parent.parent)} "
          f"({len(geojson['features'])} features)")

    print(f"\nTotal rows generated:")
    print(f"  streets:            {len(data['streets'])}")
    print(f"  sensors:            {len(data['sensors'])}")
    print(f"  coverage:           {len(data['sensor_street_coverage'])}")
    print(f"  readings:           {len(data['sensor_readings'])}")
    print(f"  heartbeats:         {len(data['sensor_heartbeats'])}")
    print(f"  daily totals:       {len(data['sensor_daily_totals'])}")


if __name__ == "__main__":
    main()
