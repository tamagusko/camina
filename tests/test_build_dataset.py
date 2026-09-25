"""Tests for the training-dataset builder.

The builder turns the real dataset (and, optionally, a synthetic one) into one
YOLO dataset with canonical class ids. Rules that keep experiments comparable:

- the test split is frozen in a manifest, and those images go nowhere else;
- test and val are stratified by each image's rarest class, so rare classes
  appear in every split in the same proportion;
- synthetic images only ever go to ``train``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.build_dataset import build_dataset, freeze_test, stratified_split
from training.class_taxonomy import TaxonomyError

CANONICAL = [
    "person",
    "cyclist",
    "car",
    "e-scooter",
    "SUV",
    "motorcyclist",
    "bus",
    "delivery_van",
    "truck",
]


def _roboflow(root: Path, names: list[str], files: dict[str, str]) -> Path:
    """A Roboflow export: ``train/images``, ``train/labels``, renamed files."""
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    for stem, label in files.items():
        rf = f"{stem}_jpg.rf.0123abcd"
        (root / "train" / "images" / f"{rf}.jpg").write_bytes(stem.encode())
        (root / "train" / "labels" / f"{rf}.txt").write_text(label)
    (root / "data.yaml").write_text(yaml.safe_dump({"names": names}))
    return root


def _yolo(root: Path, names: list[str], files: dict[str, str]) -> Path:
    """A plain YOLO dataset: ``images/train``, ``labels/train``."""
    (root / "images" / "train").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    for stem, label in files.items():
        (root / "images" / "train" / f"{stem}.jpg").write_bytes(stem.encode())
        (root / "labels" / "train" / f"{stem}.txt").write_text(label)
    (root / "data.yaml").write_text(yaml.safe_dump({"names": dict(enumerate(names))}))
    return root


def _read(out: Path, split: str) -> dict[str, str]:
    return {p.stem: p.read_text() for p in sorted((out / "labels" / split).glob("*.txt"))}


def _no_holdout(tmp_path: Path) -> Path:
    path = tmp_path / "holdout.json"
    path.write_text(json.dumps({"test_files": []}))
    return path


# 200 images: every one has a person; 20 also have a van (the rare class).
PEOPLE_AND_VANS = {
    f"img{i:03d}": "0 0.5 0.5 0.1 0.2\n" + ("1 0.3 0.3 0.2 0.2\n" if i % 10 == 0 else "")
    for i in range(200)
}


@pytest.fixture
def real(tmp_path: Path) -> Path:
    return _roboflow(tmp_path / "real", ["person", "delivery_van"], PEOPLE_AND_VANS)


# ---------- stratified_split ----------


def test_a_rare_class_gets_the_same_share_of_every_split() -> None:
    classes = {
        s: {"person", "delivery_van"} if i % 10 == 0 else {"person"}
        for i, s in enumerate(PEOPLE_AND_VANS)
    }

    split = stratified_split(classes, {"test": 0.1, "val": 0.1}, seed=42)

    vans = [split[s] for s, c in classes.items() if "delivery_van" in c]
    assert vans.count("test") == 2 and vans.count("val") == 2 and vans.count("train") == 16
    assert list(split.values()).count("test") == 20


def test_the_split_is_deterministic() -> None:
    classes = {s: {"person"} for s in PEOPLE_AND_VANS}

    assert stratified_split(classes, {"test": 0.1}, 7) == stratified_split(
        classes, {"test": 0.1}, 7
    )


def test_background_images_are_stratified_too() -> None:
    classes = {f"bg{i}": set() for i in range(10)} | {f"p{i}": {"person"} for i in range(10)}

    split = stratified_split(classes, {"test": 0.2}, seed=1)

    assert sum(split[f"bg{i}"] == "test" for i in range(10)) == 2


# ---------- freeze_test + build_dataset ----------


def test_the_frozen_test_split_is_stratified_and_hashed(real: Path, tmp_path: Path) -> None:
    manifest = freeze_test(real, tmp_path / "holdout.json", fraction=0.1, seed=42)

    assert manifest["num_test"] == 20
    assert manifest["instances"]["delivery_van"] == 2
    record = manifest["test_files"][0]
    assert set(record) == {"image", "image_sha256", "label_sha256"}
    assert "_jpg.rf." not in record["image"]  # original name, not Roboflow's
    assert json.loads((tmp_path / "holdout.json").read_text()) == manifest


def test_build_puts_the_frozen_test_images_in_test_only(real: Path, tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    frozen = {Path(r["image"]).stem for r in freeze_test(real, holdout)["test_files"]}
    out = tmp_path / "out"

    manifest = build_dataset(real, out, holdout=holdout, val_fraction=0.1)

    assert set(_read(out, "test")) == frozen
    assert not frozen & (set(_read(out, "train")) | set(_read(out, "val")))
    assert manifest["val"]["instances"]["delivery_van"] == 2  # stratified val as well
    assert manifest["train"]["images"] + manifest["val"]["images"] == 180


def test_labels_are_rewritten_to_canonical_ids(tmp_path: Path) -> None:
    real = _yolo(
        tmp_path / "real",
        ["pedestrian", "motorcycle"],
        {"a": "0 0.5 0.5 0.1 0.2\n1 0.4 0.4 0.1 0.1\n"},
    )

    build_dataset(real, tmp_path / "out", holdout=_no_holdout(tmp_path), val_fraction=0.0)

    ids = [line.split()[0] for line in _read(tmp_path / "out", "train")["a"].splitlines()]
    assert ids == [str(CANONICAL.index("person")), str(CANONICAL.index("motorcyclist"))]
    data = yaml.safe_load((tmp_path / "out" / "data.yaml").read_text())
    assert data["names"] == dict(enumerate(CANONICAL))


def test_synthetic_images_go_to_train_only_and_can_be_capped(real: Path, tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.json"
    freeze_test(real, holdout)
    syn = _yolo(tmp_path / "syn", ["SUV"], {f"s{i}": "0 0.5 0.5 0.2 0.2\n" for i in range(500)})
    out = tmp_path / "out"

    manifest = build_dataset(real, out, holdout=holdout, synthetic=syn, syn_fraction=1.0)

    train = _read(out, "train")
    synthetic = [label for stem, label in train.items() if stem.startswith("syn_")]
    assert manifest["train"]["synthetic_images"] == len(synthetic) == len(train) // 2
    assert synthetic[0].split()[0] == str(CANONICAL.index("SUV"))
    assert not any(k.startswith("syn_") for k in _read(out, "val") | _read(out, "test"))


def test_an_unknown_class_name_fails_loudly(real: Path, tmp_path: Path) -> None:
    syn = _yolo(tmp_path / "syn", ["tram"], {"s1": "0 0.5 0.5 0.2 0.2\n"})

    with pytest.raises(TaxonomyError, match="tram"):
        build_dataset(real, tmp_path / "out", holdout=_no_holdout(tmp_path), synthetic=syn)


def test_with_no_val_split_the_training_images_stand_in_for_val(real: Path, tmp_path: Path) -> None:
    """Final training merges val into train; Ultralytics still needs a val path."""
    holdout = tmp_path / "holdout.json"
    freeze_test(real, holdout)
    out = tmp_path / "out"

    manifest = build_dataset(real, out, holdout=holdout, val_fraction=0.0)

    assert manifest["val"]["images"] == 0 and manifest["train"]["images"] == 180
    assert yaml.safe_load((out / "data.yaml").read_text())["val"] == "images/train"


# ---------- video sequences never cross splits ----------


def test_frames_of_one_sequence_stay_in_one_split() -> None:
    """Consecutive frames are near-duplicates: split by sequence, not by frame."""
    classes = {f"seq{s}_{f:03d}_{f:08d}": {"person"} for s in range(20) for f in range(10)}
    groups = {stem: stem.rsplit("_", 2)[0] for stem in classes}

    split = stratified_split(classes, {"test": 0.1, "val": 0.1}, seed=3, groups=groups)

    by_group: dict[str, set[str]] = {}
    for stem, name in split.items():
        by_group.setdefault(groups[stem], set()).add(name)
    assert all(len(splits) == 1 for splits in by_group.values())
    assert list(split.values()).count("test") == 20  # 2 whole sequences of 10


def test_sequence_names_group_frames_and_leave_photos_alone() -> None:
    from training.build_dataset import sequence_of

    assert sequence_of("9_3_429_00000060") == sequence_of("9_3_431_00000066") == "9_3"
    assert sequence_of("09-26_25_2_10176_00000026") == "09-26_25_2"
    assert sequence_of("000000001722") == "000000001722"  # a COCO photo is its own group
