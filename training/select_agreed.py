"""Select the images whose checked boxes Claude all agreed with, plus a random audit sample.

An image is kept when at least one of its boxes was checked by ``training.claude_check``
and every checked box has ``claude_verdict == "agree"``. Unchecked boxes (below
``--min-side``, or of a class not checked) keep their label and do not disqualify the
image. Method and results: ``training/MONTREAL.md``.

    .venv/bin/python -m training.select_agreed --run data/autolabel/montreal
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def agreed_images(rows: list[dict]) -> list[str]:
    """Images with at least one checked box and no checked box other than 'agree'."""
    verdicts: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        verdicts[r["image"]].add(r.get("claude_verdict", ""))
    return sorted(img for img, v in verdicts.items() if v - {""} == {"agree"})


def audit_sample(names: list[str], n: int, seed: int) -> list[str]:
    """A seeded simple random sample of ``n`` names without replacement, sorted."""
    return sorted(random.Random(seed).sample(names, min(n, len(names))))


def export(run: Path, names: list[str], dest: Path) -> None:
    """Copy images, labels and ``data.yaml`` of ``names`` to ``dest`` (replaced if present)."""
    shutil.rmtree(dest, ignore_errors=True)
    (dest / "images").mkdir(parents=True)
    (dest / "labels").mkdir()
    shutil.copy2(run / "data.yaml", dest / "data.yaml")
    for name in names:
        shutil.copy2(run / "images" / name, dest / "images" / name)
        label = run / "labels" / f"{Path(name).stem}.txt"
        if label.exists():
            shutil.copy2(label, dest / "labels" / label.name)
    (dest / "images.txt").write_text("".join(f"{n}\n" for n in names))


def _log_classes(rows: list[dict], names: list[str]) -> None:
    keep = set(names)
    boxes = [r for r in rows if r["image"] in keep]
    total = Counter(r["class"] for r in boxes)
    agreed = Counter(r["class"] for r in boxes if r.get("claude_verdict") == "agree")
    for cls, n in total.most_common():
        logger.info("  %-13s %6d boxes, %5d agreed", cls, n, agreed[cls])


def run(args: argparse.Namespace) -> None:
    with open(args.run / "boxes.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    tier_a = agreed_images(rows)
    sample = audit_sample(tier_a, args.audit, args.seed)
    export(args.run, tier_a, args.run / "tier_a")
    export(args.run, sample, args.run / "tier_a_audit")
    logger.info(
        "%d of %d images with boxes selected; audit sample %d (seed %d)",
        len(tier_a),
        len({r["image"] for r in rows}),
        len(sample),
        args.seed,
    )
    _log_classes(rows, tier_a)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", type=Path, required=True, help="folder with boxes.csv")
    parser.add_argument("--audit", type=int, default=60, help="images in the audit sample")
    parser.add_argument("--seed", type=int, default=0, help="seed of the audit sample")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
