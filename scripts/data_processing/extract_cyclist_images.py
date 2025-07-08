#!/usr/bin/env python3
"""
Extract YOLO-format images and labels with cyclist class only (class 1).

Creates a YOLO-compatible structure:
  images/train/, images/test/
  labels/train/, labels/test/

Usage:
$ python extract_cyclist_dataset.py --dataset-dir datasets/cyclist_yolo --output-dir datasets/cyclist_images
"""

import argparse
from pathlib import Path
import shutil
from tqdm import tqdm

CYCLIST_CLASS_ID = "1"


def contains_cyclist(label_path: Path) -> bool:
    """Checks if label file contains class 1 (cyclist)."""
    if not label_path.exists():
        return False
    with label_path.open() as f:
        return any(line.strip().startswith(CYCLIST_CLASS_ID) for line in f)


def copy_subset(subset: str, dataset_dir: Path, output_dir: Path) -> int:
    src_img_dir = dataset_dir / "images" / subset
    src_lbl_dir = dataset_dir / "labels" / subset
    dst_img_dir = output_dir / "images" / subset
    dst_lbl_dir = output_dir / "labels" / subset

    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for image_path in tqdm(sorted(src_img_dir.glob("*.jpg")), desc=f"Checking {subset}"):
        label_path = src_lbl_dir / f"{image_path.stem}.txt"
        if contains_cyclist(label_path):
            shutil.copy2(image_path, dst_img_dir / image_path.name)
            shutil.copy2(label_path, dst_lbl_dir / label_path.name)
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Extract YOLO-format dataset with cyclist class only")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    total = 0
    for split in ["train", "test"]:
        total += copy_subset(split, args.dataset_dir, args.output_dir)

    print(f"\n✅ {total} images with cyclist copied to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
