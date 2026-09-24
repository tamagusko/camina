"""The sensor daemon must not load torch or Ultralytics.

On the Pi, `torch` alone is ~700 MB installed and Ultralytics' NCNN loader asks
for ncnn built from git source on ARM64. The daemon runs the NCNN model through
`camina.service.ncnn_detector` instead, so importing the daemon's
composition root must leave both out of `sys.modules`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_daemon_import_chain_loads_neither_torch_nor_ultralytics() -> None:
    code = (
        "import sys\n"
        "import camina.__main__\n"
        "import camina.service.sensor_daemon\n"
        "print(sorted(m for m in ('torch', 'ultralytics') if m in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True
    )

    assert out.stdout.strip() == "[]", out.stdout + out.stderr
