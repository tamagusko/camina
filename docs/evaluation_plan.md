# CAMINAv1 Evaluation Plan

Working doc for evaluating fine-tuned 9-class YOLO11 ("CAMINAv1") candidates so results
are **comparable across model versions** and gate promotion to the Pi 5 NCNN slot. Pairs
with `docs/training_plan.md` (promotion path §5).

Canonical 9-class taxonomy — now locked in `configs/classes.yaml` (single source of
truth), consumed by the edge runtime (`configs/sensor.yaml`, `detect_track.py`), the
export guard (`src/utils/export_ncnn.py`), the training toolchain (via the alias table
`custom_model_train/class_mapping.yaml`), and the dashboard
(`dashboard/src/lib/types.ts`). The 4-way conflict is **resolved** — see training plan §0:

```
0 person   1 cyclist   2 car       3 e-scooter   4 SUV
5 motorcyclist   6 bus   7 delivery_van   8 truck
```

Toolchain metrics use legacy field names (`pedestrian_map`==person, `motorcycle_map`==
motorcyclist) but are now indexed by this canonical order in
`model_comparison_framework.py`.

Minority classes for CAMINA's mobility question: **cyclist, e-scooter, motorcyclist**
(and to a lesser degree bus / delivery_van). These are the classes that matter for the
active-travel narrative and are the ones a car/person-dominated mAP will mask.

---

## 1. Held-out test set

**Does not exist yet.** `convert_sdl_to_yolo11.py:155-164` creates an **empty**
`images/test` (`:213` "Test split is empty"); today's "val" is just the SDL test split
reused. A frozen held-out set is the foundation of comparability.

Requirements:
- **Frozen, never trained on.** Materialise `images/test` + `labels/test` once, record its
  hash (§3), and **exclude it from every `data.yaml` train/val path**. Guard: assert no
  filename overlap between test and train∪val before each run.
- **Stratification.** Ensure every class — especially cyclist / e-scooter / motorcyclist —
  has a minimum instance count (target ≥ 50 boxes/class; if a rare class can't reach it,
  record the actual N and treat its metrics as low-confidence). Stratify across
  **conditions if data allows**: day / night / rain, and camera angle. Tag each test image
  with its condition so metrics can be sliced.
- **Storage + hash.** Keep under a stable path (e.g. `datasets/caminav1_heldout_vNN/`),
  version-tagged, with `sha256` over sorted label files + images recorded in the results
  JSON (§3). Re-derive the hash at eval time and refuse to compare across differing hashes.

Effort to build: **M** (materialise + stratify + hash + overlap guard).

---

## 2. Metrics

### 2a. Detection metrics (per class + overall)

Ultralytics `model.val()` yields most of these natively; the wrapper just needs to persist
them per class.

| Metric | Per-class | Overall | Source today |
|---|---|---|---|
| Precision | ✓ | ✓ | `val_results.box` (P) — **not currently persisted per class** |
| Recall | ✓ | ✓ | `val_results.box` (R) — not persisted per class |
| F1 | ✓ (derive P·R) | ✓ | derive; not stored |
| AP@50 | ✓ | mAP@50 | `box.map50`, `box.maps` (`model_comparison_framework.py:262-271`) |
| AP@50-95 | ✓ | mAP@50-95 | `box.map`, `box.maps` |
| Confusion matrix | 9×9 (+background) | — | Ultralytics emits `confusion_matrix.png`; **not captured to JSON** |

Current persistence stores **per-class mAP only** (`evaluation_logging_system.py:49-57`,
`model_comparison_framework.py:44-52`) and overall P/R/F1 as scalars — **no per-class P/R/F1
and no confusion matrix**. Extending the per-class record to P/R/F1/AP50/AP50-95 is gap G3.

### 2b. Count-level metric (CAMINA's real task)

Box mAP does **not** guarantee count accuracy — CAMINA's product is a per-class windowed
**count** (detector feeds `WindowedCounter`). A model can have decent mAP yet systematically
over/under-count a class (double-counts, ID-flicker, class confusion between cyclist↔
motorcyclist↔e-scooter).

**Per-class count error on annotated clips** (new — gap G4):
- Take short annotated clips (or the frozen test images grouped into pseudo-windows), run
  the full detect→track→count path, and compare produced per-class counts to ground-truth
  counts.
- Report per class: **count MAE** and **signed % bias** (bias sign matters for the
  dashboard's colour-coding — a class biased low reads as a quieter street than reality).
- This is the metric closest to the deliverable and the one to weight most heavily for the
  minority classes.

---

## 3. Comparability across versions

### What already exists (plan around it, don't rebuild)

- **`evaluation_logging_system.py`** — SQLite-backed experiment store
  (`ExperimentDatabase:83-242`) with an `ExperimentLog` dataclass (`:27-81`: overall
  mAP/P/R/F1, per-class mAP, size, FPS, device, hyperparams) and a `dataset_version`
  **string** field (`:33`). `generate_comparison_report()` (`:310-346`) produces a
  cross-experiment JSON (per-model comparison `:348`, per-class analysis `:367`, trends,
  Pareto frontier, recommendations). `export_results_csv()` (`:597`) and a plotting
  dashboard (`create_visualization_dashboard:495` — per-class heatmap, efficiency scatter,
  timeline) exist. CLI: `--action report|export|visualize|cleanup`.
- **`model_comparison_framework.py`** — trains/vals several YOLO variants and writes
  `per_class_performance.csv`, `model_comparison_summary.csv`, `comparison_report.json`
  (`:526-582`).

### The catch

- **Nothing writes real results in.** `ExperimentLog` rows must be populated by hand; no
  code path runs `model.val()` and inserts the row (gap G1).
- **Dummy-metric fallbacks removed (2026-07-10).** `model_comparison_framework.py` used to
  fabricate metrics — a `_create_dummy_model` returning `np.random.uniform` mAPs, and
  `benchmark_video_inference` returning random FPS when no real video was present. Both are
  gone: `setup_model` now returns `None` on failure (logged), the benchmarks return `None`
  and the caller **skips** that model rather than storing invented numbers. A comparison can
  no longer be silently synthetic (gap G2 done).
- `dataset_version` is a free-text string, not a hash → two runs labelled "v2" may differ.
  Replace with the §1 dataset hash (gap G3).

### Target results record (versioned JSON, one per candidate)

```json
{
  "model_id": "caminav1_20260710_1430",
  "dataset_hash": "sha256:ab12cd…",
  "date": "2026-07-10",
  "imgsz": 480,
  "runtime": "pytorch",              // or "ncnn"
  "overall": { "mAP50": 0.0, "mAP50_95": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0 },
  "per_class": {
    "cyclist":     { "P": 0.0, "R": 0.0, "F1": 0.0, "AP50": 0.0, "AP50_95": 0.0,
                     "gt_boxes": 0, "count_mae": 0.0, "count_bias_pct": 0.0 },
    "e-scooter":   { "...": 0 }
    // …all 9…
  },
  "confusion_matrix": [[/* 10×10 incl. background */]]
}
```

Store as `results/eval/<model_id>.json` (map cleanly onto the existing SQLite schema, or
extend it). Comparison view = the existing `generate_comparison_report()` once rows are
real; a candidate-vs-prod diff table is the practical form (gap G3 wires per-class P/R/F1
+ count fields into the record so the report can diff them).

---

## 4. Regression gates for promotion

A candidate promotes only if it clears **all** gates on the frozen held-out set (§1),
evaluated at **imgsz=480** (deployment size). "prod" = the model currently referenced by
`configs/sensor.yaml:ncnn_model_path`.

| Gate | Threshold |
|---|---|
| Overall mAP@50-95 | ≥ prod (no regression) |
| **Per-class F1 (any class)** | **must not drop > 2 pts** vs prod |
| **Minority classes** (cyclist, e-scooter, motorcyclist) | F1 **and** recall must not drop **at all**; prefer a strict improvement — weighted explicitly because a 2-pt slack on a rare class hides a large relative loss |
| Per-class count bias (§2b), minority classes | \|signed bias\| ≤ agreed % (e.g. 15 %) and no worse than prod |
| No new systematic confusion | cyclist↔motorcyclist↔e-scooter off-diagonal mass must not increase vs prod |
| Model size / params | ≤ prod + small margin (edge budget) |

Notes:
- Overall mAP passing while a minority class regresses is the failure mode these gates
  exist to catch — the minority-class rows are hard gates, not advisory.
- If a rare class has too few held-out boxes to be significant, record it and gate on the
  count metric instead of AP for that class.
- Gates are computed candidate-vs-prod from two results JSONs (§3); automating this diff is
  gap G5.

---

## 5. Post-deploy sanity eval on-device

NCNN export can shift accuracy vs the PyTorch source (quantisation, imgsz, resize).
Two checks after export, before/at field deployment:

1. **NCNN-vs-PyTorch parity (new — gap G6).** Run the same **N images** (recommend the
   full frozen held-out set, or ≥ 200 images if time-boxed) through both the PyTorch
   `best.pt` and the exported NCNN model at imgsz=480. Compare:
   - per-class detection counts and mean confidence; flag any class whose detection count
     shifts > ~5 %;
   - box IoU agreement on matched detections.
   Purpose is *parity*, not re-scoring accuracy — a large divergence means the export is
   lossy and the eval-gate numbers (measured on PyTorch) don't hold for the deployed model.
2. **FPS threshold on Pi.** From the 30-min in-enclosure benchmark (training plan §5.3):
   **FPS ≥ 5 at imgsz=480** (`.planning/ROADMAP.md:39`) sustained, ambient ≥25 °C, with
   `vcgencmd get_throttled == 0x0` (`.planning/research/PITFALLS.md:24-32`,
   `REQUIREMENTS.md` EDGE-03). Below threshold or any throttle bit set → not deployable;
   drop target FPS in config or improve cooling.

---

## 6. Gap list (does NOT exist yet)

| # | Gap | Effort |
|---|---|---|
| G0 | **Frozen, stratified, hashed held-out test set** (§1) — today's test split is empty; val is reused SDL. Prerequisite for everything. | M |
| G1 | Real `model.val()` → results-JSON + SQLite writer (nothing populates `ExperimentLog` automatically today). | M |
| G2 | ~~Remove / hard-fail the fabricating dummy paths in `model_comparison_framework.py`~~ **DONE (2026-07-10)** — dummy model + random-FPS paths removed; failures return `None` and are skipped, never fabricated. | S |
| G3 | Extend per-class record to P/R/F1/AP50/AP50-95 + confusion matrix + real `dataset_hash` (currently per-class mAP only + free-text version). | M |
| G4 | Per-class **count-error** metric over annotated clips through detect→track→count (the deliverable-relevant metric; box mAP alone is insufficient). | L |
| G5 | Automated candidate-vs-prod regression-gate diff (§4) returning pass/fail. | M |
| G6 | NCNN-vs-PyTorch parity harness (§5.1). | M |
| G7 | Condition tagging (day/night/rain) on the held-out set for sliced metrics — depends on data availability. | S–M |
