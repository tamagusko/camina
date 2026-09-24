# CAMINA plan

```
Version: 2.1 — 2026-09-15 — decisions D1–D13 recorded by the PI; 2.0 superseded old/2026-09-15-gsd/ROADMAP.md, old/2026-09-15-gsd/REQUIREMENTS.md
Provenance: Opus — code audit, E2E run, claim extraction, decision integration (v2.1). Sonnet — planning inventory, file writes. Fable — verdicts, plan design, adjudication.
Bar: TRA 2026 paper + slides (audit-2026-09-15/AUDIT.md Appendix, claims §4). Repo-only additions are marked "repo-only".
```

## 0. Design principles

- Two milestones, dependency-ordered, minimal stage count. **M1** = one Pi on one real Dublin street counting nine classes (with direction and speed) into a live public dashboard, measured against manual ground truth. **M2** = 5–10 units provisionable and maintainable by someone other than the author, managed through a full admin console.
- Cheapest unblockers first: the model bring-up is a remap, not a retrain; CI before any further feature work; live read path and provisioning before any hardware time is spent.
- Solo developer; Vercel Hobby + Neon free; privacy non-negotiable (counts only, no frames, no GPS in public responses, k_min = 5 applied to counts **and** speeds).
- Every stage has a done-test that is a command, a measurement, or a field observation with a threshold. A stage without a passing done-test is not done, whatever the code looks like.
- **Retrain is not in M1.** The paper's model exists (TRA2026 branch) and is the artefact the paper describes; no corpus on any branch has ≥ 500 instances of truck or delivery van (main: 0/0; dev_expanded_dataset: 19/28 (truck/van); paper corpus: 132/112, not in repo). Retraining before a field measurement exists is optimising blind. Retrain is the M2 quality track (S13), gated on the count-level metric that S7/S9 produce. Overrule condition: if S6 shows the TRA2026 model is unusable on the real camera view (e.g. person AP collapses at the install angle), S13 pulls forward — but that is evidence, not assumption.

## 1. Milestone M1 — First fully functional unit (target 2026-12-31, D12)

| ID | Stage | Why here (dependency) | Deliverable | Done-test (pass threshold) | Effort | Prereqs | Closes |
|---|---|---|---|---|---|---|---|
| **S1** | Paper model on main | Nothing downstream runs without a loadable 9-class model (`dryrun.log`) | `models/camina_v1_yolo11n_ncnn/` (bin+param+metadata from `origin/TRA2026:model/raspberry_pi_deployment_all/yolo11n_ncnn/`, ~10 MB — decide git vs release asset); `detect_track.py` guard becomes **name-based remap** via `class_mapping.yaml` (alphabetical model index → canonical index; `motorcycle`→`motorcyclist`); `sensor.yaml` `imgsz: 640`, model path updated; `ncnn` added to `requirements.txt`; `export_ncnn.py` imgsz check becomes an error | `scripts/run_sensor.py --config configs/sensor.yaml --dry-run` exits 0; parity probe on `custom_model_train/test_images` at NCNN@640 gives ≤ 30 dets/img and matches class names; new unit test for the remap; `pytest` green (≥ 144) | **1 day** | none | AUDIT.md §1 detector rows; audit runs #12 #13 #18; integration mismatches #7 (class list), #8 (imgsz) |
| **S2** | CI gate | Everything after this is a change to a repo with no gate; fixtures are gitignored so tests only pass by hand | `.github/workflows/ci.yml`: `uv` + pytest; pnpm install, `python scripts/generate_mock_dublin.py` (or a committed minimal fixture), `vitest`, `tsc`, `CAMINA_DATA_SOURCE=mock pnpm build`; fix/remove `lint` script (Next 16); privacy regression is part of the job | Green run on a PR; a deliberately broken assertion turns it red; `README` badge | **0.5–1 day** | none | G-d; audit #10; `dashboard/README.md:70` "enforced in CI" becomes true |
| **S3** | Config handshake (repo-only, cheap) | The poller and persist path exist and are claimed in README; small server fix | Routes return the *server's* `sensors.config_version` (mock: constant); poller persist writes to `state.db`; `_apply_config` handles or drops `frame_skip`/`min_track_hits`/`detection_zone` explicitly; server-side zod for `/config` response | e2e probe (`audit-2026-09-15/evidence/e2e_chain_mov.py`) reports `applied=1` after a version bump; vitest for the three routes | **0.5–1 day** | none | G-b; integration mismatches #1 (config handshake), #5 (config schema) |
| **S4** | Live data path | Second hard break (G-a) + provisioning (G-c); must exist before any hardware time is spent so the bench posts somewhere real | `drizzle/migrations/meta/_journal.json` generated and applied; `streets-live.ts` implements all 5 methods with k_min = 5 and no `sensor_id`/GPS; `scripts/provision-sensor.ts` (insert sensor + street coverage + SHA-256 token hash, prints the token once — the M1 bootstrap; the S11 console replaces it for day-to-day use, D5); replay window aligned (server accepts ≥ 10 days or edge caps outbox at 7); speed fields carried end-to-end and **suppressed together with counts below k_min** in both mock and live adapters (closes the speed side-channel, `streets-mock.ts:134-143`; D2) | Against local Postgres+PostGIS (docker) **and** Neon: `db:migrate` → `provision-sensor` → POST the captured edge bodies (`audit-2026-09-15/evidence/e2e_out/captured_requests.json`) with the token → `GET /api/streets`, `/api/streets/[id]/readings`, `/api/metrics` return those counts; `privacy-regression.test.ts` runs against the live adapter (PRIV-04) and asserts no speed value is returned for class counts 1–4 | **3–5 days** | Docker or a Neon dev branch | DATA-02/05/06/09, SEC-04, PRIV-04, integration mismatch #9 (replay window), chain links 11–12 |
| **S5** | Production deploy (live mode, OAuth on) | Bench (S6) and field (S8) need a real endpoint; accounts have lead time; D6 requires login before go-live | Vercel project (Hobby) + Neon (Marketplace) + PMTiles; env from a completed `.env.example`; `CAMINA_DATA_SOURCE=live`; **Google OAuth (UCD Workspace internal app) with DB-backed allowlist gating all `/admin` routes (D6)**; GH cron secrets set; headers verified | Public URL renders the Dublin map with the provisioned street; `curl` a counts body with the real token → visible on the map within one poll interval; `/api/health` 200; `cron.yml` runs once green; allowlisted account signs in to `/admin`, a non-allowlisted account is refused, unauthenticated `/admin` redirects to sign-in | **3–5 days** + account lead time | Vercel, Neon, Protomaps accounts; **UCD Google OAuth app (IT request — start now)**; domain (`camina.ucd.ie` in `sensor.yaml:7` — confirm or change) | DEPLOY-01/02, DATA-01, SEC-02/03, AUTH-01..03 |
| **S6** | Pi bench bring-up | First hardware run ever recorded; salvaged 01-02/01-03 gates (Appendix B) | Pi 5 8 GB + Active Cooler + Camera Module 3, state on SD card (D10); `docs/sensor_deployment.md` §8–§10 (install: apt `picamera2`, venv with `ncnn`, unit file, `SupplementaryGroups=video`, `YOLO_CONFIG_DIR` under `/var/lib/camina`); `scripts/bench_sensor.py` (from 01-02: FPS inst.+1-min rolling, temp, RSS, `get_throttled` at start/mid/end, JSON+MD report); heartbeat enrichment (temp/throttle/RSS, from 01-04) | (a) 30-min in-enclosure bench: **FPS ≥ 5 end-to-end at 640**; also run the paper's inference-only protocol (3 validation images × 20 cycles, NCNN@640, TRA 2026 §3.2) and record ms/img — supports or refutes claim C37 (15 FPS); neither TRA2026 benchmark script implements that protocol; `get_throttled == 0x0`; report committed to `docs/benchmarks/`; (b) `kill -9` → systemd restart ≤ 60 s, buffer drains, no duplicate rows (idempotent upsert); (c) 15-min real-publisher smoke: rows appear on the S5 dashboard; (d) 24-h bench soak, RSS flat ±10 %, zero restarts | **2–3 days** (+ hardware on hand) | Pi 5, cooler, camera, PSU, SD card | EDGE-02..07, C06/C37 evidence, deployment-gap rows (permissions, thermal, clock) |
| **S7** | Counting semantics + ground-truth protocol | The paper promises "counting" and "flows"; nothing has ever been compared to truth; the protocol must exist before the field week | Single virtual screenline with direction (A→B / B→A) per sensor, configurable via `detection_zone`-style config (D3); window boundary no longer double-counts; `docs/evaluation_plan.md` ground-truth protocol: 2 × 15-min manual counts per class and direction (observer on site or a reference clip recorded on a *separate* device and deleted after scoring; the Pi never stores frames) | On the reference clip: per-class absolute error ≤ 20 % for classes with ≥ 20 true instances, and ≤ 5 counts for rarer classes (proposed thresholds — confirm before S9); unit tests for screenline crossing and direction; e2e chain still green | **2–3 days** | S1 | C02/C46/C47; counter gap (AUDIT.md §1 row 1) |
| **S7b** | Speed estimation (D2) | Dashboard publishes speed; D2 chose to implement it; needs the S7 screenline geometry and must be calibrated before the field install | Per-site calibration method chosen and documented in `docs/CALIBRATION_SETUP.md` (two lines at a measured road distance, or a road-plane homography from ≥ 4 surveyed points; the existing `utils/calibration.py` depth path is unverified and only kept if it beats both); per-track speed from calibrated crossing timing; per-class `avg_speed_kmh` in the counts body; privacy suppression shared with S4 | On ≥ 20 vehicles with a reference speed (radar gun or timed passes over a measured baseline): mean absolute error ≤ 5 km/h and 90th percentile ≤ 10 km/h (proposed thresholds — confirm before S9); calibration reproducible from the doc in ≤ 60 min per site; unit tests for speed from crossing timestamps; payload still passes dashboard zod | **1–2 weeks** | S7; reference speed source (radar gun or measured baseline) | integration mismatch #10 (no speed producer); D2 |
| **S8** | Field install | The paper bar is a *real street*; needs site, power, consent, signage | Site + host agreement (mains power, WiFi or 4G); enclosure (3D-printed case per slide 12 / C12, or off-the-shelf IP54 box); mounting height/angle documented; site speed calibration per S7b; **DPIA-lite (2 pages) + public privacy statement page + on-site signage** (PRIV-01..03, D9); `docs/HARDWARE.md` BOM with real prices — the only unit-cost figure the project quotes (D7); cold-spare SD image | Unit boots unattended after a power cut, heartbeats for 24 h with no throttle bits, appears on the public map; calibration record committed; signage photographed; DPO/ethics sign-off filed | **2–4 days effort; 2–6 weeks calendar** | UCD DPO/ethics contact (open since 04-23), host site, enclosure, SIM if 4G | C12, C14, C52, C60, PRIV-01..03, deployment gaps |
| **S9** | M1 acceptance: 7-day live soak + ground truth | Defines "fully functional" | Public dashboard shows 7 consecutive days of counts and speeds for the street; ground-truth sessions per S7 and S7b run on site; 30-min WiFi outage drill (DEMO-05); short deliverable README with live link, screenshot and funding line "REALLOCATE (EU grant 101103924)" (D11) | Heartbeat gaps ≤ 2 intervals total over 7 days; zero unplanned restarts (watchdog restarts logged and ≤ 2); RSS flat ±10 %; outage drill: no loss, no duplicates; count thresholds from S7 met on ≥ 2 sessions; speed thresholds from S7b met on ≥ 1 session; **all measured, committed under `docs/benchmarks/`** | **1 day effort + 7 days calendar** | S5–S8 | DEMO-01/02/05/06, EDGE-08 |

**M1 critical path:** S1 → S4 → S5 → S6 → S8 → S9, with **S7 → S7b required before S8** (the site is calibrated at install). S2 and S3 run in parallel with S4/S5. Start the DPO/ethics contact, the host site and the UCD OAuth app request on day one — they are the long pole, not the code.

**M1 effort total:** ~25–33 developer-days (v2.0 estimate 15–20, plus OAuth in S5 and speed in S7b). Calendar from 2026-09-15 to the D12 target 2026-12-31 is ~15 weeks, which holds only if the S5/S8 prerequisites start this week.

## 2. Milestone M2 — Deployment-ready fleet (5–10 units, D4)

| ID | Stage | Why here | Deliverable | Done-test | Effort | Prereqs | Closes |
|---|---|---|---|---|---|---|---|
| **S10** | Provisioning for non-authors | The citizen-led model (C03/C04) needs someone else to build a unit | `scripts/provision_pi.sh` (or SD image build) that takes sensor id + token + WiFi and yields a booting unit; `docs/RUNBOOK.md` (rollback, swap, token rotation, migration, cron debugging); `docs/HARDWARE.md` assembly guide; cold spare bench-tested | A second person builds unit #2 from the docs in ≤ 2 h without author intervention and it appears on the dashboard | 3–5 days | S9 | DEPLOY-04, DEMO-03, C03/C04 |
| **S11** | Full admin console (D5) | Operators other than the author must register, map and manage sensors without the CLI | ADMIN-01..07 on top of the S5 OAuth: sensor register/edit, token issue and rotation from the UI, street drawing tool, config editor with version bump, members/allowlist management, audit log view, events view (fed by S12 reconciliation) | A non-author registers a sensor, draws its street, issues a token, and the unit posts successfully without the CLI; a config bump is applied within one publish cycle (heartbeat shows the new version); every admin mutation appears in the audit log; a removed member loses access on the next request | **2–3 weeks** | S5, S3; S12 for the events view | ADMIN-01..07, OBS-07 |
| **S12** | Ops: crons live + alerts | Silent sensors must be noticed by a human; the admin events view needs reconciliation data | detect-silent → e-mail/Slack alert; retention + refresh verified on Neon; `reconcile-daily` **implemented** (feeds the S11 events view, `docs/RECONCILIATION.md`); uptime ping on `/api/health`; Neon usage check | Unplug a unit → stale styling within 2 heartbeat intervals **and** an alert arrives; a seeded daily/window mismatch appears in `/admin/events`; retention deletes rows > 90 d on Neon; Neon CU/storage within free tier at 10 units | 2–3 days | S5 | CRON-01..04, OBS-06, DEMO-04 |
| **S13** | Model quality track (parallel; can start once S9 clips exist) | Truck/van AP ≈ 0.11 (C35) will show up as count error; the paper lists this as future work (C62/C63) | Corpus per D8b: merge Roboflow v3 (paper, frozen as the comparison reference) with `dev_expanded_dataset` + relabel guide (TODO.md relabel block) → ≥ 500 inst/class where feasible; frozen holdout; retrain YOLO11n; NCNN parity at 640; **count-level metric** on S7/S9 reference clips; promotion pipeline | Per-class AP50 on the frozen holdout ≥ TRA Table 1 for every class **and** count error on the reference clips ≤ M1 baseline; NCNN@640 parity within ±1 det/img on test images | 1–2 weeks (+ labelling time) | GPU host, Roboflow v3 export | C62, C63, C35 weak classes |
| **S14** | Fleet scale-up to 5–10 + optional LoRa | The slides' 10+/50+, re-baselined by D4 | 5–10 units provisioned via S10 and managed in S11; per-unit ground-truth and speed spot check; optional: LoRa transport (D1 — needs radio, TTN app, sensor-id format fix, `Publisher` abstraction), CSV open data (PRIV-05) | 5–10 units on the dashboard for 7 days; Neon within free tier; each unit has one passed ground-truth session | 1 week effort + procurement (+1–2 weeks if LoRa is taken up) | S10–S12 | C58, C61 (re-baselined) |

**M2 critical path:** S10 → S14, with S11 (the longest M2 stage) and S12 in parallel; S13 fully parallel and gated by evidence, not by calendar.

## 3. Decisions (recorded 2026-09-15)

| ID | Decision | Chosen | Consequence in this plan |
|---|---|---|---|
| **D1** | LoRaWAN | M2 optional | Codec + webhook stay tested prototypes; LoRa only enters via S14; EDGE-09 closed for M1 |
| **D2** | Speed estimation | **Implement** (against the hide recommendation) | New M1 stage S7b (+1–2 weeks); speeds suppressed with counts below k_min (S4); speed checked in S9 |
| **D3** | Counting method | Screenline + direction | S7; ground truth counted per class and direction |
| **D4** | Fleet target | M1 = 1 unit, M2 = 5–10 units | Slides' Jun/Sep 2026 targets recorded as missed; "pilot network" wording |
| **D5** | Admin console vs CLI | **Full admin console** (against the CLI recommendation) | ADMIN-01..07 carried into S11 (2–3 weeks); S4 CLI kept only as the M1 bootstrap; `reconcile-daily` implemented in S12 |
| **D6** | Auth scope for M1 | **OAuth before the first deploy** (against the defer recommendation) | AUTH-01..03 move into S5 (+2–3 days); UCD OAuth app request is an M1 prerequisite |
| **D7** | Unit cost claim | Publish a BOM and quote that | `docs/HARDWARE.md` in S8; neither €100 nor €250 is repeated until then |
| **D8** | Dublin-only; canonical dataset | Dublin kept; dataset = merge with Roboflow v3 as reference | S13; `all_camina_classes/` on main (6 classes with instances) is never called the 9-class dataset |
| **D9** | Privacy artefacts for S8 | DPIA-lite + privacy statement + signage | S8 prerequisite; start the DPO contact now |
| **D10** | State storage | SD card for M1 | USB-SSD only if S6/S9 show corruption |
| **D11** | Funding wording | REALLOCATE (EU grant 101103924) | INTERREG removed from live repo docs on 2026-09-15; dated research snapshots and archives unchanged |
| **D12** | M1 date | 2026-12-31 | TRL-6 2026-05-31 recorded as missed in STATE.md |
| **D13** | Paper errata | Fix in the next paper, no erratum | Report corrected Table 1 mean/percentages and the v10n run there; not a code stage |

## 4. Closed on 2026-09-15 (PI decision)

| Item | Basis |
|---|---|
| EDGE-09 Publisher abstraction (for M1) | D1 — reopens inside S14 only if LoRa is taken up |
| OBS-01..05 (Sentry, Speed Insights, Analytics, log wrapper) | Closed as a group; uptime ping and alerts remain in S12 |
| SEC-01 BotID, DEPLOY-03 Rolling Releases (not on Hobby), DEPLOY-05 | Closed as a group |
| DATA-07 grep rule, DATA-09 Dockerised DB parity (replaced by the S4 live contract test), PRIV-05 CSV export in M1 (optional in S14) | Closed as a group |
| 17-byte LoRa spec, Python 3.11 upgrade, cacheComponents/Suspense polish, conflict-zone analytics (C65) | Closed as a group |
| The 2026-05-15 / 2026-05-31 dates | D12 |
| The GSD workflow | Superseded by v2.0 at the PI's request |

Not closed: ADMIN-01..07 (reinstated by D5 → S11).

## Appendix A — REQ-ID crosswalk

Source: planning review (`audit-2026-09-15/AUDIT.md` §7), updated with the 2026-09-15 decisions. DONE = evidence on main. DEAD = closed 2026-09-15 (§4).

| REQ | Disposition | Evidence / new stage |
|---|---|---|
| EDGE-01 | **DONE (code) / BROKEN (data)** | `run_sensor.py` + compose exist (old/…/01-01); cannot start on the shipped model (`dryrun.log`) → the data half is **S1** |
| EDGE-02 | DONE (code), UNVERIFIED (hardware) | `camera.py` picamera2 RGB888; verify in **S6** |
| EDGE-03, EDGE-04 | CARRIED → **S6** | 30-min bench + Active Cooler + temp/throttle in heartbeat (01-02 done-tests) |
| EDGE-05 | CARRIED → **S6**; USB-SSD not required for M1 (D10) | `sqlite_integrity.py` exists; SSD never mounted |
| EDGE-06, EDGE-07 | DONE (code: unit L6,13-14; `systemd_notify.py`; server skew `ingest-store.ts:26`) | drill in **S6** |
| EDGE-08 | CARRIED → **S9** (7-day on-street soak replaces 48-h bench soak; a 24-h bench pre-check in S6) | — |
| EDGE-09 | **DEAD for M1 (D1)** | reopens in S14 only if LoRa is taken up |
| LORA-01 | DONE (as 20-byte v2, `lora_codec.py`, `docs/lora.md`) | superseded spec (17-byte) closed |
| LORA-02 | PARTIAL (round-trip tests exist, no hypothesis/fast-check, no CI) | → **S14** if LoRa is taken up (D1) |
| LORA-03, LORA-04, LORA-05, LORA-07, LORA-08 | CARRIED → **S14 optional (D1)** | no radio, no TTN app, id-format conflict |
| LORA-06 | DONE (mock) | `uplink/route.ts`, 8 tests; sensor-id mapping defect remains |
| SIM-01..07 | **DONE** | `generate_mock_dublin.py` 8 sensors (#7), k-anon edge case in privacy tests, `docs/simulation.md` (17-byte note stale) |
| DATA-01 | CARRIED → **S5** (Neon account) | — |
| DATA-02 | PARTIAL → **S4** (migrations exist, journal missing, never applied) | — |
| DATA-03 | DONE | `schema.ts:96-107` cascade (07-10) |
| DATA-04 | DONE (schema) | MV without sensor_id; unverified live → S4 |
| DATA-05 | **CARRIED → S4** (the stub, G-a) | — |
| DATA-06 | DONE mock / CARRIED live → **S4** | — |
| DATA-07 | **DEAD** | closed 2026-09-15 |
| DATA-08 | DONE | `db.ts:33` |
| DATA-09 | **DEAD** | replaced by one live contract test in **S4** |
| AUTH-01, AUTH-02, AUTH-03 | CARRIED → **S5** (D6) | env allowlist only today |
| AUTH-04, AUTH-05, AUTH-06 | DONE | `fail-closed.test.ts` 13; public map ungated |
| ADMIN-01..07 | **CARRIED → S11** full console (D5); **S4** CLI as the M1 bootstrap | stubs only |
| ADMIN-08 | DONE | `next.config.mjs:6-15` |
| CRON-01 | DONE (code, piggyback + GH cron), UNVERIFIED live → **S12** | — |
| CRON-02 | PARTIAL (logs only) → **S12** | — |
| CRON-03 | STUB (501) → **S12** (implement; feeds the S11 events view) | — |
| CRON-04 | DONE (code, 90 d not 13 mo; `retention.test.ts`) → verify live **S12** | — |
| CRON-05 | DONE (advisory lock) | — |
| SEC-01 (BotID) | **DEAD** | closed 2026-09-15 |
| SEC-02 | PARTIAL (`vercel.ts` headers) → verify in **S5** | — |
| SEC-03 | DONE (env-gated) → enable in **S5** if Upstash account | — |
| SEC-04 | PARTIAL (hash lookup exists, issuance missing) → **S4** | — |
| SEC-05 | DONE (ingest); `reconcile-daily` 501 remains (CRON-03) | — |
| SEC-06 | DONE | CLAUDE.md note |
| OBS-01..05 | **DEAD** | closed 2026-09-15 |
| OBS-06 | CARRIED → **S12** (uptime ping) | — |
| OBS-07 | CARRIED → **S11** (fleet health in the console) | — |
| DEPLOY-01, DEPLOY-02 | CARRIED → **S5** | — |
| DEPLOY-03 (Rolling Releases) | **DEAD** | closed 2026-09-15 (not on Hobby) |
| DEPLOY-04 (RUNBOOK) | CARRIED → **S10** | — |
| DEPLOY-05 | **DEAD** | closed 2026-09-15 |
| PRIV-01, PRIV-02, PRIV-03 | CARRIED → **S8** (DPIA-lite + statement + signage, D9) | — |
| PRIV-04 | CARRIED → **S4** (privacy regression against live adapter, incl. speed suppression) | — |
| PRIV-05 | **DEAD for M1**; **S14** optional | — |
| DEMO-01, DEMO-02, DEMO-05 | CARRIED → **S9** | — |
| DEMO-03 (cold spare) | CARRIED → **S10** | — |
| DEMO-04 | CARRIED → **S12** (needs reconcile-daily) | — |
| DEMO-06 | CARRIED → **S9** (deliverable README, REALLOCATE funding line) | — |

## Appendix B — Salvaged done-tests

Source files live in `old/2026-09-15-gsd/phases/01-edge-baseline-on-pi/` (never executed; read-only history).

| Salvaged into | Done-test | Source |
|---|---|---|
| S6(a) | 30-min in-enclosure bench: FPS instantaneous + 1-min rolling, core temp, RSS, `vcgencmd get_throttled` at start/mid/end; pass FPS ≥ 5, throttled == 0x0 | `old/2026-09-15-gsd/phases/01-edge-baseline-on-pi/01-02-PLAN.md:19-23,56` |
| S6(c) | 15-min real-publisher smoke against a live dashboard | `old/2026-09-15-gsd/phases/01-edge-baseline-on-pi/01-02-PLAN.md` (Task 4) |
| S6(b) | `kill -9` → systemd restart ≤ 60 s, buffer drains on boot; SD-corruption rehearsal | `old/2026-09-15-gsd/phases/01-edge-baseline-on-pi/01-03-PLAN.md:38,780,696` |
| S6 | Heartbeat enrichment: temp/throttle/RSS in every heartbeat payload | `old/2026-09-15-gsd/phases/01-edge-baseline-on-pi/01-04-PLAN.md:62` |
| S9 | Extended soak (48 h → 7 days on-street): RSS flat ±10 %, zero unplanned restarts, no throttle bits; `kill -9` drill sequenced before the clean window; `soak_monitor.py` | `old/2026-09-15-gsd/phases/01-edge-baseline-on-pi/01-04-PLAN.md:30-32,62` |
