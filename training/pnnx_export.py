"""TorchScript -> NCNN export through a pinned pnnx, plus a runtime smoke test.

Why this exists alongside the Ultralytics export path in ``export_ncnn.py``:

1. The 9-class CAMINAv1 weights survive only as the TorchScript intermediate
   on ``origin/TRA2026`` (``model/yolo_comparison/YOLO11n/train/weights/
   best.torchscript``) — there is no ``.pt``, and Ultralytics cannot export
   from TorchScript. pnnx can: Ultralytics' own NCNN export is "write
   TorchScript, run pnnx on it, write metadata.yaml", and this module is that
   second half.
2. pnnx releases are not interchangeable. The pnnx bundled with the installed
   Ultralytics emits a detection-head graph that segfaults inside NCNN's
   forward pass (ncnn 1.0.20260526), while pnnx 20250924 reproduces the
   shipped FP32 export byte for byte (verified 2026-09-24; see
   ``models/camina_v1_yolo11n_ncnn_model/PROVENANCE.md``). Hence the explicit
   ``pnnx`` path and the smoke test.
3. A segfault kills the process that hits it, so the smoke test runs the
   forward pass in a child process and judges it by exit code.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess]

# Child-process forward pass. Keeps a reference to the input array: ncnn.Mat
# wraps the numpy buffer without owning it, so an inline temporary is freed
# before forward() and crashes a healthy model.
_SMOKE_CODE = """
import sys
import numpy as np
import ncnn
d, size = sys.argv[1], int(sys.argv[2])
net = ncnn.Net()
if net.load_param(d + "/model.ncnn.param") or net.load_model(d + "/model.ncnn.bin"):
    print("load failed"); sys.exit(2)
ex = net.create_extractor()
x = np.ascontiguousarray(np.random.default_rng(0).random((3, size, size), dtype=np.float32))
mat = ncnn.Mat(x)
ex.input(net.input_names()[0], mat)
ret, out = ex.extract(net.output_names()[0])
a = np.array(out)
ok = ret == 0 and a.size > 0 and bool(np.isfinite(a).all())
print(f"ret={ret} shape={a.shape} finite={ok}")
sys.exit(0 if ok else 3)
"""


def read_torchscript_metadata(path: Path) -> dict[str, Any]:
    """Return the metadata Ultralytics embeds in a TorchScript export.

    Args:
        path: ``*.torchscript`` file written by Ultralytics.

    Returns:
        The metadata dict (``names``, ``imgsz``, ``date``, ``version``, ...).

    Raises:
        ValueError: when the archive carries no ``extra/config.txt``.
    """
    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.endswith("extra/config.txt")]
        if not members:
            raise ValueError(
                f"{path} has no extra/config.txt; not an Ultralytics TorchScript export"
            )
        return json.loads(z.read(members[0]))


def export_torchscript(
    source: Path,
    target_dir: Path,
    *,
    imgsz: int,
    half: bool,
    pnnx: Path,
    runner: Runner = subprocess.run,
) -> None:
    """Convert an Ultralytics TorchScript export to an NCNN model directory.

    Args:
        source: ``*.torchscript`` written by Ultralytics.
        target_dir: Output directory (created; must end in ``_ncnn_model``
            for Ultralytics to recognise it).
        imgsz: Square input size baked into the graph.
        half: Store FP16 weights.
        pnnx: pnnx binary to run. Use a release validated by ``smoke_test``.
        runner: ``subprocess.run`` stand-in, injectable for tests.

    Raises:
        RuntimeError: when pnnx exits non-zero.
    """
    metadata = read_torchscript_metadata(source)
    target_dir.mkdir(parents=True, exist_ok=True)

    # pnnx drops debug files in its working directory; keep them out of the repo.
    with tempfile.TemporaryDirectory(prefix="camina_pnnx_") as scratch:
        tmp = Path(scratch)
        cmd = [
            str(pnnx),
            str(source),
            f"ncnnparam={target_dir / 'model.ncnn.param'}",
            f"ncnnbin={target_dir / 'model.ncnn.bin'}",
            f"ncnnpy={tmp / 'model_ncnn.py'}",
            f"pnnxparam={tmp / 'model.pnnx.param'}",
            f"pnnxbin={tmp / 'model.pnnx.bin'}",
            f"pnnxpy={tmp / 'model_pnnx.py'}",
            f"pnnxonnx={tmp / 'model.pnnx.onnx'}",
            f"fp16={int(half)}",
            "device=cpu",
            f"inputshape=[1,3,{imgsz},{imgsz}]",
        ]
        logger.info("Running pnnx: %s", " ".join(cmd))
        result = runner(cmd, cwd=tmp, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"pnnx exited {result.returncode}:\n{result.stderr or result.stdout}"
            )

    # Same content Ultralytics writes, from the same embedded dict: names keyed
    # by int, and `args.half` reflecting this export rather than the source's.
    metadata["names"] = {int(k): v for k, v in metadata["names"].items()}
    metadata["args"] = {**metadata.get("args", {}), "half": half}
    (target_dir / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
    )


def smoke_test(model_dir: Path, *, runner: Runner = subprocess.run) -> None:
    """Run one forward pass of an NCNN model in a child process.

    Args:
        model_dir: NCNN model directory with ``metadata.yaml``.
        runner: ``subprocess.run`` stand-in, injectable for tests.

    Raises:
        RuntimeError: when the forward pass crashes, fails, or yields
            non-finite output.
    """
    imgsz = yaml.safe_load((model_dir / "metadata.yaml").read_text())["imgsz"]
    size = imgsz[0] if isinstance(imgsz, list) else int(imgsz)
    cmd = [sys.executable, "-c", _SMOKE_CODE, str(model_dir), str(size)]
    result = runner(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode < 0:
        raise RuntimeError(
            f"{model_dir.name}: NCNN forward pass crashed (signal {-result.returncode}). "
            "The pnnx release that built it is likely incompatible with this ncnn "
            "runtime; rebuild with pnnx 20250924."
        )
    if result.returncode != 0:
        raise RuntimeError(f"{model_dir.name}: smoke test failed: {result.stdout.strip()}")
    logger.info("Smoke test passed for %s: %s", model_dir.name, result.stdout.strip())


__all__ = ["export_torchscript", "read_torchscript_metadata", "smoke_test"]
