"""Generate deterministic mock Dublin data for the dashboard's mock mode.

Writes JSON fixtures to ``data/mock/dublin/``, shaped like the database tables;
the dashboard reads them when ``CAMINA_DATA_SOURCE=mock``.

Eight sensors on real Dublin streets in two zones (UCD Belfield campus and the
city-centre -> UCD corridor), 14 days of 15-min windows with diurnal patterns,
per-transport window loss (WiFi / cellular), heartbeats and daily rollups.
See ``docs/simulation.md``.

Usage:
    python scripts/generate_mock_dublin.py
"""

from __future__ import annotations

import json
import logging
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SEED = 20260421
CITY = "dublin"
DAYS = 14
WINDOW_MINUTES = 15
HEARTBEAT_MINUTES = 5

# Canonical 9-class taxonomy. Kept in sync with the dashboard's
# ``ROAD_USER_CLASSES`` (dashboard/src/lib/types.ts).
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

# Transport reporting model ------------------------------------------------
# Fraction of 15-min windows dropped per transport (brief outages / uplink
# loss).
MISSING_RATE: dict[str, float] = {
    "wifi": 0.005,  # brief WiFi/HTTPS outages
    "cellular": 0.015,  # cellular bearer, slightly less reliable
}

# Max cellular ingest latency (seconds). Cellular is HTTPS over a cellular
# bearer, so payloads are identical to WiFi; the only real-world difference is
# a small ``produced_at`` latency jitter at ingest time. The DB-shaped readings
# fixture has no ``produced_at`` column (that field lives only in the ingest
# countsPayload), so this jitter is documented but not materialised here.
CELLULAR_LATENCY_MAX_S = 90

# Eight real Dublin streets across two zones. Each LineString is a compact
# 2-point approximation of the segment covered by a single sensor (for
# visualization only — precise OSM geometry will come from the admin draw tool
# in production). ``zone`` and ``transport`` drive traffic character and
# reporting behaviour; ``transport`` is also surfaced in sensors.json metadata.
# Coordinates are [lon, lat] (GeoJSON order); the sensor sits at the midpoint.
STREETS: list[dict[str, Any]] = [
    # --- UCD Belfield campus: 1 WiFi, 3 cellular ---
    {
        "id": "ucd-stillorgan-rd-entrance",
        "display_name": "UCD Stillorgan Road Entrance",
        "osm_way_ids": [4254201],
        "coords": [[-6.22520, 53.30630], [-6.22320, 53.30710]],
        "zone": "ucd",
        "transport": "cellular",
    },
    {
        "id": "ucd-clonskeagh-wynnsward",
        "display_name": "UCD Wynnsward Drive / Clonskeagh Entrance",
        "osm_way_ids": [4254202],
        "coords": [[-6.22900, 53.30940], [-6.22700, 53.31020]],
        "zone": "ucd",
        "transport": "cellular",
    },
    {
        "id": "ucd-n11-belfield-flyover",
        "display_name": "N11 Belfield Flyover",
        "osm_way_ids": [4254203],
        "coords": [[-6.22450, 53.30460], [-6.22250, 53.30540]],
        "zone": "ucd",
        "transport": "wifi",
    },
    {
        "id": "ucd-fosters-ave-entrance",
        "display_name": "UCD Foster's Avenue Entrance",
        "osm_way_ids": [4254204],
        "coords": [[-6.22240, 53.30250], [-6.22040, 53.30330]],
        "zone": "ucd",
        "transport": "cellular",
    },
    # --- City-centre -> UCD access corridor: 1 WiFi, 3 cellular ---
    {
        "id": "leeson-st-lower",
        "display_name": "Leeson Street Lower",
        "osm_way_ids": [4254205],
        "coords": [[-6.25330, 53.33280], [-6.25130, 53.33360]],
        "zone": "corridor",
        "transport": "cellular",
    },
    {
        "id": "morehampton-rd-donnybrook",
        "display_name": "Morehampton Road, Donnybrook",
        "osm_way_ids": [4254206],
        "coords": [[-6.23950, 53.32490], [-6.23750, 53.32570]],
        "zone": "corridor",
        "transport": "cellular",
    },
    {
        "id": "n11-stillorgan-rd-montrose",
        "display_name": "N11 Stillorgan Road at RTE / Montrose",
        "osm_way_ids": [4254207],
        "coords": [[-6.23060, 53.31680], [-6.22860, 53.31760]],
        "zone": "corridor",
        "transport": "wifi",
    },
    {
        "id": "ranelagh-rd",
        "display_name": "Ranelagh Road",
        "osm_way_ids": [4254208],
        "coords": [[-6.25650, 53.32510], [-6.25450, 53.32590]],
        "zone": "corridor",
        "transport": "cellular",
    },
]


def _midpoint(coords: list[list[float]]) -> tuple[float, float]:
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return round(lon, 5), round(lat, 5)


def _bbox(coords: list[list[float]]) -> dict:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.0005
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min(lons) - pad, min(lats) - pad],
                [max(lons) + pad, min(lats) - pad],
                [max(lons) + pad, max(lats) + pad],
                [min(lons) - pad, max(lats) + pad],
                [min(lons) - pad, min(lats) - pad],
            ]
        ],
    }


# Per-class baseline activity profile (counts per 15-min window at peak).
# Chosen to loosely match observed urban-mobility patterns in a European city.
# These are MOCK values for UI demo purposes only.
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

# Zone class weighting. UCD sensors skew pedestrian / cyclist / e-scooter
# heavy (campus mobility); corridor sensors skew car / bus / freight heavy
# (arterial commuter traffic).
ZONE_CLASS_WEIGHTS: dict[str, dict[str, float]] = {
    "ucd": {
        "person": 1.40,
        "cyclist": 1.50,
        "car": 0.65,
        "e-scooter": 1.40,
        "SUV": 0.60,
        "motorcyclist": 0.90,
        "bus": 0.55,
        "delivery_van": 0.80,
        "truck": 0.50,
    },
    "corridor": {
        "person": 0.70,
        "cyclist": 0.85,
        "car": 1.35,
        "e-scooter": 0.80,
        "SUV": 1.25,
        "motorcyclist": 1.10,
        "bus": 1.60,
        "delivery_van": 1.25,
        "truck": 1.30,
    },
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


def _commuter_boost(hour: float, weekday: int, zone: str) -> float:
    """Sharpen weekday AM/PM peaks for UCD campus sensors."""
    if zone != "ucd" or weekday >= 5:
        return 1.0
    am = 0.6 * math.exp(-((hour - 8.5) ** 2) / 1.5)
    pm = 0.6 * math.exp(-((hour - 17.5) ** 2) / 1.5)
    return 1.0 + am + pm


def _sensor_character(idx: int) -> dict[str, float]:
    """Per-sensor modality weights — gives each sensor a distinct mix."""
    rng = random.Random(SEED + idx)
    return {cls: rng.uniform(0.55, 1.45) for cls in CLASSES}


def _missing_window_set(idx: int, n_windows: int, transport: str) -> set[int]:
    """Deterministic set of dropped window indices for a sensor.

    Each transport drops isolated windows at its ``MISSING_RATE``.
    """
    rng = random.Random(SEED + 1000 + idx)
    rate = MISSING_RATE[transport]
    missing: set[int] = set()
    w = 0
    while w < n_windows:
        if rng.random() < rate:
            missing.add(w)
        w += 1
    return missing


def generate() -> dict:
    rng = random.Random(SEED)

    # ------- streets (public) -------
    streets = []
    for s in STREETS:
        streets.append(
            {
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
            }
        )

    # ------- sensors (admin-only) -------
    sensors = []
    sensor_zone: list[str] = []
    coverage = []
    start_date = date(2026, 4, 15)
    for i, street in enumerate(STREETS):
        lon, lat = _midpoint(street["coords"])
        sensor_id = f"cam-dub-{i + 1:02d}"
        sensors.append(
            {
                "id": sensor_id,
                "display_name": f"Dublin #{i + 1} ({street['display_name']})",
                "latitude": lat,
                "longitude": lon,
                "install_date": start_date.isoformat(),
                "active": True,
                # Transport is dashboard-internal sensor metadata only. It is NOT a
                # field on any ingest payload validated by dashboard schemas.ts.
                "transport": street["transport"],
                "config_json": {
                    "publish_interval_minutes": 15,
                    "heartbeat_interval_minutes": 5,
                    "frame_skip": 5,
                    "daily_publish_time_utc": "00:00",
                    "min_track_hits": 3,
                },
                "config_version": f"mock-v1-{i:02x}",
                "last_heartbeat": None,  # filled in heartbeat fixture (WiFi/cell)
                "fw_version": "0.2.0",
                "notes": "MOCK data — generated by scripts/generate_mock_dublin.py",
            }
        )
        sensor_zone.append(street["zone"])
        coverage.append(
            {
                "sensor_id": sensor_id,
                "street_id": street["id"],
                "weight": 1.0,
            }
        )

    # ------- readings (time-series) -------
    readings = []
    end = datetime(2026, 4, 21, 0, 0, 0, tzinfo=timezone.utc)
    start = end - timedelta(days=DAYS)
    windows = int((end - start).total_seconds() // (WINDOW_MINUTES * 60))

    gap_stats: dict[str, dict[str, int]] = {
        t: {"sensors": 0, "windows_missing": 0} for t in MISSING_RATE
    }

    for sensor_idx, sensor in enumerate(sensors):
        transport = sensor["transport"]
        zone = sensor_zone[sensor_idx]
        character = _sensor_character(sensor_idx)
        missing = _missing_window_set(sensor_idx, windows, transport)
        gap_stats[transport]["sensors"] += 1
        gap_stats[transport]["windows_missing"] += len(missing)

        for w in range(windows):
            if w in missing:
                continue
            window_start = start + timedelta(minutes=WINDOW_MINUTES * w)
            hour = window_start.hour + window_start.minute / 60.0
            weekday = window_start.weekday()
            time_factor = (
                _diurnal_factor(hour)
                * _weekday_factor(weekday)
                * _commuter_boost(hour, weekday, zone)
            )

            full_counts: dict[str, int] = {}
            for cls in CLASSES:
                mean = (
                    PEAK_BASELINE[cls]
                    * time_factor
                    * character[cls]
                    * ZONE_CLASS_WEIGHTS[zone][cls]
                )
                full_counts[cls] = max(0, int(rng.gauss(mean, max(mean * 0.3, 1.5))))

            for cls in CLASSES:
                count = full_counts[cls]
                if count <= 0:
                    continue
                speed = SPEED_BASELINE[cls] * rng.uniform(0.85, 1.15)
                readings.append(
                    {
                        "sensor_id": sensor["id"],
                        "window_start": window_start.isoformat(),
                        "window_end": (
                            window_start + timedelta(minutes=WINDOW_MINUTES)
                        ).isoformat(),
                        "class_name": cls,
                        "count": count,
                        "avg_speed_kmh": round(speed, 1),
                        "partial": False,
                    }
                )

    # ------- heartbeats (last 24 h only) -------
    heartbeats = []
    hb_start = end - timedelta(hours=24)
    hb_windows = int(24 * 60 / HEARTBEAT_MINUTES)
    for sensor in sensors:
        for h in range(hb_windows):
            ts = hb_start + timedelta(minutes=HEARTBEAT_MINUTES * h)
            heartbeats.append(
                {
                    "sensor_id": sensor["id"],
                    "ts": ts.isoformat(),
                    "uptime_s": int(3600 * 24 * 3 + HEARTBEAT_MINUTES * 60 * h),
                    "cpu_temp_c": round(rng.uniform(45.0, 58.0), 1),
                    "last_window_end": (
                        ts.replace(second=0, microsecond=0)
                        - timedelta(minutes=ts.minute % WINDOW_MINUTES)
                    ).isoformat(),
                    "config_version": sensor["config_version"],
                }
            )
    # Update sensors.last_heartbeat to match.
    for sensor in sensors:
        latest = max(
            (hb["ts"] for hb in heartbeats if hb["sensor_id"] == sensor["id"]),
            default=None,
        )
        sensor["last_heartbeat"] = latest

    # ------- daily rollups (per sensor, for the DAYS days) -------
    daily = []
    for sensor in sensors:
        for day_offset in range(DAYS):
            day = (start + timedelta(days=day_offset)).date()
            day_readings = [
                r
                for r in readings
                if r["sensor_id"] == sensor["id"] and r["window_start"].startswith(day.isoformat())
            ]
            totals: dict[str, int] = {cls: 0 for cls in CLASSES}
            for r in day_readings:
                totals[r["class_name"]] += r["count"]
            daily.append(
                {
                    "sensor_id": sensor["id"],
                    "day": day.isoformat(),
                    "totals_json": totals,
                    "window_count": len({r["window_start"] for r in day_readings}),
                    "late": False,
                    "reconciled": True,
                }
            )

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
            "transport_counts": {
                t: sum(1 for s in sensors if s["transport"] == t) for t in MISSING_RATE
            },
            "gap_stats": gap_stats,
        },
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out_dir = Path(__file__).resolve().parent.parent / "data" / "mock" / "dublin"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = generate()

    # Write each table to its own file for clarity.
    root = out_dir.parent.parent.parent
    for key, value in data.items():
        path = out_dir / f"{key}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
        logger.info(
            "wrote %s (%s)",
            path.relative_to(root),
            len(value) if isinstance(value, list) else "meta",
        )

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
    logger.info("wrote %s (%s features)", geo_path.relative_to(root), len(geojson["features"]))

    meta = data["meta"]
    logger.info("Total rows generated:")
    logger.info("  streets:            %d", len(data["streets"]))
    logger.info("  sensors:            %d  %s", len(data["sensors"]), meta["transport_counts"])
    logger.info("  coverage:           %d", len(data["sensor_street_coverage"]))
    logger.info("  readings:           %d", len(data["sensor_readings"]))
    logger.info("  heartbeats:         %d", len(data["sensor_heartbeats"]))
    logger.info("  daily totals:       %d", len(data["sensor_daily_totals"]))
    logger.info("Gap stats (windows dropped per transport): %s", meta["gap_stats"])


if __name__ == "__main__":
    main()
