# Feature Research

**Domain:** Privacy-first edge-CV traffic-sensor network for academic research (TRL-6, single-sensor Dublin deployment)
**Researched:** 2026-04-23
**Confidence:** HIGH for competitor/table-stakes items (multiple independent sources: Telraam, Vivacity, Numina, Miovision, Helsinki Open Data, TU Delft UMO, ICO ANPR guidance). MEDIUM for GDPR-interpretation and INTERREG-specific academic norms (primarily official ICO + smart-city literature, not CAMINA-specific legal review).

## Context Recap

CAMINA is deliberately narrower than commercial peers: one Pi 5 on one Dublin street, 9 classes (`person, cyclist, e-scooter, car, SUV, motorcycle, bus, delivery van, truck`), 15-min windowed counts, dual transport (HTTPS primary + LoRaWAN secondary), public street-coloured map, admin-only sensor management with Google OAuth, anonymous public view. Already validated in `.planning/PROJECT.md`: the 9-class YOLO11 model, custom Kalman+Hungarian tracker, edge-agent daemon with WAL outbox, HTTPS ingest + reconciliation protocol, Next.js 16 dashboard scaffold, Uber-monochrome design language, MapLibre+Carto Positron basemap, privacy regression test, zod-validated ingest endpoints, cron skeletons.

Competitor scan (all accept edge-CV + aggregate-only counts as the norm): **Telraam** (citizen-hosted, 15-min aggregates, AI on-device, public map), **Vivacity Labs** (10+ classes incl. e-scooters, 97% classification accuracy validated by TfL, near-miss/speed/paths), **Numina** (pedestrian-focused, onboard compute, anonymous desire lines, Boston deployments), **Miovision** (intersection TMCs/ATRs, 15-min increments, 95%+ accuracy, dashboard + API), **Helsinki** (5-min open API, public map), **TU Delft UMO** (campus digital-twin with moving-dot privacy visualisation).

## Feature Landscape

### Table Stakes (TRL-6 Demo Fails Without These)

Features users — UCD researchers, INTERREG reviewers, Dublin collaborators, and casual public visitors — expect or the demo feels unfinished.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-class road-user classification (≥ pedestrian, cyclist, car, truck) | Every peer (Telraam, Vivacity, Numina, Miovision) ships this | LOW | ✓ Validated — 9-class YOLO11 trained, weights committed |
| 15-minute windowed aggregation | Industry default (Telraam, Miovision, CAMINA); Helsinki uses 5-min | LOW | ✓ Validated — `WindowedCounter` + 60 tests |
| Edge-only inference, no image/video upload | Privacy baseline for every credible peer; DPIA prerequisite under UK/EU GDPR | LOW | ✓ Validated — privacy-by-design contract enforced by test |
| Public map with street-level visualisation | Telraam, Numina/Boston, Helsinki public map all ship this | MEDIUM | ✓ Validated — MapLibre + local Carto Positron, street-coloured paint |
| Metric toggle (counts vs speed) | Vivacity, Miovision, Helsinki ship both; toggle lets one map serve both narratives | LOW | ✓ Validated — `MetricToggle` component, cividis ramp for speed |
| Class filter (per-class breakdown on click) | Vivacity has 32 sub-classes; users expect "show me just cyclists" | LOW | ✓ Validated — `ClassFilter` + side-panel per-class breakdown |
| Time-window selector (Now / 1h / 24h / 7d) | Standard on every dashboard (Miovision, Helsinki, Telraam) | LOW | ✓ Validated — `TimeWindowPicker` scaffolded |
| Per-street time-series chart | Miovision's core reporting unit; Helsinki open API | MEDIUM | [ ] Active (M2) — `StreetTimeSeries` component exists, needs live data |
| Device health visibility (heartbeat, silent-sensor detection) | Miovision + Telraam both surface device status; required for research-grade reliability | MEDIUM | [ ] Active (M2) — cron skeletons exist (`detect-silent`), admin events page stubbed |
| Admin authentication (not anonymous sensor CRUD) | Every commercial peer + academic norms | MEDIUM | [ ] Active (M2) — Google OAuth + `allowed_members` pending |
| Bearer-token device auth | Standard for HTTPS ingest (CAMINA, all REST-API peers) | LOW | ✓ Validated — `verifyIngestToken`, per-device hash plan in schema |
| Offline buffering on network loss | Any field-deployed sensor loses WiFi; without it, data gaps are unexplainable | MEDIUM | ✓ Validated — WAL-SQLite FIFO `OfflineBuffer` with drop-oldest |
| Daily reconciliation (catch missed windows) | Required for defensible counts in research output | MEDIUM | ✓ Validated — `docs/RECONCILIATION.md` + cron skeleton |
| HTTPS-only transport with TLS | Baseline; unencrypted counts = GDPR red flag even if non-PII | LOW | ✓ Validated — `HttpsPublisher` |
| GDPR data-retention policy (documented + enforced) | Mandated by Art. 5(1)(e); smart-city literature universal | MEDIUM | [ ] Active (M2) — 13-month raw retention in Plan 02 §7, needs cron enforcement |
| Audit log on admin mutations | ICO guidance; smart-city GDPR reviews flag this | LOW | [ ] Active (M2) — `audit_log` table in schema, writer TODO |
| CSV / JSON export of aggregate counts | Telraam, Miovision, Helsinki all provide; researchers expect downloadable data | LOW | [ ] **Not in PROJECT.md Active** — gap; likely table stakes for INTERREG deliverable |
| Signage / data-collection notice at sensor site | ICO CCTV/ANPR guidance requires clear signage; standard smart-city practice | LOW | [ ] **Not in PROJECT.md** — physical-world gap; should be in M2 deployment checklist |
| DPIA (Data Protection Impact Assessment) document | ICO mandates DPIA for any surveillance system before deployment; UCD ethics likely requires it | MEDIUM | [ ] **Not in PROJECT.md** — documentation gap; belongs alongside `RUNBOOK.md` |

### Differentiators (Where CAMINA Can Lead)

Not required for TRL-6, but each one is a credible research or outreach win.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 9 domain-tuned classes including `e-scooter`, `SUV`, `delivery_van` | COCO misses these; Vivacity charges for them; micromobility is the research story | HIGH | ✓ Validated — already trained; documented in PROJECT.md Key Decisions |
| Dual-transport (HTTPS primary + LoRaWAN secondary) | Vivacity/Miovision are WiFi/cellular only; Telraam is WiFi-only. LoRaWAN proves network-poor deployment viability | HIGH | [ ] Active (M1) — payload ≤200 chars, TTN webhook, `LoRaPublisher` |
| Reproducibility: weights + training code + deployment recipe all open | No commercial peer ships this; TU Delft UMO publishes papers but not end-to-end reproducibility | LOW | ✓ Validated — weights in repo, `custom_model_train/`, `docs/sensor_deployment.md`. Differentiator *already earned* |
| Street-level k-sensor guard (hide street if only one covering sensor removed) | Not seen in Telraam/Numina/Vivacity — genuinely novel privacy invariant for v1 | LOW | [ ] Active (M2) — specified in Plan 02 §7, needs implementation in `streets-live.ts` |
| Version-gated hot config reload (no downtime) | Commercial peers require device restart / SSH; we already do it over HTTPS poll | MEDIUM | ✓ Validated — `ConfigPoller` + `config_version` propagation |
| Shareable deep links via URL hash (`#zoom/lat/lon`) | OSM-style; Telraam/Helsinki don't ship this; low-cost outreach win | LOW | ✓ Validated — `useMapHash` |
| Colour-blind-safe metric ramps (viridis/cividis) with admin preview | ICO accessibility + WCAG; most competitor dashboards fail CB testing | LOW | ✓ Validated — pinned in Plan 02 §9-ter; admin CB preview is a fresh idea |
| Mobile-first bottom-sheet UX (full-bleed map, 44×44 targets, 22px hit-line) | Telraam/Miovision are desktop-first; mobile matters for in-field demos to INTERREG partners | MEDIUM | ✓ Validated — Plan 02 §9-bis; scaffolded in `StreetSidePanel` |
| Public CSV/JSON download with street-level granularity and no sensor leak | Helsinki ships open data; commercial peers gate behind API keys. Free + privacy-safe = genuine academic contribution | MEDIUM | [ ] **Not in PROJECT.md Active** — natural M2+ extension |
| Per-class speed breakdown (not just aggregate speed) | Vivacity ships this; most open-source peers don't. Useful for VRU-safety narratives | LOW | ✓ Validated — schema carries per-class `avg_speed_kmh` |
| Dev-mode mock dashboard (full UX without real sensor) | Accelerates admin UX iteration; Vivacity/Miovision have no equivalent public-facing mock | MEDIUM | ✓ Validated — `CAMINA_DATA_SOURCE=mock` + `data/mock/dublin/` |
| Open TRL progression roadmap (TRL-6 → TRL-7 OTA → TRL-8 multi-city) | Academic/INTERREG audiences care about maturation; commercial peers don't publish one | LOW | [ ] Partial — PROJECT.md has Out-of-Scope reasons but no public roadmap artefact |

### Anti-Features (Explicitly NOT For CAMINA)

Features industry often ships but that conflict with CAMINA's privacy-first academic positioning. These are deliberate no-gos, most already listed in `PROJECT.md` Out of Scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Facial recognition of pedestrians | Demographic analytics ("age/gender of crossers") | GDPR Art. 9 special-category data; would require explicit consent per subject; incompatible with edge-only aggregate model; UCD ethics blocker | Count-only classification; if demographic research is needed, run a separate IRB-approved pilot with on-site consent |
| ANPR / license-plate recognition | Vehicle re-identification, enforcement | Plates are personal data under UK/EU GDPR (ICO guidance 2024); triggers DPIA + signage + SAR obligations disproportionate to research value; flagged in PROJECT.md Out of Scope ("Re-identification / cross-camera tracking") | Count-only classification; aggregate anonymous flows |
| Cross-camera re-identification (tracking same individual across sensors) | Origin-destination matrices, dwell-time analytics | Turns aggregate counts into tracking; violates CAMINA's core privacy contract; explicitly in PROJECT.md Out of Scope | Per-sensor aggregates; if OD is needed, do it via survey or Bluetooth MAC-hashing with a separate ethics review |
| Exact sensor GPS in public UI | "Show me where the sensors are" | Inverts the street-vs-sensor invariant that is load-bearing in CAMINA's DPIA narrative; already enforced by privacy regression test | Streets are the public identifier; admin-only GPS remains on the admin page |
| Raw image/video upload to cloud | Post-hoc re-analysis, model retraining, "trust but verify" | Eliminates the "no video leaves the device" privacy claim; explodes bandwidth; forces a DPIA rewrite; Telraam/Numina/Vivacity all avoid this | Edge-only inference; if retraining is needed, capture short opt-in clips in a separate offline pilot |
| ML forecasting / predictive traffic | "Predict tomorrow's congestion" | Out-of-scope per PROJECT.md; TRL-6 demo doesn't need it; false predictions damage research credibility more than their absence hurts | Historical aggregates only; forecasting is a follow-on project with its own paper |
| Anonymous admin access | "Just let team X edit without OAuth" | Violates audit-log accountability; removes traceable consent for GPS edits; PROJECT.md Out of Scope ("Anonymous admin access") | Google OAuth + `allowed_members`; dev-allowlist only locally |
| Short-lived JWT for devices | "Proper modern auth" | Over-engineering for TRL-5/6; opaque Bearer is sufficient for ≤500 devices; rotation via SSH is acceptable at research scale | Opaque Bearer tokens per device (`api_token_hash`); JWT is a TRL-7 concern per PROJECT.md |
| Multi-city support in v1 | "Rollout to Cork/Galway next" | Breaks focus before TRL-6 proof; data model is already city-keyed so v2 is cheap; PROJECT.md Out of Scope | Dublin only in v1; architecture preserves the extension path |
| Mobile native apps (iOS/Android) | "Push notifications, offline mode" | Responsive web is sufficient for research/public-map use cases; app-store review adds drag; PROJECT.md Out of Scope | Responsive web via MapLibre; PWA is a cheap upgrade path if needed |
| Industrial SLAs / 99.9% uptime guarantees | "Municipality wants a contract" | Not a commercial deployment; Vercel Hobby + Neon free tier is the budget; PROJECT.md Out of Scope | Research-grade reliability; `/api/health` + uptime monitor are sufficient |
| Over-the-air model updates | "Ship new YOLO weights remotely" | Security/signing surface too large for TRL-6; physical access is acceptable at n=1; PROJECT.md Out of Scope (TRL-7+) | Manual SSH + `systemctl restart`; model weights in deploy bundle |
| Internationalisation beyond English | "Irish Gaeilge / Portuguese" | Solo researcher, 5-week deadline; Portuguese deferred to v1.1 per PROJECT.md | English only in v1; Next.js i18n wiring stays easy to retrofit |

### Privacy & Ethics Features (GDPR + Academic Table Stakes)

Grouped separately because they are non-negotiable for a UCD-hosted INTERREG-funded deployment but are often overlooked in feature lists.

| Feature | Status | Complexity | Notes |
|---------|--------|------------|-------|
| No raw images/video leave the device (edge-only inference) | ✓ Validated | — | Hard privacy boundary; already enforced by architecture |
| Aggregate-only payloads (counts + avg speed per 15-min window) | ✓ Validated | — | `WindowSnapshot` + `DailySnapshot` schemas |
| Privacy regression test in CI | ✓ Validated | LOW | `tests/` asserts no public API response contains `sensor_id`/`lat`/`lon` |
| Exact sensor GPS never in public UI | ✓ Validated | LOW | Enforced by `StreetSummary` vs `StreetAdminInfo` type split |
| k-sensor guard (hide streets with only one removed-sensor history) | [ ] Active (M2) | MEDIUM | Specified in Plan 02 §7; not yet in `streets-live.ts` |
| Audit log of all admin mutations touching GPS/coverage | [ ] Active (M2) | LOW | Table exists; writer wiring TODO |
| Documented data-retention policy (13-month raw, indefinite aggregates) | [ ] Active (M2) | LOW | Policy in Plan 02 §7; needs public-facing doc + cron enforcement |
| Right-to-erasure handling (SAR workflow) | [ ] **Gap** | LOW | No PII = SAR is a formality; documenting "we hold no personal data" is the correct response but needs to be written down |
| DPIA document (Data Protection Impact Assessment) | [ ] **Gap** | MEDIUM | ICO mandates this before any surveillance deployment; should exist alongside `RUNBOOK.md` before TRL-6 demo goes public |
| Physical signage at sensor site ("CAMINA research sensor — aggregate counts only, no video recorded, contact …") | [ ] **Gap** | LOW | ICO guidance; low-cost, high-credibility; not in PROJECT.md |
| Public privacy statement / data-collection notice on the dashboard | [ ] **Gap** | LOW | `/about` or footer link; standard for open-data portals (Helsinki, Boston/Numina) |
| PII scrubber on Sentry client+server | [ ] Active (M2) | LOW | Listed in Plan 02 §6; double-check no IP or email leaks via stack traces |
| No server→device push / no remote shell / no MQTT broker | ✓ Validated | — | Reduces attack surface; config propagation via device-initiated GET is the deliberate design |
| Bearer tokens hashed in DB (Argon2/bcrypt), never stored raw | [ ] Active (M2) | LOW | Schema has `api_token_hash`; provisioning flow TODO |
| Vercel BotID on sign-in + admin mutations | [ ] Active (M2) | LOW | Defence against automated abuse of `/sign-in` |

## Feature Dependencies

```
Public street map (M0 ✓)
    └──requires──> Mock data source (M0 ✓) OR Live DB (M2)
                       └──requires──> Drizzle schema + migrations (M2)

Live dashboard (M2)
    └──requires──> Neon + PostGIS (M2)
    └──requires──> Google OAuth + allowed_members (M2)
    └──requires──> liveStreetsRepo implementation (M2)

TRL-6 demo (M2 exit)
    └──requires──> End-to-end Pi integration (M1)
                       └──requires──> scripts/run_sensor.py (M1)
                       └──requires──> Inference benchmark (M1)
    └──requires──> Live DB + OAuth (M2)
    └──requires──> Cron implementations (M2)
    └──requires──> DPIA + privacy statement (M2, gap)
    └──requires──> Physical signage (M2, gap)

LoRaWAN path (M1)
    └──requires──> LoRa hardware procurement (M1)
    └──requires──> TTN coverage verified (M1)
    └──requires──> Compact codec ≤200 chars (M1)
    └──requires──> /api/ingest/lora/* decoder (M1)

CSV export (gap → M2+)
    └──requires──> Live DB (M2)
    └──requires──> Rate limit on export endpoint
    └──enhances──> Academic publication / open-data narrative

k-sensor guard (M2, Plan 02 §7)
    └──requires──> sensor_street_coverage history (M2)
    └──enhances──> Privacy story for single-sensor v1 deployment
    └──conflicts──> "Show historical streets even after sensor removed" (would leak sensor-presence signal)

Audit log writer (M2)
    └──requires──> audit_log table (M2 ✓ schema)
    └──requires──> All admin routes to accept actor identity from session
    └──enhances──> DPIA narrative, GDPR accountability

Facial recognition / ANPR (never)
    └──conflicts──> Edge-only aggregate contract
    └──conflicts──> PROJECT.md Out of Scope
    └──conflicts──> UCD ethics baseline
```

### Dependency Notes

- **Public CSV/JSON export requires live DB** — cheap to add once M2 lands; would be a meaningful academic/open-data differentiator. Currently a gap in PROJECT.md Active.
- **k-sensor guard requires coverage history** — must preserve "street X had a sensor once" metadata, not just "does street X have a sensor now", otherwise the add/remove events themselves leak location.
- **DPIA and signage are blocking for public TRL-6 demo** — not software, but if the Pi goes live on a Dublin street, ICO/UCD-ethics will ask for these documents. Treat as M2 deliverables alongside `RUNBOOK.md`.
- **LoRaWAN path blocks on hardware + TTN coverage** — both are procurement-gated, not code-gated. Verify TTN Dublin coverage before writing `LoRaPublisher`.
- **Forecasting conflicts with TRL-6 framing** — adding predictions would force a new validation narrative ("how accurate?") and is explicitly deferred.

## MVP Definition

### Launch With (TRL-6 Demo, 2026-05-31)

Minimum to call the INTERREG deliverable done. Maps directly to PROJECT.md Active M1+M2.

- [x] 9-class fine-tuned YOLO11 model (validated)
- [x] Custom Kalman + Hungarian tracker (validated)
- [x] Windowed counter + daily accumulator + WAL offline buffer (validated, 60 tests)
- [x] HTTPS ingest protocol + reconciliation spec (validated)
- [x] Next.js 16 dashboard scaffold in mock mode (validated)
- [x] Public Dublin map (MapLibre + Carto Positron) with street-level colouring (validated)
- [x] Metric toggle, class filter, time-window selector, side panel (validated)
- [x] Privacy regression test (validated)
- [ ] Production entry point `scripts/run_sensor.py` composing YOLO + tracker + daemon (M1)
- [ ] Pi 5 benchmark + systemd deployment (M1)
- [ ] At least one transport live end-to-end on real hardware (M1 — HTTPS primary)
- [ ] Neon Postgres + PostGIS provisioned, `liveStreetsRepo` implemented (M2)
- [ ] Google OAuth + `allowed_members` live (M2)
- [ ] Admin CRUD for sensors + street coverage (M2)
- [ ] Cron jobs live: refresh-aggregates, detect-silent, reconcile-daily (M2)
- [ ] k-sensor guard implemented (M2, Plan 02 §7)
- [ ] Audit log writer on admin mutations (M2)
- [ ] Retention-enforcement cron (13-month raw) (M2)
- [ ] PII scrubber on Sentry + CSP + BotID on auth (M2)
- [ ] One Pi on one real Dublin street publishing for ≥ 1 week (M2 — the TRL-6 gate)
- [ ] **DPIA document** committed to repo (gap — must add to M2)
- [ ] **Public privacy statement on the dashboard** (gap — must add to M2)
- [ ] **Physical signage at the sensor site** (gap — must add to M2 deployment checklist)

### Add After Validation (v1.1, post-TRL-6)

Low-cost additions that extend the story once the one-sensor demo is live.

- [ ] Public CSV/JSON export of street-level aggregates — trigger: first INTERREG partner asks for data
- [ ] LoRaWAN second transport end-to-end — trigger: M1 hardware lands + TTN coverage confirmed
- [ ] Portuguese localisation — trigger: UCD×Portuguese partner visibility push
- [ ] `/about` page with methodology, classes, accuracy, DPIA link — trigger: any media/outreach
- [ ] Admin colour-blindness preview toggle — trigger: accessibility review
- [ ] Reconciliation-mismatch email/Slack alert — trigger: first real mismatch caught in production
- [ ] Historical backfill UI (view any 7-day window) — trigger: first "show me last month" question

### Future Consideration (v2+)

Deferred until v1 is validated in production. Mostly PROJECT.md Out of Scope.

- [ ] Multi-city support (Cork, Galway) — v2, data model already supports it
- [ ] OTA model updates (TRL-7+)
- [ ] Short-lived JWT for device auth (TRL-7+)
- [ ] Multi-sensor intersections (true TMC-style turning movements) — v2
- [ ] Public API with rate-limited keys (à la Helsinki) — v2
- [ ] Data-space / FAIR-compliant publication to European Traffic Flow Data Space — v2
- [ ] Paper / benchmark artefacts — follow-on milestone per PROJECT.md

## Feature Prioritization Matrix

Scoped to features that are still open or where prioritization decisions remain. Already-validated items are skipped.

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `scripts/run_sensor.py` production entry | HIGH | LOW | P1 |
| Pi 5 inference benchmark + thermal test | HIGH | MEDIUM | P1 |
| Neon + PostGIS + `liveStreetsRepo` | HIGH | MEDIUM | P1 |
| Google OAuth + allowed_members | HIGH | MEDIUM | P1 |
| Admin sensor/coverage CRUD | HIGH | HIGH | P1 |
| Cron: refresh-aggregates, detect-silent, reconcile-daily | HIGH | MEDIUM | P1 |
| k-sensor guard | HIGH | LOW | P1 (privacy-load-bearing) |
| Audit log writer | HIGH | LOW | P1 (GDPR-load-bearing) |
| Retention-enforcement cron | HIGH | LOW | P1 (GDPR-load-bearing) |
| DPIA document + privacy statement + signage | HIGH | LOW | P1 (regulatory-load-bearing) |
| LoRaWAN path (compact codec + publisher + TTN decoder) | MEDIUM | HIGH | P2 (procurement-gated) |
| Public CSV/JSON export | MEDIUM | LOW | P2 |
| PII scrubber + BotID + CSP hardening | HIGH | LOW | P1 |
| Reconciliation-mismatch alerts | MEDIUM | LOW | P2 |
| Admin CB preview toggle | LOW | LOW | P3 |
| Portuguese i18n | LOW | MEDIUM | P3 |
| Historical backfill / long-range view | MEDIUM | MEDIUM | P3 |
| Multi-city support | LOW (v1) / HIGH (v2) | HIGH | P3 |
| OTA model updates | LOW (v1) / MEDIUM (v2) | HIGH | P3 |

**Priority key:**
- P1: Must have for TRL-6 demo by 2026-05-31
- P2: Should have in v1.1 once demo is live
- P3: Nice to have, v2 or later

## Competitor Feature Analysis

| Feature | Telraam | Vivacity | Numina | Miovision | CAMINA (our approach) |
|---------|---------|----------|--------|-----------|-----------------------|
| Classes | ~5 (pedestrian, cyclist, car, heavy vehicle) | 10+ (32 sub-classes) | ~5 (ped, bike, car, truck, bus) | cars/motorcycles/vans/trucks/buses + bike/ped, custom e-scooter | 9 domain-tuned incl. SUV, e-scooter, delivery van |
| Accuracy | High (AI-on-device, citizen-hosted) | 97% (TfL-validated) | 95%+ accuracy claim | 95+% visual-inspected | Target: ≥90% field accuracy, to be benchmarked in M1 |
| Aggregation window | 15 min | Real-time + 15 min rollups | 15 min | 15 min | 15 min (matches industry default) |
| Speed measurement | Yes | Yes, per class | No (pedestrian-focused) | Yes | Yes, per class (schema supports `avg_speed_kmh`) |
| Privacy posture | Edge-only, no video upload, 15-min aggregates | Edge-only, on-site processing | Edge-only, "onboard compute pre-process then erase imagery" | Edge-only, no images retained per GDPR | Edge-only, privacy regression test, k-sensor guard |
| Public map | Yes, per-device map | No (enterprise dashboard) | Partial (city-specific, e.g. Boston) | Yes (city-hosted, e.g. Cambridge MA) | Yes, street-coloured (not sensor-marker) |
| Data export | CSV + open API | Enterprise API | API + city open-data portal | API + dashboard | Planned: CSV/JSON, not in M1/M2 yet |
| Admin auth | Yes (per-device account) | Enterprise SSO | Enterprise SSO | Enterprise | Google OAuth + allowlist |
| Open source / reproducible | Partial (API open, hardware+model closed) | Closed | Closed | Closed | Fully open (weights, training code, deployment) |
| Hardware | Proprietary S2 unit with low-res camera | Proprietary sensor | Proprietary sensor | Proprietary Scout/Core | Off-the-shelf Pi 5 8GB + camera |
| Transport | Cellular (built-in mobile data) | Cellular / WiFi | Cellular | Cellular | HTTPS primary + LoRaWAN secondary (novel) |
| Near-miss / safety analytics | No | Yes (3D PET analysis) | Limited (desire lines) | Limited | Not in v1 (out of scope); v2+ candidate |
| ANPR / re-identification | No | No (explicit privacy) | No | No | No (explicit PROJECT.md Out of Scope) |
| Facial recognition | No | No | No | No | No (explicit anti-feature) |
| Forecasting | No | Partial (traffic control) | No | Yes (signal optimization) | No (PROJECT.md Out of Scope) |
| Citizen-hosting model | Yes (signature feature) | No | No | No | No — academic/municipal only in v1 |
| Deployment scale | ~3000+ devices globally | City-wide deployments | Dozens per city | Intersection-dense | One sensor, one street (TRL-6) |

**Takeaways:**
- CAMINA is **not** trying to out-feature commercial peers. Scope is deliberately narrower (n=1 vs n=thousands).
- Credible differentiators: **open reproducibility**, **dual-transport including LoRaWAN**, **domain-tuned 9 classes with e-scooter + SUV + delivery van**, **k-sensor privacy guard**, **Uber-monochrome design language applied to smart-city data**.
- Feature gaps vs peers that are acceptable for v1: no near-miss analytics, no forecasting, no multi-sensor TMC, no cellular, no mobile app.
- Feature gaps vs peers that are **not** acceptable for v1 (should be added): **public CSV export**, **DPIA + privacy statement + signage**, **audit-log writer wired to admin routes**, **retention-enforcement cron**.

## Sources

Competitor / industry research:
- [Telraam — Privacy-friendly edge AI traffic counter](https://telraam.net/en/our-traffic-counter) — 15-min aggregates, edge-only inference, low-res camera, open API
- [Telraam Network dashboard](https://telraam.net/,/network) — public map, per-segment KPIs, data export
- [Vivacity Labs — 10+ classes, 97% accuracy (TfL-validated), near-miss, per-class speed](https://vivacitylabs.com/technology/sensors/)
- [Vivacity brochure — sensor capabilities including e-scooter detection](https://info.vivacitylabs.com/vivacity-traffic-sensor-technology-info)
- [Numina — pedestrian/bike/car/truck/bus classification, desire lines, privacy-first onboard compute](https://numina.co/)
- [Numina privacy philosophy — no imagery retained, aggregate-only datasets](https://numina.co/our-privacy-principles/)
- [Numina in Boston — municipal deployment example](https://www.boston.gov/departments/new-urban-mechanics/numina-street-sensors)
- [Miovision — multimodal intersection counts, 15-min increments, custom e-scooter class](https://miovision.com/solutions/traffic-detection-management/)
- [Miovision Scout — traffic studies with TMCs/ATRs/classification](https://miovision.com/scout-plus/traffic-studies/)
- [Helsinki Region Infoshare — traffic counter open data, 5-min API](https://hri.fi/data/en_GB/dataset/liikennemaarat-helsingissa)
- [TU Delft Urban Mobility Observatory — cameras/radar/LIDAR, campus digital twin, moving-dot privacy](https://www.tudelft.nl/en/urban-mobility)
- [TU Delft UMO portal publication](https://research.tudelft.nl/en/publications/urban-mobility-observatory)
- [Open traffic data collection (GraphHopper curated list)](https://github.com/graphhopper/open-traffic-collection)
- [Open-source Pi traffic counters (rmcqueen, rpi-urban-mobility-tracker, Qengineering)](https://github.com/nathanrooy/rpi-urban-mobility-tracker)
- [Real-Time Traffic Data Analysis on Resource-Constrained Edge Devices (MDPI 2025)](https://www.mdpi.com/2079-9292/15/8/1703)

Privacy / GDPR / academic sources:
- [ICO guidance on ANPR as personal data processing](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/cctv-and-video-surveillance/guidance-on-video-surveillance-including-cctv/additional-considerations-for-technologies-other-than-cctv/automatic-number-plate-recognition-anpr/)
- [UK GOV National ANPR Service DPIA — template for surveillance-system DPIA content](https://www.gov.uk/government/publications/national-anpr-service-data-protection-impact-assessment/national-anpr-service-data-protection-impact-assessment-accessible)
- [MDPI Sensors — Data Protection by Design in Smart Cities](https://www.mdpi.com/1424-8220/21/21/7154)
- [MDPI Sensors — Automated GDPR Compliance Verification Framework](https://www.mdpi.com/1424-8220/22/7/2763)
- [Plate Recognizer — GDPR compliance for ANPR (industry perspective on personal-data classification)](https://platerecognizer.com/gdpr-compliance-for-anpr/)

CAMINA project artefacts (read and cross-referenced):
- `/Users/tamagusko/repos/camina/.planning/PROJECT.md`
- `/Users/tamagusko/repos/camina/.planning/codebase/ARCHITECTURE.md`
- `/Users/tamagusko/repos/camina/DESIGN.md`
- `/Users/tamagusko/repos/camina/plan/02-dashboard-vercel.md`

---
*Feature research for: Privacy-first edge-CV traffic-sensor network (CAMINA)*
*Researched: 2026-04-23*
