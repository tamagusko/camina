# Tracker occlusion rules — count error on the hand-counted clip — 2026-09-27

## Setup

- Clip: `videos/test.mov`, 5988 frames at 60 fps (99.8 s), 416 x 416; hand count
  `videos/test.counts.csv` (screenline x = 0.5, all nine classes complete, 30 crossings).
- Model: `models/camina_v1_yolo11n_ncnn_model` (FP32 NCNN, imgsz 640, conf 0.3), CPU.
  OpenCV 4.11.0, ncnn 1.0.20260526, numpy 2.2.5, scipy 1.15.2, filterpy 1.4.5.
- Command, on each commit:
  `python -m training.count_eval --video videos/test.mov --truth videos/test.counts.csv`
  - **Before:** base `ca6ed2a` (SORT, `max_age` 90 frames = 1.5 s at 60 fps).
  - **After:** `3abe1ab` (feat/tracker-occlusion), defaults: `max_occlusion_s` 5.0,
    re-link `RELINK_K` 0.5, area ratio [0.5, 2], `min_class_hits` 3, rider overlap 0.6.
    Frames are stamped with their clip time (index / fps).
- Ablation: the detector's output was cached once per frame and replayed through the
  tracker and gate with one rule switched off at a time (scratch script, not committed).
  The cache replays the base commit's counts exactly, and "all rules" equals the "After"
  run of `count_eval`.

## Count error

| Class | Dir | Truth | Before | After | No re-link | No rider rule | `min_class_hits` 1 | Occlusion 1.5 s |
|---|---|---|---|---|---|---|---|---|
| SUV | BA | 3 | 2 (−1) | 1 (−2) | 2 (−1) | 1 (−2) | 1 (−2) | 2 (−1) |
| car | AB | 11 | 11 (0) | 11 (0) | 11 (0) | 11 (0) | 11 (0) | 10 (−1) |
| car | BA | 6 | 12 (+6) | 13 (+7) | 12 (+6) | 13 (+7) | 13 (+7) | 12 (+6) |
| cyclist | AB | 1 | 1 (0) | 1 (0) | 1 (0) | 1 (0) | 1 (0) | 1 (0) |
| delivery_van | BA | 2 | 0 (−2) | 0 (−2) | 0 (−2) | 0 (−2) | 0 (−2) | 0 (−2) |
| person | AB | 2 | 2 (0) | 3 (+1) | 2 (0) | 3 (+1) | 3 (+1) | 2 (0) |
| person | BA | 5 | 3 (−2) | 13 (+8) | 3 (−2) | 13 (+8) | 13 (+8) | 6 (+1) |
| **Sum of \|error\|** | | 30 | **11** | **20** | 11 | 20 | 20 | 11 |
| S7 | | | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| Re-links | | | – | 199 | 0 | 201 | 199 | 165 |
| `unconfirmed_dropped` | | | – | 0 | 0 | 0 | 0 | 0 |

Still pending (crossed, class unconfirmed) at the end of the clip: 0 in every run.

## Reading

- **The rules as a set make this clip worse: the summed error goes from 11 to 20.** The
  whole change comes from the **re-link**: with it switched off, the counts equal the base
  commit's exactly. It adds eight `person` B→A counts (3 → 13 against a truth of 5), one
  `person` A→B, one `car` B→A and loses one `SUV`.
- **Why the re-link over-counts people.** The logged re-links show long-lived tracks on
  static false positives (the bollards and signs the count gate exists for; two of them
  had 1296 and 1829 detections) just right of the line. When a pedestrian walks past, the
  static detection is hidden, and 2–4 s later the static track is re-linked to the
  pedestrian 30–65 px away, on the other side of the line. The track then "crosses" and
  counts, while the pedestrian's own track may count as well. The gate radius grows with
  the time hidden (`1 + s`), which suits a moving object but gives a static one 2–3 box
  heights of reach. On the vehicle side, near boxes are ~200 px tall, so the radius is too
  (~280 px after 1.8 s hidden): three short car tracks at the right frame edge were
  re-linked to SUVs 45–125 px away.
- **Occlusion in seconds** alone (no re-link) changes nothing here: the 5 s survival equals
  the base 1.5 s on this clip. With re-link on, 1.5 s instead of 5 s cuts the damage (sum
  11, person B→A +1), because static tracks have less time to be re-linked.
- **Class confirmation** changes nothing here: at 60 fps three detections take 50 ms, and no
  track crossed while unconfirmed (`unconfirmed_dropped` 0). It matters more on the Pi at
  ~10 fps, where three detections take 0.3 s; this clip cannot show it.
- **Rider rule** changes nothing here: the clip has one cyclist, counted right in every run
  (two fewer re-links only).
- **Speed** (`tests/test_tracker_benchmark.py`, 60 objects, half hidden, this host):
  `Sort.update` mean 5.8–6.2 ms before, 1.8 ms after (vectorised IoU), re-linking included.

## Caveats

- One 100 s clip with 30 true crossings; five of seven cells have fewer than seven. It is the
  only truth we have, so it cannot choose thresholds without overfitting to it: the
  defaults above are the conservative values picked before this measurement, not tuned on
  it.
- Diagnostic only, **not adopted**: `RELINK_K` 0.25 gives sum 12 (person B→A +3), 1.0 gives
  25; re-linking only tracks moving at ≥ 0.5 box heights/s gives sum 13 (person B→A −1, car
  B→A +7). These point at the mechanism (static tracks), but picking any of them from this
  clip would be fitting the clip. Deciding whether static tracks may be re-linked needs a
  second hand-counted clip.
