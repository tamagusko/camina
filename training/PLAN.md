# Training plan

How a new detector is trained, compared and promoted to the Pi. Commands are in
[`README.md`](README.md); what "better" means is in [`EVALUATION.md`](EVALUATION.md).

## Where the data stands (2026-09-25)

- `dataset/` has 1,296 real images. Only six classes are labelled: person, cyclist, car,
  motorcyclist, bus, truck. **e-scooter, SUV and delivery_van have no labels.** The
  paper model (CAMINAv1) got them from YOLO-World pseudo-labels in a Roboflow export that
  is not in the repo.
- 192 images are the frozen held-out test set (`holdout_manifest.json`); `build_dataset`
  keeps them out of training in every experiment.
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
3. **Evaluate** (`evaluate`): every model as the Pi runs it (FP16 NCNN, 640), on the same
   held-out images and the same hand-counted clips; per-class AP50, mAP50-95, count error
   per class and direction (S7), NCNN speed.

## Experiments

| Experiment | Train data | Question |
|---|---|---|
| `yolo26n_real` | real only | Baseline: YOLO26n on what we have |
| `yolo26n_real_synthetic` | real + synthetic (≤ 1× real) | Does synthetic data add the missing classes and help the rest? |

They differ **only in training data**: same base config, seed, validation and test
images. Put the synthetic dataset (YOLO format, class names mapped in
`configs/class_mapping.yaml`) at `data/synthetic/`.

**Caveats for reading the results**

- The real test set has no e-scooter, SUV or delivery_van, so AP says nothing about
  them; only the hand-counted clips do (`videos/test.counts.csv` has SUVs and vans).
  A small, real, hand-labelled test set for these three classes is the missing piece.
- CAMINAv1 was trained on these same 1,296 images, held-out ones included: its held-out AP
  is not comparable (the evaluator skips it). Compare it on the clips only.

## Promotion to the Pi

A candidate replaces CAMINAv1 only when, in order:

1. **Evaluation:** per-class count error on every hand-counted clip no worse than the
   current model, and S7 passing; held-out AP no worse for the six real classes.
2. **Export:** FP16 NCNN at 640 (the evaluator's export, smoke-tested). Class names must map
   onto the canonical nine through `configs/class_mapping.yaml`; the order is free.
3. **Pi benchmark (S6):** 30 minutes in the enclosure, ambient ≥ 25 °C, Active Cooler on:
   ≥ 5 FPS at 640 and `vcgencmd get_throttled` = `0x0`.
4. **Record:** copy the NCNN directory to `models/<name>_fp16_ncnn_model/` with a
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
