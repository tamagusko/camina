import argparse
import csv
import json
from pathlib import Path

import pytest
from PIL import Image

from training import claude_check
from training.claude_check import (
    account_env,
    build_command,
    build_message,
    parse_stream,
    select_rows,
)
from training.codex_check import flagged_images


def test_command_runs_without_tools_settings_or_mcp() -> None:
    cmd = build_command("opus", "medium", {"type": "object"})
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert {"--strict-mcp-config", "--no-session-persistence"} <= set(cmd)
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == {"type": "object"}


def test_message_has_every_image_in_order_then_the_prompt() -> None:
    images = [Image.new("RGB", (8, 8), c) for c in ("red", "blue")]
    msg = json.loads(build_message(images, "which class?"))
    content = msg["message"]["content"]
    assert [c["type"] for c in content] == ["image", "image", "text"]
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[-1]["text"] == "which class?"


def test_env_uses_the_given_login_and_drops_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/home/x/.claude-ucd")
    monkeypatch.setenv("CLAUDE_ACCOUNT", "ucd")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    env = account_env(Path("/home/x/.claude"))
    assert env["CLAUDE_CONFIG_DIR"] == "/home/x/.claude"
    assert "ANTHROPIC_API_KEY" not in env and "CLAUDE_ACCOUNT" not in env


def test_parse_stream_reads_the_result_event() -> None:
    events = [
        {"type": "system"},
        {"type": "result", "is_error": False, "structured_output": {"items": []}},
    ]
    assert parse_stream("\n".join(json.dumps(e) for e in events)) == {"items": []}


def test_parse_stream_raises_on_an_error_result() -> None:
    event = {"type": "result", "is_error": True, "result": "usage limit reached"}
    with pytest.raises(RuntimeError, match="usage limit"):
        parse_stream(json.dumps(event))
    with pytest.raises(RuntimeError, match="no result"):
        parse_stream("")


def _row(cls: str, side: float = 50, **extra: str) -> dict:
    return {"class": cls, "x1": "0", "y1": "0", "x2": str(side), "y2": str(side * 2), **extra}


def test_select_rows_skips_answered_and_keeps_only_disputed_on_request() -> None:
    rows = [
        _row("SUV", vlm_verdict="disagree"),
        _row("SUV", vlm_verdict="agree"),
        _row("car", vlm_verdict="unsure", claude_label="car"),
        _row("person", vlm_verdict="disagree"),
    ]
    assert select_rows(rows, {"SUV", "car"}, disputed=False) == rows[:2]
    assert select_rows(rows, {"SUV", "car"}, disputed=True) == rows[:1]


def test_select_rows_skips_boxes_too_small_to_judge() -> None:
    rows = [_row("car", side=10), _row("car", side=30)]
    assert select_rows(rows, {"car"}, disputed=False, min_side=24) == rows[1:]


def test_a_failed_batch_stops_the_run_and_keeps_the_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    (tmp_path / "data.yaml").write_text("names: {0: car}\n")
    rows = []
    for n in range(3):
        Image.new("RGB", (64, 64)).save(tmp_path / "images" / f"{n}.jpg")
        rows.append({"image": f"{n}.jpg", "box": "0", **_row("car", side=30)})
    with open(tmp_path / "boxes.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def fake_ask(crops: list[Path], args: argparse.Namespace) -> dict:
        if "1__0" in crops[0].name:
            raise RuntimeError("usage limit reached")
        return {1: ("SUV", "tall body")}

    monkeypatch.setattr(claude_check, "_ask_claude", fake_ask)
    args = argparse.Namespace(
        run=tmp_path,
        classes="car",
        disputed=False,
        min_side=0,
        limit=0,
        batch=1,
        workers=1,
        margin=0.4,
        model="opus",
    )
    with pytest.raises(SystemExit, match="re-run to resume"):
        claude_check.run(args)
    with open(tmp_path / "boxes.csv", newline="") as f:
        saved = {r["image"]: r["claude_label"] for r in csv.DictReader(f)}
    assert saved["0.jpg"] == "SUV"
    assert saved["1.jpg"] == ""


def test_an_image_is_flagged_when_either_checker_disputes_a_box() -> None:
    rows = [
        {"image": "a.jpg", "vlm_verdict": "agree", "claude_verdict": "disagree"},
        {"image": "b.jpg", "vlm_verdict": "unsure"},
        {"image": "c.jpg", "vlm_verdict": "agree", "claude_verdict": "agree"},
    ]
    assert flagged_images(rows) == ["a.jpg", "b.jpg"]
