# Requirements: CAMINA

**Defined:** 2026-04-23
**Core Value:** One Raspberry Pi on one real Dublin street, detecting and counting nine road-user classes and feeding a live public dashboard — demonstrably privacy-preserving, lightweight, and reproducible.

---

## v1 Requirements

Committed scope for the TRL-6 milestone by **2026-05-31**. Each requirement maps to exactly one roadmap phase (see `ROADMAP.md`).

### Edge agent on Pi (EDGE)

- [ ] **EDGE-01**: `scripts/run_sensor.py` composes the fine-tuned 9-class YOLO11 (NCNN export) + the existing custom Kalman tracker + `WindowedCounter` + `DailyAccumulator` + `SensorDaemon` on Pi 5 8GB.
- [ ] **EDGE-02**: Camera input uses `picamera2` + `libcamera` (not `cv2.VideoCapture`); RGB888 direct feed; no YUV→BGR conversion step.
- [ ] **EDGE-03**: 30-minute sustained, in-enclosure inference benchmark on Pi 5 8GB captures FPS, CPU load, memory RSS, core temperature, and `vcgencmd get_throttled`. Documented in `docs/sensor_deployment.md`.
- [ ] **EDGE-04**: Pi 5 Official Active Cooler is a documented deployment prerequisite; daemon logs core temperature + throttle bits in every heartbeat.
- [ ] **EDGE-05**: `state.db` and the OfflineBuffer live on a USB SSD (not the SD card); `PRAGMA synchronous=FULL`; boot-time `PRAGMA integrity_check`; daemon refuses to start on corruption.
- [ ] **EDGE-06**: systemd unit uses `Type=notify` + `WatchdogSec=300` + `sd_notify` pings from the daemon's main loop; camera is not re-initialised on transient errors.
- [ ] **EDGE-07**: systemd unit requires `time-sync.target`; daemon refuses to start until NTP synced; server rejects payloads with `abs(produced_at - server_now) > 60 s`.
- [ ] **EDGE-08**: 48-hour bench soak on Pi 5 + dev-side Vercel preview passes with flat RSS and no camera re-init failures.
- [ ] **EDGE-09**: `Publisher` interface extracted from `HttpsPublisher`; `SensorDaemon` accepts any `Publisher`; `OfflineBuffer` remains transport-agnostic. Zero behavioural change for HTTPS path; existing 60-test suite still green.

### LoRaWAN transport (LORA)

- [ ] **LORA-01**: ≤200-char payload codec (actual target ≤24 base64 chars over a 17-byte binary layout): 3 B camera ID (`LNN`, e.g. `D01`), 4 B epoch timestamp, 9 B class counts, 1 B schema version. Implemented in Python (`src/camina/io/lora_codec.py`) and mirrored in TypeScript (`dashboard/src/lib/lora-codec.ts`).
- [ ] **LORA-02**: Joint round-trip property-based tests: Python `hypothesis` + TypeScript `fast-check` + shared vector fixtures in `tests/fixtures/lora/`. Mismatch fails CI.
- [ ] **LORA-03**: `LoRaPublisher` in `src/camina/io/` parallel to `HttpsPublisher`, plugged via the `Publisher` interface. Config flag `transport: https | lora | both` in `configs/sensor.yaml`.
- [ ] **LORA-04**: LoRa path is counts-only, uplink-only, at the same 15-minute cadence. Sensors configured `transport=lora` skip heartbeat and config polling (both remain HTTPS-only features).
- [ ] **LORA-05**: Airtime budget documented for worst-case TTN spreading factors (SF7–SF12); hard gate that refuses to transmit if projected daily airtime exceeds 30 s/device. Fallback to HTTPS when SF > 10.
- [ ] **LORA-06**: `POST /api/ingest/lora/uplink` on the dashboard decodes the TTN webhook payload, validates schema + camera ID + timestamp, persists to the same canonical `sensor_readings` table used by the HTTPS path. Idempotency via `(sensor_id, window_start)` primary key.
- [ ] **LORA-07**: TTN Community v3 application + device registered; HMAC webhook signature verified on every POST.
- [ ] **LORA-08**: Round-trip test with a real TTN dev device (not the deployment Pi) wires end-to-end on a Vercel preview before the deployment Pi is touched.

### Data layer (DATA)

- [ ] **DATA-01**: Neon Postgres + PostGIS project provisioned via Vercel Marketplace; pooled and unpooled URLs set in `.env.local` and later via `vercel env add`.
- [ ] **DATA-02**: Drizzle migration `dashboard/drizzle/migrations/0000_init.sql` applied; schema includes `sensors`, `streets`, `street_coverage`, `sensor_readings`, `daily_totals`, `heartbeats`, `events`, `audit_log`, `allowed_members`, `config_history`.
- [ ] **DATA-03**: `ON DELETE CASCADE` from `sensors` to `sensor_readings`, `heartbeats`, `street_coverage`, `daily_totals`, `config_history` — right-to-erasure by design.
- [ ] **DATA-04**: `street_readings_15m` materialized view contains **no `sensor_id`**; aggregates at street × 15 min × class level.
- [ ] **DATA-05**: `dashboard/src/lib/repo/streets-live.ts` implements the `StreetsRepository` interface end-to-end (currently throws).
- [ ] **DATA-06**: `k_min = 5` k-anonymity floor enforced in the repository layer (both mock and live adapters) on every public response; counts below `k_min` collapse to `null` or `"< 5"`. Documented in the DPIA.
- [ ] **DATA-07**: CI grep enforces `DATABASE_URL_UNPOOLED` is used only in migration/CLI code, never in `dashboard/src/app/api/**`.
- [ ] **DATA-08**: `@vercel/functions` installed; `attachDatabasePool(client)` called immediately after the `postgres()` client is constructed in `dashboard/src/lib/db.ts`.
- [ ] **DATA-09**: Mock/live parity tests: every `StreetsRepository` method produces structurally identical shapes for the same input across mock + Dockerized Postgres-PostGIS.

### Authentication (AUTH)

- [ ] **AUTH-01**: Auth.js v5 Google OAuth wired with `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` configured for UCD Google Workspace (internal app type to skip external-app verification).
- [ ] **AUTH-02**: `allowed_members` table populated; admin access gated by a live DB lookup (not env-var allowlist).
- [ ] **AUTH-03**: `CAMINA_DEV_ALLOWED_EMAILS` dev fallback **removed** in the live auth path.
- [ ] **AUTH-04**: Allowlist defaults to **fail-closed** whenever `NODE_ENV=production` or `VERCEL_ENV` is set. Module-init assertion blocks boot if misconfigured.
- [ ] **AUTH-05**: `requireAdmin()` guard returns 401 for every admin route when no session or session email not in `allowed_members`.
- [ ] **AUTH-06**: Public map routes remain viewable without sign-in. Admin console (`/admin/**`) gated.

### Admin console (ADMIN)

- [ ] **ADMIN-01**: `<SensorForm>` (create/edit) accepts sensor ID (`LNN`), GPS (lat/lon), install date, firmware version, street coverage — admin-only.
- [ ] **ADMIN-02**: `<StreetDrawTool>` picks OSM ways visually and saves to `street_coverage`.
- [ ] **ADMIN-03**: `/admin/members` supports invite / revoke / role editing of `allowed_members`.
- [ ] **ADMIN-04**: `PATCH /api/admin/sensors/[id]` updates sensor config, bumps `config_version`, writes an `audit_log` row with actor, timestamp, before/after.
- [ ] **ADMIN-05**: Admin UI shows "awaiting device ack" → "✓ applied" state driven by the next heartbeat's `config_version`.
- [ ] **ADMIN-06**: `/admin/events` lists cron-generated events (silent sensors, reconciliation mismatches) with acknowledge / dismiss workflow.
- [ ] **ADMIN-07**: `/admin/audit` filterable log of all admin mutations.
- [ ] **ADMIN-08**: Build-time guard in `vercel.ts` fails the build when `VERCEL_ENV ∈ {preview, production}` and `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true`.

### Scheduled jobs (CRON)

- [ ] **CRON-01**: `refresh-aggregates` runs every 15 min: `REFRESH MATERIALIZED VIEW CONCURRENTLY street_readings_15m` wrapped in a Postgres advisory lock. Authenticated with `VERCEL_CRON_SECRET` (fail-closed when secret unset).
- [ ] **CRON-02**: `detect-silent` runs every 15 min: inserts an `events` row for any sensor whose last heartbeat is older than 15 min (HTTPS) or whose last LoRa uplink is older than 30 min.
- [ ] **CRON-03**: `reconcile-daily` runs at 01:00 UTC: compares `daily_totals` received from devices against the sum of windowed counts in `sensor_readings` per the rules in `docs/RECONCILIATION.md`; emits mismatch events.
- [ ] **CRON-04**: `retention-enforce` runs daily: deletes raw `sensor_readings`, `heartbeats`, and `audit_log` rows older than 13 months. Aggregates in `street_readings_15m` remain (anonymised).
- [ ] **CRON-05**: All cron handlers are idempotent: use an `idempotency_keys` table or advisory locks so overlapping invocations do not double-process.

### Security hardening (SEC)

- [ ] **SEC-01**: Vercel BotID enabled on `/sign-in` and on every admin mutation endpoint.
- [ ] **SEC-02**: CSP + HSTS + `X-Content-Type-Options: nosniff` + `Referrer-Policy: strict-origin-when-cross-origin` headers configured in `vercel.ts`.
- [ ] **SEC-03**: Upstash Ratelimit sliding-window: per-device on `/api/ingest/*` (10 req / 15 min), per-IP on `/api/admin/*` (30 req / min), per-IP on `/sign-in` (5 req / min).
- [ ] **SEC-04**: Bearer token per device stored in `sensors.ingest_token`; rotation documented in `docs/sensor_deployment.md`. Manual (SSH) rotation is sufficient for TRL-6.
- [ ] **SEC-05**: 501 stubs audited and removed from `/api/ingest/*` before the `CAMINA_DATA_SOURCE=live` flag flips; edge agent treats any 501 as dead-letter, not retry.
- [ ] **SEC-06**: AUTH_SECRET rotated (done 2026-04-23) and documented in the runbook as something to rotate after every new contributor touches `.env.local`.

### Observability (OBS)

- [ ] **OBS-01**: Sentry client + server configured with a `beforeSend` PII scrubber that strips `sensor_id`, `latitude`, `longitude`, `gps`, and any key matching `/_gps$/i` from the event payload and tags.
- [ ] **OBS-02**: Sentry source maps uploaded per release.
- [ ] **OBS-03**: Vercel Speed Insights enabled on the public dashboard.
- [ ] **OBS-04**: Vercel Analytics enabled.
- [ ] **OBS-05**: Uniform route-handler logging wrapper (shared via `dashboard/src/lib/log.ts`) emits request ID + route + status + latency; never logs request body for `/api/ingest/*` or `/api/admin/*`.
- [ ] **OBS-06**: Uptime check pings `/api/health` every 5 min and pages on 3 consecutive failures.
- [ ] **OBS-07**: `/api/admin/fleet/health` endpoint exposes per-sensor last-heartbeat age; `<FleetHealth>` component surfaces it in `/admin`.

### Deployment (DEPLOY)

- [ ] **DEPLOY-01**: `vercel.ts` configuration complete with framework, buildCommand, rewrites, redirects, headers, and cron schedules.
- [ ] **DEPLOY-02**: `vercel link` binds the repo to the project; `vercel env add` populates preview + production env from `dashboard/.env.example`.
- [ ] **DEPLOY-03**: Vercel Rolling Releases configured: 10 % → 50 % → 100 % with health gates (`/api/health` 200, `/api/streets/*` p95 < 500 ms, `/api/ingest/*` 5xx rate < 1 %) and auto-rollback on gate failure.
- [ ] **DEPLOY-04**: `dashboard/docs/RUNBOOK.md` covers rollback, sensor swap, AUTH_SECRET rotation, Neon migration, cron debugging, DPIA update.
- [ ] **DEPLOY-05**: Vercel CLI updated to the latest version documented in the runbook.

### Privacy artefacts (PRIV) — **was missing from PROJECT.md; surfaced by research**

- [ ] **PRIV-01**: **DPIA document** at `docs/PRIVACY/DPIA.md` covering data collected, retention, recipients, lawful basis, k-anonymity floor, physical access controls, right-to-erasure flow, DPO contact. Reviewed by UCD ethics before the sensor is installed on a public street.
- [ ] **PRIV-02**: **Public privacy statement** at `/about` (or footer link) on the dashboard. Plain-language summary of what's collected, what isn't (no faces, no plates, no video stored), who can see raw data (no one), contact for data subject requests.
- [ ] **PRIV-03**: **Physical signage** at the sensor site: "CAMINA research sensor — aggregate counts only, no video recorded, contact [DPO] — ref [sensor-id]." Printed and installed alongside the Pi.
- [ ] **PRIV-04**: Privacy regression test extended to the live adapter: raw `sensor_id`, exact GPS, raw camera frames never appear in any response on `/api/streets/*` or `/api/public/*`.
- [ ] **PRIV-05**: CSV/JSON export at `/api/public/aggregates.csv` (k-anonymity-respecting) — open-data parity with peer projects (Telraam, Helsinki).

### TRL-6 demo (DEMO)

- [ ] **DEMO-01**: One Pi installed on a real Dublin street, publishing to production Vercel → live Neon → public map. Transport is `https`, `lora`, or `both` depending on W1 TTN coverage outcome.
- [ ] **DEMO-02**: Continuous publishing for **≥ 7 days** (degraded-but-presentable acceptable — OfflineBuffer gap-fills count as continuous).
- [ ] **DEMO-03**: Cold-spare Pi bench-tested and swap-ready at the lab.
- [ ] **DEMO-04**: Daily reconciliation mismatches investigated; public map never shows `null` counts on a working day without an explanatory tooltip.
- [ ] **DEMO-05**: Synthetic outage simulation: disconnect WiFi for 30 min; OfflineBuffer drains on reconnect without data loss or duplicates.
- [ ] **DEMO-06**: INTERREG deliverable README ready with a link to the live dashboard, a screenshot, and a 30-second demo video.

---

## v2 Requirements

Acknowledged but explicitly deferred past the 2026-05-31 TRL-6 milestone.

### Tech-debt polish (TECH)

- **TECH-01**: Re-enable `reactStrictMode: true` in `dashboard/next.config.mjs` once the MapLibre init is fully ref-guarded.
- **TECH-02**: Re-enable `cacheComponents: true` once every dynamic read is wrapped in `<Suspense>` (if still outstanding post-W1).
- **TECH-03**: Remove the `[CAMINA] ancestor heights` diagnostic log in `dashboard/src/components/StreetMap.tsx`.
- **TECH-04**: Drizzle typed `geometry()` migration for PostGIS columns.
- **TECH-05**: Retire committed YOLO weights (`yolo11n.pt`, `yolo11n.torchscript`) from git history; replace with NCNN model + a documented download script.
- **TECH-06**: Remove `test.mov` (23 MB) and `camina-preview.png` from git; replace with lightweight fixtures.
- **TECH-07**: Deduplicate `environment.yml` vs `requirements.txt` vs `requirements_calibration.txt`; switch to `uv` lock file on the Pi side.

### UX polish (UX)

- **UX-01**: Bottom-sheet with 3 snap points (peek / half / full) on < 600 px viewports.
- **UX-02**: 44×44 px tap-target audit on every control.
- **UX-03**: Reduced-motion fallback audit.
- **UX-04**: Street detail page mirrors the side-panel richness above the time-series chart; time-range selector (1 h / 24 h / 7 d / 30 d).
- **UX-05**: Admin strip on the street detail page for logged-in admins.

### Accessibility (A11Y)

- **A11Y-01**: Keyboard-reachable map controls with shortcuts `M`, `C`, `T`, `Esc`, `?`.
- **A11Y-02**: ARIA live region for metric-toggle announcements.
- **A11Y-03**: Protanopia / Deuteranopia preview toggle on `/admin`.
- **A11Y-04**: WCAG 2.1 AA audit pass.

### Internationalisation (I18N)

- **I18N-01**: `next-intl` scaffold.
- **I18N-02**: English + Portuguese translations.

### Auth hardening (AUTH-v2)

- **AUTH-v2-01**: Short-lived JWT per device (vs opaque Bearer), rotated via `/v1/sensors/{id}/token` endpoint.
- **AUTH-v2-02**: Hardware-bound keys (TPM) for sensor identity.

### Operations (OPS)

- **OPS-01**: OTA model / firmware update pipeline (explicitly TRL-7+).
- **OPS-02**: Docker / Balena image for 10+ device deployments.
- **OPS-03**: Integration tests against a deployed Vercel preview with one real sensor.

### Research artefacts (RES)

- **RES-01**: Dataset card for `custom_model_train/` with provenance + licence.
- **RES-02**: Inference benchmark table (Pi 5 vs Hailo-8L vs others) for publication.
- **RES-03**: TR / ITSC / ITS paper submission draft.
- **RES-04**: Public model card for the fine-tuned 9-class CAMINAv1 model.

### Scale (SCALE)

- **SCALE-01**: Multi-city support (data model already keyed by city; requires admin UX + city-switcher).
- **SCALE-02**: 10+ sensor deployments.
- **SCALE-03**: TimescaleDB hypertable migration once rows > 10 M/year.

---

## Out of Scope

Explicitly excluded from all CAMINA versions. Each item maps back to PROJECT.md's Out-of-Scope section.

| Feature | Reason |
|---|---|
| Facial recognition | Violates privacy-by-design; ethics non-starter. |
| Automatic Number Plate Recognition (ANPR) | ICO high-risk category; not the research mission. |
| Cross-camera re-identification (Re-ID) | Would trigger journey-tracking concerns under GDPR. |
| Exact sensor GPS in public UI | Hard privacy boundary; enforced by regression test. |
| Raw camera frame / video upload | Stays at the edge forever; aggregates only leave the Pi. |
| Anonymous admin access | Allow-listed Google OAuth required; documented privacy model. |
| Anonymous public access gating | Opposite: public read is intentionally unauthenticated so aggregates are available as open data. |
| ML forecasting / predictions | Separate research project. |
| Native mobile apps | Responsive web only. |
| 99.9 % SLA / commercial deployment | Research-grade reliability is the bar. |
| LoRaWAN downlink control plane (Class C) | Uplink-only in v1; config hot-reload stays on HTTPS. |
| LoRaWAN carrying heartbeats or config polls | Would blow the 30 s/day TTN Fair Use budget. |
| Hailo-8L AI HAT in v1 | Untested software path under 5-week deadline. |
| CayenneLPP LoRa encoding | Wastes 18 B of channel+type overhead; custom `struct.pack` wins. |
| Self-hosted ChirpStack | TTN Community is sufficient; ChirpStack is overkill for N=1. |
| TimescaleDB | ≤ 3.15 M rows/year doesn't justify an extension. |
| Docker / Balena on Pi in v1 | No OTA in v1; bare systemd is simpler and proven. |
| Mid-milestone Tailwind v4 / zod v4 migration | Breaking changes; post-demo tech-debt. |
| Short-lived JWT device auth in v1 | Opaque Bearer is sufficient for TRL-5/6. |

## Traceability

Populated during `ROADMAP.md` creation. Each v1 requirement maps to exactly one phase.

| Requirement | Phase | Status |
|---|---|---|
| EDGE-01..09 | (TBD) | Pending |
| LORA-01..08 | (TBD) | Pending |
| DATA-01..09 | (TBD) | Pending |
| AUTH-01..06 | (TBD) | Pending |
| ADMIN-01..08 | (TBD) | Pending |
| CRON-01..05 | (TBD) | Pending |
| SEC-01..06 | (TBD) | Pending |
| OBS-01..07 | (TBD) | Pending |
| DEPLOY-01..05 | (TBD) | Pending |
| PRIV-01..05 | (TBD) | Pending |
| DEMO-01..06 | (TBD) | Pending |

**Coverage:**
- v1 requirements: **63 total**
- Mapped to phases: 0 (pending ROADMAP.md)
- Unmapped: 63 ⚠️ (expected at this stage; ROADMAP.md will assign)

---
*Requirements defined: 2026-04-23*
*Last updated: 2026-04-23 after initial definition*
