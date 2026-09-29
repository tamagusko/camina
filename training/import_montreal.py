"""Import the Montreal traffic-camera images as CAMINA pre-labels, for review.

Source: Ville de Montréal, "Images annotées de caméras de circulation" (open.canada.ca
dataset 3c30b818-3cd9-4877-8273-600a2ee80b05), licence "Creative Commons 4.0
Attribution (CC-BY) licence - Quebec". Pascal VOC boxes for vehicle, pedestrian,
cyclist, bus and construction. Only the 704x480 images are taken.

The human boxes are kept; the auto-labeller (``training.autolabel``: YOLO26x + rider
rule + SAM 3) only supplies classes Montreal does not have:

- ``vehicle`` takes the class of the detection it matches (car, SUV, truck, bus,
  delivery_van, motorcyclist), with the human box; unmatched, it becomes ``car``
  with source ``montreal-default`` (mostly tiny, far vehicles: review these).
- ``pedestrian`` -> ``person``, unless SAM 3 found an e-scooter on it.
- ``cyclist`` -> ``cyclist`` (or e-scooter / motorcyclist if detected so); ``bus`` -> ``bus``.
- ``construction`` (cones, barriers) is dropped, and so is any detection on it.
- A detection matching no Montreal box is added with source ``<detector>-new``.

Writes the ``training.autolabel`` layout (``images``, ``labels``, ``data.yaml``,
``boxes.csv``), so ``training.codex_check`` and Roboflow upload work unchanged.
Runs in the GPU environment::

    .venv-train/bin/python -m training.import_montreal \\
        --src <unzipped images-annotees-detection-objets> --out data/autolabel/montreal
"""

from __future__ import annotations

import argparse
import csv
import logging
import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import yaml

from training.autolabel import (
    MIN_FRAGMENT_INSIDE,
    MIN_MATCH_IOU,
    Box,
    _detect_coco,
    _detect_sam3,
    _inside,
    _load_models,
    _same_object,
    apply_open_vocab,
    build_riders,
    drop_fragments,
    iou,
    to_yolo_lines,
)
from training.class_taxonomy import load_canonical_classes

logger = logging.getLogger(__name__)

SIZE = (704, 480)
PREFIX = "mtl_"
RENAME = {"pedestrian": "person", "cyclist": "cyclist", "bus": "bus", "vehicle": "car"}
# Detector classes a Montreal label may be refined into.
REFINE = {
    "vehicle": {"car", "SUV", "truck", "bus", "delivery_van", "motorcyclist"},
    "pedestrian": {"e-scooter"},
    "cyclist": {"e-scooter", "motorcyclist"},
    "bus": set(),
}
ATTRIBUTION = """\
Images and original boxes: Ville de Montréal, "Images annotées de caméras de
circulation", open.canada.ca dataset 3c30b818-3cd9-4877-8273-600a2ee80b05,
Creative Commons 4.0 Attribution (CC-BY) licence - Quebec.
Changed: 704x480 images only; classes remapped to CAMINA and refined by
training.import_montreal (YOLO26x + SAM 3); construction boxes removed.
"""


def read_voc(path: Path) -> tuple[tuple[int, int], list[Box]]:
    """Read one Pascal VOC file: image size and its boxes (source ``montreal``)."""
    root = ET.parse(path).getroot()
    size = (int(root.findtext("size/width")), int(root.findtext("size/height")))
    boxes = []
    for obj in root.findall("object"):
        b = obj.find("bndbox")
        x1, y1, x2, y2 = (float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        boxes.append(Box(obj.findtext("name"), x1, y1, x2, y2, 1.0, "montreal"))
    return size, boxes


def _match(label: Box, auto: list[Box], used: set[int]) -> int | None:
    """Index of the detection that is the same object as ``label`` and refines it."""
    best, best_i = 0.0, None
    for i, a in enumerate(auto):
        if i in used or a.cls not in REFINE[label.cls]:
            continue
        score = iou(label, a)
        # an e-scooter box contains its rider, so containment counts as a match
        if a.cls == "e-scooter" and _inside(label, a) >= MIN_FRAGMENT_INSIDE:
            score = max(score, MIN_MATCH_IOU)
        if score >= MIN_MATCH_IOU and score > best:
            best, best_i = score, i
    return best_i


def reconcile(labels: list[Box], auto: list[Box]) -> list[Box]:
    """Merge Montreal boxes with auto-labeller boxes under the rules in the docstring."""
    out: list[Box] = []
    used: set[int] = set()
    for label in labels:
        if label.cls == "construction":
            continue
        i = _match(label, auto, used)
        if i is None:
            source = "montreal-default" if label.cls == "vehicle" else "montreal"
            out.append(replace(label, cls=RENAME[label.cls], source=source))
            continue
        used.add(i)
        a = auto[i]
        source = f"montreal+{a.source}"
        if a.cls == "e-scooter":  # the scooter box covers rider and deck
            out.append(replace(a, source=source))
        else:
            out.append(replace(label, cls=a.cls, source=source))

    for i, a in enumerate(auto):
        if i not in used and not any(_same_object(a, lb) for lb in labels):
            out.append(replace(a, source=f"{a.source}-new"))
    return out


def run(args: argparse.Namespace) -> None:
    classes = load_canonical_classes()
    selected = []
    for xml in sorted((args.src / "Annotations").glob("*.xml")):
        size, labels = read_voc(xml)
        if size == SIZE:
            selected.append((args.src / "JPEGImages" / f"{xml.stem}.jpeg", labels))
    if args.limit:
        selected = selected[: args.limit]
    logger.info("%d images of %dx%d", len(selected), *SIZE)
    for sub in ("images", "labels"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)
    coco, sam3 = _load_models(args)

    rows = []
    for n, (image, labels) in enumerate(selected, 1):
        auto = build_riders(drop_fragments(_detect_coco(coco, image, args.conf, args.imgsz)))
        if sam3 is not None:
            auto = apply_open_vocab(auto, _detect_sam3(sam3, image))
        boxes = reconcile(labels, auto)

        name = f"{PREFIX}{image.stem}"
        shutil.copy2(image, args.out / "images" / f"{name}.jpg")
        lines = to_yolo_lines(boxes, *SIZE, classes)
        (args.out / "labels" / f"{name}.txt").write_text("".join(f"{x}\n" for x in lines))
        for i, b in enumerate(boxes):
            rows.append(
                {
                    "image": f"{name}.jpg",
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
        if n % 100 == 0 or n == len(selected):
            logger.info("%d/%d images", n, len(selected))

    fields = ["image", "box", "class", "conf", "source", "x1", "y1", "x2", "y2"]
    with open(args.out / "boxes.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    data = {"train": "images", "val": "images", "nc": len(classes), "names": classes}
    (args.out / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    (args.out / "ATTRIBUTION.txt").write_text(ATTRIBUTION)
    logger.info("%d boxes on %d images -> %s", len(rows), len(selected), args.out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, required=True, help="unzipped Montreal dataset")
    parser.add_argument("--out", type=Path, required=True, help="output folder")
    parser.add_argument("--model", default="weights/yolo26x.pt", help="COCO-trained detector")
    parser.add_argument("--conf", type=float, default=0.3)
    # 960: half the Montreal vehicles are under 20 px tall at 640
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--sam3", type=Path, default=Path("weights/sam3.pt"))
    parser.add_argument("--sam3-conf", type=float, default=0.8)  # as training.autolabel
    parser.add_argument("--limit", type=int, help="first N images only (trial run)")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
