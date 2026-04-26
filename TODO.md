# CAMINA — Contributor Tasks

Authoritative project roadmap: [`.planning/ROADMAP.md`](./.planning/ROADMAP.md). This file is the **work queue** — modular, well-defined tasks you can pick up without needing to touch the load-bearing core.

**Difficulty:** ★ starter (<½ day) · ★★ medium (1–2 days) · ★★★ deeper (2–5 days)
**Tracks:** 📚 Docs · 🎨 Dashboard UX · 🧪 Tests · 🛠 Tooling · 🔧 Ops

**How to claim a task:** flip `[ ]` → `[x]`, fill **Claimed by:** with your name, commit as `chore(todo): claim <task name>`. See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full flow.

---

## 📚 Documentation

### [X] ★ Clean up debug log in `StreetMap.tsx`
**Claimed by:** Guillaume
**File:** `dashboard/src/components/StreetMap.tsx`
**Task:** Remove the `[CAMINA] ancestor heights` diagnostic `console.log` near the ResizeObserver setup.
**Acceptance:** `grep -rn "ancestor heights" dashboard/src` returns nothing; `pnpm dev` still renders the map.

### [X] ★ Dashboard README first-run polish
**Claimed by:** Guillaume
**File:** `dashboard/README.md`
**Task:** Add a "First-run" section covering `pnpm install` → tile download → `.env.local` → `pnpm dev`. Include a troubleshooting row for missing tiles.
**Acceptance:** A fresh contributor can go from clone to `/dublin` following only the README.

### [X] ★ Python docstring pass on `src/camina/core/`
**Claimed by:** Guillaume
**Files:** `src/camina/core/counter.py`, `daily_accumulator.py`, `offline_buffer.py`, `tracker.py`
**Task:** Every public class + method gets a Google-style docstring (Args, Returns, Raises).
**Acceptance:** `uv run pydocstyle src/camina/core/` returns no missing-docstring warnings.

### [ ] ★★ Hardware BOM + assembly guide
**Claimed by:** _(available)_
**File:** new `docs/HARDWARE.md`
**Task:** Document the Pi 5 8GB sensor assembly — parts list with links/prices, photos of wiring, enclosure mount, USB SSD, Active Cooler.
**Acceptance:** `docs/HARDWARE.md` contains sections `## Bill of materials`, `## Assembly`, `## Enclosure`, `## Known-good vendors`; every assembly step has a photo in `docs/img/hardware/`.
**Depends on:** ask @tamagusko for bench access + an assembled prototype to photograph.

### [ ] ★★ Dashboard `RUNBOOK.md` skeleton
**Claimed by:** _(available)_
**File:** new `dashboard/docs/RUNBOOK.md`
**Task:** Operational runbook covering deploy, rollback, "sensor went silent", "map not loading", "DB connection spike". Each scenario gets **symptom / check / fix**.
**Acceptance:** ≥5 scenarios with the three-section format; linked from `dashboard/README.md`.

---

## 🎨 Dashboard UX

### [ ] ★★ Street detail page: mirror side-panel richness
**Claimed by:** _(available)_
**File:** `dashboard/src/app/[city]/street/[slug]/page.tsx`
**Task:** The map-click side-panel shows total count, avg speed, per-class breakdown. Add the same summary above the time-series chart on the street detail page.
**Acceptance:** Visual match with the side-panel; Playwright test navigates to a street detail page and asserts per-class rows.

### [ ] ★★ Time-range selector on street detail
**Claimed by:** _(available)_
**File:** same page as above
**Task:** Segmented selector `1h / 24h / 7d / 30d`; drives the chart via `?range=` query param; URL param persists on refresh.
**Acceptance:** Switching updates the chart without full reload; Playwright test asserts URL ↔ chart sync.

### [ ] ★★ 44×44 px tap-target audit
**Claimed by:** _(available)_
**Files:** `dashboard/src/components/**`
**Task:** Find every clickable control smaller than 44×44 px on mobile and fix via padding (not font-size).
**Acceptance:** Before/after table in PR description listing ≥5 controls; Playwright snapshot on 390×844 viewport.

### [ ] ★★ Keyboard shortcuts (`M`, `C`, `T`, `Esc`, `?`)
**Claimed by:** _(available)_
**Files:** `MetricToggle.tsx`, `ClassFilter.tsx`, `TimeWindowPicker.tsx`, new `KeyboardShortcuts.tsx`
**Task:** `M` cycles metric, `C` cycles class filter, `T` cycles time window, `Esc` closes the panel, `?` opens a shortcuts overlay.
**Acceptance:** Playwright fires each key and asserts the UI change; overlay lists all shortcuts.

### [ ] ★★ ARIA live region for filter announcements
**Claimed by:** _(available)_
**File:** `dashboard/src/components/MetricToggle.tsx` (+ siblings)
**Task:** When metric / class / time window changes, announce the new state in a visually-hidden `aria-live="polite"` region.
**Acceptance:** Vitest asserts announcement text after a change; passes VoiceOver manual check.

### [ ] ★★★ Mobile bottom-sheet for street panel
**Claimed by:** _(available)_
**Files:** `StreetPanel.tsx`, new `BottomSheet.tsx`
**Task:** Below 600 px viewport, render the panel as a bottom-sheet with three snap points (peek 120 px / half 50 vh / full 90 vh), swipeable. Fall back to the current side-panel ≥600 px.
**Acceptance:** Playwright on 390×844 viewport drags through all three snap points; reduced-motion skips the animation.

### [ ] ★★★ Colour-blindness preview on `/admin`
**Claimed by:** _(available)_
**File:** new `dashboard/src/app/admin/colour-preview/page.tsx`
**Task:** Toggle that overlays Protanopia / Deuteranopia / Tritanopia CSS filters on the map — lets admins check the viridis/cividis ramps.
**Acceptance:** Three toggle states render; screenshots stored in `dashboard/docs/img/colour-preview/`.

### [ ] ★★★ i18n scaffold (EN + PT)
**Claimed by:** _(available)_
**Files:** `dashboard/next.config.mjs`, new `dashboard/src/i18n/{en,pt}.ts`, route moves to `dashboard/src/app/[locale]/...`
**Task:** Wire `next-intl`; extract visible strings into locale files; English + Portuguese initial set.
**Acceptance:** `/en/dublin` and `/pt/dublin` render translated strings; Playwright asserts language switch.

---

## 🧪 Tests

### [ ] ★★ `WindowedCounter` edge-case expansion
**Claimed by:** _(available)_
**File:** `tests/test_counter.py`
**Task:** Add tests for TZ midnight rollover, DST transition, empty windows, counts on second-boundary edges.
**Acceptance:** +5 tests; `uv run pytest tests/test_counter.py` stays under 1 s.

### [ ] ★★ `DailyAccumulator` crash-recovery tests
**Claimed by:** _(available)_
**File:** `tests/test_daily_accumulator.py`
**Task:** Simulate corrupted `state.db` (truncated file, zeroed header) with `tmp_path`; assert the accumulator quarantines + logs, never crashes the daemon.
**Acceptance:** +3 tests using real file corruption (not mocks).

### [ ] ★★ Privacy regression for admin routes
**Claimed by:** _(available)_
**File:** new `dashboard/tests/privacy/admin-auth.spec.ts`
**Task:** Every `/api/admin/**` route must return 401 without a valid session. Parametrize over the full route table.
**Acceptance:** Vitest asserts 401 for ≥10 admin routes; test fails if a new admin route is added without a session guard.

### [ ] ★★★ Playwright E2E: 3 golden paths on preview
**Claimed by:** _(available)_
**Files:** `dashboard/tests/e2e/{street-click,metric-toggle,side-panel}.spec.ts`
**Task:** Three E2E flows against a Vercel preview URL (env `PREVIEW_URL`): click a street, toggle metric, open+close side-panel.
**Acceptance:** `PREVIEW_URL=https://... pnpm exec playwright test` passes all three; GitHub Action runs them per PR.

---

## 🛠 Tooling

### [ ] ★ Pre-commit hook bundle
**Claimed by:** _(available)_
**File:** new `.pre-commit-config.yaml`
**Task:** `ruff + mypy + pytest -x --ff` on Python; `eslint + tsc + vitest --run` on dashboard.
**Acceptance:** Fresh clone + `pre-commit install` + a deliberately bad commit is blocked.

### [ ] ★ Dependabot
**Claimed by:** _(available)_
**File:** new `.github/dependabot.yml`
**Task:** Weekly bumps for Python (`pip` or `uv` ecosystem), `pnpm` dashboard deps, and GitHub Actions.
**Acceptance:** File validates; first weekly run produces at least one PR.

### [ ] ★★ GitHub Actions: lint + test on PR
**Claimed by:** _(available)_
**File:** new `.github/workflows/ci.yml`
**Task:** Matrix job — Python (ruff, mypy, pytest) and dashboard (lint, tsc, vitest) on every PR. Cache `uv` and `pnpm` stores.
**Acceptance:** First PR after merge runs both jobs green in <5 min.

### [ ] ★★ Coverage reporting
**Claimed by:** _(available)_
**Files:** update `.github/workflows/ci.yml`, add `.codecov.yml`
**Task:** `pytest --cov` + vitest `--coverage` uploaded to Codecov; PR comment with delta.
**Acceptance:** Coverage badge in `README.md`; PR gets a coverage comment.

---

## 🔧 Ops helpers (no Pi hardware needed)

### [ ] ★★ Synthetic payload generator `tools/gen_mock_counts.py`
**Claimed by:** _(available)_
**File:** new `tools/gen_mock_counts.py`
**Task:** CLI that posts well-formed `/counts` payloads to `localhost:3000/api/ingest/...` at a given cadence; deterministic from a seed.
**Acceptance:** `uv run python tools/gen_mock_counts.py --sensor D99 --rate 1/s --seed 42 --duration 60s` posts 60 payloads; dashboard map updates.

### [ ] ★★ YOLO dev-host benchmark `scripts/bench_host.py`
**Claimed by:** _(available)_
**Files:** new `scripts/bench_host.py`, update `docs/sensor_deployment.md`
**Task:** Run CAMINAv1 **on the dev host** against a folder of test images; report FPS, latency P50/P95, per-image class counts. This is a sanity check, not a thermal benchmark.
**Acceptance:** `uv run python scripts/bench_host.py --images tests/fixtures/images/ --imgsz 480` prints a summary table; docs get a "Host vs Pi benchmark" note explaining what this does and doesn't measure.
**Depends on:** sample test images — ask @tamagusko for 20 frames.

### [ ] ★★★ Read-only `/admin/diagnostics` page
**Claimed by:** _(available)_
**File:** new `dashboard/src/app/admin/diagnostics/page.tsx`
**Task:** Four cards: build info (commit sha, build time), DB health (up/down, latency), tile cache size, last cron run. **Read-only** — no mutations.
**Acceptance:** Authenticated admin sees all four cards; guarded by `requireAdmin()`; visual snapshot in PR.

---

## Out-of-scope for contributors (ping @tamagusko first)

These touch load-bearing core or security-sensitive paths:

- Neon Postgres live repo + migrations (`dashboard/src/lib/repo/streets-live.ts`, `drizzle/migrations/*`)
- Google OAuth wiring + `lib/auth.ts` live allowlist
- LoRaWAN codec + TTN webhook + `/api/ingest/lora/uplink`
- Privacy k-anonymity enforcement (`k_min=5`) changes
- YOLO fine-tuning, CAMINAv1 model weights, tracker logic
- systemd + NTP gate + USB SSD durability on the Pi
- Vercel Rolling Releases, BotID, Upstash rate-limiting, Sentry setup
- Anything under `.planning/` — that's the project memory layer

Want to work on one of these? Ping first. Sometimes the answer is yes-but-pair.

---

## When a task is done

1. Tests + lint + types green locally.
2. Screenshots in the PR if it touches UI.
3. `[x]` the box in this file with your name on the same PR.
4. Ship it.
