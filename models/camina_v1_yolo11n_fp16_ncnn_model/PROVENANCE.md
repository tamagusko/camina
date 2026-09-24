# CAMINAv1 — YOLO11n NCNN, FP16 (TRA 2026 model)

The same network as `../camina_v1_yolo11n_ncnn_model/` (FP32) with weights
stored in half precision: `model.ncnn.bin` 5,351,980 B vs 10,503,980 B.
Built 2026-09-24.

## Source

- **Weights:** `origin/TRA2026` @ `7aaf3fc`,
  `model/yolo_comparison/YOLO11n/train/weights/best.torchscript`
  (SHA-256 `a0d8ff9e46d8ef6cc80517be2d0fecf015a5dc5b1d02d4d060a6dbb5866ff62a`).
  No `.pt` survives in any branch; this TorchScript is the intermediate of the
  FP32 export itself — its embedded metadata carries the same export stamp
  (`2025-09-25T22:03:35.355222`, Ultralytics 8.3.200, 640×640, same nine names).
- **Converter:** pnnx **20250924** (`pnnx-20250924-linux.zip` from
  github.com/pnnx/pnnx/releases; binary SHA-256
  `41357dd5c64297a0c6652364993e1e33034655b03087550e31188352ecd91dcf`).

## Command

```bash
cp <best.torchscript> camina_v1_yolo11n.torchscript   # the stem names the output dir
uv run python -m src.utils.export_ncnn \
    --source camina_v1_yolo11n.torchscript --pnnx <pnnx-20250924>/pnnx --out-dir models
```

`--half` is the default. The export ends with a forward pass in a child
process (`src/utils/pnnx_export.py:smoke_test`) and the canonical-taxonomy check.

## Verification (x86 dev host, ncnn 1.0.20260526)

| Check | Result |
|---|---|
| Same command with `--no-half` vs the committed FP32 model | `model.ncnn.bin`, `model.ncnn.param`, `metadata.yaml` **byte-identical** |
| Smoke test (random 640×640 input) | exit 0, output (13, 8400), all finite |
| Detections vs FP32 on `custom_model_train/test_images` (10 images, conf 0.3, imgsz 640) | 81 / 81 matched (IoU ≥ 0.5), **0 class changes**; box IoU min 0.9918, mean 0.9991; \|Δconf\| max 0.0198, mean 0.0027; no detection gained or lost |
| `model.ncnn.bin` SHA-256 | `e1d276b0d3af1aec46f06dab3b1fd333fdb35c9dc533e194286892afc0b0ff66` |

Not yet run on a Raspberry Pi (PLAN.md S6).

## Why pnnx 20250924 and not the one Ultralytics bundles

The pnnx bundled with the installed Ultralytics (8.3.123) and pnnx 20260526 both
emit a detection head that computes the anchor grid (one more `Split`, one fewer
`Reshape` and `MemoryData`; 67,200 B smaller = 8,400 anchors × 2 × float32).
Those models load but **segfault inside NCNN's forward pass** on
ncnn 1.0.20260526, at FP32 and FP16 alike. pnnx 20250924 and 20250912 reproduce
the shipped FP32 export byte for byte. The export smoke test rejects the
crashing builds.

## Which one to deploy

- **Pi 5 (Cortex-A76, ARMv8.2-A):** native FP16 arithmetic; NCNN already runs
  FP16 math there even from the FP32 file, so the gain is mainly size and load
  time.
- **Pi 4 (Cortex-A72, ARMv8.0-A):** no FP16 arithmetic; weights are stored in
  FP16 and computed in FP32 — smaller and less memory traffic, not faster math.

Switch by pointing `configs/sensor.yaml::ncnn_model_path` at this directory;
`imgsz` stays 640.
