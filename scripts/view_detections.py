#!/usr/bin/env python3
"""Render a video with what the sensor sees, for a visual check.

Runs the daemon's pipeline — ``NcnnDetector``, one ``Sort`` tracker per class and
the ``CountGate``, same threshold and class mapping as ``detect_track.py`` — and
writes an MP4:

- a bold box and label (``car 7``) once a track has been counted;
- a thin box for a confirmed track that has not been counted (yet);
- a faint outline for detections the tracker has not confirmed;
- the screenline with its A and B sides, when one is given;
- a bar with the running count per class, per direction, and the time.

Usage::

    python scripts/view_detections.py --video tests/test.mov --out /tmp/annotated.mp4 \
        --screenline 0.65 0.15 0.65 0.72 --play
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.camina.core.counting import CountGate, Screenline
from src.camina.core.tracker import Sort
from src.camina.service.detect_track import (
    _map_model_classes,
    _split_detections_by_class,
)
from src.camina.service.ncnn_detector import NcnnDetector
from src.camina.utils.taxonomy import load_canonical_classes

logger = logging.getLogger(__name__)

# One restrained colour per class, in configs/classes.yaml order (RGB).
COLOURS = [
    (255, 255, 255), (52, 199, 89), (10, 132, 255), (191, 90, 242), (255, 159, 10),
    (255, 69, 58), (255, 214, 10), (100, 210, 255), (172, 142, 104),
]
FONT = "/usr/share/fonts/noto/NotoSans-Medium.ttf"


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, pad: int) -> None:
    """A black capsule label with white text, top-left at ``xy``."""
    x, y = xy
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    w, h = r - l + 2 * pad, b - t + pad
    y = max(0, y - h - 2)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=(0, 0, 0, 200))
    draw.text((x + pad - l, y + pad / 2 - t), text, font=font, fill=(255, 255, 255, 255))


def _screenline(draw: ImageDraw.ImageDraw, line: Screenline, W: int, H: int, font, width: int) -> None:
    """The counting line, with an A and a B badge on each side of its midpoint."""
    (x1, y1), (x2, y2) = (line.start[0] * W, line.start[1] * H), (line.end[0] * W, line.end[1] * H)
    draw.line((x1, y1, x2, y2), fill=(255, 255, 255, 200), width=width)
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5
    nx, ny = -dy / norm, dx / norm  # points to side A (see Screenline)
    mx, my, off = (x1 + x2) / 2, (y1 + y2) / 2, 14 * width
    for label, sign in (("A", 1), ("B", -1)):
        cx, cy = mx + sign * nx * off, my + sign * ny * off
        r = 7 * width
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 200))
        l, t, rr, b = draw.textbbox((0, 0), label, font=font)
        draw.text((cx - (rr - l) / 2 - l, cy - (b - t) / 2 - t), label, font=font, fill=(255, 255, 255, 255))


def main() -> int:
    """Annotate a video and optionally open it in mpv."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="annotated .mp4 to write")
    ap.add_argument("--model", type=Path, default=Path("models/camina_v1_yolo11n_ncnn_model"))
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--screenline", type=float, nargs=4, metavar=("X1", "Y1", "X2", "Y2"),
                    help="count on crossing this line (fractions of the frame); default: on movement")
    ap.add_argument("--min-move", type=float, default=1.0, help="movement threshold, in box heights")
    ap.add_argument("--max-frames", type=int, default=0, help="0 = whole video")
    ap.add_argument("--play", action="store_true", help="open the result in mpv when done")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    classes = load_canonical_classes()
    detector = NcnnDetector(args.model, imgsz=640, conf=args.conf)
    model_names = [detector.names[i] for i in sorted(detector.names)]
    to_class = _map_model_classes(model_names, classes)
    trackers = {i: Sort() for i in range(len(classes))}
    line = Screenline(tuple(args.screenline[:2]), tuple(args.screenline[2:])) if args.screenline else None
    gate = CountGate(screenline=line, min_move=args.min_move)
    seen: dict[int, set[int]] = {i: set() for i in range(len(classes))}   # every confirmed track (old rule)
    counted: dict[int, dict[str, int]] = {i: {} for i in range(len(classes))}  # direction -> n
    counted_keys: set[str] = set()

    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total = min(total, args.max_frames) if args.max_frames else total
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    k = max(1, round(800 / min(w, h)))            # render small videos at 2x, crisply
    W, H = w * k, h * k
    label_font, bar_font = _font(11 * k // 2 + 6), _font(12 * k // 2 + 7)
    lw = max(2, k)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(args.out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    n, started = 0, time.perf_counter()
    while n < total:
        ok, frame = cap.read()
        if not ok:
            break
        dets = detector(frame)
        tracks = []
        for m_idx, d in _split_detections_by_class(dets, len(model_names), args.conf).items():
            c = to_class[m_idx]
            for x1, y1, x2, y2, tid in (trackers[c].update(d) if d.size else trackers[c].update()):
                seen[c].add(int(tid))
                tracks.append((c, int(tid), (x1, y1, x2, y2)))
        for ev in gate.step(((f"{c}-{tid}", box) for c, tid, box in tracks), (w, h)):
            c = int(ev.key.split("-")[0])
            direction = ev.direction or "moved"
            counted[c][direction] = counted[c].get(direction, 0) + 1
            counted_keys.add(ev.key)

        big = cv2.resize(frame, (W, H), interpolation=cv2.INTER_CUBIC) if k > 1 else frame
        img = Image.fromarray(big[..., ::-1]).convert("RGBA")
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        for x1, y1, x2, y2, _score, m_idx in dets:  # quiet outline: detected, not confirmed
            draw.rectangle((x1 * k, y1 * k, x2 * k, y2 * k), outline=(255, 255, 255, 90), width=1)
        if line is not None:
            _screenline(draw, line, W, H, label_font, width=lw)
        for c, tid, (x1, y1, x2, y2) in tracks:
            box = (x1 * k, y1 * k, x2 * k, y2 * k)
            if f"{c}-{tid}" in counted_keys:
                draw.rounded_rectangle(box, radius=3 * k, outline=COLOURS[c] + (255,), width=lw)
                _pill(draw, (box[0], box[1]), f"{classes[c]} {tid}", label_font, pad=4 * k)
            else:
                draw.rounded_rectangle(box, radius=3 * k, outline=COLOURS[c] + (130,), width=1)

        bar_h = 22 * k
        draw.rectangle((0, H - bar_h, W, H), fill=(0, 0, 0, 170))
        counts = "   ".join(f"{classes[c]} {sum(d.values())}" for c, d in counted.items() if d) or "nothing counted yet"
        if line is not None:
            ab = sum(d.get("AB", 0) for d in counted.values())
            ba = sum(d.get("BA", 0) for d in counted.values())
            counts += f"      A to B {ab}   B to A {ba}"
        clock = f"{int(n / fps) // 60:02d}:{int(n / fps) % 60:02d} / {int(total / fps) // 60:02d}:{int(total / fps) % 60:02d}"
        _, t, _, b = draw.textbbox((0, 0), counts, font=bar_font)
        ty = H - bar_h + (bar_h - (b - t)) / 2 - t
        draw.text((8 * k, ty), counts, font=bar_font, fill=(255, 255, 255, 255))
        cw = draw.textlength(clock, font=bar_font)
        draw.text((W - cw - 8 * k, ty), clock, font=bar_font, fill=(255, 255, 255, 150))

        out.write(np.asarray(Image.alpha_composite(img, layer).convert("RGB"))[..., ::-1].copy())
        n += 1
        if n % 1000 == 0:
            logger.info("%d/%d frames", n, total)

    out.release()
    elapsed = time.perf_counter() - started
    logger.info("Wrote %s: %d frames in %.0f s", args.out, n, elapsed)
    logger.info("Confirmed tracks (every track counted): %s",
                {classes[c]: len(ids) for c, ids in seen.items() if ids})
    logger.info("Counted (%s): %s", "screenline" if line else f"moved >= {args.min_move} box heights",
                {classes[c]: d for c, d in counted.items() if d})
    if args.play:
        subprocess.Popen(["mpv", "--keep-open=yes", str(args.out)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
