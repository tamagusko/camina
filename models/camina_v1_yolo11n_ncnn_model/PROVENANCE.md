# CAMINAv1 — YOLO11n NCNN (TRA 2026 model)

- **Source:** `origin/TRA2026` @ `7aaf3fc`, `model/raspberry_pi_deployment_all/yolo11n_ncnn/` (copied 2026-09-15, PLAN.md S1). `model_ncnn.py` was not copied; Ultralytics only needs `metadata.yaml`, `model.ncnn.param` and `model.ncnn.bin`.
- **`model.ncnn.bin` SHA-256:** `fc1aa20c2ab4a3ba920fdce8eadf64291425215067b453c3ddee1ecf13636fa0`
- **Export:** Ultralytics 8.3.200, 2025-09-25, imgsz 640×640, batch 1, FP32. Run it at `imgsz: 640` only; `detect_track.py` refuses any other size.
- **Training:** YOLO11n, 150 epochs, on `datasetV3_stratified` (not in this repo; the paper's Roboflow v3 export). Training log on the same branch (`model/yolo_comparison/YOLO11n/train/results.csv`): best mAP50 0.571 (epoch 136), last 0.549. The paper reports 0.563; no per-class validation artefact exists.
- **Class order:** alphabetical as exported (`SUV, bus, car, cyclist, delivery_van, e-scooter, motorcycle, person, truck`). `detect_track.py` maps each name to the canonical order in `configs/classes.yaml` through `custom_model_train/class_mapping.yaml` (`motorcycle` → `motorcyclist`).
