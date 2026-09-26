"""Check each auto-label's class with Codex before a person reviews it in Roboflow.

Reads ``<run>/boxes.csv`` from ``training.autolabel``, crops every box of the checked
classes, and asks Codex (``codex exec``, the user's own login: no key in the repo)
which class each crop shows, using the definitions of docs/labelling_guide. The answer
is written back to ``boxes.csv`` (``vlm_label``, ``vlm_note``, ``vlm_verdict``), batch by
batch, so an interrupted run resumes where it stopped.

Codex only sorts the queue; it changes no label. Images with any box it disagrees with,
or is unsure of, go to ``<run>/review/flagged``; the rest to ``<run>/review/ok``. Upload
each as its own Roboflow batch and review the flagged one first.

Crops leave this machine (they go to OpenAI). For camera images, keep person-carrying
classes out of ``--classes`` until GDPR and the camera terms are settled.

    .venv/bin/python -m training.codex_check --run data/autolabel/dev_expanded_new
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from training.class_taxonomy import load_canonical_classes

logger = logging.getLogger(__name__)

DEFAULT_CLASSES = "car,SUV,delivery_van,truck,cyclist,e-scooter,motorcyclist"
EXTRA_LABELS = ["none", "unsure"]
MAX_CROP_SIDE = 512
MIN_CROP_SIDE = 160  # far-away vehicles are a few pixels wide
ID_STRIP = 22
BOX_COLOUR = (0, 255, 0)

PROMPT = """<task>
There are exactly {n} images attached, ids 1 to {n}, in the order attached; each shows
its id in a black strip along its top edge. Each is a crop around one auto-labelled road
user, whose box is outlined in green. Say which class the object inside the green box
shows; other road users around it are context only. Answer from the images alone; do
not run any command.
</task>
<classes>
person: anyone on foot, including someone pushing a bicycle or scooter.
cyclist: a person riding a bicycle, e-bike or cargo bike.
car: saloon, hatchback, estate, coupe, MPV, taxi.
e-scooter: a person standing on a kick scooter, electric or not.
SUV: sport utility vehicle or crossover; tall body sitting high over the wheels, upright
  tailgate (RAV4, Qashqai, Tucson). MPVs are car; pickups are truck.
motorcyclist: a person riding a motorcycle or moped.
bus: a bus or coach. A tram is none.
delivery_van: any van body (Transit, Transporter, Kangoo).
truck: goods vehicle with a separate cab: lorry, box truck, tipper, pickup.
none: no road user; a parked or riderless bicycle, scooter or motorcycle; a tram; a
  picture of a vehicle (poster, sign, screen, advert).
unsure: you cannot tell. Between car and SUV, prefer unsure to a guess.
</classes>
<output>
Exactly {n} items, one per id from 1 to {n}. note: at most eight words on what decided it.
</output>"""


def build_prompt(n: int) -> str:
    return PROMPT.format(n=n)


def crop_region(
    x1: float, y1: float, x2: float, y2: float, width: int, height: int, margin: float
) -> tuple[int, int, int, int]:
    """Pixel box plus ``margin`` of its size on each side, clipped to the image."""
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    return (
        max(0, round(x1 - mx)),
        max(0, round(y1 - my)),
        min(width, round(x2 + mx)),
        min(height, round(y2 + my)),
    )


def build_command(
    images: list[Path], schema: Path, out: Path, model: str, effort: str
) -> list[str]:
    """``codex exec`` call: read-only, no session saved, prompt on stdin."""
    return [
        "codex",
        "exec",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "-s",
        "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "--output-schema",
        str(schema.resolve()),
        "-o",
        str(out.resolve()),
        "-i",
        *(str(p.resolve()) for p in images),
        "-",
    ]


def output_schema(labels: list[str]) -> dict:
    item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "label", "note"],
        "properties": {
            "id": {"type": "integer"},
            "label": {"type": "string", "enum": labels},
            "note": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {"items": {"type": "array", "items": item}},
    }


def parse_reply(text: str, n: int) -> dict[int, tuple[str, str]]:
    """Map id (1..n) to (label, note); fail on missing ids or unknown labels."""
    labels = set(load_canonical_classes()) | set(EXTRA_LABELS)
    items = json.loads(text)["items"]
    out = {int(it["id"]): (it["label"], it["note"]) for it in items}
    if set(out) != set(range(1, n + 1)):
        raise ValueError(f"reply ids {sorted(out)} do not match 1..{n}")
    bad = {lab for lab, _ in out.values()} - labels
    if bad:
        raise ValueError(f"reply has unknown label(s) {sorted(bad)}")
    return out


def verdict(current: str, vlm_label: str) -> str:
    if vlm_label == "unsure":
        return "unsure"
    return "agree" if vlm_label == current else "disagree"


def boxed_crop(
    img: Image.Image, box: tuple[float, float, float, float], margin: float
) -> Image.Image:
    """The box with ``margin`` of context, the box itself outlined in green.

    Without the outline, a rider in front of a labelled car sits at the crop's centre and
    gets classified instead of the car.
    """
    img = img.convert("RGB")
    ImageDraw.Draw(img).rectangle(box, outline=BOX_COLOUR, width=max(2, img.width // 400))
    return img.crop(crop_region(*box, img.width, img.height, margin))


def labelled_crop(crop: Image.Image, n: int) -> Image.Image:
    """Enlarge a small crop and put its id in a strip above it, clear of the object."""
    crop = crop.convert("RGB")
    scale = max(1.0, MIN_CROP_SIDE / min(crop.size))
    if scale > 1:
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    out = Image.new("RGB", (crop.width, crop.height + ID_STRIP), (0, 0, 0))
    out.paste(crop, (0, ID_STRIP))
    ImageDraw.Draw(out).text((4, 5), str(n), fill=(255, 255, 0))
    return out


def flagged_images(rows: list[dict]) -> list[str]:
    """Images with at least one checked box that Codex did not agree with."""
    return sorted({r["image"] for r in rows if r.get("vlm_verdict") in ("disagree", "unsure")})


def _ask_codex(crops: list[Path], args: argparse.Namespace) -> dict[int, tuple[str, str]]:
    """Ask once; retry once if the reply does not validate."""
    try:
        return _ask_codex_once(crops, args)
    except ValueError as e:
        logger.warning("bad reply (%s); retrying the batch once", e)
        return _ask_codex_once(crops, args)


def _ask_codex_once(crops: list[Path], args: argparse.Namespace) -> dict[int, tuple[str, str]]:
    labels = load_canonical_classes() + EXTRA_LABELS
    with tempfile.TemporaryDirectory() as tmp:
        numbered = []
        for i, crop in enumerate(crops, 1):
            numbered.append(Path(tmp) / f"{i}.jpg")
            labelled_crop(Image.open(crop), i).save(numbered[-1], quality=90)
        schema, out = Path(tmp) / "schema.json", Path(tmp) / "reply.json"
        schema.write_text(json.dumps(output_schema(labels)))
        cmd = build_command(numbered, schema, out, args.model, args.effort)
        proc = subprocess.run(
            cmd,
            input=build_prompt(len(crops)),
            text=True,
            capture_output=True,
            cwd=tmp,
            timeout=900,
            check=False,
        )
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"codex exec failed ({proc.returncode}): {proc.stderr[-500:]}")
        return parse_reply(out.read_text(), len(crops))


def _write_rows(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    for extra in ("vlm_label", "vlm_note", "vlm_verdict"):
        if extra not in fields:
            fields.append(extra)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, restval="")
        writer.writeheader()
        writer.writerows(rows)


def _crop(row: dict, run: Path, crops: Path, margin: float) -> Path:
    path = crops / f"{Path(row['image']).stem}__{row['box']}.jpg"
    if not path.exists():
        img = Image.open(run / "images" / row["image"])
        coords = tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2"))
        crop = boxed_crop(img, coords, margin)
        crop.thumbnail((MAX_CROP_SIDE, MAX_CROP_SIDE))
        crop.save(path, quality=90)
    return path


def _review_folders(run: Path, rows: list[dict]) -> None:
    flagged = set(flagged_images(rows))
    names = sorted({r["image"] for r in rows} | {p.name for p in (run / "images").iterdir()})
    data = yaml.safe_load((run / "data.yaml").read_text())
    for group in ("flagged", "ok"):
        dest = run / "review" / group
        shutil.rmtree(dest, ignore_errors=True)
        (dest / "images").mkdir(parents=True)
        (dest / "labels").mkdir()
        (dest / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    for name in names:
        dest = run / "review" / ("flagged" if name in flagged else "ok")
        shutil.copy2(run / "images" / name, dest / "images" / name)
        label = run / "labels" / f"{Path(name).stem}.txt"
        if label.exists():
            shutil.copy2(label, dest / "labels" / label.name)
    (run / "flagged.txt").write_text("".join(f"{n}\n" for n in sorted(flagged)))
    logger.info("%d flagged, %d ok -> %s", len(flagged), len(names) - len(flagged), run / "review")


def run(args: argparse.Namespace) -> None:
    boxes_csv = args.run / "boxes.csv"
    with open(boxes_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    checked = set(args.classes.split(","))
    unknown = checked - set(load_canonical_classes())
    if unknown:
        raise SystemExit(f"--classes has non-canonical names: {sorted(unknown)}")
    todo = [r for r in rows if r["class"] in checked and not r.get("vlm_label")]
    logger.info("%d boxes to check with %s", len(todo), args.model)

    crops = args.run / "crops"
    crops.mkdir(exist_ok=True)
    for start in range(0, len(todo), args.batch):
        batch = todo[start : start + args.batch]
        reply = _ask_codex([_crop(r, args.run, crops, args.margin) for r in batch], args)
        if len(batch) > 1 and all(label == "unsure" for label, _ in reply.values()):
            logger.warning(
                "every answer in this batch is 'unsure'; did Codex see the images? %s", reply[1][1]
            )
        for i, row in enumerate(batch, 1):
            label, note = reply[i]
            row.update(vlm_label=label, vlm_note=note, vlm_verdict=verdict(row["class"], label))
        _write_rows(boxes_csv, rows)
        logger.info("%d/%d checked", min(start + args.batch, len(todo)), len(todo))

    if rows:
        _review_folders(args.run, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", type=Path, required=True, help="output folder of autolabel")
    parser.add_argument("--classes", default=DEFAULT_CLASSES, help="comma-separated")
    parser.add_argument("--model", default="gpt-6-astra", help="Codex model with image input")
    parser.add_argument("--effort", default="medium", help="Codex reasoning effort")
    parser.add_argument("--batch", type=int, default=20, help="crops per Codex call")
    parser.add_argument("--margin", type=float, default=0.4, help="context around each box")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
