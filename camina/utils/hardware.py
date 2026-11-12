"""Best-effort Linux hardware telemetry readers shared by bench and daemon."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

_THROTTLED_RE = re.compile(r"throttled=0x([0-9a-fA-F]+)")


def read_cpu_temp(path: Path = Path("/sys/class/thermal/thermal_zone0/temp")) -> float | None:
    """Read Linux thermal-zone temperature in degrees Celsius, or return None."""
    try:
        return round(float(path.read_text(encoding="utf-8").strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def read_process_rss_mb(path: Path = Path("/proc/self/status")) -> float | None:
    """Read this process's VmRSS from procfs in MiB, or return None."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                fields = line.split()
                if len(fields) >= 3 and fields[2] == "kB":
                    return round(int(fields[1]) / 1024.0, 2)
                return None
    except (OSError, ValueError):
        return None
    return None


def read_throttled(
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int | None:
    """Read ``vcgencmd get_throttled`` as an integer bitmask, or return None.

    A value of zero is the healthy state. Other set bits include current and
    historical undervoltage, frequency capping, and thermal throttling.
    """
    try:
        result = run(
            ["vcgencmd", "get_throttled"], capture_output=True, text=True, check=False, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = _THROTTLED_RE.search(result.stdout)
    return int(match.group(1), 16) if match else None


__all__ = ["read_cpu_temp", "read_process_rss_mb", "read_throttled"]
