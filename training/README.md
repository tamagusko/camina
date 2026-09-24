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

```bash
# 1. Train (builds runs/datasets/<name>, trains into runs/train/<name>)
.venv-train/bin/python -m training.train --experiment training/experiments/yolo26n_real.yaml
.venv-train/bin/python -m training.train --experiment training/experiments/yolo26n_real_synthetic.yaml

# 2. Compare: held-out AP, count error on the hand-counted clips, NCNN speed
.venv-train/bin/python -m training.evaluate runs/train/yolo26n_real \
    runs/train/yolo26n_real_synthetic models/camina_v1_yolo11n_ncnn_model
```

The base configuration is `configs/yolo26n.yaml` (each choice commented); an experiment in
`experiments/` names its data and overrides only what it must. Synthetic data goes in
`data/synthetic/` (YOLO format: `data.yaml`, `images/`, `labels/`).

## Tools

| Tool | What it does |
|---|---|
| `build_dataset` | Real (+ synthetic) → one dataset: canonical ids, frozen test split, manifest |
| `train` | Train one experiment; records config, versions, GPU, git commit, dataset |
| `evaluate` | Compare runs and NCNN models: AP, count error, speed |
| `count_eval` | Count error of one model on one hand-counted clip |
| `export_ncnn` | Reproducible NCNN export of the committed models (pinned pnnx) |
| `validate_labels`, `freeze_holdout`, `convert_sdl_to_yolo11` | Dataset checks and preparation |
| `sam2_clip_auto_labeling.py`, `dinov3_semi_auto_labeling.py` | Experimental pre-labelling; unverified |

## Data

- `dataset/` — 1,296 real images; six classes labelled (see `PLAN.md`).
- `holdout_manifest.json` — the 192 held-out test images, by hash.
- `SDL fine-tuned_v3-cyclist_cleaned.zip` — the source SDL export
  ([also on Google Drive](https://drive.google.com/file/d/1eDvrytc2s8MLZqQcImVsSXQq6n2rajhW/view?usp=drive_link)).
- `test_images/` — 10 images for the detector's parity test.
