import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from pycocotools.coco import COCO
from sklearn.model_selection import train_test_split
from tqdm import tqdm

def build_annotations(coco: COCO, img_ids: List[int], iou_thresh: float) -> Dict[int, List[Tuple]]:
    labels = defaultdict(list)
    for img_id in tqdm(img_ids, desc="Parsing COCO Annotations"):
        ann_ids = coco.getAnnIds(imgIds=[img_id])
        anns = coco.loadAnns(ann_ids)

        bboxes = []
        has_person = []
        has_bicycle = []

        for ann in anns:
            cat_id = ann['category_id']
            if cat_id not in [1, 2, 3, 4, 6, 8]:
                continue

            bbox = ann['bbox']
            x, y, w, h = bbox
            cx, cy = x + w / 2, y + h / 2
            area = w * h
            label = -1

            if cat_id == 1:
                has_person.append((x, y, x + w, y + h))
            elif cat_id == 2:
                has_bicycle.append((x, y, x + w, y + h))

            if cat_id == 1:
                label = 0  # person
            elif cat_id == 2:
                label = 2  # bicycle (will merge)
            elif cat_id == 3:
                label = 3  # car
            elif cat_id == 4:
                label = 4  # motorcycle
            elif cat_id == 6:
                label = 5  # bus
            elif cat_id == 8:
                label = 6  # truck

            if label in [0, 2, 3, 4, 5, 6]:
                labels[img_id].append((label, cx, cy, w, h))

        # Find overlapping person + bicycle and create cyclist label
        for px1, py1, px2, py2 in has_person:
            for bx1, by1, bx2, by2 in has_bicycle:
                inter_x1 = max(px1, bx1)
                inter_y1 = max(py1, by1)
                inter_x2 = min(px2, bx2)
                inter_y2 = min(py2, by2)

                inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
                person_area = (px2 - px1) * (py2 - py1)
                bicycle_area = (bx2 - bx1) * (by2 - by1)
                union_area = person_area + bicycle_area - inter_area

                iou = inter_area / union_area if union_area else 0

                if iou >= iou_thresh:
                    cx = (inter_x1 + inter_x2) / 2
                    cy = (inter_y1 + inter_y2) / 2
                    w = inter_x2 - inter_x1
                    h = inter_y2 - inter_y1
                    labels[img_id].append((1, cx, cy, w, h))  # cyclist

    return labels

def split_train_test(labels: Dict[int, List[Tuple]], train_size=2000, test_size=400):
    class_to_images = defaultdict(list)
    for img_id, annots in labels.items():
        present = {cid for cid, *_ in annots}
        for cid in present:
            class_to_images[cid].append(img_id)

    selected = set()
    for cid in range(6):
        imgs = class_to_images.get(cid, [])
        if len(imgs) > train_size + test_size:
            imgs = random.sample(imgs, train_size + test_size)
        selected.update(imgs)

    all_selected_labels = {img_id: labels[img_id] for img_id in selected}
    all_selected_ids = list(all_selected_labels.keys())
    train_ids, test_ids = train_test_split(all_selected_ids, test_size=test_size / (train_size + test_size), random_state=42)

    train_labels = {img_id: all_selected_labels[img_id] for img_id in train_ids}
    test_labels = {img_id: all_selected_labels[img_id] for img_id in test_ids}

    return train_labels, test_labels

def save_yolo_dataset(coco: COCO, labels: dict, coco_dir: Path, out_dir: Path, subset: str):
    img_out = out_dir / "images" / subset
    lab_out = out_dir / "labels" / subset
    img_out.mkdir(parents=True, exist_ok=True)
    lab_out.mkdir(parents=True, exist_ok=True)

    for img_id, label_list in tqdm(labels.items(), desc=f"Saving {subset} files"):
        info = coco.loadImgs(img_id)[0]
        shutil.copy2(coco_dir / "train2017" / info["file_name"], img_out / info["file_name"])

        txt_path = lab_out / f"{Path(info['file_name']).stem}.txt"
        with txt_path.open("w") as f:
            for cid, cx, cy, w, h in label_list:
                f.write(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

def save_data_yaml(out_dir: Path):
    with (out_dir / "data.yaml").open("w") as f:
        f.write(
            f"path: {out_dir.resolve()}\n"
            "train: images/train\n"
            "val: images/test\n"
            "nc: 6\n"
            "names: [person, cyclist, car, motorcycle, bus, truck]\n"
        )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coco-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--iou", type=float, default=0.5)
    args = parser.parse_args()

    coco = COCO(args.coco_dir / "annotations/instances_train2017.json")
    img_ids = coco.getImgIds()
    labels = build_annotations(coco, img_ids, args.iou)
    train_labels, test_labels = split_train_test(labels, train_size=2000, test_size=400)

    save_yolo_dataset(coco, train_labels, args.coco_dir, args.out_dir, "train")
    save_yolo_dataset(coco, test_labels, args.coco_dir, args.out_dir, "test")
    save_data_yaml(args.out_dir)

    print("✅ Dataset written to:", args.out_dir.resolve())

if __name__ == "__main__":
    main()
