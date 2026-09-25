"""Build one training dataset from the real data and, optionally, synthetic data.

Output is a YOLO dataset with canonical class ids (``configs/classes.yaml``):

- **test** — the images frozen in the holdout manifest, and nothing else, so every
  experiment is scored on the same real images;
- **val** — a stratified share of the other real images;
- **train** — the rest, plus the synthetic images if given. Synthetic data never
  enters ``val`` or ``test``.

Test and val are **stratified by each image's rarest class** (or "background"),
so rare classes such as delivery_van appear in every split in the same
proportion. The test split is chosen once (``--freeze-test``) and stored with
hashes; images added later only ever go to train or val.

Sources may be laid out as ``images/<split>/`` or, as Roboflow exports them,
``<split>/images/``; Roboflow's ``_jpg.rf.<hash>`` renames are undone. Images
are symlinked; labels are rewritten with canonical ids.

    python -m training.build_dataset --freeze-test training/holdout_manifest.json
    python -m training.build_dataset --real data/tra2026 --out runs/datasets/tra2026
    python -m training.build_dataset --real data/tra2026 --synthetic data/synthetic \\
        --syn-fraction 1.0 --out runs/datasets/tra2026_synthetic
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from training.class_taxonomy import load_canonical_classes, resolve_to_canonical

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_HOLDOUT = Path("training/holdout_manifest.json")


@dataclass(frozen=True)
class _Item:
    image: Path
    label: Path
    stem: str  # original file stem; "syn_" prefix for synthetic images
    lines: tuple[str, ...]  # label lines with canonical class ids

    @property
    def classes(self) -> set[int]:
        return {int(line.split()[0]) for line in self.lines}


def stratified_split(
    classes: dict[str, set[str]], fractions: dict[str, float], seed: int
) -> dict[str, str]:
    """Assign each image to a split, stratified by its rarest class.

    Args:
        classes: The classes present in each image (empty set: background).
        fractions: Share of each group for each named split; the rest is ``train``.
        seed: Seed for the shuffle within each group.

    Returns:
        ``{image: split}``.
    """
    frequency = Counter(c for present in classes.values() for c in present)
    groups: dict[str, list[str]] = {}
    for image in sorted(classes):
        present = classes[image]
        key = min(present, key=lambda c: (frequency[c], c)) if present else ""
        groups.setdefault(key, []).append(image)

    rng = random.Random(seed)
    split: dict[str, str] = {}
    for key in sorted(groups):
        members = groups[key]
        rng.shuffle(members)
        start = 0
        for name, fraction in fractions.items():
            n = round(fraction * len(members))
            split |= dict.fromkeys(members[start : start + n], name)
            start += n
        split |= dict.fromkeys(members[start:], "train")
    return split


def freeze_test(
    real: Path, manifest_path: Path = DEFAULT_HOLDOUT, fraction: float = 0.1, seed: int = 42
) -> dict:
    """Choose the stratified test split of ``real`` once and store it with hashes."""
    names = load_canonical_classes()
    items = _read_items(real, "")
    split = stratified_split(
        {i.stem: {names[c] for c in i.classes} for i in items}, {"test": fraction}, seed
    )
    test = [i for i in items if split[i.stem] == "test"]
    instances = Counter(names[int(line.split()[0])] for i in test for line in i.lines)
    manifest = {
        "dataset": str(real),
        "created": date.today().isoformat(),
        "method": "stratified by each image's rarest class",
        "seed": seed,
        "fraction": fraction,
        "num_pool": len(items),
        "num_test": len(test),
        "instances": dict(sorted(instances.items(), key=lambda kv: names.index(kv[0]))),
        "test_files": [
            {
                "image": f"{i.stem}{i.image.suffix}",
                "image_sha256": _sha256(i.image),
                "label_sha256": _sha256(i.label) if i.label.exists() else None,
            }
            for i in test
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def build_dataset(
    real: Path,
    out: Path,
    holdout: Path = DEFAULT_HOLDOUT,
    synthetic: Path | None = None,
    syn_fraction: float | None = None,
    seed: int = 42,
    val_fraction: float = 0.1,
) -> dict:
    """Assemble the dataset at ``out`` (replacing it) and return its manifest.

    Args:
        real: Real YOLO dataset (``data.yaml`` and images with labels).
        out: Output directory.
        holdout: Manifest from ``freeze_test``; its images form the test split.
        synthetic: Optional synthetic YOLO dataset; every image goes to train.
        syn_fraction: Cap synthetic images at this multiple of the real training
            images (seeded sample); ``None`` uses all of them.
        seed: Seed for the validation split and the synthetic sample.
        val_fraction: Stratified share of the non-test real images used for val.

    Raises:
        TaxonomyError: when a source uses a class name with no canonical mapping.
    """
    names = load_canonical_classes()
    test_stems = {Path(r["image"]).stem for r in json.loads(holdout.read_text())["test_files"]}

    items = _read_items(real, "")
    pool = [i for i in items if i.stem not in test_stems]
    val = stratified_split(
        {i.stem: {names[c] for c in i.classes} for i in pool}, {"val": val_fraction}, seed
    )
    splits = {
        "train": [i for i in pool if val[i.stem] == "train"],
        "val": [i for i in pool if val[i.stem] == "val"],
        "test": [i for i in items if i.stem in test_stems],
    }
    if synthetic is not None:
        syn = _read_items(synthetic, "syn_")
        if syn_fraction is not None:
            n = min(len(syn), round(syn_fraction * len(splits["train"])))
            syn = sorted(random.Random(seed).sample(syn, n), key=lambda i: i.stem)
        splits["train"] += syn

    if out.exists():
        shutil.rmtree(out)
    manifest: dict = {
        "sources": {"real": str(real), "synthetic": str(synthetic) if synthetic else None},
        "holdout": str(holdout),
        "syn_fraction": syn_fraction,
        "val_fraction": val_fraction,
        "seed": seed,
    }
    for split, members in splits.items():
        (out / "images" / split).mkdir(parents=True)
        (out / "labels" / split).mkdir(parents=True)
        for i in members:
            (out / "images" / split / f"{i.stem}{i.image.suffix}").symlink_to(i.image.resolve())
            (out / "labels" / split / f"{i.stem}.txt").write_text(
                "".join(f"{x}\n" for x in i.lines)
            )
        instances = Counter(names[int(line.split()[0])] for i in members for line in i.lines)
        manifest[split] = {
            "images": len(members),
            "synthetic_images": sum(i.stem.startswith("syn_") for i in members),
            "instances": dict(sorted(instances.items(), key=lambda kv: names.index(kv[0]))),
        }

    # With no val split (final training), Ultralytics still needs a val path; training
    # then runs with validation off, so nothing is ever scored on it.
    val_dir = "images/val" if splits["val"] else "images/train"
    data = {"path": str(out.resolve()), "train": "images/train", "val": val_dir}
    data |= {"test": "images/test", "names": dict(enumerate(names))}
    (out / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _read_items(root: Path, prefix: str) -> list[_Item]:
    """Every image under ``root`` with its label lines in canonical class ids."""
    names = load_canonical_classes()
    to_canonical = [names.index(c) for c in resolve_to_canonical(_names(root))]
    items = []
    for image in sorted(p for p in root.rglob("*") if _is_image(root, p)):
        label = _label_path(root, image)
        text = label.read_text() if label.exists() else ""
        lines = tuple(
            " ".join([str(to_canonical[int(cls)]), *box])
            for cls, *box in (line.split() for line in text.splitlines() if line.strip())
        )
        items.append(_Item(image, label, prefix + _original_stem(image), lines))
    return items


def _is_image(root: Path, path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS and "images" in path.relative_to(root).parts


def _label_path(root: Path, image: Path) -> Path:
    parts = list(image.relative_to(root).parts)
    i = len(parts) - 1 - parts[::-1].index("images")
    return root.joinpath(*parts[:i], "labels", *parts[i + 1 :]).with_suffix(".txt")


def _original_stem(image: Path) -> str:
    """File stem without Roboflow's ``_jpg.rf.<hash>`` rename."""
    return re.sub(r"_(jpe?g|png|bmp|webp)\.rf\.[0-9a-f]+$", "", image.stem, flags=re.IGNORECASE)


def _names(root: Path) -> list[str]:
    names = yaml.safe_load((root / "data.yaml").read_text())["names"]
    return [names[i] for i in sorted(names)] if isinstance(names, dict) else list(names)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Freeze the test split, or build a dataset, from the command line."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--real", type=Path, default=Path("data/tra2026"))
    ap.add_argument("--freeze-test", type=Path, metavar="MANIFEST", help="choose and store test")
    ap.add_argument("--test-fraction", type=float, default=0.1)
    ap.add_argument("--synthetic", type=Path)
    ap.add_argument("--syn-fraction", type=float, help="cap synthetic at this x real train images")
    ap.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    ap.add_argument("--val-fraction", type=float, default=0.1)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.freeze_test:
        manifest = freeze_test(args.real, args.freeze_test, args.test_fraction, args.seed)
        manifest = {k: v for k, v in manifest.items() if k != "test_files"}
    elif args.out:
        manifest = build_dataset(
            args.real,
            args.out,
            args.holdout,
            args.synthetic,
            args.syn_fraction,
            args.seed,
            args.val_fraction,
        )
    else:
        ap.error("give --freeze-test MANIFEST or --out DIR")
    logger.info(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
