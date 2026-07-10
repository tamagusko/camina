# CAMINAv1 Training Plan

Working doc for retraining the fine-tuned 9-class YOLO11 detector ("CAMINAv1") on a
larger dataset and promoting a candidate to the Pi 5 NCNN deployment slot.

**Scope:** off-Pi training → held-out eval gate (see `docs/evaluation_plan.md`) →
NCNN export → in-enclosure Pi benchmark → versioned model dir. Mostly orchestration
of scripts that already exist; genuine gaps are flagged in §7.

---

## 0. Taxonomy reconciliation — DONE (2026-07-10)

The four conflicting class taxonomies have been reconciled onto **one canonical
9-class taxonomy** with an explicit, enforced mapping layer. A retrain is no longer
blocked on taxonomy; what remains is dataset relabel/verification (§0.3).

### 0.1 Canonical taxonomy (single source of truth)

`configs/classes.yaml` is now the SSOT. It carries the exact set and order the whole
system publishes — the same nine the dashboard ships (`dashboard/src/lib/types.ts`
`ROAD_USER_CLASSES`), the daemon enforces (`configs/sensor.yaml` `classes`,
`src/camina/service/detect_track.py`), the LoRa 9-count codec uses, and the export guard
(`src/utils/export_ncnn.py`) checks:

```
0 person   1 cyclist   2 car   3 e-scooter   4 SUV
5 motorcyclist   6 bus   7 delivery_van   8 truck
```

`configs/classes.yaml` stays a flat `int: name` map (consumed unchanged by
`src/camina/utils/config.py:load_classes`). **Do not reorder or rename** — the index is a
wire contract.

### 0.2 What each of the four legs was, and how it is now reconciled

| Leg (was) | Verified location | Reconciliation |
|---|---|---|
| Runtime 9-class @ 480 | `configs/sensor.yaml:13-22,31`; `detect_track.py:49-50,74-77` | Adopted as canonical. Unchanged. |
| Toolchain 9-class, different names/order (`pedestrian`, `motorcycle`, order ped,cyc,car,moto,bus,truck,escooter,suv,van) | `convert_sdl_to_yolo11.py`, `train_yolo11n.py:111`, `model_comparison_framework.py`, `evaluation_logging_system.py:49-57` | Now consume the SSOT + an **alias table** (`custom_model_train/class_mapping.yaml`) via `custom_model_train/scripts/class_taxonomy.py`. `pedestrian`→`person`, `motorcycle`→`motorcyclist`; converter emits canonical order; the comparison per-class mAP is now indexed by canonical order. |
| Deployed weights 6-class @ 640 | `models/20250629_warmup_best_ncnn_model/metadata.yaml`; old `configs/classes.yaml` | Documented as **legacy** in a provenance sidecar `models/20250629_warmup_best.meta.yaml` (6 classes; can express only `person, cyclist, car, motorcyclist, bus, truck`; **missing** `e-scooter, SUV, delivery_van`). It fails the new export guard by design. |
| `scripts/train/*.yaml` @ 640, 6-class cyclist datasets | `scripts/train/train_param_warmup.yaml`, `train_param_finetune.yaml` | Left as the two-stage warm-up→fine-tune *pattern*; their `data:` paths still point at old cyclist datasets and must be repointed at the canonical `data.yaml` before use (§0.3). The fuller trainer is `custom_model_train/scripts/train_yolo11n.py`. |

### 0.3 Mapping mechanism (how toolchain names reach canonical)

- **`custom_model_train/class_mapping.yaml`** — a checked-in `label-name -> canonical-name`
  table. It lists the two real aliases (`pedestrian`, `motorcycle`) plus an identity entry
  for every canonical name, so an unknown/typo'd label is **rejected**, never silently
  passed through.
- **`custom_model_train/scripts/class_taxonomy.py`** — the loader. `load_canonical_classes()`,
  `load_class_aliases()`, `resolve_to_canonical()` (raises `TaxonomyError` on any unmapped
  name), and `assert_canonical_taxonomy()` (raises with a missing/extra/misordered diff).
  Consumed by the converter, the trainer's dataset validation, and the comparison framework.
- **`src/utils/export_ncnn.py`** reads the same two YAML files independently (kept decoupled
  from the training-only package) and, after export, resolves the model's `names` through the
  alias table and refuses export unless they equal the canonical list — with a clear diff.

### 0.4 imgsz contract

**Deployment/export imgsz = 480** is the one value carried through: training config → export
→ runtime. Training may run at a larger `imgsz` (640) for accuracy, but **promotion eval and
the exported NCNN must use 480** (deployment size; `configs/sensor.yaml:31`,
`detect_track.py` default, `export_ncnn.py --imgsz` default). Never benchmark accuracy at 640
and deploy at 480 without a validation pass at 480 (§4, §5; gap G10).

Enforcement: each weights file gets a provenance sidecar `models/<stem>.meta.yaml` recording
`train_imgsz`, the deployment `imgsz`, `canonical` (bool), and the classes it provides.
`export_ncnn.py` validates `--imgsz` against the sidecar's `imgsz`: for a **canonical** model a
mismatch **fails**; for a **legacy** model or a missing/`unknown` size it **warns** (the true
size can't be verified). The legacy sidecar records the verified 640 from the NCNN metadata.

### 0.5 What still remains before a retrain can start

Taxonomy is no longer the blocker. Steps 1, 3, and 4 are **DONE (2026-07-10)** — the
machine-executable prerequisites are complete. **Step 2 (relabel the three v2 classes +
human QA gate) is the single remaining blocker** for a full 9-class retrain.

1. **Repoint dataset configs — DONE (2026-07-10).** Unzipped `custom_model_train/SDL
   fine-tuned_v3-cyclist_cleaned.zip` (Roboflow YOLO export: `nc: 6`, `bus, car, cyclist,
   motorcycle, person, truck`; 1224 train + 72 test pairs) into `custom_model_train/datasets/`
   (gitignored). Ran `convert_sdl_to_yolo11.py` → canonical 9-class dataset at
   `custom_model_train/datasets/camina_v1_9class/` with `data.yaml` (`nc: 9`, canonical
   names/order from `configs/classes.yaml`). Repointed `scripts/train/train_param_warmup.yaml`
   and `train_param_finetune.yaml` `data:` at the new `data.yaml`.

   Per-class box counts (whole dataset, 1296 label files): `person 7361 · cyclist 1761 ·
   car 2116 · e-scooter 0 · SUV 0 · motorcyclist 445 · bus 309 · delivery_van 0 · truck 297`.
   The six SDL classes populate canonical ids **0, 1, 2, 5, 6, 8**; the three v2 classes
   (canonical ids **3 e-scooter, 4 SUV, 7 delivery_van**) are legitimately empty until step 2.
2. **Relabel the three v2 classes** — `e-scooter` (id 3), `SUV` (id 4), `delivery_van` (id 7)
   are unlabelled in the SDL source (confirmed empty above). **This is the single remaining
   blocker** and the bulk of the work (§2, gap G7): manual seed labelling → assisted SAM2+CLIP
   proposal → **mandatory human QA gate** → per-class accept/reject counts logged against the
   dataset version. Explicitly out of scope for the machine-executable prerequisite pass.
3. **Verify labels — DONE (2026-07-10).** New headless data-time guard
   `custom_model_train/scripts/validate_labels.py` (gap G2): asserts every label's
   class-id ∈ [0, 8], coords ∈ [0, 1], and `data.yaml:names` resolves exactly onto the
   canonical set via `class_taxonomy`; exits non-zero with a per-file report on violation.
   Run on `camina_v1_9class` → **PASS** (exit 0, 1296 files). Covered by
   `tests/test_validate_labels.py` (pass + each violation class).
4. **Frozen held-out set — DONE (2026-07-10).** New `custom_model_train/scripts/freeze_holdout.py`
   (`docs/evaluation_plan.md §1`): deterministic (seed 42) class-presence-stratified carve,
   default 15%. Materialised **192/1296** images into `images/test` + `labels/test` (train
   1043 / val 61 / test 192) and wrote the TRACKED proof-of-freeze manifest
   `custom_model_train/holdout_manifest.json` (relative paths + SHA-256 of every image+label +
   `manifest_sha256 = d67d261de9bf7d67a2d78122b82ff54b5183628fd65a3de205b763440216e257`).
   Idempotent (pool = train+val+test each run); covered by `tests/test_freeze_holdout.py`
   (same seed → same manifest hash).

Until a canonical 9-class model is trained and promoted, **the daemon cannot run**:
`detect_track.py:74-77` raises `ValueError` unless the loaded model's `names` equal the
canonical 9 in order, and the deployed 6-class NCNN does not.

---

## 1. Data pipeline

### Dataset layout (YOLO11 standard, produced by the converter)

```
<dataset_root>/
├── data.yaml               # path, train, val, test, nc: 9, names: {0..8}
├── classes.txt
├── images/{train,val,test}/*.jpg
└── labels/{train,val,test}/*.txt   # "class cx cy w h" normalised, e.g. 1 0.5123 0.4876 0.104 0.221
```

`convert_sdl_to_yolo11.py:155-170` (`create_data_yaml`) writes this structure. Current
`all_camina_classes/` is a 10-image COCO smoke sample; the real SDL source is a Google-
Drive zip (`custom_model_train/data.md`, `custom_model_train/SDL fine-tuned_v3-cyclist_cleaned.zip`).

### Ingesting new labelled data

| Step | Tool | Notes |
|---|---|---|
| Convert SDL / Roboflow exports to 9-class YOLO | `custom_model_train/scripts/convert_sdl_to_yolo11.py` | Remaps 6 SDL ids → 9-class schema (`:26-33`). Only classes 0-5 are populated; 6-8 come from labelling (§2). **Fix taxonomy first (§0).** |
| Strip Roboflow hash suffixes from filenames | `scripts/data_processing/rename_data.py` | `filename_jpg.rf.<hash>.txt` → `filename.txt` |
| Drop / reindex an unwanted class | `scripts/data_processing/remove_class.py` | Shifts remaining class indices down |
| Class-count / distribution audit | `scripts/data_processing/analyze_data.py` | Counts labels per class from a `data.yaml` |
| Build synthetic-cyclist labels from COCO | `scripts/data_processing/coco_to_cyclist.py` | The original cyclist-class construction (person∩bicycle, IoU≥0.3) |

### Validation

- `scripts/data_processing/validate_yolo_labels.py` — **interactive** cv2 viewer only
  (`cv2.imshow`, `:79`). Not headless; does **not** assert class-id range or coordinate
  bounds. Use for spot QA, **not** CI. A headless validator is a gap (§7, G1).
- **Class-taxonomy guard at data time:** none exists. `export_ncnn.py` guards only at
  export. Add a pre-train check that every label's class-id ∈ [0, 8] and that
  `data.yaml:names` equals the canonical taxonomy from §0 (gap §7, G2).

---

## 2. Labelling assumptions

Classes 0-5 arrive already labelled (SDL / COCO). The three v2 classes
(`e-scooter`, `SUV`, `delivery_van`) need new annotation. Two assisted labelers exist but
are **prototype-grade**:

| Labeler | Path | State |
|---|---|---|
| DINOv3 semi-auto | `custom_model_train/scripts/dinov3_semi_auto_labeling.py` | Sliding-window + **aspect-ratio heuristics** for class (`:211-233`); dummy model fallback (`:88-100`). Suggestions only — not production labels. |
| SAM2 + CLIP | `custom_model_train/scripts/sam2_clip_auto_labeling.py` | SAM2 masks + CLIP text prompts (`:51-79`); random fallback if SAM2/CLIP absent (`:377-379`). Better than DINOv3 but unverified. |

Both target only ids 6/7/8 and emit YOLO `.txt` suggestions. Recommended workflow:

1. **Manual** labelling of a seed set per new class (Roboflow / Label Studio) — treat as
   ground truth for the assisted tools.
2. Run SAM2+CLIP over unlabelled frames to propose boxes for 6/7/8.
3. **QA sampling step (mandatory, human-in-the-loop):** review every auto-label for the
   three new classes and a random ≥10 % sample of converted 0-5 labels in the viewer
   (`validate_yolo_labels.py`). Reject the batch if the auto-labeler's precision on the
   sample is below an agreed floor (e.g. 0.9); the CLIP/DINO confidences are not
   calibrated, so a human gate is non-negotiable.
4. Log per-class accept/reject counts alongside the dataset version tag (§3).

---

## 3. Configuration & reproducibility

Current scripts capture **some** config but miss seeds, hashes, and env. Target per-run:

```
runs/train/<experiment>_<timestamp>/       # e.g. caminav1_20260710_1430  (YYYYMMDD_HHMM)
├── weights/{best,last}.pt
├── args.yaml                  # Ultralytics-emitted resolved args
├── training_summary.json      # train_yolo11n.py:278-305 (already written)
├── dataset_hash.txt           # NEW — sha256 of sorted label files + data.yaml
├── env.txt                    # NEW — uv pip freeze / python + torch + ultralytics
└── config.json                # train_yolo11n.py:149-194 (already written)
```

| Concern | Existing | Gap |
|---|---|---|
| Config capture | `train_yolo11n.py:149-194` dumps full hyperparams + aug config to `configs/<exp>_config.json` | — |
| Output naming `{experiment}_{timestamp}` | `train_yolo11n.py:76` uses `yolo11n_9class_<ts>` | Rename to `caminav1_<ts>` for clarity |
| **Seed pinning** | **None** — no `seed=` passed to `model.train()` | G3: pass `seed=42`, set `deterministic=True` |
| **Dataset hash / version** | Only a free-text `dataset_version` string (`evaluation_logging_system.py:33`) | G4: compute sha256 over sorted label set, record tag `caminav1-ds-vNN` |
| **Environment record** | Device only (`train_yolo11n.py:120-147`) | G5: `uv pip freeze > env.txt`, log python/torch/ultralytics/CUDA |
| Dependency management | No `pyproject.toml` / `uv.lock` at repo root; only `requirements.txt` | G6: adopt `uv` per project convention; pin |

---

## 4. Training

**Hardware:** training runs **off-Pi** (dev box GPU / MPS / cloud). The Pi 5 is
inference-only. `train_yolo11n.py:120-147` auto-selects cuda / mps / cpu and shrinks
batch accordingly.

### Recipe (recommended path: `custom_model_train/scripts/train_yolo11n.py`)

This is the fuller of the two trainers (validates 9-class schema, logs config, exports).
The alternative `scripts/train/fine_tune.py` is a thin YAML-driven wrapper
(`train_param_warmup.yaml` → `train_param_finetune.yaml`, warm-up→fine-tune two-stage)
still pointing at 6-class cyclist datasets — useful as the two-stage pattern, but its
YAMLs need repointing.

Hyperparameter surface (`train_yolo11n.py:37-66`), tuned for 9-class edge detection:

| Group | Values |
|---|---|
| Schedule | `epochs=100`, `patience=10`, `optimizer=AdamW`, `lr0=0.001`, `cos_lr=True`, `warmup_epochs=3`, `weight_decay=0.0005` |
| Batch / size | `batch=16` (auto-reduced on low VRAM/MPS/CPU), `imgsz=640` |
| Loss gains | `box=7.5`, `cls=0.5`, `dfl=1.5` |
| Aug | `mosaic=1.0`, `mixup=0.15`, `copy_paste=0.3`, `fliplr=0.5`, `scale=0.9`, `hsv_*` |

Command:
```bash
uv run python custom_model_train/scripts/train_yolo11n.py \
    --data <dataset_root>/data.yaml --epochs 100 --batch 16 --imgsz 640 \
    --project caminav1
```

**imgsz decision — resolve before promotion:** training default is 640; deployment runs
at 480 (`configs/sensor.yaml`, `export_ncnn.py`). Train at 640 for accuracy, but the
promotion eval and the exported NCNN **must** use imgsz=480 (§5) so eval reflects the
deployed model. Consider a final fine-tune / validation at 480 to close the train/deploy
gap. Do not benchmark accuracy at 640 and deploy at 480.

**Checkpointing:** `save_period=10` writes periodic checkpoints; `best.pt` / `last.pt`
under `weights/`. `--resume` continues from `last.pt`. For class imbalance on the three
minority classes, weight the eval (see evaluation plan §4) rather than over-sampling
blindly.

**Minority-class caution:** e-scooter / SUV / delivery_van will be rare. Track their
per-class recall from the first epoch; a high overall mAP driven by `car`/`person` can
mask near-zero minority recall (this is exactly what the count-level metric in the eval
plan guards against).

---

## 5. Promotion path

```
candidate best.pt
   │  (1) eval gate — docs/evaluation_plan.md §4 regression gates
   ▼
   │  (2) NCNN export  ── src/utils/export_ncnn.py --imgsz 480 --half
   ▼   (taxonomy guard + imgsz contract must PASS → confirms canonical 9-class + 480)
   │  (3) Pi smoke benchmark  ── 30-min in-enclosure, ambient ≥25 °C
   ▼
   │  (4) NCNN-vs-PyTorch parity check (eval plan §5)
   ▼
versioned model dir under models/<date>_caminav1_best_ncnn_model/
```

1. **Eval gate.** Candidate must clear the regression gates in `docs/evaluation_plan.md`
   on the frozen held-out set before anything else.
2. **NCNN export** via `src/utils/export_ncnn.py` (the one hardened, tested export path):
   ```bash
   uv run python -m src.utils.export_ncnn --source models/<date>_caminav1_best.pt --imgsz 480 --half
   ```
   - `imgsz` **must be 480** to match `configs/sensor.yaml`. The export CLI enforces this
     against the candidate's `models/<stem>.meta.yaml` sidecar (`imgsz: 480`, `canonical:
     true`) — a mismatch fails for a canonical model (§0.4). (`train_yolo11n.py:342-358`
     also exports but defaults to 640 and to onnx/tflite/ncnn — **do not use it for the
     production NCNN artefact**; use `export_ncnn.py`.)
   - The canonical-taxonomy guard (`_verify_canonical_taxonomy`) is the promotion gate — it
     resolves the exported model's `names` through `custom_model_train/class_mapping.yaml`
     and passes only if they equal the canonical 9-class list in order (§0.3).
   - Idempotent: re-export needs `--force`.
3. **Pi smoke benchmark (blocker).** `.planning/STATE.md:61` and `REQUIREMENTS.md`
   EDGE-03 require a **30-minute sustained, in-enclosure** benchmark on Pi 5 8GB at
   **ambient ≥25 °C**, capturing FPS, CPU load, RSS, core temp, and
   `vcgencmd get_throttled`, documented in `docs/sensor_deployment.md`. Gate:
   **FPS ≥ 5 at imgsz=480** (`.planning/ROADMAP.md:39`) and `get_throttled == 0x0`.
   The Pi 5 Official Active Cooler is a documented prerequisite (EDGE-04;
   `.planning/research/PITFALLS.md:13-32` — throttling silently drops FPS 25-40 % and
   corrupts counts). Benchmark on a desk ≠ benchmark in the box.
4. **Parity check.** NCNN export can shift accuracy vs PyTorch — run the parity check in
   `docs/evaluation_plan.md §5` on N images before field deployment.
5. **Version + record.** Place the NCNN dir under `models/` with a dated name, update
   `configs/sensor.yaml:ncnn_model_path`, and record the model_id + dataset_hash + eval
   JSON (eval plan §3). Retire stale committed weights per `.planning/REQUIREMENTS.md`
   TECH-05.

---

## 6. What promotion touches vs what it must not

- Edit: `configs/sensor.yaml` (`ncnn_model_path`), `configs/classes.yaml` (once, §0),
  new `models/<date>_...` dir, eval-results JSON.
- Do **not** silently change `imgsz`, class order, or `conf_threshold` without a
  re-benchmark — the daemon, LoRa 9-count codec, and dashboard all assume the fixed
  9-class order and 480 input.

---

## 7. Gap list (does NOT exist yet)

| # | Gap | Effort |
|---|---|---|
| **G0** | **Canonical taxonomy not defined once** — 4 conflicting lists; export guard rejects both current and toolchain models (§0). Highest priority. | **M** |
| G1 | Headless label validator (class-id range, coord bounds, image/label pairing, empty-file policy) for CI. Current one is an interactive viewer. | S |
| G2 | Data-time taxonomy guard: assert `data.yaml:names` == canonical list before training. | S |
| G3 | Seed pinning + `deterministic=True` in the trainer. | S |
| G4 | Dataset hashing + version tag (`sha256` over sorted labels + `data.yaml`). | S |
| G5 | Environment capture per run (`uv pip freeze`, python/torch/ultralytics/CUDA). | S |
| G6 | Adopt `uv` with `pyproject.toml` + `uv.lock` at repo root (only `requirements.txt` today). | M |
| G7 | Real annotation of e-scooter / SUV / delivery_van; the assisted labelers are prototypes (heuristic/random fallbacks). Bulk of the effort in a v2 retrain. | **L** |
| G8 | Automatic write of val metrics into the experiment DB (nothing populates `ExperimentLog` from a real `model.val()` run today — see eval plan §3). | M |
| G9 | Single promotion script tying eval-gate → export → parity → version bump (currently manual steps). | M |
| G10 | Resolve train@640 / deploy@480 (final fine-tune or validation at 480). | S |
