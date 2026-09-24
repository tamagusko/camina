# Training

Tools to build the dataset, train YOLO11n and export the NCNN model the sensor runs.
Run them from the repo root, with the dev environment (`requirements.txt`).

| Tool | What it does |
|---|---|
| `python -m training.convert_sdl_to_yolo11 --sdl-dataset <dir> --output <dir>` | Convert the SDL export to YOLO format with canonical class names |
| `python -m training.validate_labels --data <data.yaml>` | Check every label: class in the taxonomy, box in bounds |
| `python -m training.freeze_holdout --data <data.yaml>` | Freeze a stratified held-out test set (`holdout_manifest.json`) |
| `python -m training.train_yolo11n --data <data.yaml>` | Train YOLO11n |
| `python -m training.export_ncnn --source <weights>` | Export to NCNN (`models/<stem>_ncnn_model/`), smoke-tested |
| `sam2_clip_auto_labeling.py`, `dinov3_semi_auto_labeling.py` | Experimental pre-labelling; unverified |

## Data

- `dataset/` — the 9-class training set (1,224 train, 72 val images), `data.yaml` inside.
- `SDL fine-tuned_v3-cyclist_cleaned.zip` — the source SDL export
  ([also on Google Drive](https://drive.google.com/file/d/1eDvrytc2s8MLZqQcImVsSXQq6n2rajhW/view?usp=drive_link)).
- `test_images/` — 10 images; the detector's parity test runs on them.
- Class names map to the canonical taxonomy through `configs/class_mapping.yaml`;
  the order is fixed by `configs/classes.yaml`.

## Export

Only pnnx **20250924** produces valid models; other versions build models that segfault.
Every export runs the model once and fails if it crashes. `models/*/PROVENANCE.md`
records how each committed model was made.

## Plan

[`PLAN.md`](PLAN.md): data audit, relabelling and the retraining plan (stage S13).
