"""Generate deterministic mock Dublin data for the dashboard's mock mode.

Writes JSON fixtures to ``data/mock/dublin/``, shaped like the database tables;
the dashboard reads them when ``CAMINA_DATA_SOURCE=mock``.

Eight sensors on real Dublin streets in two zones (UCD Belfield campus and the
city-centre -> UCD corridor), 21 days of 15-min windows with diurnal patterns,
per-transport window loss (WiFi / cellular), heartbeats and daily rollups.
See ``docs/simulation.md``.

Usage:
    python scripts/generate_mock_dublin.py
"""

from __future__ import annotations

import bisect
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
DAYS = 21
WINDOW_MINUTES = 15
HEARTBEAT_MINUTES = 15  # the pilot's interval (dashboard/src/lib/heartbeat.ts)

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

# One longer outage, so the dashboard's coverage line has a gap to report:
# sensor index -> (hours before the end of the data, length in hours). The
# sensor sends neither counts nor heartbeats while it is down.
OUTAGES: dict[int, tuple[int, int]] = {4: (40, 6)}  # Leeson Street Lower

# Max cellular ingest latency (seconds). Cellular is HTTPS over a cellular
# bearer, so payloads are identical to WiFi; the only real-world difference is
# a small ``produced_at`` latency jitter at ingest time. The DB-shaped readings
# fixture has no ``produced_at`` column (that field lives only in the ingest
# countsPayload), so this jitter is documented but not materialised here.
CELLULAR_LATENCY_MAX_S = 90

# Eight real Dublin streets across two zones. Each line is the stretch of road
# the sensor covers, from one junction to the next (a junction is where another
# public road or slip road joins; car-park accesses are ignored): anyone can
# join or leave at a junction, so counts only mean something between two.
# Geometry and way ids are from OpenStreetMap (© OpenStreetMap contributors,
# ODbL), fetched 2026-09-27 with one Overpass query and kept here so the
# generator stays offline and deterministic. Dual carriageways use one side.
# zone and transport drive traffic character and reporting behaviour;
# transport is also surfaced in sensors.json metadata.
# Coordinates are [lon, lat] (GeoJSON order); the sensor sits at the midpoint.
# speed_limit_kmh is the ways' OSM maxspeed (fetched 2026-09-28); where they
# differ (N11 at Montrose: 50 and 60), the limit over most of the length.
STREETS: list[dict[str, Any]] = [
    # --- UCD Belfield campus: 1 WiFi, 3 cellular ---
    {
        "id": "ucd-stillorgan-rd-entrance",
        "speed_limit_kmh": 60,
        "display_name": "UCD Stillorgan Road Entrance",
        "osm_way_ids": [25094842, 327046546],
        "coords": [
            [-6.213322, 53.3068],
            [-6.213777, 53.307087],
            [-6.214847, 53.307698],
            [-6.215857, 53.308222],
            [-6.216849, 53.308739],
            [-6.217446, 53.309037],
            [-6.218036, 53.30933],
            [-6.218819, 53.309764],
            [-6.219113, 53.30992],
            [-6.219393, 53.310083],
            [-6.219592, 53.310208],
            [-6.219739, 53.310308],
            [-6.219881, 53.310415],
            [-6.220114, 53.310617],
            [-6.220317, 53.310802],
            [-6.22051, 53.311015],
        ],
        "zone": "ucd",
        "transport": "cellular",
    },
    {
        "id": "ucd-clonskeagh-wynnsward",
        "speed_limit_kmh": 30,
        "display_name": "UCD Wynnsward Drive / Clonskeagh Entrance",
        "osm_way_ids": [32297486, 1316561310, 1444805901],
        "coords": [
            [-6.231848, 53.307831],
            [-6.231207, 53.307844],
            [-6.230974, 53.307848],
            [-6.230855, 53.307848],
            [-6.230672, 53.307857],
            [-6.230073, 53.307867],
            [-6.229908, 53.30787],
            [-6.229779, 53.307873],
            [-6.229271, 53.307867],
            [-6.228859, 53.307854],
            [-6.228345, 53.307834],
            [-6.227924, 53.307805],
            [-6.227314, 53.307749],
            [-6.226881, 53.307707],
            [-6.226697, 53.307691],
            [-6.226569, 53.307678],
            [-6.226426, 53.307652],
            [-6.2263, 53.30761],
            [-6.226155, 53.307562],
        ],
        "zone": "ucd",
        "transport": "cellular",
    },
    {
        "id": "ucd-n11-belfield-flyover",
        "speed_limit_kmh": 60,
        "display_name": "N11 Belfield Flyover",
        "osm_way_ids": [25094836, 496165839],
        "coords": [
            [-6.213412, 53.307049],
            [-6.212587, 53.306517],
            [-6.211658, 53.305857],
            [-6.211233, 53.305565],
            [-6.209773, 53.304563],
            [-6.209475, 53.304374],
            [-6.208596, 53.303784],
            [-6.208569, 53.303766],
            [-6.208478, 53.3037],
        ],
        "zone": "ucd",
        "transport": "wifi",
    },
    {
        "id": "ucd-fosters-ave-entrance",
        "speed_limit_kmh": 50,
        "display_name": "UCD Foster's Avenue Entrance",
        "osm_way_ids": [41517971],
        "coords": [
            [-6.217485, 53.300028],
            [-6.215356, 53.300899],
            [-6.213919, 53.301486],
        ],
        "zone": "ucd",
        "transport": "cellular",
    },
    # --- City-centre -> UCD access corridor: 1 WiFi, 3 cellular ---
    {
        "id": "leeson-st-lower",
        "speed_limit_kmh": 30,
        "display_name": "Leeson Street Lower",
        "osm_way_ids": [2110728, 906237416],
        "coords": [
            [-6.253312, 53.332587],
            [-6.25348, 53.332747],
            [-6.253525, 53.332788],
            [-6.253565, 53.332825],
            [-6.254003, 53.333229],
            [-6.254023, 53.333247],
            [-6.254044, 53.333267],
            [-6.254181, 53.333393],
            [-6.254726, 53.333892],
            [-6.255166, 53.334315],
            [-6.25523, 53.334376],
            [-6.255255, 53.334401],
        ],
        "zone": "corridor",
        "transport": "cellular",
    },
    {
        "id": "morehampton-rd-donnybrook",
        "speed_limit_kmh": 50,
        "display_name": "Morehampton Road, Donnybrook",
        "osm_way_ids": [33909888, 1273176962, 1314372295],
        "coords": [
            [-6.240789, 53.324921],
            [-6.240685, 53.32484],
            [-6.240649, 53.324811],
            [-6.240503, 53.324696],
            [-6.240265, 53.324509],
            [-6.240138, 53.324409],
            [-6.240104, 53.324382],
            [-6.240081, 53.324365],
            [-6.240067, 53.324353],
            [-6.240036, 53.324329],
            [-6.239585, 53.323975],
            [-6.239562, 53.323957],
            [-6.239414, 53.32384],
            [-6.239374, 53.323809],
        ],
        "zone": "corridor",
        "transport": "cellular",
    },
    {
        "id": "n11-stillorgan-rd-montrose",
        "speed_limit_kmh": 60,
        "display_name": "N11 Stillorgan Road at RTE / Montrose",
        "osm_way_ids": [33924202, 750297159, 750298029],
        "coords": [
            [-6.229255, 53.317123],
            [-6.229835, 53.317524],
            [-6.230408, 53.317906],
            [-6.230737, 53.318148],
            [-6.231479, 53.318695],
            [-6.231589, 53.318776],
        ],
        "zone": "corridor",
        "transport": "wifi",
    },
    {
        "id": "ranelagh-rd",
        "speed_limit_kmh": 50,
        "display_name": "Ranelagh Road",
        "osm_way_ids": [36819764],
        "coords": [
            [-6.259691, 53.329972],
            [-6.259553, 53.329822],
            [-6.259245, 53.329442],
            [-6.259059, 53.329164],
        ],
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

# Per-class speeds on a 50 km/h Dublin road: the mean and the spread (sd) of
# individual road users, km/h (motor traffic is rescaled per road below). Walking is about 1.3 m/s;
# e-scooters are limited to 20 km/h in Ireland. v85 lands about one sd above
# the mean: a pedestrian at 5-6 km/h, a car at 36-38.
SPEED_PROFILE: dict[str, tuple[float, float]] = {
    "person": (4.8, 0.7),
    "cyclist": (18.0, 3.5),
    "car": (32.0, 5.0),
    "e-scooter": (17.0, 2.0),
    "SUV": (31.0, 5.0),
    "motorcyclist": (35.0, 6.0),
    "bus": (23.0, 4.0),
    "delivery_van": (29.0, 5.0),
    "truck": (25.0, 4.0),
}
# A window's mean differs from the class mean by up to this fraction.
WINDOW_SPEED_JITTER = 0.05
# Motor traffic follows the road: SPEED_PROFILE is a 50 km/h road, scaled here
# by the limit (Dublin's 30 km/h streets are widely exceeded; the 60 km/h N11
# runs near 45-50), and by the time of day (rush hours slower, nights faster).
MOTOR_CLASSES = {"car", "SUV", "motorcyclist", "bus", "delivery_van", "truck"}
LIMIT_SPEED_FACTOR: dict[int, float] = {30: 0.9, 50: 1.2, 60: 1.45}


def _time_of_day_speed_factor(hour: float, weekday: int) -> float:
    if hour < 6 or hour >= 22:
        return 1.12
    rush = weekday < 5 and (7.5 <= hour < 9.5 or 16.5 <= hour < 18.5)
    return 0.85 if rush else 1.0


# Speed histograms, as the edge sends them: the lower edges of the bins in
# camina/core/counter.py SPEED_BIN_EDGES (kept stdlib-only here; a test checks
# they agree): 1 km/h to 20, 2 km/h to 60, 5 km/h to 120, the last open.
SPEED_BIN_EDGES: tuple[float, ...] = (
    tuple(range(0, 20)) + tuple(range(20, 60, 2)) + tuple(range(60, 121, 5))
)
# The edge sends a speed only over at least this many timed road users.
SPEED_K_MIN = 5


def _timed_speeds(mean_kmh: float, sd_kmh: float, n: int, rng: random.Random) -> list[float]:
    return [max(0.5, rng.gauss(mean_kmh, sd_kmh)) for _ in range(n)]


def _speed_histogram(speeds: list[float]) -> list[int]:
    hist = [0] * len(SPEED_BIN_EDGES)
    for kmh in speeds:
        hist[bisect.bisect_right(SPEED_BIN_EDGES, kmh) - 1] += 1
    return hist


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

    Each transport drops isolated windows at its ``MISSING_RATE``; a sensor in
    ``OUTAGES`` also loses a block of windows.
    """
    rng = random.Random(SEED + 1000 + idx)
    rate = MISSING_RATE[transport]
    missing: set[int] = set()
    w = 0
    while w < n_windows:
        if rng.random() < rate:
            missing.add(w)
        w += 1
    if idx in OUTAGES:
        per_hour = 60 // WINDOW_MINUTES
        hours_before_end, length = OUTAGES[idx]
        first = n_windows - hours_before_end * per_hour
        missing.update(range(first, first + length * per_hour))
    return missing


def _direction_counts(
    count: int,
    sensor_idx: int,
    class_idx: int,
    hour: float,
    weekday: int,
    rng: random.Random,
) -> tuple[int, int]:
    """Split a mock count between the street geometry's A→B and B→A directions."""
    base_share = 0.46 + 0.04 * ((sensor_idx + class_idx) % 3)
    commute_bias = 0.0
    if weekday < 5:
        commute_bias = 0.12 * math.exp(-((hour - 8.5) ** 2) / 2)
        commute_bias -= 0.12 * math.exp(-((hour - 17.5) ** 2) / 2)
    ab_share = min(0.8, max(0.2, base_share + commute_bias + rng.uniform(-0.05, 0.05)))
    ab_count = round(count * ab_share)
    return ab_count, count - ab_count


def generate() -> dict:
    rng = random.Random(SEED)
    direction_rng = random.Random(SEED + 3000)
    # Own stream, so adding histograms left every other fixture value as it was.
    speed_rng = random.Random(SEED + 4000)

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
                "speed_limit_kmh": s["speed_limit_kmh"],
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
        street_limit = STREETS[sensor_idx]["speed_limit_kmh"]
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
                class_mean, class_sd = SPEED_PROFILE[cls]
                if cls in MOTOR_CLASSES:
                    factor = LIMIT_SPEED_FACTOR[street_limit] * _time_of_day_speed_factor(
                        hour, weekday
                    )
                    class_mean, class_sd = class_mean * factor, class_sd * factor
                speed = class_mean * rng.uniform(1 - WINDOW_SPEED_JITTER, 1 + WINDOW_SPEED_JITTER)
                reading = {
                    "sensor_id": sensor["id"],
                    "window_start": window_start.isoformat(),
                    "window_end": (window_start + timedelta(minutes=WINDOW_MINUTES)).isoformat(),
                    "class_name": cls,
                    "count": count,
                    "avg_speed_kmh": round(speed, 1),
                    "partial": False,
                }
                if count >= SPEED_K_MIN:
                    # Every road user timed: the mean and the histogram agree.
                    timed = _timed_speeds(speed, class_sd, count, speed_rng)
                    reading["avg_speed_kmh"] = round(sum(timed) / len(timed), 1)
                    reading["speed_hist_kmh"] = _speed_histogram(timed)
                # Six of eight mock streets represent bidirectional coverage.
                # The remaining two exercise the API's optional direction data.
                if sensor_idx < 6:
                    ab_count, ba_count = _direction_counts(
                        count,
                        sensor_idx,
                        CLASSES.index(cls),
                        hour,
                        weekday,
                        direction_rng,
                    )
                    reading["direction_ab_count"] = ab_count
                    reading["direction_ba_count"] = ba_count
                readings.append(reading)

    # ------- heartbeats (every window the sensor was up) -------
    # A dropped window is an outage: no heartbeat either, so the dashboard can
    # tell a sensor that was down from a street that was empty.
    heartbeats = []
    per_window = WINDOW_MINUTES // HEARTBEAT_MINUTES
    for sensor_idx, sensor in enumerate(sensors):
        missing = _missing_window_set(sensor_idx, windows, sensor["transport"])
        for h in range(windows * per_window):
            if h // per_window in missing:
                continue
            ts = start + timedelta(minutes=HEARTBEAT_MINUTES * h)
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
