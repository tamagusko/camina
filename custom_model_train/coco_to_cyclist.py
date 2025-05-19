#!/usr/bin/env python3
"""
Create a YOLO-style dataset (with a synthetic *cyclist* class)
from COCO 2017 annotations.

Final label map
---------------
0 person
1 cyclist  (IoU ≥ 0.3 between *person* ∩ *bicycle*)
2 car
3 motorcycle
4 bus
5 truck

How to run:

python coco_to_cyclist.py \
  --coco-dir ~/repos/camina/data/coco \
  --out-dir ./datasets/cyclist_yolo \
  --iou 0.3
"""

import argparse
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from pycocotools.coco import COCO
from sklearn.model_selection import train_test_split
from tqdm import tqdm

COCO_CLASSES = {1: "person", 2: "bicycle", 3: "car", 4: "motorcycle", 6: "bus", 8: "truck"}
YOLO_MAP = {1: 0, 3: 2, 4: 3, 6: 4, 8: 5}  # COCO ID to YOLO ID
YOLO_NAMES = ["person", "cyclist", "car", "motorcycle", "bus", "truck"]

def build_annotations(
    coco: COCO, img_ids: List[int], iou_thresh: float
) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
    labels = defaultdict(list)

    for img_id in tqdm(img_ids, desc="Parsing COCO"):
        anns = coco.loadAnns(coco.getAnnIds(imgIds=[img_id]))
        img_info = coco.loadImgs(img_id)[0]
        img_w, img_h = img_info["width"], img_info["height"]

        person_boxes, bicycle_boxes = [], []

        for ann in anns:
            cid = ann["category_id"]
            if cid not in COCO_CLASSES:
                continue

            x, y, w, h = ann["bbox"]
            cx, cy = x + w / 2, y + h / 2

            cx /= img_w
            cy /= img_h
            w /= img_w
            h /= img_h

            if cid == 1:
                person_boxes.append((x, y, x + w * img_w, y + h * img_h))
            elif cid == 2:
                bicycle_boxes.append((x, y, x + w * img_w, y + h * img_h))

            if cid in YOLO_MAP:
                labels[img_id].append((YOLO_MAP[cid], cx, cy, w, h))

        for px1, py1, px2, py2 in person_boxes:
            for bx1, by1, bx2, by2 in bicycle_boxes:
                ix1, iy1 = max(px1, bx1), max(py1, by1)
                ix2, iy2 = min(px2, bx2), min(py2, by2)
                iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
                inter_area = iw * ih
                if inter_area == 0:
                    continue
                union = ((px2 - px1) * (py2 - py1)) + ((bx2 - bx1) * (by2 - by1)) - inter_area
                iou = inter_area / union
                if iou >= iou_thresh:
                    ux1 = min(px1, bx1)
                    uy1 = min(py1, by1)
                    ux2 = max(px2, bx2)
                    uy2 = max(py2, by2)

                    ucx = (ux1 + ux2) / 2 / img_w
                    ucy = (uy1 + uy2) / 2 / img_h
                    uw = (ux2 - ux1) / img_w
                    uh = (uy2 - uy1) / img_h

                    labels[img_id].append((1, ucx, ucy, uw, uh))

    return labels

def split_balanced(
    labels: Dict[int, List[Tuple]], train_size: int = 2000, test_size: int = 400
) -> tuple[dict, dict]:
    per_class_imgs = defaultdict(set)
    for img_id, anns in labels.items():
        for cid, *_ in anns:
            per_class_imgs[cid].add(img_id)

    chosen_imgs = set()
    for cid in range(len(YOLO_NAMES)):
        imgs = list(per_class_imgs.get(cid, []))
        need = train_size + test_size
        if len(imgs) < need:
            print(f"⚠️  class '{YOLO_NAMES[cid]}' only has {len(imgs)} images")
            chosen = imgs
        else:
            chosen = random.sample(imgs, need)
        chosen_imgs.update(chosen)

    selected = {i: labels[i] for i in chosen_imgs}
    img_ids = list(selected.keys())
    train_ids, test_ids = train_test_split(
        img_ids,
        test_size=test_size / (train_size + test_size),
        shuffle=True,
        random_state=42,
    )
    train = {i: selected[i] for i in train_ids}
    test = {i: selected[i] for i in test_ids}
    return train, test

def copy_yolo_files(
    coco: COCO, subset_labels: dict, coco_dir: Path, out_dir: Path, subset: str
) -> None:
    img_dir = out_dir / "images" / subset
    lbl_dir = out_dir / "labels" / subset
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    for img_id, anns in tqdm(subset_labels.items(), desc=f"Export {subset}"):
        info = coco.loadImgs(img_id)[0]
        src_img = coco_dir / "train2017" / info["file_name"]
        if not src_img.exists():
            print(f"⚠️  missing image skipped: {src_img}")
            continue

        shutil.copy2(src_img, img_dir / info["file_name"])
        txt_path = lbl_dir / f"{Path(info['file_name']).stem}.txt"
        with txt_path.open("w") as f:
            for cid, cx, cy, w, h in anns:
                f.write(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

def write_data_yaml(out_dir: Path) -> None:
    (out_dir / "data.yaml").write_text(
        f"path: {out_dir.resolve()}\n"
        "train: images/train\n"
        "val: images/test\n"
        f"nc: {len(YOLO_NAMES)}\n"
        f"names: {YOLO_NAMES}\n"
    )

def class_summary(label_dict: dict, title: str) -> None:
    counter = Counter(cid for anns in label_dict.values() for cid, *_ in anns)
    print(f"\n{title} detections")
    for cid, name in enumerate(YOLO_NAMES):
        print(f"{name:<10s}: {counter.get(cid, 0):>6d}")
    print(f"Images    : {len(label_dict)}")

def main() -> None:
    parser = argparse.ArgumentParser(description="COCO → YOLO cyclist builder")
    parser.add_argument("--coco-dir", type=Path, required=True, help="Root COCO folder")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output dataset dir")
    parser.add_argument("--iou", type=float, default=0.3, help="IoU for cyclist synth")
    args = parser.parse_args()

    annotations = args.coco_dir / "annotations/instances_train2017.json"
    if not annotations.exists():
        parser.error(f"Annotation file not found: {annotations}")

    coco = COCO(str(annotations))
    all_labels = build_annotations(coco, coco.getImgIds(), args.iou)

    train_lbls, test_lbls = split_balanced(all_labels)
    copy_yolo_files(coco, train_lbls, args.coco_dir, args.out_dir, "train")
    copy_yolo_files(coco, test_lbls, args.coco_dir, args.out_dir, "test")
    write_data_yaml(args.out_dir)

    class_summary(train_lbls, "TRAIN")
    class_summary(test_lbls, "TEST")

    print("\n✅  Dataset written to:", args.out_dir.resolve())

if __name__ == "__main__":
    main()
