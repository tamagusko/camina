# CAMINA — tasks

Two lists: the maintainer's next stages (from [`.planning/PLAN.md`](.planning/PLAN.md)), and
self-contained tasks anyone can pick up. **Difficulty:** ★ under half a day · ★★ 1–2 days ·
★★★ 2–5 days.

**To claim a task:** put your name after it, open a draft PR into `dev` early (see
[`CONTRIBUTING.md`](CONTRIBUTING.md)), and delete the task from this file in the PR that finishes it.

## Maintainer — next

- [ ] **S2 — CI.** pytest, ESLint, `tsc`, vitest (with generated fixtures), mock build, on every PR.
- [ ] **S3 — Config handshake.** The server returns its own `config_version`; the sensor applies it.
- [ ] **S4 — Live data path.** Migrations, `streets-live.ts`, a `provision-sensor` script; counts and
  speeds below 5 suppressed.
- [ ] **S5 — Deploy.** Vercel + Neon in live mode, Google OAuth on `/admin`.
- [ ] **S6 — Pi bench.** Follow [`docs/raspberry_pi_5.md`](docs/raspberry_pi_5.md) on real hardware; then
  promote `dev` → `main`.
- [ ] **Start now (long lead times):** UCD DPO/ethics approval, a host site, the UCD Google OAuth app.
- [ ] **Before any retraining (S13):** audit `dev_expanded_dataset`.

## Open tasks

### Documentation

- **Hardware list and assembly guide** ★★ — new `docs/HARDWARE.md`: parts with prices, wiring,
  enclosure, Active Cooler (state on the SD card, no SSD). The only unit cost the project will quote.
  *Needs an assembled unit to photograph — ask @tamagusko.*
- **Operations runbook** ★★ — new `dashboard/docs/RUNBOOK.md`: deploy, rollback, "sensor went
  silent", "map not loading", "database spike", each as symptom / check / fix.

### Dashboard

- **Street page summary** ★★ — `dashboard/src/app/[city]/street/[slug]/page.tsx`: show the same
  totals, average speed and per-class rows as the map side panel.
- **Time range on the street page** ★★ — same page: `1h / 24h / 7d / 30d`, kept in `?range=`.
- **Swipe for the mobile panel** ★★ — `dashboard/src/components/panels/StreetSidePanel.tsx` is
  already a bottom sheet on small screens; add drag with peek / half / full snap points.
- **Keyboard shortcuts** ★★ — `M` metric, `C` classes, `T` time window, `Esc` close panel, `?` help
  (`dashboard/src/components/map/`).
- **Screen-reader announcements** ★ — announce metric, class and time-window changes in an
  `aria-live="polite"` region.
- **Tap targets** ★ — every control at least 44×44 px on a 390×844 viewport.

### Tests

- **Click-a-street end-to-end test** ★★ — Playwright: open `/dublin`, click a street, assert the
  panel opens *inside the viewport* with the API's total. (An off-screen panel shipped once.)
- **Counter edge cases** ★★ — `tests/test_windowed_counter.py`: midnight, DST change, empty
  windows, events exactly on a window boundary.
- **State-file corruption** ★★ — `tests/test_daily_accumulator.py`: truncated or zeroed `state.db`
  is quarantined and logged, never crashes the daemon. Use real files, not mocks.
- **Admin routes need a session** ★★ — every `/api/admin/**` route returns 401 without one; the test
  fails when a new route is added unguarded. *After S5.*

### Tooling

- **Pre-commit hooks** ★ — `.pre-commit-config.yaml`: ruff and pytest for Python; ESLint, `tsc`
  and vitest for the dashboard.
- **Fake sensor** ★★ — `scripts/fake_sensor.py`: posts valid count payloads to a local dashboard at a
  set rate, reproducible from a seed. Useful for demos and for testing S4.

## Ask first

These touch the core or security; talk to @tamagusko before starting: database migrations and
the live repository, authentication, privacy thresholds, the model and tracker, the Pi service
setup, and anything in `.planning/`.
