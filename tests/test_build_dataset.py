"""Tests for the training-dataset builder.

The builder turns the real dataset (and, optionally, a synthetic one) into one
YOLO dataset with canonical class ids. Two rules keep experiments comparable:
the frozen held-out images go to ``test`` and nowhere else, and synthetic
images only ever go to ``train`` — validation and test are always real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from training.build_dataset import build_dataset
from training.class_taxonomy import TaxonomyError

SDL_NAMES = ["pedestrian", "cyclist", "car", "motorcycle", "bus", "truck"]  # real dataset order
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


def _dataset(root: Path, names: list[str], files: dict[str, dict[str, str]]) -> Path:
    """A YOLO dataset: ``files = {split: {stem: label_text}}``."""
    for split, items in files.items():
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)
        for stem, label in items.items():
            (root / "images" / split / f"{stem}.jpg").write_bytes(b"jpg")
            (root / "labels" / split / f"{stem}.txt").write_text(label)
    (root / "data.yaml").write_text(yaml.safe_dump({"names": dict(enumerate(names))}))
    return root


def _holdout(path: Path, stems: list[str]) -> Path:
    path.write_text(json.dumps({"test_files": [{"image": f"images/test/{s}.jpg"} for s in stems]}))
    return path


@pytest.fixture
def real(tmp_path: Path) -> Path:
    return _dataset(
        tmp_path / "real",
        SDL_NAMES,
        {
            "train": {
                "a": "0 0.5 0.5 0.1 0.2\n",
                "b": "2 0.5 0.5 0.3 0.2\n",
                "c": "3 0.4 0.4 0.1 0.1\n",
            },
            "val": {"d": "5 0.5 0.5 0.4 0.3\n", "e": ""},
        },
    )


def _read(out: Path, split: str) -> dict[str, str]:
    return {p.stem: p.read_text() for p in sorted((out / "labels" / split).glob("*.txt"))}


def test_labels_are_rewritten_to_canonical_ids(real: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_dataset(real, out, holdout=_holdout(tmp_path / "h.json", []))

    train = _read(out, "train")
    assert train["a"].split()[0] == str(CANONICAL.index("person"))
    assert train["b"].split()[0] == str(CANONICAL.index("car"))
    assert train["c"].split()[0] == str(CANONICAL.index("motorcyclist"))
    assert _read(out, "val")["d"].split()[0] == str(CANONICAL.index("truck"))
    assert yaml.safe_load((out / "data.yaml").read_text())["names"] == dict(enumerate(CANONICAL))


def test_holdout_images_go_to_test_only(real: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_dataset(real, out, holdout=_holdout(tmp_path / "h.json", ["a", "d"]))

    assert set(_read(out, "test")) == {"a", "d"}
    assert set(_read(out, "train")) == {"b", "c"}
    assert set(_read(out, "val")) == {"e"}


def test_background_images_keep_an_empty_label(real: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_dataset(real, out, holdout=_holdout(tmp_path / "h.json", []))

    assert _read(out, "val")["e"] == ""


def test_synthetic_images_go_to_train_only_with_their_own_names(real: Path, tmp_path: Path) -> None:
    syn = _dataset(
        tmp_path / "syn",
        ["SUV", "delivery_van"],
        {"train": {"s1": "0 0.5 0.5 0.2 0.2\n"}, "val": {"s2": "1 0.5 0.5 0.2 0.2\n"}},
    )
    out = tmp_path / "out"
    manifest = build_dataset(real, out, holdout=_holdout(tmp_path / "h.json", []), synthetic=syn)

    train = _read(out, "train")
    assert train["syn_s1"].split()[0] == str(CANONICAL.index("SUV"))
    assert train["syn_s2"].split()[0] == str(CANONICAL.index("delivery_van"))
    assert not any(k.startswith("syn_") for k in _read(out, "val"))
    assert manifest["train"]["synthetic_images"] == 2


def test_syn_fraction_caps_synthetic_images_deterministically(real: Path, tmp_path: Path) -> None:
    syn = _dataset(
        tmp_path / "syn", ["SUV"], {"train": {f"s{i}": "0 0.5 0.5 0.2 0.2\n" for i in range(10)}}
    )
    holdout = _holdout(tmp_path / "h.json", [])

    a = build_dataset(real, tmp_path / "a", holdout=holdout, synthetic=syn, syn_fraction=1.0)
    build_dataset(real, tmp_path / "b", holdout=holdout, synthetic=syn, syn_fraction=1.0)

    assert a["train"]["synthetic_images"] == 3  # 1.0 x the 3 real training images
    assert set(_read(tmp_path / "a", "train")) == set(_read(tmp_path / "b", "train"))


def test_manifest_counts_instances_per_class_and_split(real: Path, tmp_path: Path) -> None:
    manifest = build_dataset(real, tmp_path / "out", holdout=_holdout(tmp_path / "h.json", []))

    assert manifest["train"]["instances"] == {"person": 1, "car": 1, "motorcyclist": 1}
    assert manifest["val"]["images"] == 2
    assert json.loads((tmp_path / "out" / "manifest.json").read_text()) == manifest


def test_an_unknown_class_name_fails_loudly(real: Path, tmp_path: Path) -> None:
    syn = _dataset(tmp_path / "syn", ["tram"], {"train": {"s1": "0 0.5 0.5 0.2 0.2\n"}})

    with pytest.raises(TaxonomyError, match="tram"):
        build_dataset(
            real, tmp_path / "out", holdout=_holdout(tmp_path / "h.json", []), synthetic=syn
        )
