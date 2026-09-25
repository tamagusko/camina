"""Tests for the Codex class check (``training/codex_check.py``) that need no Codex call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from training.codex_check import (
    build_command,
    build_prompt,
    crop_region,
    flagged_images,
    parse_reply,
    verdict,
)


def test_crop_region_adds_margin_and_clips_to_image() -> None:
    assert crop_region(10, 10, 110, 60, width=200, height=100, margin=0.1) == (0, 5, 120, 65)
    assert crop_region(0, 0, 200, 100, width=200, height=100, margin=0.5) == (0, 0, 200, 100)


def test_command_attaches_images_then_reads_prompt_from_stdin(tmp_path: Path) -> None:
    images = [tmp_path / "1.jpg", tmp_path / "2.jpg"]
    cmd = build_command(images, tmp_path / "s.json", tmp_path / "o.json", "gpt-6-astra", "medium")
    assert cmd[:2] == ["codex", "exec"]
    assert cmd[cmd.index("-m") + 1] == "gpt-6-astra"
    assert cmd[cmd.index("-s") + 1] == "read-only"
    i = cmd.index("-i")
    assert cmd[i + 1 : i + 3] == [str(p) for p in images]
    assert cmd[-1] == "-"  # -i takes many files, so the prompt must come from stdin


def test_parse_reply_maps_ids_to_labels() -> None:
    reply = json.dumps(
        {
            "items": [
                {"id": 2, "label": "SUV", "note": "tall"},
                {"id": 1, "label": "car", "note": ""},
            ]
        }
    )
    assert parse_reply(reply, 2) == {1: ("car", ""), 2: ("SUV", "tall")}


def test_parse_reply_rejects_missing_ids_and_unknown_labels() -> None:
    with pytest.raises(ValueError, match="ids"):
        parse_reply(json.dumps({"items": [{"id": 1, "label": "car", "note": ""}]}), 2)
    with pytest.raises(ValueError, match="label"):
        parse_reply(json.dumps({"items": [{"id": 1, "label": "tram", "note": ""}]}), 1)


def test_verdict() -> None:
    assert verdict("SUV", "SUV") == "agree"
    assert verdict("SUV", "car") == "disagree"
    assert verdict("cyclist", "none") == "disagree"
    assert verdict("car", "unsure") == "unsure"


def test_flagged_images_are_those_with_any_box_not_agreed() -> None:
    rows = [
        {"image": "a.jpg", "vlm_verdict": "agree"},
        {"image": "a.jpg", "vlm_verdict": "unsure"},
        {"image": "b.jpg", "vlm_verdict": "agree"},
        {"image": "c.jpg", "vlm_verdict": ""},  # class not checked
    ]
    assert flagged_images(rows) == ["a.jpg"]


def test_prompt_states_the_number_of_images() -> None:
    prompt = build_prompt(20)
    assert "exactly 20 images" in prompt
    assert "ids 1 to 20" in prompt


def test_command_uses_absolute_image_paths() -> None:
    # Codex runs in a temporary directory, so relative paths would not resolve there.
    cmd = build_command([Path("crops/1.jpg")], Path("s.json"), Path("o.json"), "m", "low")
    image = cmd[cmd.index("-i") + 1]
    assert Path(image).is_absolute()
    for flag in ("--output-schema", "-o"):
        assert Path(cmd[cmd.index(flag) + 1]).is_absolute()
