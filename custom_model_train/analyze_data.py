import argparse
import yaml
from pathlib import Path
from collections import defaultdict


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def count_labels(labels_dir, class_names):
    class_counts = defaultdict(int)
    total = 0
    for label_file in Path(labels_dir).rglob("*.txt"):
        with open(label_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                class_id = int(parts[0])
                if 0 <= class_id < len(class_names):
                    class_counts[class_names[class_id]] += 1
                    total += 1
    return class_counts, total


def print_summary(name, counts, total):
    print(f"\n{name.upper()} SET SUMMARY")
    print(f"Total annotations: {total}")
    if total > 0:
        for cls, count in counts.items():
            percentage = (count / total) * 100
            print(f"{cls}: {count} ({percentage:.2f}%)")
    else:
        print("No annotations found.")


def main():
    parser = argparse.ArgumentParser(description="Analyze YOLO dataset class distribution.")
    parser.add_argument("yaml_path", type=str, help="Path to data.yaml")
    args = parser.parse_args()

    data_yaml_path = Path(args.yaml_path).resolve()
    if not data_yaml_path.exists():
        print(f"YAML file not found: {data_yaml_path}")
        return

    data = load_yaml(data_yaml_path)
    base_dir = data_yaml_path.parent

    # Resolve image and label paths relative to the data.yaml file
    train_images_dir = base_dir / data["train"]
    val_images_dir = base_dir / data["val"]

    train_labels_dir = train_images_dir.as_posix().replace("/images/", "/labels/")
    val_labels_dir = val_images_dir.as_posix().replace("/images/", "/labels/")

    print(f"Scanning {train_labels_dir} and {val_labels_dir}")

    class_names = data["names"]

    train_counts, train_total = count_labels(train_labels_dir, class_names)
    val_counts, val_total = count_labels(val_labels_dir, class_names)

    print_summary("Train", train_counts, train_total)
    print_summary("Test", val_counts, val_total)


if __name__ == "__main__":
    main()
