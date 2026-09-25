"""Tests for the model comparison's pure parts: finding the model, scoring counts."""

from __future__ import annotations

from pathlib import Path

import pytest

from training.count_eval import Row
from training.evaluate import resolve_model, summarise_counts


def test_a_training_run_resolves_to_its_best_weights(tmp_path: Path) -> None:
    (tmp_path / "exp" / "weights").mkdir(parents=True)
    (tmp_path / "exp" / "weights" / "best.pt").write_bytes(b"pt")

    name, path = resolve_model(tmp_path / "exp")

    assert name == "exp" and path == tmp_path / "exp" / "weights" / "best.pt"


def test_an_ncnn_directory_is_used_as_is(tmp_path: Path) -> None:
    ncnn = tmp_path / "camina_v1_yolo11n_ncnn_model"
    ncnn.mkdir()
    (ncnn / "model.ncnn.param").write_text("")

    assert resolve_model(ncnn) == ("camina_v1_yolo11n_ncnn_model", ncnn)


def test_anything_else_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a training run or an NCNN model"):
        resolve_model(tmp_path)


def test_count_summary_adds_absolute_errors_and_needs_every_row_to_pass() -> None:
    rows = [Row("car", "AB", 11, 11), Row("car", "BA", 6, 12), Row("person", "BA", 5, 3)]

    assert summarise_counts(rows) == {"truth": 22, "counted": 26, "abs_error": 8, "s7": False}
