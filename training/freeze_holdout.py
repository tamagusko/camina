#!/usr/bin/env python3
"""Freeze a stratified, hashed held-out test set for CAMINAv1 evaluation.

Implements ``training/EVALUATION.md §1``: carve a deterministic, class-presence
stratified held-out split out of a converted YOLO dataset, materialise it into
``images/test`` + ``labels/test`` (so it is excluded from the train/val paths),
and record an immutable manifest — the SHA-256 of every image and label plus a
manifest hash over the whole set — as committable proof the set never changed.

Determinism: the same ``--seed`` over the same pooled files always selects the
same held-out set and produces the same ``manifest_sha256``. The pool is the
union of train+val+test each run, so re-running is idempotent.

The manifest (``training/holdout_manifest.json`` by default) is the one
TRACKED artefact; it stores paths **relative to the dataset root** only, so it
references the gitignored dataset without embedding machine-specific paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import shutil
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

POOL_SPLITS = ("train", "val", "test")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
DEFAULT_MANIFEST = Path("training/holdout_manifest.json")


class HoldoutError(ValueError):
    """Raised when the held-out set cannot be frozen safely."""


def _sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _class_ids(label_file: Path | None) -> tuple[int, ...]:
    """Return the sorted unique class-ids present in a label file (() if none)."""
    if label_file is None or not label_file.exists():
        return ()
    ids = set()
    with open(label_file) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) == 5:
                try:
                    ids.add(int(parts[0]))
                except ValueError:
                    continue
    return tuple(sorted(ids))


def _gather_pool(dataset_root: Path, splits: Sequence[str]) -> dict[str, dict[str, Path | None]]:
    """Collect ``stem -> {image, label, split}`` pairs across the given splits.

    Raises:
        HoldoutError: if a filename stem appears in more than one split.
    """
    pool: dict[str, dict[str, Path | None]] = {}
    for split in splits:
        img_dir = dataset_root / "images" / split
        if not img_dir.is_dir():
            continue
        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in IMAGE_EXTS:
                continue
            stem = img.stem
            if stem in pool:
                raise HoldoutError(
                    f"Duplicate image stem {stem!r} across splits "
                    f"({pool[stem]['split']} and {split}); stems must be unique."
                )
            label = dataset_root / "labels" / split / f"{stem}.txt"
            pool[stem] = {
                "image": img,
                "label": label if label.exists() else None,
                "split": split,  # type: ignore[dict-item]
            }
    return pool


def _stratified_select(
    pool: dict[str, dict[str, Path | None]],
    frac: float,
    seed: int,
) -> list[str]:
    """Deterministically select ~``frac`` of stems, stratified by class presence.

    Groups images by the sorted set of class-ids they contain, then samples the
    same fraction from each stratum with a seeded RNG. Returns sorted stems.
    """
    strata: dict[tuple[int, ...], list[str]] = {}
    for stem, entry in pool.items():
        key = _class_ids(entry["label"])
        strata.setdefault(key, []).append(stem)

    rng = random.Random(seed)
    selected: list[str] = []
    for key in sorted(strata.keys()):
        members = sorted(strata[key])
        rng.shuffle(members)
        n_test = round(frac * len(members))
        selected.extend(members[:n_test])
    return sorted(selected)


def _relocate_to_test(
    dataset_root: Path,
    pool: dict[str, dict[str, Path | None]],
    selected: Sequence[str],
) -> None:
    """Move selected image/label pairs into images/test and labels/test.

    Idempotent: a pair already under ``test`` is left in place.

    Raises:
        HoldoutError: if the test split already holds a non-selected file
            (a leftover from a different seed), to avoid mixing splits.
    """
    selected_set = set(selected)
    test_img_dir = dataset_root / "images" / "test"
    test_lbl_dir = dataset_root / "labels" / "test"
    test_img_dir.mkdir(parents=True, exist_ok=True)
    test_lbl_dir.mkdir(parents=True, exist_ok=True)

    for stem, entry in pool.items():
        if entry["split"] == "test" and stem not in selected_set:
            raise HoldoutError(
                f"images/test already contains non-selected file {stem!r}; the test "
                "split holds a set from a different seed. Reset the dataset before re-freezing."
            )

    for stem in selected:
        entry = pool[stem]
        if entry["split"] == "test":
            continue
        img = entry["image"]
        assert img is not None
        shutil.move(str(img), str(test_img_dir / img.name))
        label = entry["label"]
        if label is not None:
            shutil.move(str(label), str(test_lbl_dir / label.name))


def _build_file_records(dataset_root: Path, selected: Sequence[str]) -> list[dict[str, str | None]]:
    """Build sorted per-file records (relative paths + sha256) from the test split."""
    records: list[dict[str, str | None]] = []
    test_img_dir = dataset_root / "images" / "test"
    test_lbl_dir = dataset_root / "labels" / "test"
    for stem in sorted(selected):
        image = next(
            (p for ext in IMAGE_EXTS for p in [test_img_dir / f"{stem}{ext}"] if p.exists()),
            None,
        )
        if image is None:
            raise HoldoutError(f"Selected image for stem {stem!r} missing from images/test.")
        label = test_lbl_dir / f"{stem}.txt"
        records.append(
            {
                "image": str(image.relative_to(dataset_root)),
                "label": str(label.relative_to(dataset_root)) if label.exists() else None,
                "image_sha256": _sha256_file(image),
                "label_sha256": _sha256_file(label) if label.exists() else None,
            }
        )
    records.sort(key=lambda r: r["image"])  # stable, path-ordered
    return records


def _manifest_sha256(records: Sequence[dict[str, str | None]]) -> str:
    """Hash the file set + contents only (independent of run date / metadata)."""
    digest = hashlib.sha256()
    for rec in records:
        line = "|".join(str(rec[k]) for k in ("image", "image_sha256", "label", "label_sha256"))
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def freeze_holdout(
    data_yaml: Path,
    frac: float = 0.15,
    seed: int = 42,
    dataset_tag: str | None = None,
) -> dict[str, object]:
    """Carve and materialise the frozen held-out set; return the manifest dict."""
    with open(data_yaml) as f:
        config = yaml.safe_load(f) or {}
    dataset_root = Path(config.get("path", data_yaml.parent))
    if not dataset_root.is_absolute():
        dataset_root = (data_yaml.parent / dataset_root).resolve()

    pool = _gather_pool(dataset_root, POOL_SPLITS)
    if not pool:
        raise HoldoutError(
            f"No images found under {dataset_root}/images/{{{','.join(POOL_SPLITS)}}}."
        )

    selected = _stratified_select(pool, frac=frac, seed=seed)
    if not selected:
        raise HoldoutError(f"frac={frac} selected 0 images from a pool of {len(pool)}.")

    _relocate_to_test(dataset_root, pool, selected)
    records = _build_file_records(dataset_root, selected)
    manifest_hash = _manifest_sha256(records)

    manifest: dict[str, object] = {
        "dataset": dataset_root.name,
        "dataset_tag": dataset_tag,
        "created": date.today().isoformat(),
        "seed": seed,
        "frac": frac,
        "num_pool": len(pool),
        "num_test": len(records),
        "test_files": records,
        "manifest_sha256": manifest_hash,
    }
    return manifest


def _write_manifest(manifest: dict[str, object], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze a stratified, hashed held-out test set (training/EVALUATION.md §1).",
    )
    parser.add_argument("--data", required=True, type=Path, help="Path to the dataset data.yaml.")
    parser.add_argument(
        "--frac", type=float, default=0.15, help="Held-out fraction (default 0.15)."
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed (default 42).")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Manifest output path (default {DEFAULT_MANIFEST}).",
    )
    parser.add_argument("--dataset-tag", default=None, help="Optional dataset version tag.")
    args = parser.parse_args()

    try:
        manifest = freeze_holdout(
            args.data, frac=args.frac, seed=args.seed, dataset_tag=args.dataset_tag
        )
    except (HoldoutError, FileNotFoundError) as exc:
        logger.error("Freeze FAILED: %s", exc)
        return 1

    _write_manifest(manifest, args.manifest)
    logger.info(
        "Froze %d/%d images into held-out test set (seed=%d, frac=%.2f)",
        manifest["num_test"],
        manifest["num_pool"],
        args.seed,
        args.frac,
    )
    logger.info("manifest_sha256=%s", manifest["manifest_sha256"])
    logger.info("Wrote manifest -> %s", args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
