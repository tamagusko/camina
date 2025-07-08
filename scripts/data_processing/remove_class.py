from pathlib import Path


def remove_object_class(label_dir: str, object_class_index: int) -> None:
    """
    Removes the 'object' class from YOLO label files and shifts the class indices accordingly.

    Args:
        label_dir (str): Path to the directory containing YOLO label .txt files.
        object_class_index (int): Index of the class to be removed.
    """
    label_path = Path(label_dir)
    label_files = list(label_path.rglob("*.txt"))

    for file_path in label_files:
        updated_lines = []

        for line in file_path.read_text().splitlines():
            parts = line.strip().split()
            class_id = int(parts[0])

            if class_id == object_class_index:
                continue  # Skip 'object' class

            if class_id > object_class_index:
                class_id -= 1  # Shift class index down by 1

            parts[0] = str(class_id)
            updated_lines.append(" ".join(parts))

        file_path.write_text("\n".join(updated_lines))


if __name__ == "__main__":
    CLASS_TO_REMOVE = 4  # Index of the class to be removed (e.g., 'object' class)
    base_path = Path("/Users/tamagusko/repos/camina/custom_model_train/datasets/SDL-fine-tuned/labels")
    remove_object_class(base_path / "train", CLASS_TO_REMOVE)
    remove_object_class(base_path / "test", CLASS_TO_REMOVE)
