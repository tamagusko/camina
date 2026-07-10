"""Minimal ``sd_notify(3)`` client (stdlib-only).

Sends readiness and watchdog keep-alive datagrams to the systemd notification
socket advertised via ``$NOTIFY_SOCKET``. Used by the sensor daemon under a
``Type=notify`` unit with ``WatchdogSec=300`` so a stalled main loop is
restarted automatically.

Design notes:
    - No-op when ``$NOTIFY_SOCKET`` is unset (i.e. run outside systemd, or in
      CI/tests), so importing/constructing is always safe.
    - Handles the abstract-namespace form (leading ``@``) of the socket path by
      replacing the ``@`` with a leading NUL byte, per the systemd protocol.
    - stdlib-only; must not import ``core/`` or ``io/``.
"""
from __future__ import annotations

import logging
import os
import socket
from typing import Optional


logger = logging.getLogger(__name__)

# Sentinel distinguishing "read $NOTIFY_SOCKET from the environment" (default)
# from "explicitly disabled" (pass ``socket_path=""``), which tests rely on.
_USE_ENV = object()


class SystemdNotifier:
    """Thin wrapper over an ``AF_UNIX`` datagram socket to ``$NOTIFY_SOCKET``.

    Args:
        socket_path: Notification socket path. Defaults to reading
            ``$NOTIFY_SOCKET``; pass an explicit path (e.g. a fake socket in
            tests) or ``""`` to force the notifier disabled.
    """

    def __init__(self, socket_path: object = _USE_ENV) -> None:
        raw = os.environ.get("NOTIFY_SOCKET") if socket_path is _USE_ENV else socket_path
        self._addr: Optional[str] = self._resolve_addr(raw)  # type: ignore[arg-type]
        self._sock: Optional[socket.socket] = None
        if self._addr is not None:
            try:
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            except OSError:
                logger.warning("Could not open sd_notify socket", exc_info=True)
                self._addr = None

    @property
    def enabled(self) -> bool:
        """``True`` when a usable notification socket is configured."""
        return self._sock is not None and self._addr is not None

    def ready(self) -> bool:
        """Signal ``READY=1`` (service start-up complete)."""
        return self.notify("READY=1")

    def watchdog(self) -> bool:
        """Signal ``WATCHDOG=1`` (keep-alive; resets ``WatchdogSec``)."""
        return self.notify("WATCHDOG=1")

    def notify(self, state: str) -> bool:
        """Send a raw sd_notify state line. Returns ``True`` if sent."""
        if not self.enabled:
            return False
        try:
            self._sock.sendto(state.encode("utf-8"), self._addr)  # type: ignore[union-attr]
            return True
        except OSError:
            logger.warning("sd_notify send failed for state %r", state, exc_info=True)
            return False

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    @staticmethod
    def _resolve_addr(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        # Abstract namespace: systemd advertises a leading '@' which maps to a
        # NUL-prefixed AF_UNIX name.
        if raw.startswith("@"):
            return "\0" + raw[1:]
        return raw


__all__ = ["SystemdNotifier"]
