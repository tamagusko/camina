# CAMINAv1 — YOLO11n NCNN (TRA 2026 model)

- **Source:** `origin/TRA2026` @ `7aaf3fc`, `model/raspberry_pi_deployment_all/yolo11n_ncnn/` (copied 2026-09-15, PLAN.md S1). `model_ncnn.py` was not copied; Ultralytics only needs `metadata.yaml`, `model.ncnn.param` and `model.ncnn.bin`.
- **`model.ncnn.bin` SHA-256:** `fc1aa20c2ab4a3ba920fdce8eadf64291425215067b453c3ddee1ecf13636fa0`
- **Export:** Ultralytics 8.3.200, 2025-09-25, imgsz 640×640, batch 1, FP32. Run it at `imgsz: 640` only; `detect_track.py` refuses any other size.
- **Training:** YOLO11n, 150 epochs, on `datasetV3_stratified` (not in this repo; the paper's Roboflow v3 export). Training log on the same branch (`model/yolo_comparison/YOLO11n/train/results.csv`): best mAP50 0.571 (epoch 136), last 0.549. The paper reports 0.563; no per-class validation artefact exists.
- **Class order:** alphabetical as exported (`SUV, bus, car, cyclist, delivery_van, e-scooter, motorcycle, person, truck`). `detect_track.py` maps each name to the canonical order in `configs/classes.yaml` through `custom_model_train/class_mapping.yaml` (`motorcycle` → `motorcyclist`).

## Precision, and how to build the FP16 sibling

This export is **FP32** (`metadata.yaml: args.half: false`). An FP16 export of
the same weights halves the `.bin` — useful on a memory-constrained board, and
free to take on any Pi — and lives beside this one as
`models/camina_v1_yolo11n_fp16_ncnn_model/`:

```bash
uv run python -m src.utils.export_ncnn \
    --source <camina_v1 weights>.pt --imgsz 640 --half
```

**Blocker: the `.pt` that produced this export is not in the repository.** It is
not in `models/`, and not on `origin/TRA2026` (searched 2026-09-22 — that branch
carries only NCNN artefacts). NCNN cannot be converted back to PyTorch, and
converting an existing FP32 `.bin` to FP16 in place needs `ncnnoptimize`, which
is not in the `ncnn` Python wheel. So the FP16 artefact cannot be produced from
anything currently under version control.

To unblock, recover `best.pt` from wherever CAMINAv1 was trained (the training
run's `runs/*/weights/`, per `metadata.yaml` originally
`/home/tiago/repos/camina/data/datasetV3_stratified/`), commit it with a
`models/<stem>.meta.yaml` sidecar (`imgsz: 640`, `canonical: true`), and run the
command above. Until then this FP32 export is the only runnable artefact — and
the only copy of the model the paper reports, which is a reproducibility risk
worth closing regardless of FP16.
