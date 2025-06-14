import os
from pathlib import Path
import shutil

# Paths
SOURCE_DIR = Path("datasets/SDL-fine-tuned")
TARGET_DIR = Path("datasets/cyclist_only")

CYCLIST_CLASS_ID = 2

# Go through train and test folders
for split in ["train", "test"]:
    label_src = SOURCE_DIR / "labels" / split
    image_src = SOURCE_DIR / "images" / split

    label_dst = TARGET_DIR / "labels" / split
    image_dst = TARGET_DIR / "images" / split

    label_dst.mkdir(parents=True, exist_ok=True)
    image_dst.mkdir(parents=True, exist_ok=True)

    for label_path in label_src.glob("*.txt"):
        with open(label_path, "r") as f:
            lines = f.readlines()

        # Keep only cyclist lines
        cyclist_lines = [line for line in lines if line.startswith(f"{CYCLIST_CLASS_ID} ")]

        if cyclist_lines:
            # Rewrite class ID to 0 (optional, simplifies training)
            cyclist_lines = ["0" + line[1:] for line in cyclist_lines]

            # Save new label file
            new_label_path = label_dst / label_path.name
            with open(new_label_path, "w") as f:
                f.writelines(cyclist_lines)

            # Copy corresponding image
            image_name = label_path.with_suffix('.jpg').name
            image_file = image_src / image_name
            if image_file.exists():
                shutil.copy2(image_file, image_dst / image_name)
