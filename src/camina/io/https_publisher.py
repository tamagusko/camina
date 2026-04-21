"""HTTPS publisher for ingest payloads.

Wraps :class:`HttpClient` with three domain methods (counts / daily /
heartbeat) and a one-call ``sync`` pathway that (a) drains the offline
buffer, (b) sends the fresh payload, and (c) reports the server's
advertised config version so the caller can refresh configuration.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from src.camina.core.counter import DailySnapshot, WindowSnapshot
from src.camina.io.http_client import HttpClient
from src.camina.io.offline_buffer import OfflineBuffer, OutboxItem
from src.camina.io.schemas import (
    CountsPayload,
    DailyPayload,
    HeartbeatPayload,
    IngestResponse,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublisherResult:
    """Outcome of a publish attempt from the caller's perspective."""

    delivered: bool          # True → backend accepted (in real time OR via drain)
    enqueued: bool           # True → request failed and was buffered for later
    latest_config_version: Optional[str]


class HttpsPublisher:
    """Publish ingest payloads and drain the offline outbox opportunistically.

    Each POST carries an idempotency key so the backend can deduplicate
    retries on ``(sensor_id, window_start)`` primary keys.
    """

    def __init__(
        self,
        sensor_id: str,
        http_client: HttpClient,
        outbox: OfflineBuffer,
    ) -> None:
        self._sensor_id = sensor_id
        self._http = http_client
        self._outbox = outbox

    # ---------- Public high-level API ----------

    def post_counts(
        self,
        snapshot: WindowSnapshot,
        config_version: str,
        fw_version: str,
        avg_speed_kmh: Optional[dict[str, float]] = None,
    ) -> PublisherResult:
        payload = CountsPayload(
            sensor_id=self._sensor_id,
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
            partial=snapshot.partial,
            counts=snapshot.counts,
            avg_speed_kmh=avg_speed_kmh or {},
            config_version=config_version,
            fw_version=fw_version,
        )
        return self._send("counts", f"/v1/sensors/{self._sensor_id}/counts", payload)

    def post_daily(
        self,
        snapshot: DailySnapshot,
        config_version: str,
        fw_version: str,
    ) -> PublisherResult:
        payload = DailyPayload(
            sensor_id=self._sensor_id,
            day=snapshot.day,
            totals=snapshot.totals,
            window_count=snapshot.window_count,
            late=snapshot.late,
            config_version=config_version,
            fw_version=fw_version,
        )
        return self._send("daily", f"/v1/sensors/{self._sensor_id}/daily", payload)

    def post_heartbeat(self, heartbeat: HeartbeatPayload) -> PublisherResult:
        return self._send(
            "heartbeat",
            f"/v1/sensors/{self._sensor_id}/heartbeat",
            heartbeat,
        )

    def drain_outbox(self, max_items: int = 50) -> int:
        """Try to flush up to ``max_items`` buffered messages. Returns delivered count."""
        return self._outbox.drain(self._send_outbox_item, max_items=max_items)

    # ---------- Internal ----------

    def _send(
        self,
        endpoint_label: str,
        path: str,
        payload: BaseModel,
    ) -> PublisherResult:
        body = payload.model_dump_json(by_alias=True).encode()
        # Try to drain whatever we buffered earlier first (no-op if empty).
        try:
            self._outbox.drain(self._send_outbox_item, max_items=10)
        except Exception:
            logger.exception("drain_outbox raised (ignored, continuing)")

        try:
            response = self._http.request(
                "POST",
                path,
                content=body,
                idempotency_key=str(uuid.uuid4()),
            )
        except Exception:
            logger.warning(
                "Publish %s failed; enqueuing to offline buffer", endpoint_label
            )
            self._outbox.enqueue(endpoint_label, body)
            return PublisherResult(delivered=False, enqueued=True, latest_config_version=None)

        parsed = self._parse_response(response.content)
        return PublisherResult(
            delivered=True,
            enqueued=False,
            latest_config_version=parsed.latest_config_version if parsed else None,
        )

    def _send_outbox_item(self, item: OutboxItem) -> bool:
        path = f"/v1/sensors/{self._sensor_id}/{item.endpoint}"
        try:
            self._http.request(
                "POST",
                path,
                content=item.payload,
                idempotency_key=f"outbox-{item.id}",
            )
            return True
        except Exception:
            logger.warning(
                "Outbox item %d (%s) failed to send", item.id, item.endpoint
            )
            return False

    @staticmethod
    def _parse_response(content: bytes) -> Optional[IngestResponse]:
        if not content:
            return None
        try:
            return IngestResponse.model_validate_json(content)
        except Exception:
            logger.warning("Unparseable ingest response: %r", content[:200])
            return None


__all__ = ["HttpsPublisher", "PublisherResult"]
