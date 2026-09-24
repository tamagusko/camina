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
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

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
        csv.writer(f).writerow([frame, cls, direction])


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
        writer = csv.writer(f)
        writer.writerow(["frame", "class", "direction"])
        writer.writerows(rows)


def compare(
    truth: Counter[tuple[str, str]], counted: Counter[tuple[str, str]], classes: set[str]
) -> list[Row]:
    """One row per (class, direction) of ``classes`` present in either count, sorted."""
    keys = sorted(k for k in set(truth) | set(counted) if k[0] in classes)
    return [Row(cls, d, truth[cls, d], counted[cls, d]) for cls, d in keys]


def count_clip(
    video: Path, model: Path, line: Screenline, min_move: float = 1.0
) -> Counter[tuple[str, str]]:
    """Run the sensor pipeline over ``video``; crossings per (class, direction)."""
    import cv2

    from camina.core.tracker import Sort
    from camina.service.detect_track import _map_model_classes, _to_canonical
    from camina.service.ncnn_detector import NcnnDetector
    from camina.utils.taxonomy import load_canonical_classes

    classes = load_canonical_classes()
    detector = NcnnDetector(model)
    model_names = [detector.names[i] for i in sorted(detector.names)]
    to_class = _map_model_classes(model_names, classes)
    tracker, gate = Sort(), CountGate(screenline=line, min_move=min_move)
    counts: Counter[tuple[str, str]] = Counter()

    cap = cv2.VideoCapture(str(video))
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dets = _to_canonical(detector(frame), to_class, len(model_names), detector.conf)
        tracks = tracker.update(dets)
        class_of = {str(int(t)): classes[int(c)] for *_, t, c in tracks}
        boxes = [(str(int(t)), (x1, y1, x2, y2)) for x1, y1, x2, y2, t, _ in tracks]
        for event in gate.step(boxes, (frame.shape[1], frame.shape[0])):
            counts[class_of[event.key], event.direction] += 1
    return counts


def main() -> None:
    """Print the count error table for one clip."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Count error against a hand count (S7).")
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True, help="hand-count CSV")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--min-move", type=float, default=1.0)
    args = ap.parse_args()

    line, truth, complete = read_truth(args.truth)
    if not complete:
        raise SystemExit(f"No class in {args.truth} has a complete hand count yet")
    rows = compare(truth, count_clip(args.video, args.model, line, args.min_move), complete)
    logger.info("Hand-counted classes: %s", ", ".join(sorted(complete)))
    logger.info("%-14s %-3s %6s %8s %6s  %s", "class", "dir", "truth", "counted", "error", "S7")
    for r in rows:
        verdict = "pass" if r.passes else "FAIL"
        logger.info(
            "%-14s %-3s %6d %8d %+6d  %s", r.cls, r.direction, r.truth, r.counted, r.error, verdict
        )
    logger.info("S7 on this clip: %s", "PASS" if all(r.passes for r in rows) else "FAIL")


if __name__ == "__main__":
    main()
