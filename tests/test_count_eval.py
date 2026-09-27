"""Tests for count evaluation: hand-count files and count error against them.

A hand count is done one class per pass: every screenline crossing of that
class, with its direction. A pass is complete only when the whole clip was
played; only complete classes are compared. S7's done-test passes a class and
direction when the error is within 20 % (at least 20 true crossings) or within
5 counts (rarer).
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from pathlib import Path

import pytest

from camina.core.counting import Screenline
from training import count_eval
from training.count_eval import (
    Row,
    compare,
    load_manifest,
    main,
    mark_complete,
    pool_rows,
    read_truth,
    start_pass,
    write_event,
    write_header,
)

LINE = Screenline((0.65, 0.15), (0.65, 0.72))


def test_a_hand_count_file_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "clip.counts.csv"
    write_header(path, LINE)
    write_event(path, 120, "person", "AB")
    write_event(path, 480, "car", "BA")
    write_event(path, 481, "car", "BA")
    mark_complete(path, "car")

    line, counts, complete = read_truth(path)

    assert line == LINE
    assert counts == Counter({("person", "AB"): 1, ("car", "BA"): 2})
    assert complete == {"car"}
    assert b"\r" not in path.read_bytes()  # plain \n line endings, easy to edit by hand


def test_starting_a_pass_replaces_that_class_only(tmp_path: Path) -> None:
    path = tmp_path / "clip.counts.csv"
    write_header(path, LINE)
    write_event(path, 10, "person", "AB")
    write_event(path, 20, "car", "AB")
    mark_complete(path, "person")
    mark_complete(path, "car")

    start_pass(path, "person")

    _, counts, complete = read_truth(path)
    assert counts == Counter({("car", "AB"): 1})
    assert complete == {"car"}


def test_an_unknown_direction_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "clip.counts.csv"
    write_header(path, LINE)
    write_event(path, 10, "car", "left")

    with pytest.raises(ValueError, match="direction"):
        read_truth(path)


def test_only_complete_classes_are_compared() -> None:
    truth = Counter({("car", "AB"): 12})
    counted = Counter({("car", "AB"): 12, ("person", "AB"): 3})

    rows = compare(truth, counted, classes={"car"})

    assert [(r.cls, r.direction) for r in rows] == [("car", "AB")]


def test_compare_reports_error_per_class_and_direction() -> None:
    truth = Counter({("car", "AB"): 12, ("car", "BA"): 10, ("person", "AB"): 3})
    counted = Counter({("car", "AB"): 12, ("car", "BA"): 11, ("person", "BA"): 1})

    rows = {(r.cls, r.direction): r for r in compare(truth, counted, {"car", "person"})}

    assert rows[("car", "BA")].truth == 10 and rows[("car", "BA")].counted == 11
    assert rows[("person", "AB")].error == -3
    assert rows[("person", "BA")].error == 1


def test_s7_threshold_is_20_percent_for_common_classes_else_5_counts() -> None:
    truth = Counter({("car", "AB"): 25, ("person", "AB"): 4})

    ok = {
        r.cls: r.passes
        for r in compare(
            truth, Counter({("car", "AB"): 30, ("person", "AB"): 9}), {"car", "person"}
        )
    }
    bad = {
        r.cls: r.passes
        for r in compare(
            truth, Counter({("car", "AB"): 31, ("person", "AB"): 10}), {"car", "person"}
        )
    }

    assert ok == {"car": True, "person": True}  # 5/25 = 20 %; |9 - 4| = 5
    assert bad == {"car": False, "person": False}


def _write_truth(
    path: Path, line: Screenline, events: list[tuple[int, str, str]], complete: set[str]
) -> None:
    write_header(path, line)
    for frame, cls, direction in events:
        write_event(path, frame, cls, direction)
    for cls in complete:
        mark_complete(path, cls)


HEADER = "{:<14} {:<3} {:>6} {:>8} {:>6}  {}".format(
    "class", "dir", "truth", "counted", "error", "S7"
)


def _row_line(cls: str, direction: str, truth: int, counted: int, verdict: str) -> str:
    error = counted - truth
    return f"{cls:<14} {direction:<3} {truth:>6d} {counted:>8d} {error:+6d}  {verdict}"


def test_pool_rows_sums_truth_and_counted_across_clips() -> None:
    clip_a = [Row("car", "AB", 25, 32), Row("person", "AB", 3, 3)]
    clip_b = [Row("car", "AB", 25, 18)]

    pooled = pool_rows([clip_a, clip_b])

    by_key = {(r.cls, r.direction): r for r in pooled}
    assert by_key[("car", "AB")].truth == 50
    assert by_key[("car", "AB")].counted == 50  # clip errors of +7/-7 cancel out pooled
    assert by_key[("person", "AB")].truth == 3
    assert by_key[("person", "AB")].counted == 3


def test_load_manifest_resolves_paths_relative_to_the_manifest_file(tmp_path: Path) -> None:
    manifest = tmp_path / "eval.yaml"
    manifest.write_text(
        "clips:\n"
        "  - video: videos/a.mov\n"
        "    truth: videos/a.counts.csv\n"
        "  - video: videos/b.mov\n"
        "    truth: videos/b.counts.csv\n"
    )

    clips = load_manifest(manifest)

    assert clips == [
        (tmp_path / "videos" / "a.mov", tmp_path / "videos" / "a.counts.csv"),
        (tmp_path / "videos" / "b.mov", tmp_path / "videos" / "b.counts.csv"),
    ]


def test_single_clip_cli_output_matches_the_original_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """`--video V --truth T` alone must print exactly what it printed before multi-clip support."""
    video, truth_path = tmp_path / "clip.mov", tmp_path / "clip.counts.csv"
    _write_truth(truth_path, LINE, [(120, "person", "AB")], complete={"person"})

    def fake_count_clip(
        video_arg: Path, model: Path, line: Screenline, min_move: float, relink: bool
    ) -> tuple[Counter, dict]:
        assert video_arg == video
        stats = {"relinks": 0, "unconfirmed_dropped": 0, "pending_at_end": 0}
        return Counter({("person", "AB"): 1}), stats

    monkeypatch.setattr(count_eval, "count_clip", fake_count_clip)
    monkeypatch.setattr(
        sys, "argv", ["count_eval.py", "--video", str(video), "--truth", str(truth_path)]
    )

    with caplog.at_level(logging.INFO):
        main()

    messages = [r.getMessage() for r in caplog.records]
    assert messages == [
        "Hand-counted classes: person",
        HEADER,
        _row_line("person", "AB", 1, 1, "pass"),
        "Tracking: relinks=0 unconfirmed_dropped=0 pending_at_end=0",
        "S7 on this clip: PASS",
    ]


def test_multiple_clip_pairs_report_per_clip_and_pooled_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    video1, truth1 = tmp_path / "clip1.mov", tmp_path / "clip1.counts.csv"
    video2, truth2 = tmp_path / "clip2.mov", tmp_path / "clip2.counts.csv"
    # Each clip alone fails S7 (|7| > 20 % of 25); pooled, the errors cancel and it passes.
    _write_truth(truth1, LINE, [(i, "car", "AB") for i in range(25)], complete={"car"})
    _write_truth(truth2, LINE, [(i, "car", "AB") for i in range(25)], complete={"car"})
    counted_by_video = {
        video1: Counter({("car", "AB"): 32}),
        video2: Counter({("car", "AB"): 18}),
    }

    def fake_count_clip(
        video_arg: Path, model: Path, line: Screenline, min_move: float, relink: bool
    ) -> tuple[Counter, dict]:
        stats = {"relinks": 0, "unconfirmed_dropped": 0, "pending_at_end": 0}
        return counted_by_video[video_arg], stats

    monkeypatch.setattr(count_eval, "count_clip", fake_count_clip)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "count_eval.py",
            "--video",
            str(video1),
            "--truth",
            str(truth1),
            "--video",
            str(video2),
            "--truth",
            str(truth2),
        ],
    )

    with caplog.at_level(logging.INFO):
        main()

    messages = [r.getMessage() for r in caplog.records]
    assert f"--- {video1} ---" in messages
    assert f"--- {video2} ---" in messages
    assert messages.count("S7 on this clip: FAIL") == 2  # +7 and -7 each fail their own clip
    assert "--- pooled (2 clips) ---" in messages
    assert _row_line("car", "AB", 50, 50, "pass") in messages
    assert messages[-1] == "S7 on pooled counts: PASS"


def test_manifest_combines_with_video_truth_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    video1, truth1 = tmp_path / "clip1.mov", tmp_path / "clip1.counts.csv"
    video2, truth2 = tmp_path / "clip2.mov", tmp_path / "clip2.counts.csv"
    _write_truth(truth1, LINE, [(1, "car", "AB")], complete={"car"})
    _write_truth(truth2, LINE, [(1, "car", "AB")], complete={"car"})
    manifest = tmp_path / "eval.yaml"
    manifest.write_text(f"clips:\n  - video: {video1.name}\n    truth: {truth1.name}\n")
    counted_by_video = {
        video1: Counter({("car", "AB"): 1}),
        video2: Counter({("car", "AB"): 1}),
    }

    def fake_count_clip(
        video_arg: Path, model: Path, line: Screenline, min_move: float, relink: bool
    ) -> tuple[Counter, dict]:
        stats = {"relinks": 0, "unconfirmed_dropped": 0, "pending_at_end": 0}
        return counted_by_video[video_arg], stats

    monkeypatch.setattr(count_eval, "count_clip", fake_count_clip)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "count_eval.py",
            "--manifest",
            str(manifest),
            "--video",
            str(video2),
            "--truth",
            str(truth2),
        ],
    )

    with caplog.at_level(logging.INFO):
        main()

    messages = [r.getMessage() for r in caplog.records]
    assert f"--- {video1} ---" in messages  # from the manifest
    assert f"--- {video2} ---" in messages  # from --video/--truth
    assert "--- pooled (2 clips) ---" in messages


def test_mismatched_video_and_truth_counts_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["count_eval.py", "--video", "a.mov", "--video", "b.mov", "--truth", "a.csv"],
    )

    with pytest.raises(SystemExit):
        main()


def test_no_clips_given_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["count_eval.py"])

    with pytest.raises(SystemExit):
        main()
