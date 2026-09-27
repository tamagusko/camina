# STATE
Version: 2.4 — 2026-09-27 — live data layer, CI, direction end to end, dashboard redesign,
tracker occlusion rules (PR feat/dashboard-live → dev)
Last verified: 2026-09-27. The 2026-09-15 audit folder was removed from the tree; it is in git
history (`git show 594756c:.planning/audit-2026-09-15/AUDIT.md`).

## Current stage
M1 / S1 — **done** 2026-09-24 (#21). On `feat/dashboard-live` (2026-09-27), awaiting merge:
- **S2** CI workflow (`.github/workflows/ci.yml`: Python + dashboard) — written; first green run
  on GitHub is the done-test.
- **S3** config handshake — done: ingest acks carry the server's config version; the device
  fetches, applies and persists it (`state.config.json`) and restores it on start.
- **S4** live data path — done **locally** (PostGIS in Docker): migrations 0000–0003,
  `streets-live.ts`, `provision-sensor.ts`, `db:seed`, 10-day backfill, replay of a synthetic
  week (`scripts/make_test_payloads.py` + `replay_payloads.py`) matches an independent
  recomputation; privacy regression runs against the live adapter. Neon itself: not yet (S5).
- **S7** direction published end to end (payload schema 1.1, DB, API, panel). Hand count of
  `videos/test.mov` exists; count error on it: summed |error| 11 over 30 crossings, S7 FAIL
  (car BA +6, delivery van −2).
- Dashboard redesign (two design rounds + independent gates) and complementary privacy
  suppression at the 15-min cell (`dashboard/src/lib/privacy.ts`).
- Tracker: occlusion in seconds (5 s), class confirmation (3 detections), rider rule, 3× faster;
  re-linking built but **off** (it doubled the count error on the only clip,
  `docs/benchmarks/2026-09-27_tracker_occlusion.md`).
Also open: #41 (YOLO26n pipeline), #42 (auto-labelling; draft, waits on #41).

## Verified working (dev host, 2026-09-27)
- Edge: 269 pytest green; ruff clean; the Pi runtime imports neither PyTorch nor Ultralytics.
- Dashboard: 194 vitest with a local PostGIS (174 + 20 skipped without); tsc, ESLint and the
  mock build clean; UI acceptance script 91/91 at 1440 and 390 px, light and dark.
- Privacy: an attacker test differences every aggregation level, window and class filter:
  0 recoverable values below 5 (mock week and live replay).
- systemd unit: Type=notify + WatchdogSec=300 + time-sync gate (never run on a Pi).

## Blockers (in order)
1. No Pi run, benchmark, soak or field evidence exists — S6/S8/S9.
2. Accounts for the first deploy — S5: Vercel project, Neon (via Vercel Marketplace), the UCD
   Google OAuth app (D6, IT request), cron secret; domain to confirm.
3. Ethics/DPO + site + enclosure for a real street — S8 (longest lead time).
4. Count accuracy: S7 fails on the hand-counted clip; a second hand-counted clip (with a bus
   stopping at the line) is needed before re-linking can be judged.
5. No speed producer and no calibration method or reference speed source — S7b (D2).

## Missed / re-baselined
- TRL-6 target 2026-05-31: missed (no field unit). M1 re-baselined to 2026-12-31 (D12).
- Slides roadmap Apr/May/Jun/Sep 2026: none met. Fleet re-baselined to 5–10 units in M2 (D4).

## Decisions (PLAN.md §3)
D1 LoRa → dropped from the code 2026-09-24 · D2 speed → implement (S7b) · D3 → screenline +
direction · D4 → M2 = 5–10 units · D5 → full admin console (S11) · D6 → OAuth before first
deploy (S5) · D7 → publish BOM · D8 → Dublin; dataset merge with Roboflow v3 reference ·
D9 → DPIA-lite + statement + signage · D10 → SD card · D11 → not funded · D12 → 2026-12-31 ·
D13 → fix in next paper · D14 → YOLO26n as S13 candidate · D15 → heartbeat every 15 min in
the free-tier pilot (`CAMINA_HEARTBEAT_MINUTES`), goal 5 min.

## Priority map (2026-09-27)

Who: **agent** = code work that needs no hardware, no accounts and no people (done in this
session, tests first, one worktree each); **Tiago** = needs a person, hardware, an account or
a decision. P0 blocks everything after it.

| P | Task | Stage | Who | Done when |
|---|---|---|---|---|
| P0 | CI green on PR #43 (Node 20.11 cannot load Vitest's ESM deps) | S2 | agent | Dashboard + Python jobs pass on GitHub |
| P0 | Bug sweep, edge (Python) and dashboard | — | agent | Each bug has a failing test, then a fix |
| P0 | Record and hand-count a **second clip** (occlusions, a bus stopping at the line) | S7 | Tiago | `videos/<clip>.counts.csv` exists; `count_eval` run on both clips |
| P1 | Two-clip evaluation: `count_eval` sums error over several clips; clip-2 protocol | S7 | agent | One command reports per-clip and total error |
| P1 | Pi bench tooling: `scripts/bench_sensor.py` (FPS, temp, RSS, throttle) + heartbeat health fields | S6 | agent | Unit tests with fakes; runs unchanged on the Pi |
| P1 | Speed from screenline timing + calibration method doc | S7b | agent | Unit tests; `avg_speed_kmh` in the payload; `docs/CALIBRATION_SETUP.md` |
| P1 | First Pi run: 30-min bench, FPS ≥ 5 at 640 | S6 | Tiago (+ Sonia) | Report in `docs/benchmarks/` |
| P2 | Merge order: #43 → #41 (YOLO26n) → #42 (auto-labelling) | S13 | Tiago | PRs merged into `dev` |
| P2 | Label the 235 `dev_expanded` images in Roboflow (SUV, van, e-scooter) | S13 | Tiago | Reviewed labels exported; retrain; error on both clips |
| P2 | Decide re-linking with clip 2 (`count_eval --relink`) | S7 | agent after clip 2 | Adopt only if it lowers the two-clip error |
| P2 | Neon + Vercel live deploy, UCD OAuth app | S5 | Tiago (accounts) | Live map shows a provisioned street |
| P3 | DPO/ethics, host site, enclosure, signage | S8 | Tiago | Sign-off filed; unit on a street |
| P3 | Speed reference measurements (radar gun or timed passes) | S7b | Tiago | ≥ 20 vehicles scored |
| — | Digital twin | — | paused | Resumes with a sensor network or funding |

## Next action
- Merge the dashboard PR after CI is green.
- S5: create the Vercel + Neon projects, set the env from `dashboard/.env.example`
  (`CAMINA_DATA_SOURCE=live`, `CAMINA_HEARTBEAT_MINUTES=15`), run `db:migrate`, provision one
  sensor, replay the synthetic week against the preview, check Neon compute hours.
- S7: hand-count a second clip with occlusions; then decide on re-linking.
- In parallel: UCD DPO/ethics, host site, UCD Google OAuth app request.
