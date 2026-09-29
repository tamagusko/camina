# Training

Build a dataset, train YOLO26n, and compare models the way the sensor runs them.
The plan and the experiments are in [`PLAN.md`](PLAN.md); the metrics in
[`EVALUATION.md`](EVALUATION.md).

## Environment (GPU)

```bash
uv venv -p 3.12 .venv-train
uv pip install --python .venv-train/bin/python -r training/requirements.txt
```

## Train and compare

Two modes. **dev** trains on train, early-stops on val: use it to compare experiments.
**final** retrains the chosen experiment on train + val for the dev run's best epoch
count, validation off: that is the model for the Pi. Test is never used for either.

```bash
# 1. Dev runs (runs/datasets/<name>, runs/train/<name>)
.venv-train/bin/python -m training.train --experiment training/experiments/yolo26n_tra2026.yaml
.venv-train/bin/python -m training.train --experiment training/experiments/yolo26n_tra2026_synthetic.yaml

# 2. Compare on test: held-out AP, count error on the hand-counted clips, NCNN speed
.venv-train/bin/python -m training.evaluate runs/train/yolo26n_tra2026 \
    runs/train/yolo26n_tra2026_synthetic models/camina_v1_yolo11n_ncnn_model

# 3. Final model of the chosen experiment (runs/train/<name>_final), then evaluate it too
.venv-train/bin/python -m training.train --experiment training/experiments/yolo26n_tra2026.yaml --final
```

The base configuration is `configs/yolo26n.yaml` (each choice commented); an experiment in
`experiments/` names its data and overrides only what it must. Synthetic data goes in
`data/synthetic/` (YOLO format: `data.yaml`, `images/`, `labels/`).

## Tools

| Tool | What it does |
|---|---|
| `build_dataset` | `--prepare`: download → the split `dataset/` (once). Otherwise: one experiment's dataset (+ synthetic, or `--final`) |
| `train` | Train one experiment; records config, versions, GPU, git commit, dataset |
| `evaluate` | Compare runs and NCNN models: AP, count error, speed |
| `count_eval` | Count error of one model on one hand-counted clip |
| `export_ncnn` | Reproducible NCNN export of the committed models (pinned pnnx) |
| `download_tra2026` | Download the TRA 2026 dataset from Roboflow (`ROBOFLOW_API_KEY`) |
| `validate_labels` | Check every label: class in the taxonomy, box in bounds |
| `autolabel` | Pre-label new images for Roboflow (below) |
| `codex_check` | Check each pre-label's class with Codex; split images into flagged / ok (below) |
| `apply_audit` | Apply the audit page's decisions: corrected labels locally, then (`--push`) to Roboflow with tags |
| `sam2_clip_auto_labeling.py`, `dinov3_semi_auto_labeling.py` | Experimental pre-labelling; unverified |

## Pre-labelling new images

Rules: `docs/labelling_guide/`. Every box is still reviewed by a person in Roboflow.

```bash
# 1. YOLO26x (COCO) + rider rule; SAM 3 relabels van / e-scooter if weights/sam3.pt
#    exists (gated: accept the licence at huggingface.co/facebook/sam3, then download).
#    --existing keeps labels already in hand. GPU env.
.venv-train/bin/python -m training.autolabel --images <dir> --out data/autolabel/<name> \
    --model weights/yolo26x.pt [--existing <labels dir>] [--imgsz 1280 for camera frames]
# 2. Codex (your `codex login`, model gpt-6-astra) classifies a crop of each box; resumable
.venv/bin/python -m training.codex_check --run data/autolabel/<name>
# 3. Upload data/autolabel/<name>/review/flagged, then review/ok, as two Roboflow batches
```

Crops go to OpenAI in step 2. For camera images, leave person-carrying classes out of
`--classes` until GDPR and the camera terms are settled.

## Label audit

The TRA 2026 vehicle labels were checked by two models; many SUV labels are wrong. How to review
the disputed boxes and push the fixes to Roboflow: [`AUDIT.md`](AUDIT.md).

## Data

- `dataset/` — the TRA 2026 dataset (Roboflow `sdl-urban-mobility-dataset` v3): 1,837
  images, all nine classes, split train / val / test (stratified, whole video sequences).
  `split.json` records how, with a hash of every test image and label.
- `test_images/` — 10 images for the detector's parity test.
