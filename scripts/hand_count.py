#!/usr/bin/env python3
"""Hand-count screenline crossings in a video, one class per pass: S7 ground truth.

Plays the clip with the screenline and its A and B sides drawn. Watch one class
only; each time one crosses the line, press ``a`` if it went from A to B, ``b``
if from B to A. Crossings are saved as you press. A pass is marked complete only
when the clip plays to the end; redoing a class replaces its earlier crossings.

Without ``--class`` it runs one pass for every class not yet complete, in
``configs/classes.yaml`` order; each pass starts paused. ``q`` stops the session,
and the next run picks up at the first class left.

    a  A -> B      b  B -> A      u  undo last
    space  pause/play      , .  step back/forward (paused)
    [ ]  slower/faster     q    quit (this pass stays incomplete)

Usage::

    # every class left, one after another
    python scripts/hand_count.py --video videos/test.mov \\
        --screenline 0.65 0.15 0.65 0.72 --out videos/test.counts.csv

    # redo one class
    python scripts/hand_count.py --video videos/test.mov --class car --out videos/test.counts.csv

``--screenline`` is needed only for a new file. Then compare the sensor with
it: ``python -m training.count_eval --video videos/test.mov --truth videos/test.counts.csv``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from camina.core.counting import Screenline
from camina.utils.taxonomy import load_canonical_classes
from training.count_eval import mark_complete, read_truth, start_pass, write_event, write_header

logger = logging.getLogger(__name__)

WHITE, GREY = (255, 255, 255), (170, 170, 170)
LEGEND = "a: A to B   b: B to A   u: undo   space: pause   , .: step   [ ]: speed   q: quit"


def _undo_last(path: Path) -> None:
    lines = path.read_text().splitlines(keepends=True)
    path.write_text("".join(lines[:-1]))


def _draw(frame: np.ndarray, line: Screenline, top: str, bottom: str) -> np.ndarray:
    h, w = frame.shape[:2]
    k = max(1, round(800 / min(w, h)))
    img = cv2.resize(frame, (w * k, h * k), interpolation=cv2.INTER_CUBIC) if k > 1 else frame
    W, H = w * k, h * k
    a = (int(line.start[0] * W), int(line.start[1] * H))
    b = (int(line.end[0] * W), int(line.end[1] * H))
    cv2.line(img, a, b, WHITE, 2, cv2.LINE_AA)
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = max(1.0, (dx * dx + dy * dy) ** 0.5)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    for label, sign in (("A", 1), ("B", -1)):  # A is on the (-dy, dx) side, as in Screenline
        x, y = int(mid[0] - sign * 30 * dy / norm), int(mid[1] + sign * 30 * dx / norm)
        cv2.circle(img, (x, y), 13, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.putText(img, label, (x - 6, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)
    cv2.rectangle(img, (0, H - 76), (W, H), (0, 0, 0), -1)
    cv2.putText(img, top, (10, H - 54), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1, cv2.LINE_AA)
    cv2.putText(img, bottom, (10, H - 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREY, 1, cv2.LINE_AA)
    cv2.putText(img, LEGEND, (10, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREY, 1, cv2.LINE_AA)
    return img


def _count_pass(video: Path, out: Path, cls: str, line: Screenline, header: str) -> bool:
    """One pass over the whole clip for ``cls``; True if it reached the end."""
    start_pass(out, cls)
    logger.info("%s: counting %s. Keys: %s", header, cls, LEGEND)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n, speed, paused, last = 0, 1.0, True, "press space to start"
    ab = ba = 0
    ok, frame = cap.read()
    while ok:
        top = f"{header}  {cls}:  A to B {ab}   B to A {ba}   {last}"
        bottom = f"{n}/{total}  {n / fps:5.1f}s  x{speed:g}{'  PAUSED' if paused else ''}"
        cv2.imshow("hand count", _draw(frame, line, top, bottom))
        key = cv2.waitKey(0 if paused else max(1, int(1000 / (fps * speed)))) & 0xFF
        ch = chr(key) if key < 128 else ""

        if ch == "q" or key == 27:
            logger.info("%s stopped at frame %d: pass incomplete", cls, n)
            return False
        if ch in ("a", "b"):
            direction = "AB" if ch == "a" else "BA"
            write_event(out, n, cls, direction)
            ab, ba = ab + (ch == "a"), ba + (ch == "b")
            last = f"+ {direction} @ {n}"
        elif ch == "u" and ab + ba:
            *_, direction = out.read_text().splitlines()[-1].split(",")
            _undo_last(out)
            ab, ba = ab - (direction == "AB"), ba - (direction == "BA")
            last = f"undid {direction}"
        elif ch == " ":
            paused, last = not paused, ""
        elif ch == "[":
            speed = max(0.125, speed / 2)
        elif ch == "]":
            speed = min(8.0, speed * 2)

        if ch in (",", ".") and paused:
            n = max(0, n - 1) if ch == "," else min(total - 1, n + 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, n)
            ok, frame = cap.read()
        elif not paused:
            ok, frame = cap.read()
            n += 1

    mark_complete(out, cls)
    logger.info("%s complete: A to B %d, B to A %d", cls, ab, ba)
    return True


def main() -> int:
    """Count one class, or every class not yet complete, one pass each."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    classes = load_canonical_classes()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument(
        "--class", dest="cls", choices=classes, help="count (or redo) one class; default: all left"
    )
    ap.add_argument("--screenline", type=float, nargs=4, metavar=("X1", "Y1", "X2", "Y2"))
    ap.add_argument("--out", type=Path, required=True, help="hand-count CSV (created or extended)")
    args = ap.parse_args()

    if not args.out.exists():
        if not args.screenline:
            ap.error("--screenline is required for a new file")
        write_header(args.out, Screenline(tuple(args.screenline[:2]), tuple(args.screenline[2:])))
    line, _, complete = read_truth(args.out)
    todo = [args.cls] if args.cls else [c for c in classes if c not in complete]
    if not todo:
        logger.info("Every class in %s is complete; use --class to redo one", args.out)
    for i, cls in enumerate(todo, 1):
        if not _count_pass(args.video, args.out, cls, line, f"[{i}/{len(todo)}]"):
            break
    cv2.destroyAllWindows()
    _, _, complete = read_truth(args.out)
    logger.info("Complete: %s", ", ".join(c for c in classes if c in complete) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
