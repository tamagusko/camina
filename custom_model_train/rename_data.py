import argparse
from pathlib import Path
import re

# Match: filename_jpg.rf.<hash>.txt
LABEL_PATTERN = re.compile(r"^(.*)_jpg\.rf\.[a-f0-9]{32}\.txt$")
# Match: filename_jpg.rf.<hash>.jpg or .png
IMAGE_PATTERN = re.compile(r"^(.*)_jpg\.rf\.[a-f0-9]{32}(\.jpg|\.png)$")


def rename_labels(label_dir: Path):
    if not label_dir.exists():
        print(f"⚠️ Label folder not found: {label_dir}")
        return

    renamed = 0
    for label_file in label_dir.rglob("*.txt"):
        match = LABEL_PATTERN.match(label_file.name)
        if match:
            new_name = match.group(1) + ".txt"
            new_path = label_file.with_name(new_name)
            label_file.rename(new_path)
            renamed += 1
    print(f"✅ Renamed {renamed} label files in: {label_dir}")


def rename_images(image_dir: Path):
    if not image_dir.exists():
        print(f"⚠️ Image folder not found: {image_dir}")
        return

    renamed = 0
    for image_file in image_dir.rglob("*.[jp][pn]g"):
        match = IMAGE_PATTERN.match(image_file.name)
        if match:
            new_name = match.group(1) + match.group(2)
            new_path = image_file.with_name(new_name)
            image_file.rename(new_path)
            renamed += 1
    print(f"✅ Renamed {renamed} image files in: {image_dir}")


def process_dataset(root_dir: Path):
    subfolders = [
        ("images/train", rename_images),
        ("images/test", rename_images),
        ("labels/train", rename_labels),
        ("labels/test", rename_labels),
    ]

    for subfolder, func in subfolders:
        folder_path = root_dir / subfolder
        func(folder_path)


def main():
    parser = argparse.ArgumentParser(description="Rename Roboflow-style YOLO files to original names in images/ and labels/ subfolders.")
    parser.add_argument("dataset_root", type=Path, help="Root dataset folder (e.g., datasets/SDL-fine-tuned/)")

    args = parser.parse_args()

    if not args.dataset_root.exists():
        print("❌ Dataset root folder does not exist.")
        return

    process_dataset(args.dataset_root)


if __name__ == "__main__":
    main()
