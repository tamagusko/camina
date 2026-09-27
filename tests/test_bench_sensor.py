"""Fake-driven coverage for sensor bench telemetry on non-Pi machines."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import bench_sensor


def test_hardware_readers_parse_values_and_fail_cleanly(tmp_path: Path) -> None:
    temp_path = tmp_path / "temp"
    rss_path = tmp_path / "status"
    temp_path.write_text("48750\n", encoding="utf-8")
    rss_path.write_text("Name:\tbench\nVmRSS:\t2048 kB\n", encoding="utf-8")

    def vcgencmd(args: list[str], **_kwargs: object) -> object:
        assert args == ["vcgencmd", "get_throttled"]

        class Result:
            returncode = 0
            stdout = "throttled=0x50000\n"

        return Result()

    assert bench_sensor.read_cpu_temp(temp_path) == 48.8
    assert bench_sensor.read_process_rss_mb(rss_path) == 2.0
    assert bench_sensor.read_throttled(run=vcgencmd) == 0x50000
    assert bench_sensor.read_cpu_temp(tmp_path / "missing") is None
    assert bench_sensor.read_process_rss_mb(tmp_path / "missing") is None

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise OSError

    assert bench_sensor.read_throttled(run=unavailable) is None


def test_benchmark_uses_fake_pipeline_and_emits_three_telemetry_phases(
    tmp_path: Path,
) -> None:
    now = [0.0]

    def clock() -> float:
        current = now[0]
        now[0] += 0.025
        return current

    samples: list[str] = []

    def telemetry() -> dict[str, object]:
        samples.append("sample")
        return {"cpu_temp_c": 50.0, "rss_mb": 12.5, "throttled": 0}

    report = bench_sensor.run_benchmark(
        frames=[object(), object(), object(), object()],
        detect=lambda _frame: (),
        duration_s=0.2,
        telemetry=telemetry,
        clock=clock,
    )
    assert report["pass_criteria"]["fps_minimum"] == 5
    assert [sample["phase"] for sample in report["hardware_samples"]] == [
        "start",
        "middle",
        "end",
    ]
    assert len(samples) == 3
    assert report["frames_processed"] >= 2
    assert len(report["fps_samples"]) == report["frames_processed"]
    assert {"instantaneous", "rolling_1m"} <= report["fps_samples"][-1].keys()
    assert report["fps"]["instantaneous"] >= 5
    assert report["fps"]["rolling_1m"] >= 5
    assert report["pass_criteria"]["passed"] is True

    out = tmp_path / "bench.json"
    bench_sensor.write_reports(report, out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert saved == report
    assert "Hardware samples" in markdown
    assert "0x0" in markdown


def test_benchmark_reports_failed_threshold_or_unavailable_throttle() -> None:
    report = bench_sensor.summarize_benchmark(
        frame_times=[0.0, 0.5],
        telemetry_samples=[
            {"phase": phase, "cpu_temp_c": None, "rss_mb": None, "throttled": None}
            for phase in ("start", "middle", "end")
        ],
        duration_s=1.0,
    )
    assert report["pass_criteria"]["passed"] is False
