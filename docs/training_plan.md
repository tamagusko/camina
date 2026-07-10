# CAMINAv1 Training Plan

Working doc for retraining the fine-tuned 9-class YOLO11 detector ("CAMINAv1") on a
larger dataset and promoting a candidate to the Pi 5 NCNN deployment slot.

**Scope:** off-Pi training → held-out eval gate (see `docs/evaluation_plan.md`) →
NCNN export → in-enclosure Pi benchmark → versioned model dir. Mostly orchestration
of scripts that already exist; genuine gaps are flagged in §7.

---

## 0. Blocking issue before any retraining: taxonomy is not defined once

Four different class taxonomies exist in the repo. They do **not** agree. This must be
resolved before a retrain, because the export guard will reject a mismatched model.

| Source | # | Order / names |
|---|---|---|
| **Edge runtime contract** — `configs/sensor.yaml` (`classes:`) + `src/utils/export_ncnn.py:42-52` (`CAMINAV1_CLASSES`) | 9 | `person, cyclist, car, e-scooter, SUV, motorcyclist, bus, delivery_van, truck` |
| **Deployed weights** — `models/20250629_warmup_best_ncnn_model/metadata.yaml` + `configs/classes.yaml` | 6 | `bus, car, cyclist, motorcycle, person, truck` (indices 0-5) |
| **Training toolchain** — `custom_model_train/scripts/convert_sdl_to_yolo11.py:36-46`, `train_yolo11n.py:111`, `evaluation_logging_system.py:49-57` | 9 | `pedestrian, cyclist, car, motorcycle, bus, truck, e-scooter, SUV, delivery_van` |

Consequences:
- The shipped model is **6-class**, not 9. e-scooter / SUV / delivery_van were never
  trained — `docs/MODELS.md:99-105` lists them as "CAMINAv2 roadmap".
- The deployed NCNN was exported at **imgsz 640** (`metadata.yaml`), but the runtime
  declares `imgsz: 480` (`configs/sensor.yaml`) and `export_ncnn.py:128-133` defaults to 480.
- `export_ncnn.py:102-105` asserts the exported model's `names` equal `CAMINAV1_CLASSES`
  **in order**. A model produced by `custom_model_train/` uses different names
  (`pedestrian`≠`person`, `motorcycle`≠`motorcyclist`) and a different order, so the guard
  would exit non-zero. It would also reject today's 6-class model.

**Action (must precede retrain):** pick one canonical 9-class taxonomy — recommend the
runtime contract (`sensor.yaml` / `CAMINAV1_CLASSES`) since the daemon, LoRa codec, and
dashboard already key off it — then:
1. rewrite `configs/classes.yaml` to the canonical 9-class list;
2. align `convert_sdl_to_yolo11.py` `new_classes` and its `class_mapping` to it
   (note `person`→`person` not `pedestrian`; `motorcycle`→`motorcyclist`);
3. align the per-class field order in `evaluation_logging_system.py` /
   `model_comparison_framework.py`.

Effort to reconcile: **M**. Everything below assumes the canonical list is fixed first.

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
   ▼   (taxonomy guard :102-105 must PASS → confirms canonical 9-class order)
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
   - `imgsz` **must be 480** to match `configs/sensor.yaml`. (`train_yolo11n.py:342-358`
     also exports but defaults to 640 and to onnx/tflite/ncnn — **do not use it for the
     production NCNN artefact**; use `export_ncnn.py`.)
   - The class-taxonomy assertion (`:102-105`) is the promotion guard — a pass proves the
     candidate carries the canonical 9-class names in order.
   - Idempotent: re-export needs `--force` (`:75-80`).
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
