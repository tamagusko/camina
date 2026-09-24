"""Pydantic models for the ingest payloads and the remote sensor config.

The dashboard validates the same shapes with zod (``dashboard/src/lib/schemas.ts``);
``docs/PROTOCOL.md`` describes the wire format.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"


# --------------------------------------------------------------------- Payloads


class CountsPayload(BaseModel):
    """Windowed counts POSTed to `/sensors/{id}/counts`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    sensor_id: str
    window_start: datetime
    window_end: datetime
    partial: bool
    counts: dict[str, int] = Field(default_factory=dict)
    avg_speed_kmh: dict[str, float] = Field(default_factory=dict)
    config_version: str
    fw_version: str
    produced_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @field_validator("window_start", "window_end", "produced_at")
    @classmethod
    def _must_be_utc_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


class DailyPayload(BaseModel):
    """Per-day cumulative totals POSTed to `/sensors/{id}/daily`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    sensor_id: str
    day: date
    totals: dict[str, int]
    window_count: int
    late: bool = False
    config_version: str
    fw_version: str
    produced_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @field_validator("produced_at")
    @classmethod
    def _produced_at_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("produced_at must be timezone-aware")
        return v.astimezone(timezone.utc)


class HeartbeatPayload(BaseModel):
    """Status + telemetry POSTed to `/sensors/{id}/heartbeat`."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    uptime_s: int
    cpu_temp_c: float | None = None
    last_window_end: datetime | None = None
    config_version: str
    fw_version: str
    auth_error: bool = False
    config_error: bool = False

    @field_validator("ts", "last_window_end")
    @classmethod
    def _utc_aware(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


# --------------------------------------------------------------------- Config


class SensorConfig(BaseModel):
    """Remote configuration payload returned by `GET /sensors/{id}/config`."""

    model_config = ConfigDict(extra="forbid")

    config_version: str
    publish_interval_minutes: int = Field(gt=0, le=1440)
    heartbeat_interval_minutes: int = Field(gt=0, le=60)
    daily_publish_time_utc: str = "00:00"
    detection_zone: dict[str, Any] | None = None
    frame_skip: int = Field(ge=1, le=120)
    min_track_hits: int = Field(ge=1, le=20)

    @field_validator("daily_publish_time_utc")
    @classmethod
    def _valid_time(cls, v: str) -> str:
        # Accept 'HH:MM' in UTC.
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("daily_publish_time_utc must be 'HH:MM'")
        hh, mm = parts
        if not (hh.isdigit() and mm.isdigit()):
            raise ValueError("daily_publish_time_utc must be numeric 'HH:MM'")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError("daily_publish_time_utc out of range")
        return v


class IngestResponse(BaseModel):
    """Response envelope returned by every ingest POST."""

    model_config = ConfigDict(extra="allow")

    ok: bool
    latest_config_version: str


__all__ = [
    "SCHEMA_VERSION",
    "CountsPayload",
    "DailyPayload",
    "HeartbeatPayload",
    "IngestResponse",
    "SensorConfig",
]
