# Training plan

How a new detector is trained, compared and promoted to the Pi. Commands are in
[`README.md`](README.md); what "better" means is in [`EVALUATION.md`](EVALUATION.md).

## Where the data stands (2026-09-25)

- **`training/dataset/`** — the TRA 2026 training set (Roboflow `sdl-urban-mobility-dataset`
  v3), the data CAMINAv1 was trained on: 1,837 images, all nine classes, canonical ids,
  already split (`split.json`). Thin classes: delivery_van 112 instances, truck 132,
  motorcyclist 307.
- Splits: train 1,488 / val 165 / test 184, **stratified by rarest class, whole video
  sequences at a time** (590 images are frames of 167 sequences; neighbouring frames in
  train and test would inflate every score). Every class is in every split; delivery_van
  and truck have 11 test instances each. Re-create only from a new download:
  `download_tra2026`, then `build_dataset --prepare data/tra2026 --out training/dataset`.
- `dev_expanded_dataset` (a branch) holds more data, unaudited: do not use it until audited.

## Pipeline

```
build_dataset ──▶ train ──▶ evaluate ──▶ promote
 real (+ synthetic)   YOLO26n    held-out AP, count error    NCNN FP16 640 on the Pi
```

1. **Build** (`build_dataset`): canonical class ids; held-out images → `test` only;
   synthetic images → `train` only. `manifest.json` records sources and class counts.
2. **Train** (`train`): one base config (`configs/yolo26n.yaml`), fixed seed, deterministic;
   `run.json` records parameters, git commit, library versions, GPU and the dataset
   manifest. Runs in the GPU environment (`requirements.txt` in this folder).
   - **dev** mode: train on train, early-stop on val; records the best epoch.
   - **final** mode (`--final`): the chosen experiment retrained on train + val for that
     many epochs, validation off. Same parameters as its dev run, or it refuses.
3. **Evaluate** (`evaluate`): every model as the Pi runs it (FP16 NCNN, 640), on the same
   held-out images and the same hand-counted clips; per-class AP50, mAP50-95, count error
   per class and direction (S7), NCNN speed.

## Experiments

| Experiment | Train data | Question |
|---|---|---|
| `yolo26n_tra2026` | TRA 2026 only | Baseline: YOLO26n on the paper's data |
| `yolo26n_tra2026_synthetic` | TRA 2026 + synthetic (≤ 1× real) | Does synthetic data help the thin classes (van, truck, motorcyclist) and the rest? |

They differ **only in training data**: same base config, seed, validation and test
images. Put the synthetic dataset (YOLO format, class names mapped in
`configs/class_mapping.yaml`) at `data/synthetic/`.

**Caveats for reading the results**

- Rare classes have few test instances (delivery_van 9, truck 14): their AP is noisy.
- CAMINAv1 was trained on the TRA 2026 images, held-out ones included: its held-out AP is
  not comparable (the evaluator skips it). Compare it on the clips only.

## Promotion to the Pi

A candidate replaces CAMINAv1 only when, in order:

1. **Evaluation:** per-class count error on every hand-counted clip no worse than the
   current model, and S7 passing; held-out AP no worse for the six real classes.
2. **Final model:** `--final` run of the chosen experiment, evaluated again on test and
   the clips (it should match or beat its dev run).
3. **Export:** FP16 NCNN at 640 (the evaluator's export, smoke-tested). Class names must map
   onto the canonical nine through `configs/class_mapping.yaml`; the order is free.
4. **Pi benchmark (S6):** 30 minutes in the enclosure, ambient ≥ 25 °C, Active Cooler on:
   ≥ 5 FPS at 640 and `vcgencmd get_throttled` = `0x0`.
5. **Record:** copy the NCNN directory to `models/<name>_fp16_ncnn_model/` with a
   `PROVENANCE.md` (run.json, evaluation JSON, dataset manifest), point
   `configs/sensor.yaml` at it, keep CAMINAv1 until the new model has run in the field.

Never change `imgsz` or the class list without re-running all of the above.

## Open gaps

| Gap | Why it matters |
|---|---|
| Real labels for e-scooter, SUV, delivery_van (train and test) | Synthetic data can train them; only real labels can test them |
| Audit of `dev_expanded_dataset` | More real data, currently unusable |
| More hand-counted clips, from the install views | One clip is one scene, one line |
| A smaller input (512, 480) tried on the Pi | Speed headroom, if 640 misses 5 FPS |
