# Archive

Historical code and documents kept for reference. **Nothing here is maintained,
imported by the active codebase, or covered by tests.** Internal imports may be
broken by the move — files are preserved as-is for history, not for execution.

| Path | What it was | Superseded by |
|---|---|---|
| `legacy_app/main.py` + `legacy_app/app.py` | Original `ModalShareCounterApp` entry point (OpenCV window, local display) | `scripts/run_sensor.py` + `src/camina/service/sensor_daemon.py` |
| `legacy_app/display.py` | E-paper/OLED display glue for the legacy app | Headless daemon (no local display) |
| `dev/` | Development experiments (motion detector, low-light counter, camera position check, plugged counter, speed-estimation prototype) | `src/camina/core/tracker.py` (tracker), rest unused |
| `hw_utils/` | E-paper/OLED drivers + single-image inference helper | Not part of the v1 architecture |
| `plans/` | Pre-GSD planning docs (Apr 2026) | `.planning/` (ROADMAP, phases) |
| `docs/TODO.md` | Early brain-dump TODO | Root `TODO.md` (curated work queue) |
| `environment.yml` | Conda environment | `requirements.txt` + `uv` |
