import argparse
from pathlib import Path
import re


def rename_labels(label_dir: Path):
    pattern = re.compile(r"^(.*)_jpg\.rf\.[a-f0-9]{32}\.txt$")

    renamed = 0
    for label_file in label_dir.rglob("*.txt"):
        match = pattern.match(label_file.name)
        if match:
            new_name = match.group(1) + ".txt"
            new_path = label_file.with_name(new_name)
            label_file.rename(new_path)
            renamed += 1

    print(f"✅ Renamed {renamed} label files in: {label_dir.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Rename Roboflow-style YOLO labels to original format.")
    parser.add_argument("folder", type=Path, help="Root folder containing labels/train and labels/test")

    args = parser.parse_args()

    if not args.folder.exists():
        print("❌ Folder does not exist.")
        return

    rename_labels(args.folder)


if __name__ == "__main__":
    main()
