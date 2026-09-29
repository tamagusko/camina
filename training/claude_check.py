"""Second opinion on each auto-label's class, from Claude, before the Roboflow review.

The same crops, prompt and class definitions as ``training.codex_check``, asked of Claude
through ``claude -p`` with your personal login (``--config-dir``, default ``~/.claude``;
never the UCD one), no tools, no hooks, no MCP servers. The answer goes to ``boxes.csv``
as ``claude_label``, ``claude_note`` and ``claude_verdict``, batch by batch, so an
interrupted run (a usage limit, say) resumes where it stopped.

Claude changes no label. An image goes to ``<run>/review/flagged`` when Codex *or* Claude
disagrees with, or is unsure of, any of its boxes. ``--disputed`` asks Claude only about
the boxes Codex already disputed: the cheap way to get two opinions where they matter.

Crops leave this machine (they go to Anthropic). For camera images, keep person-carrying
classes out of ``--classes`` until GDPR and the camera terms are settled.

    .venv/bin/python -m training.claude_check --run data/autolabel/montreal --disputed
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import logging
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from training.class_taxonomy import load_canonical_classes
from training.codex_check import (
    DEFAULT_CLASSES,
    EXTRA_LABELS,
    _crop,
    _review_folders,
    _write_rows,
    build_prompt,
    labelled_crop,
    output_schema,
    parse_reply,
    verdict,
)

logger = logging.getLogger(__name__)

PREFIX = "claude"
DISPUTED = ("disagree", "unsure")


def build_command(model: str, effort: str, schema: dict) -> list[str]:
    """Headless Claude Code: images and prompt on stdin, JSON schema for the reply."""
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--effort",
        effort,
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        json.dumps(schema),
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
    ]


def build_message(images: list[Image.Image], prompt: str) -> str:
    """One stream-json user turn: every image inline, in id order, then the prompt."""
    content = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        data = base64.b64encode(buf.getvalue()).decode()
        source = {"type": "base64", "media_type": "image/jpeg", "data": data}
        content.append({"type": "image", "source": source})
    content.append({"type": "text", "text": prompt})
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"


def account_env(config_dir: Path) -> dict[str, str]:
    """The environment with Claude pointed at ``config_dir``'s login.

    An API key in the environment would take precedence over that login, so it is dropped.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDE_ACCOUNT")}
    env["CLAUDE_CONFIG_DIR"] = str(config_dir.expanduser())
    return env


def parse_stream(stdout: str) -> dict:
    """The structured reply from the ``result`` event of a stream-json run."""
    for line in reversed(stdout.splitlines()):
        event = json.loads(line) if line.strip() else {}
        if event.get("type") == "result":
            if event.get("is_error") or "structured_output" not in event:
                raise RuntimeError(f"claude failed: {str(event.get('result'))[:500]}")
            return event["structured_output"]
    raise RuntimeError("claude returned no result")


def box_side(row: dict) -> float:
    """The shorter side of a box, in pixels."""
    return min(float(row["x2"]) - float(row["x1"]), float(row["y2"]) - float(row["y1"]))


def select_rows(
    rows: list[dict], classes: set[str], disputed: bool, min_side: float = 0
) -> list[dict]:
    """Rows still to check: in ``classes``, not answered yet, at least ``min_side`` px on
    the shorter side, and (with ``disputed``) ones Codex disagreed with or was unsure of."""
    todo = [
        r
        for r in rows
        if r["class"] in classes and not r.get(f"{PREFIX}_label") and box_side(r) >= min_side
    ]
    if disputed:
        todo = [r for r in todo if r.get("vlm_verdict") in DISPUTED]
    return todo


def _ask_claude(crops: list[Path], args: argparse.Namespace) -> dict[int, tuple[str, str]]:
    """Ask once; retry once if the reply does not validate."""
    try:
        return _ask_claude_once(crops, args)
    except ValueError as e:
        logger.warning("bad reply (%s); retrying the batch once", e)
        return _ask_claude_once(crops, args)


def _ask_claude_once(crops: list[Path], args: argparse.Namespace) -> dict[int, tuple[str, str]]:
    images = [labelled_crop(Image.open(c), i) for i, c in enumerate(crops, 1)]
    schema = output_schema(load_canonical_classes() + EXTRA_LABELS)
    with tempfile.TemporaryDirectory() as tmp:  # an empty cwd: no project settings or files
        proc = subprocess.run(
            build_command(args.model, args.effort, schema),
            input=build_message(images, build_prompt(len(crops))),
            text=True,
            capture_output=True,
            cwd=tmp,
            env=account_env(args.config_dir),
            timeout=900,
            check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed ({proc.returncode}): {proc.stderr[-500:]}")
    return parse_reply(json.dumps(parse_stream(proc.stdout)), len(crops))


def _apply(batch: list[dict], reply: dict[int, tuple[str, str]]) -> None:
    if len(batch) > 1 and all(label == "unsure" for label, _ in reply.values()):
        logger.warning("every answer in this batch is 'unsure': %s", reply[1][1])
    for i, row in enumerate(batch, 1):
        label, note = reply[i]
        row.update(
            {
                f"{PREFIX}_label": label,
                f"{PREFIX}_note": note,
                f"{PREFIX}_verdict": verdict(row["class"], label),
            }
        )


def _check_batch(
    batch: list[dict], crops: Path, args: argparse.Namespace
) -> dict[int, tuple[str, str]]:
    return _ask_claude([_crop(r, args.run, crops, args.margin) for r in batch], args)


def run(args: argparse.Namespace) -> None:
    boxes_csv = args.run / "boxes.csv"
    with open(boxes_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    checked = set(args.classes.split(","))
    unknown = checked - set(load_canonical_classes())
    if unknown:
        raise SystemExit(f"--classes has non-canonical names: {sorted(unknown)}")
    todo = select_rows(rows, checked, args.disputed, args.min_side)
    if args.limit:
        todo = todo[: args.limit]
    logger.info(
        "%d boxes to check with Claude (%s, %d workers)", len(todo), args.model, args.workers
    )

    crops = args.run / "crops"
    crops.mkdir(exist_ok=True)
    batches = [todo[i : i + args.batch] for i in range(0, len(todo), args.batch)]
    done, failure = 0, None
    # Workers only call Claude; rows are updated and saved here, one batch at a time.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_check_batch, b, crops, args): b for b in batches}
        for future in as_completed(futures):
            if future.cancelled():
                continue
            try:
                reply = future.result()
            except Exception as e:  # a usage limit, a timeout: keep what is done, stop
                if failure is None:
                    failure = e
                    pool.shutdown(wait=False, cancel_futures=True)
                continue
            _apply(futures[future], reply)
            _write_rows(boxes_csv, rows, PREFIX)
            done += len(futures[future])
            logger.info("%d/%d checked", done, len(todo))

    if rows:
        _review_folders(args.run, rows)
    if failure is not None:
        raise SystemExit(f"stopped after {done}/{len(todo)} boxes ({failure}); re-run to resume")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", type=Path, required=True, help="output folder of autolabel")
    parser.add_argument("--classes", default=DEFAULT_CLASSES, help="comma-separated")
    parser.add_argument(
        "--disputed", action="store_true", help="only boxes Codex disagreed with or was unsure of"
    )
    parser.add_argument("--model", default="opus", help="Claude model alias or id")
    parser.add_argument("--effort", default="medium", help="Claude effort level")
    parser.add_argument("--batch", type=int, default=20, help="crops per Claude call")
    parser.add_argument("--margin", type=float, default=0.4, help="context around each box")
    parser.add_argument(
        "--min-side", type=float, default=0, help="skip boxes shorter than this (px) on a side"
    )
    parser.add_argument("--workers", type=int, default=1, help="Claude calls in parallel")
    parser.add_argument("--limit", type=int, default=0, help="check at most this many boxes")
    parser.add_argument(
        "--config-dir", type=Path, default=Path("~/.claude"), help="whose Claude login to use"
    )
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
