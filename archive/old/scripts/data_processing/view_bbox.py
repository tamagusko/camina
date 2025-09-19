import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

# --------------------------------------------------------------------------- #
# Configuration: map class IDs to labels
# --------------------------------------------------------------------------- #
LABEL_MAP: Dict[int, str] = {
    0: "bus",
    1: "car",
    2: "cyclist",
    3: "motorcycle",
    4: "person",
    5: "truck",
}

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def has_class(label_path: Path, target_class: int) -> bool:
    with label_path.open() as f:
        return any(int(line.split()[0]) == target_class for line in f if line.strip())

def gather_pairs(
    images_dir: Path, labels_dir: Path, class_id: int
) -> List[Tuple[Path, Path]]:
    pairs: List[Tuple[Path, Path]] = []
    for img_path in sorted(images_dir.glob("*.*")):
        lbl_path = labels_dir / f"{img_path.stem}.txt"
        if not lbl_path.exists():
            continue
        if class_id >= 0 and not has_class(lbl_path, class_id):
            continue
        pairs.append((img_path, lbl_path))
    return pairs

def draw_annotations(image_path: str, label_path: str, label_map: Dict[int, str]) -> None:
    image = cv2.imread(image_path)
    if image is None:
        return

    with open(label_path, "r") as f:
        labels = [line.strip().split() for line in f if line.strip()]

    for label in labels:
        cls_id, x, y, w, h = map(float, label)
        cls_id = int(cls_id)
        label_str = label_map.get(cls_id, str(cls_id))

        h_img, w_img = image.shape[:2]
        x1 = int((x - w / 2) * w_img)
        y1 = int((y - h / 2) * h_img)
        x2 = int((x + w / 2) * w_img)
        y2 = int((y + h / 2) * h_img)

        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(image, label_str, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("YOLO Dataset Viewer", image)

# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="YOLO dataset visualizer")
    parser.add_argument("--root", type=Path, default=Path("datasets/SDL-fine-tuned"))
    parser.add_argument("--split", choices=("train", "test", "val"), default="train")
    parser.add_argument("--class-id", type=int, default=-1, help="Class ID to filter by (-1 = all classes)")
    args = parser.parse_args()

    images_dir = args.root / "images" / args.split
    labels_dir = args.root / "labels" / args.split

    if not images_dir.is_dir() or not labels_dir.is_dir():
        sys.exit("Error: 'images/<split>' or 'labels/<split>' directory not found")

    pairs = gather_pairs(images_dir, labels_dir, args.class_id)
    if not pairs:
        sys.exit("No images matched the criteria.")

    print(f"Viewing {len(pairs)} images (press SPACE to continue, Q to quit)")

    for img_path, lbl_path in pairs:
        draw_annotations(str(img_path), str(lbl_path), LABEL_MAP)
        while True:
            key = cv2.waitKey(0) & 0xFF
            if key == ord("q"):
                cv2.destroyAllWindows()
                sys.exit(0)
            elif key == ord(" "):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
