"""Speed budget for ``Sort.update``: a busy street must not slow the loop.

Scene: 60 objects, half of them hidden every other second (so the tracker
carries 30 lost tracks through association), 300 frames. The test fails when
the mean ``Sort.update`` time exceeds ``BUDGET_MS``.

Development host (AMD Ryzen 7 5700X, idle, 2026-09-27), same scene:
- base ca6ed2a (Python double-loop IoU): mean 5.8-6.2 ms per frame
  (8.7-10.5 ms while the machine was also running count_eval);
- vectorised IoU, with re-linking and class confirmation: mean 1.8 ms.
The budget is generous on purpose: it catches an accidental O(n^2) Python
loop, not a few percent. The Pi 5 is several times slower than this host.
"""

from __future__ import annotations

import time

import numpy as np

from camina.core.tracker import Sort

N_OBJECTS = 60
N_FRAMES = 300
FPS = 30.0
BUDGET_MS = 15.0


def _frame(i: int, x0: np.ndarray, y0: np.ndarray) -> np.ndarray:
    rows = []
    for k in range(N_OBJECTS):
        if k % 2 and (i // int(FPS)) % 2:  # odd objects hidden every other second
            continue
        x, y = x0[k] + 2.0 * i, y0[k]
        rows.append([x, y, x + 40.0, y + 60.0, 0.9, k % 9])
    return np.asarray(rows, dtype=float)


def test_sort_update_stays_within_budget_at_60_objects() -> None:
    rng = np.random.default_rng(0)
    x0, y0 = rng.uniform(0, 1800, N_OBJECTS), rng.uniform(0, 1000, N_OBJECTS)
    frames = [_frame(i, x0, y0) for i in range(N_FRAMES)]
    tracker = Sort(relink=True)  # worst case: the re-link pass runs
    times = []
    for i, dets in enumerate(frames):
        start = time.perf_counter()
        tracker.update(dets, t=i / FPS)
        times.append(time.perf_counter() - start)

    mean_ms = 1e3 * float(np.mean(times[int(FPS) :]))  # skip the warm-up second
    assert mean_ms <= BUDGET_MS, f"Sort.update mean {mean_ms:.1f} ms > {BUDGET_MS} ms"
