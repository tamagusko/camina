"""Apply the label-audit decisions (``audit_decisions.csv`` from data/autolabel/audit/).

Step 1, local and safe: write corrected YOLO labels for every image with a class change
or a deleted box to ``--out/<split>/labels/``, plus ``plan.csv``. The committed dataset
(training/dataset) is not touched.

    .venv/bin/python -m training.apply_audit --decisions ~/Downloads/audit_decisions.csv

Step 2, writes to Roboflow: replace each changed image's annotation and tag it
``audit-fixed``; tag images whose box must be redrawn ``audit-box``. Try one image
first. The key comes from ``ROBOFLOW_API_KEY``; the SDK is not in requirements.txt
(it pulls in its own OpenCV), so run it from a throwaway venv with ``roboflow``::

    ROBOFLOW_API_KEY=... <venv>/bin/python -m training.apply_audit --decisions ... --push --limit 1

Roboflow keeps version 3 (the paper's) as it is; generate a new version after the push.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from training.class_taxonomy import load_canonical_classes

logger = logging.getLogger(__name__)

DATASET = Path("training/dataset")
RUNS = Path("data/autolabel")
WORKSPACE = "tiago-tamagusko"
PROJECT = "sdl-urban-mobility-dataset-crcy8"
ROBOFLOW_NAMES = {"motorcyclist": "motorcycle"}  # canonical -> the project's class name
MIN_MATCH_IOU = 0.9


@dataclass(frozen=True)
class Decision:
    action: str  # keep | change | delete | fix_box
    to: str  # new class for "change"


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0.0, w) * max(0.0, h)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def find_line(
    lines: list[str], xyxy: tuple[float, float, float, float], width: int, height: int
) -> int | None:
    """Index of the label line whose box is ``xyxy`` (pixels), or None if none matches."""
    best, best_iou = None, MIN_MATCH_IOU
    for i, line in enumerate(lines):
        _, cx, cy, w, h = (float(v) for v in line.split()[:5])
        box = (
            (cx - w / 2) * width,
            (cy - h / 2) * height,
            (cx + w / 2) * width,
            (cy + h / 2) * height,
        )
        score = _iou(box, xyxy)
        if score >= best_iou:
            best, best_iou = i, score
    return best


def apply_edits(lines: list[str], edits: dict[int, Decision], classes: list[str]) -> list[str]:
    """Label lines with class changes applied and deleted boxes removed."""
    out = []
    for i, line in enumerate(lines):
        d = edits.get(i)
        if d and d.action == "delete":
            continue
        if d and d.action == "change":
            line = " ".join([str(classes.index(d.to)), *line.split()[1:]])
        out.append(line)
    return out


def tags_for(decisions: list[Decision]) -> list[str]:
    actions = {d.action for d in decisions}
    tags = []
    if "fix_box" in actions:
        tags.append("audit-box")
    if actions & {"change", "delete"}:
        tags.append("audit-fixed")
    return tags


def roboflow_labelmap(classes: list[str]) -> dict[str, str]:
    """YOLO class id -> the Roboflow project's class name."""
    return {str(i): ROBOFLOW_NAMES.get(c, c) for i, c in enumerate(classes)}


def _read_decisions(path: Path) -> dict[tuple[str, str], list[tuple[str, Decision]]]:
    """(split, image) -> [(box, decision)], skipping plain keeps."""
    per_image: dict[tuple[str, str], list[tuple[str, Decision]]] = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            d = Decision(r["action"], r["new_label"])
            if d.action != "keep":
                per_image[(r["split"], r["image"])].append((r["box"], d))
    return per_image


def _coords(split: str) -> dict[tuple[str, str], tuple[float, float, float, float]]:
    with open(RUNS / f"tra2026_{split}" / "boxes.csv", newline="") as f:
        return {
            (r["image"], r["box"]): tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))
            for r in csv.DictReader(f)
        }


def write_fixed(decisions: Path, out: Path) -> list[dict]:
    """Write corrected labels and plan.csv; return the plan rows."""
    from PIL import Image

    classes = load_canonical_classes()
    coords: dict[str, dict] = {}
    plan = []
    for (split, image), items in sorted(_read_decisions(decisions).items()):
        coords.setdefault(split, _coords(split))
        label = DATASET / "labels" / split / f"{Path(image).stem}.txt"
        lines = [ln for ln in label.read_text().splitlines() if ln.strip()]
        width, height = Image.open(DATASET / "images" / split / image).size
        edits: dict[int, Decision] = {}
        for box, d in items:
            i = find_line(lines, coords[split][(image, box)], width, height)
            if i is None:
                logger.warning(
                    "%s/%s box %s is not in the dataset labels; skipped", split, image, box
                )
                continue
            edits[i] = d
        if not edits:
            continue
        fixed = apply_edits(lines, edits, classes)
        changed = fixed != lines
        if changed:
            dest = out / split / "labels" / label.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("".join(f"{ln}\n" for ln in fixed))
        plan.append(
            {
                "split": split,
                "image": image,
                "tags": " ".join(tags_for(list(edits.values()))),
                "boxes_changed": sum(d.action in ("change", "delete") for d in edits.values()),
                "label_file": str(out / split / "labels" / label.name) if changed else "",
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "plan.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["split", "image", "tags", "boxes_changed", "label_file"]
        )
        writer.writeheader()
        writer.writerows(plan)
    logger.info(
        "%d images in the plan (%d with new labels) -> %s",
        len(plan),
        sum(bool(p["label_file"]) for p in plan),
        out,
    )
    return plan


def push(plan: list[dict], limit: int | None) -> None:
    """Replace annotations and add tags in Roboflow for the planned images."""
    from roboflow import Roboflow
    from roboflow.adapters import rfapi

    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        raise SystemExit("Set ROBOFLOW_API_KEY")
    project = Roboflow(api_key=key).workspace(WORKSPACE).project(PROJECT)
    ids = {}
    for page in project.search_all(in_dataset=True, fields=["id", "name"], limit=250):
        ids.update({img["name"]: img["id"] for img in page})
    labelmap = roboflow_labelmap(load_canonical_classes())
    for row in plan[:limit]:
        image_id = ids.get(row["image"])
        if image_id is None:
            logger.error("%s not found in Roboflow; skipped", row["image"])
            continue
        if row["label_file"]:
            project.save_annotation(
                annotation_path=row["label_file"],
                annotation_labelmap=labelmap,
                image_id=image_id,
                annotation_overwrite=True,
            )
        if row["tags"]:
            rfapi.update_image_metadata(key, WORKSPACE, image_id, add_tags=row["tags"].split())
        logger.info("pushed %s (%s)", row["image"], row["tags"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--decisions", type=Path, required=True, help="audit_decisions.csv")
    parser.add_argument("--out", type=Path, default=RUNS / "audit" / "fixed")
    parser.add_argument("--push", action="store_true", help="write the fixes to Roboflow")
    parser.add_argument("--limit", type=int, default=None, help="push only the first N images")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parser.parse_args()
    plan = write_fixed(args.decisions, args.out)
    if args.push:
        push(plan, args.limit)


if __name__ == "__main__":
    main()
