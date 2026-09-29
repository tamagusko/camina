"""Tests for the hand-count session: scripted key presses, no window.

``cv2.imshow`` is replaced by a no-op and ``cv2.waitKey`` by a key script, so a
whole counting session runs on a tiny generated video.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from training.count_eval import read_truth  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hand_count.py"
CLASSES = [
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


def _load():
    spec = importlib.util.spec_from_file_location("hand_count", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _video(path: Path, frames: int = 4) -> Path:
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
    for _ in range(frames):
        out.write(np.zeros((64, 64, 3), np.uint8))
    out.release()
    return path


def _run(monkeypatch: pytest.MonkeyPatch, keys: list[str], argv: list[str]) -> None:
    mod = _load()
    script = iter(keys)
    monkeypatch.setattr(mod.cv2, "imshow", lambda *_a: None)
    monkeypatch.setattr(mod.cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(mod.cv2, "waitKey", lambda _ms: ord(next(script, "\xff")))
    monkeypatch.setattr(sys, "argv", ["hand_count.py", *argv])
    mod.main()


def test_a_session_counts_every_class_and_stops_on_q(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video, out = _video(tmp_path / "clip.mp4"), tmp_path / "clip.counts.csv"
    args = ["--video", str(video), "--out", str(out), "--screenline", "0.5", "0", "0.5", "1"]
    # person: start, one A->B, play to the end; cyclist: start, play to the end; car: quit.
    keys = [" ", "a", "\xff", "\xff", "\xff", "\xff", " ", "\xff", "\xff", "\xff", "\xff", "q"]

    _run(monkeypatch, keys, args)

    _, counts, complete = read_truth(out)
    assert complete == {"person", "cyclist"}
    assert counts[("person", "AB")] == 1


def test_the_next_session_resumes_at_the_first_class_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video, out = _video(tmp_path / "clip.mp4"), tmp_path / "clip.counts.csv"
    args = ["--video", str(video), "--out", str(out), "--screenline", "0.5", "0", "0.5", "1"]
    _run(monkeypatch, [" ", "a", "\xff", "\xff", "\xff", "\xff", "q"], args)

    # Second session: starts at cyclist (person is kept), counts all eight left.
    _run(monkeypatch, [" ", *["\xff"] * 5] * 8, args[:4])

    _, counts, complete = read_truth(out)
    assert complete == set(CLASSES)
    assert counts[("person", "AB")] == 1
