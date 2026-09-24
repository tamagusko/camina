"""Build one training dataset from the real data and, optionally, synthetic data.

Output is a YOLO dataset with canonical class ids (``configs/classes.yaml``):

- **test** — the frozen held-out images listed in ``holdout_manifest.json``, and
  nothing else, so every experiment is scored on the same real images;
- **val** — the real dataset's ``val`` split minus the held-out images;
- **train** — the rest of the real images, plus the synthetic images if given.
  Synthetic data never enters ``val`` or ``test``.

Images are symlinked; labels are rewritten with canonical ids (each source's
own ``data.yaml`` names are mapped through ``configs/class_mapping.yaml``).
``manifest.json`` records the sources and per-split image and instance counts.

    python -m training.build_dataset --real training/dataset --out runs/datasets/real
    python -m training.build_dataset --real training/dataset --synthetic <dir> \\
        --syn-fraction 1.0 --out runs/datasets/real_syn
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
from collections import Counter
from pathlib import Path

import yaml

from training.class_taxonomy import load_canonical_classes, resolve_to_canonical

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_HOLDOUT = Path("training/holdout_manifest.json")


def build_dataset(
    real: Path,
    out: Path,
    holdout: Path = DEFAULT_HOLDOUT,
    synthetic: Path | None = None,
    syn_fraction: float | None = None,
    seed: int = 42,
) -> dict:
    """Assemble the dataset at ``out`` (replacing it) and return its manifest.

    Args:
        real: Real YOLO dataset with ``data.yaml`` and ``images/{train,val}``.
        out: Output directory.
        holdout: Manifest of the frozen held-out images (by file name).
        synthetic: Optional synthetic YOLO dataset; every image goes to train.
        syn_fraction: Cap synthetic images at this multiple of the real
            training images (seeded sample); ``None`` uses all of them.
        seed: Seed for the synthetic sample.

    Raises:
        TaxonomyError: when a source uses a class name with no canonical mapping.
    """
    classes = load_canonical_classes()
    test_names = {Path(r["image"]).name for r in json.loads(holdout.read_text())["test_files"]}

    real_images = _images(real)
    splits: dict[str, list[tuple[Path, str, Path]]] = {"train": [], "val": [], "test": []}
    for image in real_images:
        if image.name in test_names:
            split = "test"
        elif image.parent.name == "val":
            split = "val"
        else:
            split = "train"
        splits[split].append((image, image.stem, real))

    syn_images: list[Path] = []
    if synthetic is not None:
        syn_images = _images(synthetic)
        if syn_fraction is not None:
            n = min(len(syn_images), round(syn_fraction * len(splits["train"])))
            syn_images = sorted(random.Random(seed).sample(syn_images, n))
        splits["train"] += [(image, f"syn_{image.stem}", synthetic) for image in syn_images]

    to_canonical = {
        root: [classes.index(c) for c in resolve_to_canonical(_names(root))]
        for root in [real] + ([synthetic] if synthetic else [])
    }

    if out.exists():
        shutil.rmtree(out)
    manifest: dict = {
        "sources": {"real": str(real), "synthetic": str(synthetic) if synthetic else None},
        "holdout": str(holdout),
        "syn_fraction": syn_fraction,
        "seed": seed,
    }
    for split, items in splits.items():
        (out / "images" / split).mkdir(parents=True)
        (out / "labels" / split).mkdir(parents=True)
        instances: Counter[str] = Counter()
        for image, stem, root in items:
            (out / "images" / split / f"{stem}{image.suffix}").symlink_to(image.resolve())
            lines = []
            for line in _label_of(root, image).splitlines():
                if line.strip():
                    cls, *box = line.split()
                    canonical = to_canonical[root][int(cls)]
                    instances[classes[canonical]] += 1
                    lines.append(" ".join([str(canonical), *box]))
            (out / "labels" / split / f"{stem}.txt").write_text("".join(f"{x}\n" for x in lines))
        manifest[split] = {
            "images": len(items),
            "synthetic_images": sum(root != real for *_, root in items),
            "instances": dict(sorted(instances.items(), key=lambda kv: classes.index(kv[0]))),
        }

    data = {"path": str(out.resolve()), "train": "images/train", "val": "images/val"}
    data |= {"test": "images/test", "names": dict(enumerate(classes))}
    (out / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _images(root: Path) -> list[Path]:
    return sorted(p for p in (root / "images").rglob("*") if p.suffix.lower() in IMAGE_EXTS)


def _names(root: Path) -> list[str]:
    names = yaml.safe_load((root / "data.yaml").read_text())["names"]
    return [names[i] for i in sorted(names)] if isinstance(names, dict) else list(names)


def _label_of(root: Path, image: Path) -> str:
    label = root / "labels" / image.relative_to(root / "images").with_suffix(".txt")
    return label.read_text() if label.exists() else ""


def main() -> None:
    """Build a dataset from the command line and print its manifest."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--real", type=Path, default=Path("training/dataset"))
    ap.add_argument("--synthetic", type=Path)
    ap.add_argument("--syn-fraction", type=float, help="cap synthetic at this x real train images")
    ap.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    manifest = build_dataset(
        args.real, args.out, args.holdout, args.synthetic, args.syn_fraction, args.seed
    )
    logger.info(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
