"""Tests for the dataset tools.

``prepare_dataset`` turns a download (e.g. the Roboflow TRA 2026 export) into the
committed, already-split ``training/dataset``: canonical class ids, original file
names, test and val stratified by rarest class with whole video sequences. It runs
once; ``build_dataset`` then assembles each experiment from that split, adding
synthetic images to train only, or merging val into train for final training.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.build_dataset import build_dataset, prepare_dataset, sequence_of, stratified_split
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


def _stems(root: Path, split: str) -> set[str]:
    return {p.stem for p in (root / "labels" / split).glob("*.txt")}


# 200 images: every one has a person (SDL name "pedestrian"); 20 also have a van.
PEOPLE_AND_VANS = {
    f"{i:012d}": "0 0.5 0.5 0.1 0.2\n" + ("1 0.3 0.3 0.2 0.2\n" if i % 10 == 0 else "")
    for i in range(200)
}


@pytest.fixture
def download(tmp_path: Path) -> Path:
    return _roboflow(tmp_path / "download", ["pedestrian", "delivery_van"], PEOPLE_AND_VANS)


@pytest.fixture
def prepared(download: Path, tmp_path: Path) -> Path:
    prepare_dataset(download, tmp_path / "dataset")
    return tmp_path / "dataset"


# ---------- stratified_split ----------


def test_a_rare_class_gets_the_same_share_of_every_split() -> None:
    classes = {
        s: {"person", "delivery_van"} if i % 10 == 0 else {"person"}
        for i, s in enumerate(PEOPLE_AND_VANS)
    }

    split = stratified_split(classes, {"test": 0.1, "val": 0.1}, seed=42)

    vans = [split[s] for s, c in classes.items() if "delivery_van" in c]
    assert vans.count("test") == 2 and vans.count("val") == 2 and vans.count("train") == 16


def test_the_split_is_deterministic() -> None:
    classes = {s: {"person"} for s in PEOPLE_AND_VANS}

    assert stratified_split(classes, {"test": 0.1}, 7) == stratified_split(
        classes, {"test": 0.1}, 7
    )


def test_frames_of_one_sequence_stay_in_one_split() -> None:
    """Consecutive frames are near-duplicates: split by sequence, not by frame."""
    classes = {f"seq{s}_{f:03d}_{f:08d}": {"person"} for s in range(20) for f in range(10)}
    groups = {stem: sequence_of(stem) for stem in classes}

    split = stratified_split(classes, {"test": 0.1, "val": 0.1}, seed=3, groups=groups)

    by_group: dict[str, set[str]] = {}
    for stem, name in split.items():
        by_group.setdefault(groups[stem], set()).add(name)
    assert all(len(splits) == 1 for splits in by_group.values())
    assert list(split.values()).count("test") == 20  # 2 whole sequences of 10


def test_sequence_names_group_frames_and_leave_photos_alone() -> None:
    assert sequence_of("9_3_429_00000060") == sequence_of("9_3_431_00000066") == "9_3"
    assert sequence_of("09-26_25_2_10176_00000026") == "09-26_25_2"
    assert sequence_of("000000001722") == "000000001722"  # a COCO photo is its own group


# ---------- prepare_dataset ----------


def test_prepare_writes_a_stratified_split_with_canonical_ids(prepared: Path) -> None:
    split = json.loads((prepared / "split.json").read_text())

    assert split["test"]["images"] == 20 and split["val"]["images"] == 18
    assert split["test"]["instances"]["delivery_van"] == 2
    label = next((prepared / "labels" / "test").glob("*.txt")).read_text()
    assert label.split()[0] == str(CANONICAL.index("person"))
    data = yaml.safe_load((prepared / "data.yaml").read_text())
    assert data["names"] == dict(enumerate(CANONICAL))


def test_prepare_keeps_original_names_and_hashes_the_test_split(prepared: Path) -> None:
    split = json.loads((prepared / "split.json").read_text())

    assert not any("_jpg.rf." in s for s in _stems(prepared, "train"))
    assert len(split["test_files"]) == 20
    assert set(split["test_files"][0]) == {"image", "image_sha256", "label_sha256"}
    assert (prepared / "images" / "test" / split["test_files"][0]["image"]).is_file()


def test_prepare_rejects_an_unknown_class_name(tmp_path: Path) -> None:
    source = _yolo(tmp_path / "src", ["tram"], {"a": "0 0.5 0.5 0.2 0.2\n"})

    with pytest.raises(TaxonomyError, match="tram"):
        prepare_dataset(source, tmp_path / "dataset")


# ---------- build_dataset ----------


def test_build_keeps_the_prepared_split(prepared: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"

    build_dataset(out, prepared)

    for split in ("train", "val", "test"):
        assert _stems(out, split) == _stems(prepared, split)


def test_synthetic_images_go_to_train_only_and_can_be_capped(
    prepared: Path, tmp_path: Path
) -> None:
    syn = _yolo(tmp_path / "syn", ["SUV"], {f"s{i}": "0 0.5 0.5 0.2 0.2\n" for i in range(500)})
    out = tmp_path / "out"

    manifest = build_dataset(out, prepared, synthetic=syn, syn_fraction=1.0)

    synthetic = [s for s in _stems(out, "train") if s.startswith("syn_")]
    assert manifest["train"]["synthetic_images"] == len(synthetic) == 162  # 1.0 x real train
    label = (out / "labels" / "train" / f"{synthetic[0]}.txt").read_text()
    assert label.split()[0] == str(CANONICAL.index("SUV"))
    assert not any(s.startswith("syn_") for s in _stems(out, "val") | _stems(out, "test"))


def test_final_merges_val_into_train_and_leaves_test_alone(prepared: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"

    manifest = build_dataset(out, prepared, final=True)

    assert _stems(out, "train") == _stems(prepared, "train") | _stems(prepared, "val")
    assert _stems(out, "test") == _stems(prepared, "test")
    assert manifest["val"]["images"] == 0
    # Ultralytics still needs a val path; validation is off in final training.
    assert yaml.safe_load((out / "data.yaml").read_text())["val"] == "images/train"
