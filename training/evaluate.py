"""Compare detectors the way the sensor runs them: NCNN, 640, on the same data.

    python -m training.evaluate runs/train/yolo26n_real runs/train/yolo26n_real_synthetic \\
        models/camina_v1_yolo11n_ncnn_model

Each model is a training run (``weights/best.pt`` is exported to FP16 NCNN, the
Pi format, and smoke-tested) or an NCNN directory. For each:

- **held-out AP** — per class AP50 and mAP50-95 on the frozen real test split
  (``--data``), computed on the NCNN model. Skipped for models whose class
  order is not canonical; note that CAMINAv1 saw these images in training.
- **count error** — the sensor pipeline on every hand-counted clip in
  ``--videos`` (``<clip>.counts.csv``), per class and direction (S7).
- **speed** — NCNN ms per frame on this machine (a relative, not a Pi, number).

Results go to ``runs/eval/<timestamp>.json`` and a table is printed. Runs in the
GPU environment (``training/requirements.txt``).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from training.count_eval import Row, compare, count_clip, read_truth

logger = logging.getLogger(__name__)

DEFAULT_DATA = Path("runs/datasets/yolo26n_real/data.yaml")
VIDEO_EXTS = {".mov", ".mp4", ".avi", ".mkv"}


def resolve_model(path: Path) -> tuple[str, Path]:
    """``(name, weights or NCNN dir)`` for a training run or an NCNN model directory."""
    if (path / "weights" / "best.pt").exists():
        return path.name, path / "weights" / "best.pt"
    if (path / "model.ncnn.param").exists():
        return path.name, path
    raise ValueError(f"{path} is not a training run or an NCNN model")


def summarise_counts(rows: list[Row]) -> dict:
    """Total truth, total counted, summed absolute error, and whether all rows pass S7."""
    return {
        "truth": sum(r.truth for r in rows),
        "counted": sum(r.counted for r in rows),
        "abs_error": sum(abs(r.error) for r in rows),
        "s7": all(r.passes for r in rows),
    }


def to_ncnn(weights: Path, imgsz: int) -> Path:
    """Export ``best.pt`` to FP16 NCNN (once) and check it runs."""
    from ultralytics import YOLO

    from training.pnnx_export import smoke_test

    target = weights.with_name(f"{weights.stem}_ncnn_model")
    if not target.exists():
        YOLO(str(weights)).export(format="ncnn", imgsz=imgsz, half=True)
    smoke_test(target)
    return target


def held_out_ap(ncnn: Path, data: Path, imgsz: int) -> dict | None:
    """Per-class AP50, mAP50 and mAP50-95 on the test split; None if classes differ."""
    import yaml
    from ultralytics import YOLO

    model = YOLO(str(ncnn), task="detect")
    names = yaml.safe_load(data.read_text())["names"]
    if [model.names[i] for i in sorted(model.names)] != [names[i] for i in sorted(names)]:
        logger.info("%s: class order differs from the dataset, AP skipped", ncnn.name)
        return None
    m = model.val(data=str(data), split="test", imgsz=imgsz, batch=1, verbose=False).box
    per_class = {
        names[int(c)]: round(float(ap), 3) for c, ap in zip(m.ap_class_index, m.ap50, strict=True)
    }
    return {
        "map50": round(float(m.map50), 3),
        "map50_95": round(float(m.map), 3),
        "ap50": per_class,
    }


def ms_per_frame(ncnn: Path, video: Path, frames: int = 200) -> float:
    """Mean NCNN inference time over the first ``frames`` frames of ``video``."""
    import cv2

    from camina.service.ncnn_detector import NcnnDetector

    detector = NcnnDetector(ncnn)
    cap = cv2.VideoCapture(str(video))
    images = [cap.read()[1] for _ in range(frames)]
    for image in images[:10]:
        detector(image)
    start = time.perf_counter()
    for image in images:
        detector(image)
    return round(1000 * (time.perf_counter() - start) / len(images), 1)


def evaluate(models: list[Path], data: Path, videos: Path, imgsz: int) -> list[dict]:
    """Score every model on held-out AP, clip count error and speed."""
    clips = sorted(videos.glob("*.counts.csv"))
    results = []
    for path in models:
        name, model = resolve_model(path)
        ncnn = model if model.is_dir() else to_ncnn(model, imgsz)
        counts = {}
        for truth_file in clips:
            stem = truth_file.name.removesuffix(".counts.csv")
            video = next(p for p in _videos(videos) if p.stem == stem)
            line, truth, complete = read_truth(truth_file)
            rows = compare(truth, count_clip(video, ncnn, line), complete)
            counts[video.name] = {
                **summarise_counts(rows),
                "rows": [r.__dict__ | {"error": r.error, "passes": r.passes} for r in rows],
            }
        speed_video = _videos(videos)[0]
        results.append(
            {
                "model": name,
                "ncnn": str(ncnn),
                "held_out": held_out_ap(ncnn, data, imgsz) if data.exists() else None,
                "counts": counts,
                "ms_per_frame": ms_per_frame(ncnn, speed_video),
            }
        )
    return results


def _videos(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXTS)


def _table(results: list[dict]) -> None:
    logger.info(
        "%-34s %7s %9s %10s %6s %8s", "model", "mAP50", "mAP50-95", "count err", "S7", "ms/frm"
    )
    for r in results:
        ap = r["held_out"] or {}
        err = sum(c["abs_error"] for c in r["counts"].values())
        s7 = all(c["s7"] for c in r["counts"].values()) if r["counts"] else None
        logger.info(
            "%-34s %7s %9s %10s %6s %8.1f",
            r["model"],
            ap.get("map50", "-"),
            ap.get("map50_95", "-"),
            err if r["counts"] else "-",
            {True: "pass", False: "FAIL", None: "-"}[s7],
            r["ms_per_frame"],
        )


def main() -> None:
    """Evaluate the models given on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("models", type=Path, nargs="+", help="training runs or NCNN model dirs")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help="dataset with the test split")
    ap.add_argument("--videos", type=Path, default=Path("videos"))
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    results = evaluate(args.models, args.data, args.videos, args.imgsz)
    out = Path("runs/eval") / f"{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    _table(results)
    logger.info("Details: %s", out)


if __name__ == "__main__":
    main()
