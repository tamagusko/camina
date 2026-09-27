"""Count error of the sensor pipeline against a hand count of the same clip.

A hand count (``scripts/hand_count.py``) is a CSV next to the video, filled one
class per pass::

    # screenline: 0.65 0.15 0.65 0.72
    # complete: car person
    frame,class,direction
    120,person,AB

A class is listed as complete once a pass played the whole clip; only complete
classes are compared. This tool runs the sensor's pipeline (NCNN detector,
tracker, count gate) over the clip with the same screenline and prints, per
class and direction, the true count, the counted value and the S7 verdict: pass
when the error is within 20 % of the truth (at least 20 true crossings) or within
5 counts (rarer).

    python -m training.count_eval --video videos/test.mov --truth videos/test.counts.csv

Several clips can be scored in one run, either as repeated ``--video``/``--truth``
pairs (paired in the order given) or listed in a YAML manifest (``--manifest``,
see ``training/EVALUATION.md``). With more than one clip, each clip's table is
printed under a ``--- <video> ---`` header, followed by one pooled table that
sums truth and counted per class and direction across every clip, and the S7
verdict is reported on that pooled table. A single ``--video``/``--truth`` pair
prints exactly as it always has, with no per-clip headers and the verdict
labelled "S7 on this clip".
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from camina.core.counting import CountGate, Screenline

logger = logging.getLogger(__name__)

DIRECTIONS = ("AB", "BA")
DEFAULT_MODEL = Path("models/camina_v1_yolo11n_ncnn_model")


@dataclass(frozen=True)
class Row:
    """One class and direction: true count, pipeline count, S7 verdict."""

    cls: str
    direction: str
    truth: int
    counted: int

    @property
    def error(self) -> int:
        return self.counted - self.truth

    @property
    def passes(self) -> bool:
        if self.truth >= 20:
            return abs(self.error) <= 0.2 * self.truth
        return abs(self.error) <= 5


def write_header(path: Path, line: Screenline) -> None:
    """Start a hand-count file for ``line``."""
    (x1, y1), (x2, y2) = line.start, line.end
    _write(path, f"{x1} {y1} {x2} {y2}", set(), [])


def write_event(path: Path, frame: int, cls: str, direction: str) -> None:
    """Append one crossing."""
    with path.open("a", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow([frame, cls, direction])


def start_pass(path: Path, cls: str) -> None:
    """Begin a pass for ``cls``: drop its earlier rows and its complete mark."""
    line, complete, rows = _read(path)
    _write(path, line, complete - {cls}, [r for r in rows if r[1] != cls])


def mark_complete(path: Path, cls: str) -> None:
    """Record that a pass for ``cls`` covered the whole clip."""
    line, complete, rows = _read(path)
    _write(path, line, complete | {cls}, rows)


def read_truth(path: Path) -> tuple[Screenline, Counter[tuple[str, str]], set[str]]:
    """The screenline, crossings per (class, direction), and the complete classes."""
    line, complete, rows = _read(path)
    counts: Counter[tuple[str, str]] = Counter()
    for _, cls, direction in rows:
        if direction not in DIRECTIONS:
            raise ValueError(f"direction must be AB or BA, got {direction!r} in {path}")
        counts[cls, direction] += 1
    x1, y1, x2, y2 = (float(v) for v in line.split())
    return Screenline((x1, y1), (x2, y2)), counts, complete


def _read(path: Path) -> tuple[str, set[str], list[list[str]]]:
    lines = path.read_text().splitlines()
    meta = {k.strip("# "): v.strip() for k, _, v in (m.partition(":") for m in lines[:2])}
    rows = list(csv.reader(lines[3:]))
    return meta["screenline"], set(meta["complete"].split()), rows


def _write(path: Path, line: str, complete: set[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="") as f:
        f.write(f"# screenline: {line}\n# complete: {' '.join(sorted(complete))}\n")
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["frame", "class", "direction"])
        writer.writerows(rows)


def compare(
    truth: Counter[tuple[str, str]], counted: Counter[tuple[str, str]], classes: set[str]
) -> list[Row]:
    """One row per (class, direction) of ``classes`` present in either count, sorted."""
    keys = sorted(k for k in set(truth) | set(counted) if k[0] in classes)
    return [Row(cls, d, truth[cls, d], counted[cls, d]) for cls, d in keys]


def pool_rows(clip_rows: Iterable[list[Row]]) -> list[Row]:
    """Sum truth and counted per (class, direction) across several clips' rows.

    Each clip's rows already carry only that clip's complete classes (from
    ``compare``); a class complete in one clip but not another is pooled only
    from the clips where it is complete.
    """
    truth: Counter[tuple[str, str]] = Counter()
    counted: Counter[tuple[str, str]] = Counter()
    for rows in clip_rows:
        for r in rows:
            truth[r.cls, r.direction] += r.truth
            counted[r.cls, r.direction] += r.counted
    return [Row(cls, d, truth[cls, d], counted[cls, d]) for cls, d in sorted(truth)]


def load_manifest(path: Path) -> list[tuple[Path, Path]]:
    """Load clip ``(video, truth)`` pairs from a YAML manifest.

    Format, paths resolved relative to the manifest file's own directory::

        clips:
          - video: videos/test.mov
            truth: videos/test.counts.csv
          - video: videos/test2.mov
            truth: videos/test2.counts.csv
    """
    data = yaml.safe_load(path.read_text()) or {}
    base = path.parent
    return [(base / c["video"], base / c["truth"]) for c in data.get("clips", [])]


def count_clip(
    video: Path, model: Path, line: Screenline, min_move: float = 1.0, relink: bool = False
) -> tuple[Counter[tuple[str, str]], dict[str, int]]:
    """Run the sensor pipeline over ``video``.

    Returns:
        Crossings per (class, direction), and the tracking counters:
        ``relinks``, ``unconfirmed_dropped`` and ``pending_at_end`` (tracks
        that crossed but whose class was still unconfirmed when the clip ended).

    The pipeline is the daemon's own ``make_detect_and_track`` closure. Each
    frame is stamped with its time in the clip (index / fps), so time-based
    rules see the clip's real time however slowly it is processed.
    """
    import cv2

    from camina.service.detect_track import make_detect_and_track
    from camina.utils.taxonomy import load_canonical_classes

    gate = CountGate(screenline=line, min_move=min_move)
    detect_and_track = make_detect_and_track(
        model, load_canonical_classes(), gate=gate, relink=relink
    )
    counts: Counter[tuple[str, str]] = Counter()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        for counted in detect_and_track(frame, t=i / fps):
            counts[counted.class_name, counted.direction] += 1
        i += 1
    stats = {
        "relinks": detect_and_track.tracker.relinks,  # type: ignore[attr-defined]
        "unconfirmed_dropped": gate.unconfirmed_dropped,
        "pending_at_end": gate.n_pending,
    }
    return counts, stats


@dataclass(frozen=True)
class ClipResult:
    """One clip's hand-counted classes, per-class/direction rows and tracking stats."""

    complete: set[str]
    rows: list[Row]
    stats: dict[str, int]


def _run_clip(
    video: Path, truth_path: Path, model: Path, min_move: float, relink: bool
) -> ClipResult:
    """Score one clip against its hand count."""
    line, truth, complete = read_truth(truth_path)
    if not complete:
        raise SystemExit(f"No class in {truth_path} has a complete hand count yet")
    counted, stats = count_clip(video, model, line, min_move, relink)
    return ClipResult(complete, compare(truth, counted, complete), stats)


def _print_table(rows: list[Row]) -> None:
    """Print the class/direction/truth/counted/error/S7 table for ``rows``."""
    logger.info("%-14s %-3s %6s %8s %6s  %s", "class", "dir", "truth", "counted", "error", "S7")
    for r in rows:
        verdict = "pass" if r.passes else "FAIL"
        logger.info(
            "%-14s %-3s %6d %8d %+6d  %s", r.cls, r.direction, r.truth, r.counted, r.error, verdict
        )


def main() -> None:
    """Print the count error table for one clip, or per-clip and pooled tables for several."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Count error against a hand count (S7).")
    ap.add_argument(
        "--video",
        type=Path,
        action="append",
        default=[],
        help="clip video; repeat with --truth for more clips, paired in the order given",
    )
    ap.add_argument(
        "--truth",
        type=Path,
        action="append",
        default=[],
        help="hand-count CSV, paired with --video in the order given",
    )
    ap.add_argument(
        "--manifest", type=Path, help="YAML file listing clip video/truth pairs (see EVALUATION.md)"
    )
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--min-move", type=float, default=1.0)
    ap.add_argument("--relink", action="store_true", help="re-link tracks after occlusion")
    args = ap.parse_args()

    if len(args.video) != len(args.truth):
        ap.error("--video and --truth must be given the same number of times")
    clips = (load_manifest(args.manifest) if args.manifest else []) + list(
        zip(args.video, args.truth, strict=True)
    )
    if not clips:
        ap.error("give at least one --video/--truth pair, or --manifest")

    results: list[ClipResult] = []
    for video, truth_path in clips:
        result = _run_clip(video, truth_path, args.model, args.min_move, args.relink)
        if len(clips) > 1:
            logger.info("--- %s ---", video)
        logger.info("Hand-counted classes: %s", ", ".join(sorted(result.complete)))
        _print_table(result.rows)
        logger.info("Tracking: %s", " ".join(f"{k}={v}" for k, v in result.stats.items()))
        if len(clips) > 1:
            verdict = "PASS" if all(r.passes for r in result.rows) else "FAIL"
            logger.info("S7 on this clip: %s", verdict)
        results.append(result)

    if len(clips) == 1:
        verdict = "PASS" if all(r.passes for r in results[0].rows) else "FAIL"
        logger.info("S7 on this clip: %s", verdict)
        return
    pooled = pool_rows(r.rows for r in results)
    logger.info("--- pooled (%d clips) ---", len(clips))
    _print_table(pooled)
    logger.info("S7 on pooled counts: %s", "PASS" if all(r.passes for r in pooled) else "FAIL")


if __name__ == "__main__":
    main()
