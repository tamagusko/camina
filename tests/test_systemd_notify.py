"""Unit tests for the stdlib-only sd_notify client (M8, H5-clock watchdog)."""
from __future__ import annotations

import shutil
import socket
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

from src.camina.utils.systemd_notify import SystemdNotifier


@pytest.fixture()
def short_sock_dir() -> Iterator[str]:
    """A short-path temp dir: AF_UNIX socket paths must fit ~104 bytes, which
    pytest's ``tmp_path`` blows past on macOS."""
    path = tempfile.mkdtemp(prefix="camina-nt-", dir="/tmp")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _bind_datagram_server(path: str) -> socket.socket:
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    srv.bind(path)
    srv.settimeout(2.0)
    return srv


def test_ready_and_watchdog_reach_fake_socket(short_sock_dir: str) -> None:
    sock_path = str(Path(short_sock_dir) / "notify.sock")
    srv = _bind_datagram_server(sock_path)
    notifier = SystemdNotifier(socket_path=sock_path)
    try:
        assert notifier.enabled is True

        assert notifier.ready() is True
        assert srv.recvfrom(64)[0] == b"READY=1"

        assert notifier.watchdog() is True
        assert srv.recvfrom(64)[0] == b"WATCHDOG=1"
    finally:
        notifier.close()
        srv.close()


def test_disabled_when_socket_path_empty() -> None:
    notifier = SystemdNotifier(socket_path="")
    assert notifier.enabled is False
    # No socket configured -> every notify is a silent no-op returning False.
    assert notifier.ready() is False
    assert notifier.watchdog() is False
    notifier.close()


def test_noop_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    notifier = SystemdNotifier()  # default: read env
    assert notifier.enabled is False
    assert notifier.notify("READY=1") is False


def test_reads_env_notify_socket(short_sock_dir: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sock_path = str(Path(short_sock_dir) / "env.sock")
    srv = _bind_datagram_server(sock_path)
    monkeypatch.setenv("NOTIFY_SOCKET", sock_path)
    notifier = SystemdNotifier()  # default: read env
    try:
        assert notifier.enabled is True
        assert notifier.ready() is True
        assert srv.recvfrom(64)[0] == b"READY=1"
    finally:
        notifier.close()
        srv.close()


def test_abstract_namespace_socket_resolves_to_nul_prefix() -> None:
    """A leading '@' NOTIFY_SOCKET maps to a NUL-prefixed AF_UNIX address."""
    notifier = SystemdNotifier(socket_path="@camina/notify")
    try:
        assert notifier.enabled is True
        assert notifier._addr == "\0camina/notify"
    finally:
        notifier.close()
