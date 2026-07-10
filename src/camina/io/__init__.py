"""Network and persistence I/O for the CAMINA edge agent.

Modules:
    offline_buffer: SQLite FIFO outbox that survives reboots.
    http_client: shared httpx client with retries and Bearer auth.
    https_publisher: posts counts / daily / heartbeat payloads to the backend.
    config_poller: version-check + GET /config + hot-reload callback.
    schemas: pydantic models for ingest payloads and config.
"""
from __future__ import annotations

from .offline_buffer import OfflineBuffer, OutboxItem, SendOutcome

__all__ = ["OfflineBuffer", "OutboxItem", "SendOutcome"]
