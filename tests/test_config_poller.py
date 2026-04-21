"""Unit tests for ConfigPoller."""
from __future__ import annotations

import json
from typing import Iterator

import httpx
import pytest

from src.camina.io.config_poller import ConfigPoller
from src.camina.io.http_client import HttpClient, RetryPolicy
from src.camina.io.schemas import SensorConfig


def _fast_retry() -> RetryPolicy:
    return RetryPolicy(max_attempts=2, base_delay_s=0.0, max_delay_s=0.0, jitter=0.0)


def _valid_config(version: str = "v2") -> dict:
    return {
        "config_version": version,
        "publish_interval_minutes": 15,
        "heartbeat_interval_minutes": 5,
        "daily_publish_time_utc": "00:00",
        "detection_zone": None,
        "frame_skip": 5,
        "min_track_hits": 3,
    }


def _make(
    *,
    responses: list[httpx.Response],
    apply_calls: list[SensorConfig],
    persist_calls: list[str],
    current_version: str,
) -> tuple[ConfigPoller, HttpClient]:
    idx = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses[idx["i"]]
        idx["i"] += 1
        return response

    transport = httpx.MockTransport(handler)
    client = HttpClient(
        "https://api.test", token="t", retry=_fast_retry(), transport=transport
    )
    poller = ConfigPoller(
        sensor_id="cam-01",
        http_client=client,
        current_version=current_version,
        apply=apply_calls.append,
        persist=persist_calls.append,
    )
    return poller, client


# ---------- Happy path ----------


def test_check_skips_when_versions_match() -> None:
    applied: list[SensorConfig] = []
    persisted: list[str] = []
    poller, client = _make(
        responses=[],  # no HTTP should happen
        apply_calls=applied,
        persist_calls=persisted,
        current_version="v1",
    )
    try:
        changed = poller.check("v1")
        assert changed is False
        assert applied == []
    finally:
        client.close()


def test_check_fetches_and_applies_on_mismatch() -> None:
    applied: list[SensorConfig] = []
    persisted: list[str] = []
    poller, client = _make(
        responses=[httpx.Response(200, json=_valid_config("v2"))],
        apply_calls=applied,
        persist_calls=persisted,
        current_version="v1",
    )
    try:
        changed = poller.check("v2")
        assert changed is True
        assert len(applied) == 1
        assert applied[0].config_version == "v2"
        assert poller.current_version == "v2"
        assert persisted == ["v2"]
        assert poller.has_error is False
    finally:
        client.close()


def test_check_ignores_empty_latest_version() -> None:
    applied: list[SensorConfig] = []
    poller, client = _make(
        responses=[],
        apply_calls=applied,
        persist_calls=[],
        current_version="v1",
    )
    try:
        assert poller.check(None) is False
        assert poller.check("") is False
    finally:
        client.close()


# ---------- Failure modes ----------


def test_fetch_failure_keeps_previous_config() -> None:
    applied: list[SensorConfig] = []
    poller, client = _make(
        responses=[httpx.Response(503), httpx.Response(503)],
        apply_calls=applied,
        persist_calls=[],
        current_version="v1",
    )
    try:
        changed = poller.check("v2")
        assert changed is False
        assert poller.current_version == "v1"
        assert poller.has_error is True
        assert poller.last_error == "fetch_failed"
    finally:
        client.close()


def test_invalid_payload_keeps_previous_config() -> None:
    applied: list[SensorConfig] = []
    persisted: list[str] = []
    bad_payload = {
        "config_version": "v2",
        "publish_interval_minutes": 0,  # invalid — gt=0
        "heartbeat_interval_minutes": 5,
        "daily_publish_time_utc": "00:00",
        "detection_zone": None,
        "frame_skip": 5,
        "min_track_hits": 3,
    }
    poller, client = _make(
        responses=[httpx.Response(200, json=bad_payload)],
        apply_calls=applied,
        persist_calls=persisted,
        current_version="v1",
    )
    try:
        changed = poller.check("v2")
        assert changed is False
        assert applied == []
        assert poller.current_version == "v1"
        assert poller.has_error is True
        assert poller.last_error == "invalid_payload"
    finally:
        client.close()


def test_apply_failure_is_recorded() -> None:
    def bad_apply(cfg: SensorConfig) -> None:
        raise RuntimeError("kaboom")

    responses = [httpx.Response(200, json=_valid_config("v2"))]
    idx = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        r = responses[idx["i"]]
        idx["i"] += 1
        return r

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    poller = ConfigPoller(
        sensor_id="cam-01",
        http_client=client,
        current_version="v1",
        apply=bad_apply,
    )
    try:
        changed = poller.check("v2")
        assert changed is False
        assert poller.current_version == "v1"
        assert poller.has_error is True
        assert poller.last_error == "apply_failed"
    finally:
        client.close()


def test_successful_apply_clears_prior_error() -> None:
    applied: list[SensorConfig] = []
    responses = [
        httpx.Response(503),                         # first attempt fails
        httpx.Response(503),                         # retry fails
        httpx.Response(200, json=_valid_config("v3")),  # later success
    ]
    idx = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        r = responses[idx["i"]]
        idx["i"] += 1
        return r

    transport = httpx.MockTransport(handler)
    client = HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport)
    poller = ConfigPoller(
        sensor_id="cam-01",
        http_client=client,
        current_version="v1",
        apply=applied.append,
    )
    try:
        poller.check("v2")
        assert poller.has_error is True
        poller.check("v3")
        assert poller.has_error is False
        assert poller.current_version == "v3"
    finally:
        client.close()
