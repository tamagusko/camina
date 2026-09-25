"""Pre-label images for review in Roboflow, following docs/labelling_guide.

1. YOLO26x (COCO) finds person, bicycle, car, motorcycle, bus and truck; a vehicle box
   lying mostly inside a larger one (a split detection) is dropped.
2. A person on a bicycle or motorcycle becomes one ``cyclist`` / ``motorcyclist`` box;
   a riderless bicycle or motorcycle is dropped (guide, rules 2 and 4).
3. SAM 3 (optional, text prompts) relabels a matching car or truck box as
   ``delivery_van`` and turns a person on a kick scooter into ``e-scooter``. It never
   adds a van on its own: a second box on one vehicle is a known error. There is no SUV
   prompt: on the TRA 2026 test split it relabelled most cars as SUV (23% of its SUV
   boxes matched the labels; car recall fell from 0.71 to 0.22). Cars stay ``car``
   (guide, rule 5) and ``training.codex_check`` flags the SUVs among them.
4. With ``--existing``, labels already in hand are kept and only new objects are added.

Writes ``<out>/images``, ``<out>/labels`` (canonical class order), ``data.yaml`` and
``boxes.csv`` (one row per box, read by ``training.codex_check``).

Runs in the GPU environment (``.venv-train``)::

    .venv-train/bin/python -m training.autolabel --images data/dev_expanded_new/images \\
        --existing data/dev_expanded_new/labels --out data/autolabel/dev_expanded_new

SAM 3 needs ``weights/sam3.pt`` from the gated Hugging Face repo ``facebook/sam3``;
without it, step 3 is skipped with a warning.
"""

from __future__ import annotations

import argparse
import csv
import logging
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from training.class_taxonomy import load_canonical_classes

logger = logging.getLogger(__name__)

COCO_NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
RIDDEN = {"bicycle": "cyclist", "motorcycle": "motorcyclist"}
RIDERS = {"cyclist", "motorcyclist", "e-scooter"}
RELABELLABLE = {"car", "truck"}
SAM3_PROMPTS = {"van": "delivery_van", "person riding a kick scooter": "e-scooter"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

MIN_RIDER_OVERLAP = 0.2  # share of the person's box that overlaps the vehicle
MIN_SCOOTER_OVERLAP = 0.6  # share of the person's box inside the e-scooter box
MIN_MATCH_IOU = 0.5
MIN_FRAGMENT_INSIDE = 0.8  # a box this much inside another is a piece of it
VEHICLES = {"car", "truck", "bus", "SUV", "delivery_van"}


@dataclass(frozen=True)
class Box:
    """One box in pixel corners, with the class name it will be written as."""

    cls: str
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    source: str

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


def _intersection(a: Box, b: Box) -> float:
    w = min(a.x2, b.x2) - max(a.x1, b.x1)
    h = min(a.y2, b.y2) - max(a.y1, b.y1)
    return max(0.0, w) * max(0.0, h)


def iou(a: Box, b: Box) -> float:
    inter = _intersection(a, b)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def _union(a: Box, b: Box, cls: str, source: str) -> Box:
    return Box(
        cls,
        min(a.x1, b.x1),
        min(a.y1, b.y1),
        max(a.x2, b.x2),
        max(a.y2, b.y2),
        min(a.conf, b.conf),
        source,
    )


def build_riders(boxes: list[Box]) -> list[Box]:
    """Join each person to the bicycle or motorcycle they ride; drop riderless ones."""
    persons = [b for b in boxes if b.cls == "person"]
    vehicles = [b for b in boxes if b.cls in RIDDEN]
    pairs = []
    for pi, p in enumerate(persons):
        centre_x = (p.x1 + p.x2) / 2
        for vi, v in enumerate(vehicles):
            overlap = _intersection(p, v) / p.area if p.area else 0.0
            if overlap >= MIN_RIDER_OVERLAP and v.x1 <= centre_x <= v.x2:
                pairs.append((overlap, pi, vi))

    used_p: set[int] = set()
    used_v: set[int] = set()
    riders = []
    for _, pi, vi in sorted(pairs, reverse=True):
        if pi in used_p or vi in used_v:
            continue
        used_p.add(pi)
        used_v.add(vi)
        v = vehicles[vi]
        riders.append(_union(persons[pi], v, RIDDEN[v.cls], v.source))

    others = [b for b in boxes if b.cls not in RIDDEN and b.cls != "person"]
    walkers = [p for i, p in enumerate(persons) if i not in used_p]
    return walkers + riders + others


def apply_open_vocab(boxes: list[Box], prompted: list[Box]) -> list[Box]:
    """Apply SAM 3 results (already named SUV / delivery_van / e-scooter) to COCO boxes."""
    out = list(boxes)
    for i, b in enumerate(out):
        if b.cls not in RELABELLABLE:
            continue
        matches = [p for p in prompted if p.cls != "e-scooter" and iou(b, p) >= MIN_MATCH_IOU]
        if matches:
            best = max(matches, key=lambda p: p.conf)
            out[i] = replace(b, cls=best.cls, source=f"{b.source}+sam3")

    for s in (p for p in prompted if p.cls == "e-scooter"):
        if any(r.cls in RIDERS and iou(r, s) >= MIN_MATCH_IOU for r in out):
            continue
        candidates = [
            (_intersection(p, s) / p.area, i)
            for i, p in enumerate(out)
            if p.cls == "person" and p.area
        ]
        candidates = [c for c in candidates if c[0] >= MIN_SCOOTER_OVERLAP]
        if candidates:
            _, i = max(candidates)
            out[i] = _union(out[i], s, "e-scooter", f"{out[i].source}+sam3")
        else:
            out.append(s)
    return out


def merge_existing(existing: list[Box], auto: list[Box]) -> list[Box]:
    """Keep every existing box; add automatic boxes that match none of them."""
    kept = [replace(b, source="existing") for b in existing]
    new = [a for a in auto if all(not _same_object(a, e) for e in kept)]
    return kept + new


def _inside(a: Box, b: Box) -> float:
    """Share of ``a``'s area that lies inside ``b``."""
    return _intersection(a, b) / a.area if a.area else 0.0


def _same_object(a: Box, b: Box) -> bool:
    return iou(a, b) >= MIN_MATCH_IOU or _inside(a, b) >= MIN_FRAGMENT_INSIDE


def drop_fragments(boxes: list[Box]) -> list[Box]:
    """Drop a vehicle box lying mostly inside a larger vehicle box (a split detection)."""
    vehicles = [b for b in boxes if b.cls in VEHICLES]
    return [
        b
        for b in boxes
        if b.cls not in VEHICLES
        or not any(
            o is not b and o.area > b.area and _inside(b, o) >= MIN_FRAGMENT_INSIDE
            for o in vehicles
        )
    ]


def to_yolo_lines(boxes: list[Box], width: int, height: int, classes: list[str]) -> list[str]:
    """Format boxes as YOLO label lines, clipped to the image."""
    lines = []
    for b in boxes:
        if b.cls not in classes:
            raise ValueError(f"class {b.cls!r} is not in the canonical list {classes}")
        x1, x2 = max(0.0, b.x1), min(float(width), b.x2)
        y1, y2 = max(0.0, b.y1), min(float(height), b.y2)
        cx, cy = (x1 + x2) / 2 / width, (y1 + y2) / 2 / height
        w, h = (x2 - x1) / width, (y2 - y1) / height
        lines.append(f"{classes.index(b.cls)} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return lines


def read_yolo_labels(path: Path, width: int, height: int, classes: list[str]) -> list[Box]:
    """Read a YOLO label file in canonical order back into pixel boxes."""
    if not path.exists():
        return []
    boxes = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        c, cx, cy, w, h = line.split()
        cx, w = float(cx) * width, float(w) * width
        cy, h = float(cy) * height, float(h) * height
        boxes.append(
            Box(classes[int(c)], cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, 1.0, "existing")
        )
    return boxes


def _detect_coco(model: Any, image: Path, conf: float, imgsz: int) -> list[Box]:
    result = model.predict(str(image), conf=conf, imgsz=imgsz, verbose=False)[0]
    boxes = []
    for (x1, y1, x2, y2), c, s in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.cls.tolist(),
        result.boxes.conf.tolist(),
        strict=True,
    ):
        name = COCO_NAMES.get(int(c))
        if name:  # every other COCO class, including train (the Luas), is ignored
            boxes.append(Box(name, x1, y1, x2, y2, s, "coco"))
    return boxes


def _detect_sam3(predictor: Any, image: Path) -> list[Box]:
    prompts = list(SAM3_PROMPTS)
    predictor.set_image(str(image))
    result = predictor(text=prompts)[0]
    boxes = []
    for (x1, y1, x2, y2), c, s in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.cls.tolist(),
        result.boxes.conf.tolist(),
        strict=True,
    ):
        boxes.append(Box(SAM3_PROMPTS[prompts[int(c)]], x1, y1, x2, y2, s, "sam3"))
    return boxes


def _load_models(args: argparse.Namespace) -> tuple[Any, Any]:
    from ultralytics import YOLO

    coco = YOLO(args.model)
    sam3 = None
    if args.sam3.exists():
        from ultralytics.models.sam import SAM3SemanticPredictor

        sam3 = SAM3SemanticPredictor(
            overrides={
                "conf": args.sam3_conf,
                "task": "segment",
                "mode": "predict",
                "model": str(args.sam3),
                "half": True,
                "imgsz": 1008,  # SAM 3 native input size
                "save": False,
                "verbose": False,
            }
        )
    else:
        logger.warning("%s not found: van / e-scooter prompts skipped", args.sam3)
    return coco, sam3


def run(args: argparse.Namespace) -> None:
    classes = load_canonical_classes()
    images = sorted(p for p in args.images.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise SystemExit(f"no images in {args.images}")
    for sub in ("images", "labels"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)
    coco, sam3 = _load_models(args)

    rows = []
    for n, image in enumerate(images, 1):
        width, height = Image.open(image).size
        boxes = build_riders(drop_fragments(_detect_coco(coco, image, args.conf, args.imgsz)))
        if sam3 is not None:
            boxes = apply_open_vocab(boxes, _detect_sam3(sam3, image))
        if args.existing:
            existing = read_yolo_labels(args.existing / f"{image.stem}.txt", width, height, classes)
            boxes = merge_existing(existing, boxes)

        shutil.copy2(image, args.out / "images" / image.name)
        lines = to_yolo_lines(boxes, width, height, classes)
        (args.out / "labels" / f"{image.stem}.txt").write_text("".join(f"{x}\n" for x in lines))
        for i, b in enumerate(boxes):
            rows.append(
                {
                    "image": image.name,
                    "box": i,
                    "class": b.cls,
                    "conf": f"{b.conf:.3f}",
                    "source": b.source,
                    "x1": round(b.x1),
                    "y1": round(b.y1),
                    "x2": round(b.x2),
                    "y2": round(b.y2),
                }
            )
        if n % 25 == 0 or n == len(images):
            logger.info("%d/%d images", n, len(images))

    fields = ["image", "box", "class", "conf", "source", "x1", "y1", "x2", "y2"]
    with open(args.out / "boxes.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    data = {"train": "images", "val": "images", "nc": len(classes), "names": classes}
    (args.out / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    logger.info("%d boxes on %d images -> %s", len(rows), len(images), args.out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--images", type=Path, required=True, help="folder of images")
    parser.add_argument("--out", type=Path, required=True, help="output folder")
    parser.add_argument("--existing", type=Path, help="YOLO labels to keep (canonical order)")
    parser.add_argument("--model", default="yolo26x.pt", help="COCO-trained detector")
    parser.add_argument("--conf", type=float, default=0.3)
    parser.add_argument("--imgsz", type=int, default=640, help="1280 for large camera frames")
    parser.add_argument("--sam3", type=Path, default=Path("weights/sam3.pt"))
    # 0.8: on the TRA 2026 test split, lower thresholds relabelled cars as vans
    # (car recall 0.62 at 0.4, 0.70 at 0.8, 0.71 without SAM 3).
    parser.add_argument("--sam3-conf", type=float, default=0.8)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
