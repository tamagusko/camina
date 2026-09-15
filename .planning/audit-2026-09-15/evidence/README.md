# Audit evidence (2026-09-15)

Small text artefacts from the 2026-09-15 code audit, copied here so PLAN.md done-tests can cite durable paths instead of the ephemeral scratchpad. Dev host: x86, Python 3.12 scratch venv, CPU torch (no Pi, no GPU). These are one-off audit probes run against the repo at that commit, not project code — do not import or execute them as part of the pipeline.

- `e2e_chain.py`, `e2e_chain_mov.py` — end-to-end probe scripts (camera stub → detect/track → counter → offline buffer → HTTPS publisher → dashboard mock ingest), run against `custom_model_train/test_video.mp4` and `tests/test.mov` respectively.
- `dryrun.log` — `scripts/run_sensor.py --dry-run` output showing the model/config class-taxonomy mismatch (exit 1).
- `ncnn_parity.log` — NCNN-vs-PyTorch detection-count parity at imgsz 640 (matches) vs imgsz 480 (300 dets/image, the max-detections cap).
- `e2e_out/captured_requests.json`, `e2e_out/results.json`, `e2e_out/lora_frame.json` — bodies captured from the `e2e_chain_mov.py` run and the round-tripped LoRa frame; `authorization: "Bearer tok"` / `"Bearer dev-token"` in these files are placeholder values from the scratch test config, not real credentials — verified by grep, no redaction needed.
- `dash-tests/zz-edge-contract.test.ts` — scratch-only Vitest contract test that fed the captured edge request bodies through the dashboard's zod schemas (8/8 passed).
