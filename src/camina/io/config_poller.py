"""Remote-configuration version check and hot-reload.

After each successful ingest POST, the backend's response advertises a
``latest_config_version``. If that differs from the version currently applied
on the device, :class:`ConfigPoller` fetches the new configuration, validates
it, and invokes the caller-supplied ``apply`` callback.

On validation failure the previous configuration is kept and a flag is
exposed so the next heartbeat can include ``config_error: true``.
"""
from __future__ import annotations

import logging
from threading import Lock
from typing import Callable, Optional

from pydantic import ValidationError

from src.camina.io.http_client import HttpClient
from src.camina.io.schemas import SensorConfig


logger = logging.getLogger(__name__)


class ConfigPoller:
    """Version-gated config refresher.

    Args:
        sensor_id: Sensor identifier used to build the config path.
        http_client: Shared HTTP client.
        current_version: The version already applied on the device (loaded
            from persistent state at boot). Pass empty string on first boot.
        apply: Callback invoked with a validated :class:`SensorConfig` to
            mutate running state (e.g., reconfigure WindowedCounter).
        persist: Optional callback invoked with the new version string once
            ``apply`` returns; use this to write state to disk.
    """

    def __init__(
        self,
        sensor_id: str,
        http_client: HttpClient,
        current_version: str,
        apply: Callable[[SensorConfig], None],
        persist: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._sensor_id = sensor_id
        self._http = http_client
        self._apply = apply
        self._persist = persist
        self._version = current_version
        self._last_error: Optional[str] = None
        self._lock = Lock()

    # ---------- Public API ----------

    @property
    def current_version(self) -> str:
        with self._lock:
            return self._version

    @property
    def has_error(self) -> bool:
        with self._lock:
            return self._last_error is not None

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def check(self, latest_version: Optional[str]) -> bool:
        """Compare the backend-advertised version with the current one.

        If they differ, fetch ``/config``, validate, and apply. Returns
        ``True`` if a new configuration was applied, ``False`` otherwise.
        """
        if not latest_version:
            return False
        with self._lock:
            if latest_version == self._version:
                return False

        try:
            response = self._http.request(
                "GET", f"/v1/sensors/{self._sensor_id}/config"
            )
        except Exception:
            logger.exception("Config fetch failed for sensor %s", self._sensor_id)
            with self._lock:
                self._last_error = "fetch_failed"
            return False

        try:
            config = SensorConfig.model_validate_json(response.content)
        except ValidationError as exc:
            logger.error(
                "Invalid config payload for sensor %s: %s", self._sensor_id, exc
            )
            with self._lock:
                self._last_error = "invalid_payload"
            return False

        if config.config_version == self._version:
            # Backend changed and then reverted; nothing to do.
            with self._lock:
                self._last_error = None
            return False

        try:
            self._apply(config)
        except Exception:
            logger.exception("Apply callback raised for sensor %s", self._sensor_id)
            with self._lock:
                self._last_error = "apply_failed"
            return False

        with self._lock:
            self._version = config.config_version
            self._last_error = None

        if self._persist is not None:
            try:
                self._persist(config.config_version)
            except Exception:
                logger.exception("Persist callback raised for sensor %s", self._sensor_id)

        logger.info(
            "Applied new config version %s to sensor %s",
            config.config_version, self._sensor_id,
        )
        return True

    def force_refresh(self) -> bool:
        """Fetch and apply regardless of the advertised version.

        Useful on boot to synchronize with the backend's latest config when
        persisted state might be stale.
        """
        with self._lock:
            # Pretend our current version is empty to force a mismatch.
            previous = self._version
            self._version = ""
        try:
            return self.check(latest_version="__force__")
        finally:
            with self._lock:
                # If check() didn't update us, restore.
                if not self._version:
                    self._version = previous


__all__ = ["ConfigPoller"]
