# STATE
Version: 2.6 — 2026-11-12 — restart after a six-week pause (last work 2026-09-29). Since 2.5:
the dashboard, training, auto-labelling, Montreal and Claude-check branches are merged into
`dev` (#41–#49, #51); the paper snapshot is the tag `TRA2026`; a release gate holds `main`.
Last verified: 2026-11-12 — edge `pytest`: 406 passed. Dashboard tests not re-run since 2026-09-27.
The 2026-09-15 audit folder is in git history only (`git show 594756c:.planning/audit-2026-09-15/AUDIT.md`).

## Since 2.5 (2026-09-27 → 2026-09-29)
- Merged into `dev`: #43 dashboard live data layer, #45 road analysis, #46 speed analysis
  (incl. speed limit per street, migration `0005_speed_limit.sql`), #47 tidy, #41 YOLO26n
  training pipeline, #42 auto-labelling, #44 Montreal import, #48 Claude label check,
  #49 `TRA2026` branch → tag, #51 TODO.
- **Release gate:** no `dev` → `main` until the labels are fixed and the model is retrained.
  PR #50 (dev → main) stays open; merge and tag `v0.x` after the retrain (TODO §2.6).
- Dashboard is on Vercel (project `camina-dublin`) in **mock** mode. Live mode (Neon, OAuth) is S5.
- Labels: TRA 2026 audit — 332 disputed boxes in `data/autolabel/audit/index.html`, **no
  decisions recorded yet**. `dev_expanded`: 235 images checked by Codex and Claude, split into
  `review/flagged` (64) and `review/ok` (171), not yet in Roboflow. Montreal: 662 images selected
  by Claude agreement (`training/MONTREAL.md`); the 60-image audit sample is not reviewed yet.
- Dependabot security PRs #52 (urllib3) and #53 (next) retargeted from `main` to `dev`.

## Next action (2026-11-12)
1. **Finish the TRA 2026 label audit** (TODO §2.2): it gates the retrain, and the retrain gates
   the release. Then the `dev_expanded` and Montreal reviews (TODO §2.3).
2. In parallel, the hardware and accounts path, which gates M1 (2026-12-31) more than the model
   does: S5 live deploy, S6 Pi bench, S8 DPO/ethics and a site.
3. Planning for the citizen-science phase is being drafted outside the repo
   (`~/repos/camina-plans/citizen-science-2026-11/`); nothing in it is adopted until approved.

## Current stage at 2.5 (2026-09-27), kept for reference
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
- Bug sweep: 11 edge fixes (window boundaries, outbox and publisher loss paths, config persist,
  shutdown) and 4 dashboard fixes (mock window end, live `now()`, daily date check, cron secret
  name). Count error on the clip unchanged (verified base vs head).
- **S7b** code: speed from two calibrated lines (`camina/core/speed.py`), off by default; a class
  speed is published only over ≥ 5 timed road users. Procedure: `docs/CALIBRATION_SETUP.md`.
  Not validated against a reference speed.
- **S6** prep: `scripts/bench_sensor.py` (FPS, temperature, RSS, throttling; JSON + Markdown);
  heartbeats carry `throttled` and `rss_mb` (accepted by the dashboard, not stored yet).
- **S7** prep: `training.count_eval` scores several clips and pools them; second-clip filming
  protocol in `training/EVALUATION.md`.
Also open: #41 (YOLO26n pipeline), #42 (auto-labelling; draft, waits on #41).

## Verified working (dev host, 2026-09-27)
- Edge: 327 pytest green; ruff clean; the Pi runtime imports neither PyTorch nor Ultralytics.
- Dashboard: 225 vitest + 22 skipped without a database; tsc, ESLint and the mock build clean.
- Independent verification gate (Fable) on all of the above: pass after two fixes.
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
| P0 | CI green on PR #43 (Node 20.11 cannot load Vitest's ESM deps) | S2 | **done** (Node 24) | Dashboard + Python jobs pass on GitHub |
| P0 | Bug sweep, edge (Python) and dashboard | — | **done** (15 fixes) | Each bug has a failing test, then a fix |
| P0 | Record and hand-count a **second clip** (occlusions, a bus stopping at the line) | S7 | Tiago | `videos/<clip>.counts.csv` exists; `count_eval` run on both clips |
| P1 | Two-clip evaluation: `count_eval` sums error over several clips; clip-2 protocol | S7 | **done** | One command reports per-clip and total error |
| P1 | Pi bench tooling: `scripts/bench_sensor.py` (FPS, temp, RSS, throttle) + heartbeat health fields | S6 | **done** (untested on a Pi) | Unit tests with fakes; runs unchanged on the Pi |
| P1 | Speed from screenline timing + calibration method doc | S7b | **done** (code only) | Unit tests; `avg_speed_kmh` in the payload; `docs/CALIBRATION_SETUP.md` |
| P1 | First Pi run: 30-min bench, FPS ≥ 5 at 640 | S6 | Tiago (+ Sonia) | Report in `docs/benchmarks/` |
| P2 | Merge order: #43 → #41 (YOLO26n) → #42 (auto-labelling) | S13 | Tiago | PRs merged into `dev` |
| P2 | Label the 235 `dev_expanded` images in Roboflow (SUV, van, e-scooter) | S13 | Tiago | Reviewed labels exported; retrain; error on both clips |
| P2 | Decide re-linking with clip 2 (`count_eval --relink`) | S7 | agent after clip 2 | Adopt only if it lowers the two-clip error |
| P2 | Neon + Vercel live deploy, UCD OAuth app; set `CRON_SECRET` on Vercel | S5 | Tiago (accounts) | Live map shows a provisioned street |
| P3 | DPO/ethics, host site, enclosure, signage | S8 | Tiago | Sign-off filed; unit on a street |
| P3 | Speed reference measurements (radar gun or timed passes) | S7b | Tiago | ≥ 20 vehicles scored |
| P2 | Protocol: a restart inside a 15-min window overwrites the pre-restart partial (`ingest-store.ts`) | S4 | agent, needs a decision | Partial windows merge without double-counting replays |
| — | Digital twin | — | paused | Resumes with a sensor network or funding |

## Next action at 2.5 (superseded by the one above)
- Merge the dashboard PR after CI is green.
- S5: create the Vercel + Neon projects, set the env from `dashboard/.env.example`
  (`CAMINA_DATA_SOURCE=live`, `CAMINA_HEARTBEAT_MINUTES=15`), run `db:migrate`, provision one
  sensor, replay the synthetic week against the preview, check Neon compute hours.
- S7: hand-count a second clip with occlusions; then decide on re-linking.
- In parallel: UCD DPO/ethics, host site, UCD Google OAuth app request.
