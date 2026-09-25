"""The training dataset: prepare it once, then assemble each experiment from it.

**prepare** (once, from a download such as the Roboflow TRA 2026 export) writes the
committed, already-split ``training/dataset``:

- canonical class ids (``configs/classes.yaml``, names mapped through
  ``configs/class_mapping.yaml``) and original file names (Roboflow's
  ``_jpg.rf.<hash>`` renames undone);
- test, then val, **stratified by rarest class** (or "background"), so rare classes
  such as delivery_van appear in every split in about the same proportion, **whole
  video sequences at a time**: consecutive frames are near-duplicates, and one in
  train with its neighbour in test would inflate every score;
- ``split.json``: method, seed, per-split image and instance counts, and the SHA-256
  of every test image and label, as proof the test split never changes.

**build** (per experiment) keeps that split as it is and writes a YOLO dataset under
``runs/datasets``: synthetic images, if any, go to train only; for final training,
val is merged into train. Test is never touched.

    python -m training.build_dataset --prepare data/tra2026 --out training/dataset
    python -m training.build_dataset --out runs/datasets/tra2026_synthetic \\
        --synthetic data/synthetic --syn-fraction 1.0
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
DATASET = Path("training/dataset")
SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class _Item:
    image: Path
    label: Path
    stem: str  # original file stem; "syn_" prefix for synthetic images
    lines: tuple[str, ...]  # label lines with canonical class ids

    def classes(self, names: list[str]) -> set[str]:
        return {names[int(line.split()[0])] for line in self.lines}


def sequence_of(stem: str) -> str:
    """The video sequence a frame belongs to; a still photo is its own sequence.

    TRA 2026 frames are named ``<sequence>_<frame>_<index>`` (``9_3_429_00000060``,
    ``09-26_25_2_10176_00000026``); COCO photos have a bare 12-digit id.
    """
    fields = stem.split("_")
    return "_".join(fields[:-2]) if len(fields) >= 4 else fields[0]


def stratified_split(
    classes: dict[str, set[str]],
    fractions: dict[str, float],
    seed: int,
    groups: dict[str, str] | None = None,
) -> dict[str, str]:
    """Assign each image to a split, stratified by rarest class, whole groups at a time.

    Args:
        classes: The classes present in each image (empty set: background).
        fractions: Share of each stratum's images for each named split; the rest is
            ``train``.
        seed: Seed for the shuffle within each stratum.
        groups: Image -> group (e.g. its video sequence). A group never spans two
            splits. Default: every image is its own group.

    Returns:
        ``{image: split}``.
    """
    groups = groups or {image: image for image in classes}
    members: dict[str, list[str]] = {}
    for image in sorted(classes):
        members.setdefault(groups[image], []).append(image)
    present = {g: set().union(*(classes[i] for i in imgs)) for g, imgs in members.items()}

    frequency = Counter(c for cs in present.values() for c in cs)
    strata: dict[str, list[str]] = {}
    for g in sorted(members):
        key = min(present[g], key=lambda c: (frequency[c], c)) if present[g] else ""
        strata.setdefault(key, []).append(g)

    rng = random.Random(seed)
    split: dict[str, str] = {}
    for key in sorted(strata):
        stratum = strata[key]
        rng.shuffle(stratum)
        size = sum(len(members[g]) for g in stratum)
        quota = {name: round(fraction * size) for name, fraction in fractions.items()}
        filled = dict.fromkeys(quota, 0)
        for g in stratum:
            name = next((n for n in quota if filled[n] < quota[n]), "train")
            if name != "train":
                filled[name] += len(members[g])
            split |= dict.fromkeys(members[g], name)
    return split


def prepare_dataset(
    source: Path,
    out: Path = DATASET,
    test_fraction: float = 0.1,
    val_fraction: float = 0.1,
    seed: int = 42,
) -> dict:
    """Write the split dataset at ``out`` (replacing it) and return ``split.json``.

    Raises:
        TaxonomyError: when the source uses a class name with no canonical mapping.
    """
    names = load_canonical_classes()
    items = _read_items(source)

    def split(pool: list[_Item], name: str, fraction: float) -> set[str]:
        chosen = stratified_split(
            {i.stem: i.classes(names) for i in pool},
            {name: fraction},
            seed,
            groups={i.stem: sequence_of(i.stem) for i in pool},
        )
        return {stem for stem, s in chosen.items() if s == name}

    test = split(items, "test", test_fraction)
    val = split([i for i in items if i.stem not in test], "val", val_fraction)
    splits = {
        "train": [i for i in items if i.stem not in test | val],
        "val": [i for i in items if i.stem in val],
        "test": [i for i in items if i.stem in test],
    }
    record = {
        "source": str(source),
        "created": date.today().isoformat(),
        "method": "stratified by rarest class; video sequences kept whole",
        "seed": seed,
        "test_fraction": test_fraction,
        "val_fraction": val_fraction,
    }
    record |= _write(out, splits, link=False)
    record["test_files"] = [
        {
            "image": f"{i.stem}{i.image.suffix}",
            "image_sha256": _sha256(i.image),
            "label_sha256": _sha256(i.label) if i.label.exists() else None,
        }
        for i in splits["test"]
    ]
    (out / "split.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def build_dataset(
    out: Path,
    dataset: Path = DATASET,
    synthetic: Path | None = None,
    syn_fraction: float | None = None,
    seed: int = 42,
    final: bool = False,
) -> dict:
    """Assemble one experiment's dataset at ``out`` from the prepared split.

    Args:
        out: Output directory (replaced).
        dataset: The prepared dataset (``prepare_dataset``).
        synthetic: Optional synthetic YOLO dataset; every image goes to train.
        syn_fraction: Cap synthetic images at this multiple of the real training
            images (seeded sample); ``None`` uses all of them.
        seed: Seed for the synthetic sample.
        final: Merge val into train (final training; validation is off).

    Raises:
        TaxonomyError: when the synthetic data uses a class name with no mapping.
    """
    items = _read_items(dataset)
    splits = {s: [i for i in items if i.image.parent.name == s] for s in SPLITS}
    if final:
        splits["train"], splits["val"] = splits["train"] + splits["val"], []
    if synthetic is not None:
        syn = _read_items(synthetic, prefix="syn_")
        if syn_fraction is not None:
            n = min(len(syn), round(syn_fraction * len(splits["train"])))
            syn = sorted(random.Random(seed).sample(syn, n), key=lambda i: i.stem)
        splits["train"] += syn

    manifest = {
        "dataset": str(dataset),
        "synthetic": str(synthetic) if synthetic else None,
        "syn_fraction": syn_fraction,
        "final": final,
        "seed": seed,
    }
    manifest |= _write(out, splits, link=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _write(out: Path, splits: dict[str, list[_Item]], link: bool) -> dict:
    """Write images (linked or copied), canonical labels and data.yaml; return counts."""
    names = load_canonical_classes()
    if out.exists():
        shutil.rmtree(out)
    counts = {}
    for split, members in splits.items():
        (out / "images" / split).mkdir(parents=True)
        (out / "labels" / split).mkdir(parents=True)
        for i in members:
            image = out / "images" / split / f"{i.stem}{i.image.suffix}"
            if link:
                image.symlink_to(i.image.resolve())
            else:
                shutil.copyfile(i.image, image)
            label = "".join(f"{line}\n" for line in i.lines)
            (out / "labels" / split / f"{i.stem}.txt").write_text(label)
        instances = Counter(names[int(line.split()[0])] for i in members for line in i.lines)
        counts[split] = {
            "images": len(members),
            "synthetic_images": sum(i.stem.startswith("syn_") for i in members),
            "instances": dict(sorted(instances.items(), key=lambda kv: names.index(kv[0]))),
        }
    # With no val split (final training), Ultralytics still needs a val path; training
    # then runs with validation off, so nothing is ever scored on it.
    val = "images/val" if splits["val"] else "images/train"
    data = {"path": str(out.resolve()), "train": "images/train", "val": val, "test": "images/test"}
    if not link:
        data.pop("path")  # the committed dataset is resolved next to its data.yaml
    data["names"] = dict(enumerate(names))
    (out / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return counts


def _read_items(root: Path, prefix: str = "") -> list[_Item]:
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
    """Prepare the dataset, or build one experiment's dataset, from the command line."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prepare", type=Path, metavar="SOURCE", help="download to split, once")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--test-fraction", type=float, default=0.1)
    ap.add_argument("--val-fraction", type=float, default=0.1)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--synthetic", type=Path)
    ap.add_argument("--syn-fraction", type=float, help="cap synthetic at this x real train images")
    ap.add_argument("--final", action="store_true", help="merge val into train")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.prepare:
        record = prepare_dataset(
            args.prepare, args.out, args.test_fraction, args.val_fraction, args.seed
        )
        record.pop("test_files")
    else:
        record = build_dataset(
            args.out, args.dataset, args.synthetic, args.syn_fraction, args.seed, args.final
        )
    logger.info(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
