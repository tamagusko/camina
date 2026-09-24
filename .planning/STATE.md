# STATE
Version: 2.3 — 2026-09-24 — counting (S7, sensor side) merged (#36, #37); repo cleanup; LoRa removed
Last verified: 2026-09-24. The 2026-09-15 audit folder was removed from the tree; it is in git
history (`git show 594756c:.planning/audit-2026-09-15/AUDIT.md`).

## Current stage
M1 / S1 — **done** 2026-09-24 (#21). S7 — **sensor side done** 2026-09-24 (#36, #37): count
gate (screenline with direction AB/BA, or movement), one tracker with majority-vote classes.
Open in S7: publish direction (payload + zod + DB), ground-truth protocol and the count-error
check on a reference clip. Next: S2 (CI) ∥ S3 ∥ S4.

## Verified working (dev host, 2026-09-24)
- Edge: 184 pytest green (161 + 10 skipped in the Pi-only profile); `python -m camina --dry-run`
  composes on the 9-class model; the Pi runtime imports neither PyTorch nor Ultralytics;
  ruff clean (PEP 8, `pyproject.toml`).
- Counting on `videos/test.mov`: person tracks 325 → 3 counted at a screenline (bollards and
  jitter excluded); car + SUV 75 tracks → 24 counted (parked cars excluded). Not yet compared
  with a hand count.
- Dashboard: 79 vitest, tsc and ESLint clean; street click → side panel verified in a browser.
- systemd unit: Type=notify + WatchdogSec=300 + time-sync gate (never run on a Pi).

## Blockers (in order)
1. Live read path is a stub (streets-live.ts) and nothing provisions sensors/tokens — S4.
2. Config handshake dead (routes echo client version) — S3.
3. No CI — S2.
4. No Pi run, benchmark, soak or field evidence exists — S6/S8/S9.
5. Ethics/DPO + site + enclosure for a real street — S8 (start now; longest lead time).
6. UCD Google OAuth app does not exist; required before the first live deploy (D6) — S5.
7. No speed producer and no calibration method or reference speed source — S7b (D2).

## Missed / re-baselined
- TRL-6 target 2026-05-31: missed (no field unit). M1 re-baselined to 2026-12-31 (D12).
- Slides roadmap Apr/May/Jun/Sep 2026: none met. Fleet re-baselined to 5–10 units in M2 (D4).

## Decisions (2026-09-15, PLAN.md §3)
D1 LoRa → dropped from the code 2026-09-24 (restore from git history if taken up) · D2 speed →
implement (S7b) · D3 → screenline + direction · D4 → M2 = 5–10 units · D5 → full admin console
(S11) · D6 → OAuth before first deploy (S5) · D7 → publish BOM · D8 → Dublin; dataset merge
with Roboflow v3 reference · D9 → DPIA-lite + statement + signage · D10 → SD card · D11 → not
funded · D12 → 2026-12-31 · D13 → fix in next paper.

## Next action
- S2 (CI) ∥ S3 (config handshake) ∥ S4 (live data path).
- S7 remainder: publish direction; hand-count `videos/test.mov` to measure count error.
- Training workflow review (S13 prep): see `training/PLAN.md`.
- This week, in parallel: contact UCD DPO/ethics, identify a host site, file the UCD Google
  OAuth app request.
