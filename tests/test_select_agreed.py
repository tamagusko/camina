from pathlib import Path

import yaml
from PIL import Image

from training.select_agreed import agreed_images, audit_sample, export


def _row(image: str, cls: str, verdict: str = "") -> dict:
    return {"image": image, "class": cls, "claude_verdict": verdict}


def test_keeps_images_whose_checked_boxes_all_agree() -> None:
    rows = [
        _row("a.jpg", "car", "agree"),
        _row("a.jpg", "person"),  # unchecked: does not disqualify
        _row("b.jpg", "car", "agree"),
        _row("b.jpg", "car", "unsure"),
        _row("c.jpg", "truck", "disagree"),
        _row("d.jpg", "car"),  # nothing checked: nothing verified
    ]
    assert agreed_images(rows) == ["a.jpg"]


def test_audit_sample_is_seeded_sorted_and_capped() -> None:
    names = [f"{i:03d}.jpg" for i in range(100)]
    first = audit_sample(names, 10, seed=0)
    assert first == audit_sample(names, 10, seed=0)
    assert first == sorted(first) and len(set(first)) == 10
    assert audit_sample(names[:5], 10, seed=0) == names[:5]


def test_export_copies_images_labels_list_and_data_yaml(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "images").mkdir(parents=True)
    (run / "labels").mkdir()
    (run / "data.yaml").write_text(yaml.safe_dump({"nc": 1, "names": ["car"]}))
    for stem in ("a", "b"):
        Image.new("RGB", (4, 4)).save(run / "images" / f"{stem}.jpg")
        (run / "labels" / f"{stem}.txt").write_text("0 0.5 0.5 0.1 0.1\n")

    dest = run / "tier_a"
    export(run, ["a.jpg"], dest)

    assert [p.name for p in (dest / "images").iterdir()] == ["a.jpg"]
    assert (dest / "labels" / "a.txt").read_text() == "0 0.5 0.5 0.1 0.1\n"
    assert (dest / "images.txt").read_text() == "a.jpg\n"
    assert yaml.safe_load((dest / "data.yaml").read_text())["names"] == ["car"]

    export(run, ["b.jpg"], dest)  # re-running replaces, never mixes
    assert [p.name for p in (dest / "images").iterdir()] == ["b.jpg"]
