# STATE
Version: 2.1 — 2026-09-15 — decisions D1–D13 recorded; 2.0 superseded old/2026-09-15-gsd/STATE.md
Last verified: 2026-09-15 (audit: audit-2026-09-15/AUDIT.md)

## Current stage
M1 / S1 — Paper model on main. Not started.

## Verified working (dev host, 2026-09-15)
- Edge: 144 pytest green; tracker → counter → daily → offline buffer → HTTPS publisher chain runs on tests/test.mov; payloads accepted by dashboard zod.
- Dashboard: 89 vitest (after generating data/mock fixtures), tsc clean, mock build green (28 routes).
- systemd unit: Type=notify + WatchdogSec=300 + time-sync gate (never run on a Pi).
- LoRa codec Python↔TS parity (not wired to the daemon).

## Blockers (in order)
1. No loadable 9-class model on main (dry-run exits 1). Paper's NCNN model is on origin/TRA2026 — S1.
2. Live read path is a stub (streets-live.ts) and nothing provisions sensors/tokens — S4.
3. Config handshake dead (routes echo client version) — S3.
4. No CI — S2.
5. No Pi run, benchmark, soak or field evidence exists — S6/S8/S9.
6. Ethics/DPO + site + enclosure for a real street — S8 (start now; longest lead time).
7. UCD Google OAuth app does not exist; required before the first live deploy (D6) — S5 (request now).
8. No speed producer and no calibration method or reference speed source — S7b (D2).

## Missed / re-baselined
- TRL-6 target 2026-05-31: missed (no field unit). M1 target re-baselined to 2026-12-31 (D12, decided 2026-09-15).
- Slides roadmap Apr/May/Jun/Sep 2026: none met. Fleet re-baselined to 5–10 units in M2 (D4).

## Decisions (2026-09-15, PLAN.md §3)
D1 LoRa → M2 optional · D2 speed → implement (S7b) · D3 → screenline + direction · D4 → M2 = 5–10 units · D5 → full admin console (S11) · D6 → OAuth before first deploy (S5) · D7 → publish BOM · D8 → Dublin; dataset merge with Roboflow v3 reference · D9 → DPIA-lite + statement + signage · D10 → SD card · D11 → REALLOCATE (EU grant 101103924) · D12 → 2026-12-31 · D13 → fix in next paper.
Closed items: PLAN.md §4.

## Next action
- S1: copy origin/TRA2026 yolo11n_ncnn to models/, name-based class remap in detect_track.py, imgsz 640, ncnn in requirements → `scripts/run_sensor.py --dry-run` exits 0.
- This week, in parallel: contact UCD DPO/ethics, identify a host site, file the UCD Google OAuth app request.
