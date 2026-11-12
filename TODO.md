# CAMINA — tasks

What happens next, in order. Stages (S1–S14) are defined in [`.planning/PLAN.md`](.planning/PLAN.md);
the current state is in [`.planning/STATE.md`](.planning/STATE.md).

**Difficulty:** ★ under half a day · ★★ 1–2 days · ★★★ 2–5 days. **To claim a task:** put your
name after it, open a draft PR into `dev` early ([`CONTRIBUTING.md`](CONTRIBUTING.md)), and delete
the task in the PR that finishes it.

## 1. Maintainer — now

- [ ] **Second hand-counted clip** (S7). Install-like view, occlusions, a bus stopping at the line.
  One clip of 30 crossings cannot tell models, or tracker settings, apart.
- [ ] **Deploy** (S5). Neon + Vercel in live mode; migrations `0000`–`0005`; `speed_limit_kmh` on
  each street; `CRON_SECRET`; UCD Google OAuth on `/admin`.
- [ ] **Pi bench** (S6). [`docs/raspberry_pi_5.md`](docs/raspberry_pi_5.md): 30 min, ≥ 5 FPS at 640,
  no throttling.
- [ ] **Start now, long lead times** (S8). UCD DPO/ethics, a host site, the enclosure.

## 2. Next model

The code and the GPU are ready; the labels are not. Train only after steps 1–3.

1. [x] **Merge the training PRs** into `dev`: #41, #42, #44 (2026-09-29).
2. [ ] **Finish the TRA 2026 label audit** ([`training/AUDIT.md`](training/AUDIT.md)): decide the
   332 disputed boxes in `data/autolabel/audit/index.html`, `apply_audit`, push to Roboflow,
   redraw `audit-box`, save as **v4** (v3 stays the paper's). Keep the split.
3. [ ] **Review new images in Roboflow**
   - `dev_expanded`, 235 images: checked by Codex and Claude. Upload
     `data/autolabel/dev_expanded_new/review/flagged` (64) first, then `review/ok` (171).
   - Montreal: 662 images selected by Claude agreement ([`training/MONTREAL.md`](training/MONTREAL.md)).
     Review the 60-image audit sample (pass: ≤ 2 fail), record the result, copy `tier_a` to
     `data/montreal`. Steps: `data/autolabel/montreal/AUDIT.md`.
   - Own camera images: settle GDPR and the camera terms before any leave the machine.
4. [ ] **Train and compare** YOLO26n, YOLO26s and YOLO11n (paper recipe) on the audited data,
   plus the Montreal ablation. `evaluate` on the test split and both clips; group the split by
   camera before trusting e-scooter AP.
5. [ ] **Promote** only if it beats CAMINAv1 on both clips, then `--final`, FP16 NCNN at 640, the Pi
   bench, and `models/<name>_fp16_ncnn_model/` with a `PROVENANCE.md`.
6. [ ] **Release** `dev` → `main` only after the retrain: merge #50 (left open) and tag `v0.x`.

Thin classes are the real limit: 112 delivery vans and 132 trucks, against a target of 500.

## 3. Open tasks — anyone

**Docs**
- **Hardware list and assembly guide** ★★ — `docs/HARDWARE.md`: parts and prices, wiring,
  enclosure, cooler. *Needs an assembled unit; ask @tamagusko.*
- **Operations runbook** ★★ — deploy, rollback, "sensor went silent", "map not loading", as
  symptom / check / fix. Extend [`docs/operations.md`](docs/operations.md).

**Dashboard**
- **Street page summary** ★★ — `dashboard/src/app/[city]/street/[slug]/page.tsx`: the side
  panel's totals, average speed and per-class rows.
- **Time range on the street page** ★★ — `1h / 24h / 7d / 30d`, kept in `?range=`.
- **Swipe for the mobile panel** ★★ — `StreetSidePanel.tsx`: peek / half / full snap points.
- **Keyboard shortcuts** ★★ — `M` metric, `C` classes, `T` window, `Esc` close, `?` help.
- **Screen-reader announcements** ★ — metric, class and window changes in an `aria-live` region.
- **Tap targets** ★ — every control at least 44×44 px on a 390×844 viewport.

**Tests**
- **Click-a-street end-to-end** ★★ — the panel opens inside the viewport with the API's total.
- **Counter edge cases** ★★ — midnight, DST, empty windows, events on a window boundary.
- **State-file corruption** ★★ — a truncated `state.db` is quarantined and logged, never a crash.
- **Admin routes need a session** ★★ — every `/api/admin/**` returns 401 without one. *After S5.*

**Tooling**
- **Pre-commit hooks** ★ — ruff and pytest; ESLint, `tsc` and vitest for the dashboard.

## Ask first

Talk to @tamagusko before touching: migrations and the live repository, authentication, privacy
thresholds, the model and tracker, the Pi service, and anything in `.planning/`.
