"""Render the guide's example figures from training/dataset (labels as committed).

    PYTHONPATH=. .venv/bin/python docs/labelling_guide/render.py

Each example is an image stem, an optional crop (fractions x1 y1 x2 y2) and the file
it is written to under docs/labelling_guide/figures/.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from training.class_taxonomy import load_canonical_classes

DATASET = Path("training/dataset")
OUT = Path("docs/labelling_guide/figures")
NAMES = load_canonical_classes()
# One colour per class (BGR), readable in print.
COLOURS = {
    "person": (180, 119, 31),
    "cyclist": (44, 160, 44),
    "car": (40, 39, 214),
    "e-scooter": (189, 103, 148),
    "SUV": (14, 127, 255),
    "motorcyclist": (75, 86, 140),
    "bus": (194, 119, 227),
    "delivery_van": (34, 189, 188),
    "truck": (127, 127, 127),
}
HEIGHT = 420  # output height in pixels

EXAMPLES: list[tuple[str, tuple[float, float, float, float] | None, str]] = [
    # One box per road user: rider and vehicle together
    ("000000255158", (0.05, 0.15, 0.65, 1.0), "rider_cyclist.jpg"),
    ("09-26_8_1_5630_00000072", (0.2, 0.0, 0.75, 1.0), "rider_escooter.jpg"),
    ("000000418535", (0.6, 0.0, 1.0, 0.32), "rider_motorcyclist.jpg"),
    # Rider classes need a rider (errors in the dataset)
    ("000000572362", (0.55, 0.45, 1.0, 1.0), "err_parked_bicycles.jpg"),
    ("09-26_29_5_15285_00000049", None, "rider_stopped.jpg"),
    ("00000004_000", (0.3, 0.0, 0.85, 1.0), "err_rider_as_person.jpg"),
    # Car and SUV
    ("000000449760", (0.0, 0.3, 0.55, 0.85), "car_sedan.jpg"),
    ("000000449760", (0.62, 0.45, 1.0, 1.0), "suv_4x4.jpg"),
    ("000000203458", (0.45, 0.1, 1.0, 0.5), "suv_street.jpg"),
    # Vans, trucks, buses
    ("000000012818", (0.72, 0.5, 1.0, 0.75), "van.jpg"),
    ("000000187473", (0.62, 0.35, 1.0, 0.85), "truck.jpg"),
    ("000000559974", (0.1, 0.1, 0.95, 1.0), "bus.jpg"),
    # Other errors in the dataset
    ("000000019499", (0.25, 0.05, 0.7, 0.5), "err_car_as_truck.jpg"),
    ("000000440032", (0.72, 0.15, 1.0, 0.55), "err_tram_as_bus.jpg"),
    ("00000004_000", (0.0, 0.0, 0.5, 0.55), "err_two_classes.jpg"),
]


def _find(stem: str) -> tuple[Path, Path]:
    for image in (DATASET / "images").glob(f"*/{stem}.*"):
        return image, DATASET / "labels" / image.parent.name / f"{stem}.txt"
    raise FileNotFoundError(stem)


def render(stem: str, crop: tuple[float, float, float, float] | None) -> np.ndarray:
    """The image with its committed boxes drawn, optionally cropped."""
    image_path, label_path = _find(stem)
    image = cv2.imread(str(image_path))
    h, w = image.shape[:2]
    thick = max(2, round(max(h, w) / 300))
    for line in label_path.read_text().splitlines():
        c, x, y, bw, bh = line.split()
        name = NAMES[int(c)]
        x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
        p1 = (round(x - bw / 2), round(y - bh / 2))
        p2 = (round(x + bw / 2), round(y + bh / 2))
        cv2.rectangle(image, p1, p2, COLOURS[name], thick)
    if crop:
        x1, y1, x2, y2 = crop
        image = image[round(y1 * h) : round(y2 * h), round(x1 * w) : round(x2 * w)]
    return cv2.resize(image, None, fx=HEIGHT / image.shape[0], fy=HEIGHT / image.shape[0])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, crop, name in EXAMPLES:
        cv2.imwrite(str(OUT / name), render(stem, crop), [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    main()
