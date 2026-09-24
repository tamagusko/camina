# CAMINA — code maturity audit and claims-vs-code matrix

```
Version: 1.0 — 2026-09-15
Provenance: Opus — code audit (§2, §5, §7 command log), E2E run, claims extraction (Appendix). Sonnet — planning inventory (§7). Fable — independent gate (§1, §3, §4, §6, corrections below), verdicts.
Bar: the TRA 2026 paper + slides (`bkp/TRA_2026_paper_896_adjusted_final.pdf`, `bkp/TRA_2026_896.pdf` — gitignored, local-only). See Appendix for the full claims table.
```

This is the state report of record for the 2026-09-15 planning rebuild. `PLAN.md` is the forward-looking plan; this document is the backward-looking evidence it is built on. Nothing in the repository was modified to produce it. Scratchpad paths from the original audit run have been replaced below with durable copies under `audit-2026-09-15/evidence/` where the file was small enough to retain (see `evidence/README.md`); anything not copied is marked **(scratch, not retained)**.

> **Decisions taken after this audit:** the PI resolved D1–D13 and the proposed closures on 2026-09-15 (see `../PLAN.md` §3–§4). This file stays a dated snapshot; where it says "DECISION" or "pending", the outcome is in `PLAN.md`.

## 0. Gate corrections (read first)

An independent gate (Fable) spot-checked the code audit and claims extraction against primary sources before this document was assembled. Six corrections apply throughout the sections below; they are not repeated inline everywhere, so read them once:

1. **Model status.** Code-audit §5 below (and its "no canonical 9-class CAMINAv1 weights" framing) is true for `main` only — it did not look at branches. The paper's 9-class YOLO11n NCNN (bin+param, imgsz 640) **is tracked on `origin/TRA2026`** (`model/raspberry_pi_deployment_all/yolo11n_ncnn/`, 10,503,980-byte `.bin`, `.param`, `metadata.yaml`; 88 commits not on `main`, merge-base `c383fa5`). This is the single most consequential fact for `PLAN.md`: the model does not need to be trained, it needs to be brought to `main` with a class-index remap (S1).
2. **YOLO10n.** Appendix claim D2 ("YOLO10n results are missing everywhere") is only half true: the v10n *training run exists* on `origin/TRA2026` (`model/yolo_comparison/YOLOv10n/train/results.csv`, best mAP50 0.540 at epoch 120). The paper names four variants in prose/figures but reports results for three. The run was not lost, it was under-reported — see §6.
3. **Benchmark protocol.** Neither `raspberry_pi_inference_test.py` (10 runs/image, 3 warm-ups) nor `benchmark_inference_simple.py` (50 iterations on a synthetic image) implements the paper's stated protocol (3 validation images × 20 inference cycles, C38). The 15 FPS / 64.9 ms figure has no artefact **and** no exact matching script in the repo. Re-measure end-to-end in S6, using the paper's protocol as one of the two measurements taken (see `PLAN.md` S6 done-test).
4. **Dependabot.** No `dependabot.yml` exists; what is active is GitHub's own security-update PRs (9 `origin/dependabot/*` branches). The open TODO item (version-update automation) is still open, low value.
5. **Phase 01-03 (GSD).** The GSD plan was never executed as a plan, but the *code* it specified (notify/watchdog, NTP gate, `sqlite_integrity.py`) was delivered 2026-07-10 outside GSD. What is still missing is the drill (`kill -9` → restart ≤ 60 s) and the USB-SSD step — neither has been run. Salvaged into `PLAN.md` S6 (Appendix B there).
6. All other load-bearing claims in the three source drafts (code audit, claims extraction, planning inventory) held under the gate: edge test count 144, vitest 89, typecheck/build green are accepted as run evidence.

---

## 1. Code maturity inventory (condensed)

Verdict scale: WORKS (ran, evidence) / PARTIAL / STUB / MISSING / UNVERIFIED (needs hardware, DB or account not available on the dev host).

| Component | Verdict | Evidence | Gap |
|---|---|---|---|
| Edge core: WindowedCounter, DailyAccumulator | **WORKS** | pytest 26 tests; e2e rollover `{person:42, car:9}` (command-log #16) | Counts = unique confirmed track-ids per window, no screenline/direction (`counter.py:12-16`); a track spanning a window boundary counts twice |
| Tracker (per-class Kalman+Hungarian `Sort`) | **WORKS (dev host)**, accuracy UNVERIFIED | 600 frames of `tests/test.mov` → 51 tracks (#16); `min_hits=3` (`tracker.py:159`) matches paper C44 | Reads legacy `configs/main_config.yaml` at import (`tracker.py:9`); no MOT/ID-switch measurement; speed code dead |
| Detector integration (`detect_track.py`) | **BROKEN on main** | `--dry-run` exit 1: `ValueError: Model classes [6-class] do not match config [9-class]` (`evidence/dryrun.log`; `detect_track.py:74-78`) | Guard requires `model.names` == canonical list *in order*; the TRA2026 model (alphabetical, `motorcycle`) fails it too → name-based remap needed (S1). `ncnn` not in `requirements.txt` (#12) |
| Shipped NCNN model @ configured imgsz | **BROKEN** | `sensor.yaml:31` imgsz 480 vs export at 640 → 300 boxes/image (`evidence/ncnn_parity.log`) | Set imgsz 640; the 480 "warn-only" branch in `export_ncnn.py:205-257` let this through |
| Camera (`camera.py`, picamera2) | **UNVERIFIED** | x86: `RuntimeError: picamera2 not available` (#16) | Pi-only; no USB/file source in production code; no frame_skip |
| Publisher + OfflineBuffer + HttpClient | **WORKS** | 40 pytest; e2e outage → buffered → drained (#16); real bodies pass dashboard zod (#17) | `avg_speed_kmh` always `{}`; replays >7 days or windows >60 min are 4xx'd and dropped as poison (§5 D9) |
| Config loop (ConfigPoller) | **BROKEN in integration** | e2e `applied=0` (#16) because of G-b | Persist callback only logs (`sensor_daemon.py:186`); `detection_zone`/`frame_skip`/`min_track_hits` ignored |
| LoRa encoder / TS decoder / TTN webhook | **PARTIAL** (code islands) | Python pack ↔ TS decode identical (#17) | Not imported by the daemon; no radio driver; `pack("cam-dub-01")` raises (`lora_codec.py:130-134`); webhook stores 3-char id as `sensor_id` (`uplink/route.ts:115`) ≠ `cam-dub-NN`; no hardware, no TTN app |
| Model / weights / dataset (main) | **MISSING (9-class)** | `models/` holds 6-class `20250629_warmup_best.*` + stock yolo11n/yolov8n; labels lack e-scooter/SUV/delivery_van (#19) | Paper's model is on `origin/TRA2026` (§0.1); paper's dataset (Roboflow v3, 1,834 img) not in repo; `dev_expanded_dataset` is a third, different corpus (truck 19 / delivery_van 28 instances there) |
| Metrics / Pi benchmark evidence | **MISSING** | no results file on main; TRA2026 has training `results.csv` (§0.2) but no benchmark output; `pipeline_report.json` `overall_success:false` | 15 FPS claim unreproducible from repo (§0.3) |
| Dashboard ingest routes (counts/daily/heartbeat/config) | **WORKS (mock)** / UNVERIFIED (live) | edge bodies → 200 (#17); 12 route tests | Live path never executed against Postgres |
| Live persistence (`ingest-store.ts`) | **UNVERIFIED** | upserts never run; no `drizzle/migrations/meta/_journal.json` tracked | `drizzle-kit migrate` likely fails; FK `sensor_readings.sensor_id → sensors.id` needs a row nobody creates |
| Live read path (`streets-live.ts`) | **STUB** | G-a: all 5 methods throw "Live streets repo not implemented …" | Second hard break: DB data can never reach the map/API |
| Privacy filter (k_min=5, no GPS/sensor_id) | **WORKS (mock)** / MISSING (live) | 12 privacy tests (#8); `streets-mock.ts:46-62` | Live adapter absent; speed values not suppressed for 1–4 counts (`streets-mock.ts:134-143`) |
| Auth (Auth.js Google) | **PARTIAL / UNVERIFIED** | fail-closed guards 13 tests; allowlist from env only (`auth.ts:12-20,33-43`) | No OAuth app; `allowed_members` table unused |
| Admin console | **STUB** | `admin/streets/page.tsx:9` "Implementation pending"; sensors page lists `[]` in live | No forms for register/token/config |
| Crons | **PARTIAL** | retention 11 unit tests; refresh-aggregates/detect-silent untested; `reconcile-daily` → 501 (`route.ts:13`) | GH cron workflow dormant until `CAMINA_BASE_URL` set (`cron.yml:37`) |
| DB schema + migrations | **UNVERIFIED** | `0000_init.sql`, `0001_…sql` exist | No journal; never applied |
| CI | **MISSING** | G-d: only `.github/workflows/cron.yml`, its steps are curl pings; no pytest/vitest/tsc | Nothing gates a PR; `pnpm lint` broken (Next 16 removed `next lint`, #10) |
| Deploy / systemd | **PARTIAL** | unit correct (`Type=notify`, `WatchdogSec=300`, G-f); `sd_notify` unit-tested | Never run under systemd; `ProtectSystem=strict` vs Ultralytics settings dir under `/opt/camina`, no `SupplementaryGroups=video` |
| Vercel deploy | **NOT DEPLOYED** | `dashboard/README.md:76-78`; mock build green (#11) | env inventory in §2; `.env.example` incomplete |
| Provisioning / OTA | **MISSING** | G-c: no `insert(sensors)` anywhere; `db:seed` → `scripts/seed-from-mock.ts` does not exist | docs describe sed on YAML |
| Observability (Sentry, BotID) | **MISSING** | no `@sentry/*` or `botid` in `package.json` | heartbeats + log-only detect-silent is what exists |
| Field / soak evidence | **MISSING** | no log, commit or doc of any Pi run | — |

---

## 2. End-to-end chain and integration mismatches

### End-to-end chain (dev host x86, no Pi camera, network mocked)

| # | Link | Verdict | Evidence | Where it breaks |
|---|---|---|---|---|
| 1 | Camera capture (picamera2) | **UNVERIFIED** | `RuntimeError` on x86 (#16) | Pi-only. No file/USB source in production code; the probe used `cv2.VideoCapture(tests/test.mov)`. |
| 2 | Inference: production path `make_detect_and_track` | **BROKEN** | `ValueError` model-class mismatch for all repo models (#13, #16); `ncnn` missing from `requirements.txt` (#12) | **First hard break.** No 9-class weights exist on `main` (§0.1 corrects: they exist on `origin/TRA2026`). |
| 2b | Inference: raw YOLO, legacy 6-class, bypassing the guard | **WORKS (.pt), BROKEN (NCNN@480)** | `.pt@480` 72 dets / 10 imgs, ≈22 ms/img on x86 CPU; NCNN@640 matches `.pt`; **NCNN@480 → 300 dets/img** (#18) | Runtime `imgsz: 480` (`configs/sensor.yaml:31`) vs NCNN exported at 640 |
| 3 | Tracking (per-class Sort) | **WORKS** | 600 frames test.mov → 5036 yields, 51 unique tracks (#16) | Accuracy unmeasured |
| 4 | Counting / windowing | **WORKS** | Rollover snapshot `{person:42, car:9}` (#16) | No line/zone logic; counts are "unique track ids seen" |
| 5 | Daily accumulation | **WORKS** | DailySnapshot emitted (#16) | — |
| 6 | Offline buffer | **WORKS** | Outage → buffered, then drained (#16) | Replays older than 7 days, or windows over 60 min, get 422/400 and are dropped as poison |
| 7a | Payload encode: HTTPS JSON | **WORKS** | Captured bodies (`evidence/e2e_out/captured_requests.json`) pass zod (#17) | `avg_speed_kmh` empty |
| 7b | Payload encode: LoRa binary | **PARTIAL** | Round-trip OK with "D01"; `ValueError` with the configured `cam-dub-01` (#16) | Not called by the daemon; no radio |
| 8 | Transport | HTTPS client **WORKS** (mock transport); real network, TLS, cellular and LoRa radio **UNVERIFIED** | #16 | — |
| 9 | Dashboard ingest (route + zod + auth) | **WORKS (mock mode)** | Edge bodies → 200 `{ok:true, latest_config_version:""}` (#17) | — |
| 10 | Remote config loop | **BROKEN** | `applied=0` (#16); routes echo client version (`counts/route.ts:40,47`) | Server never advertises a newer version |
| 11 | DB write | **UNVERIFIED** | `ingest-store.ts` upserts never executed; migration journal absent; no sensor provisioning | Live ingest needs a `sensors` row + token hash that no code creates (FK `sensor_readings.sensor_id → sensors.id`, `0000_init.sql:50`) |
| 12 | API read | **Mock WORKS / live BROKEN (STUB)** | `streets-live.ts:7-22` | **Second hard break:** DB data can never reach the API |
| 13 | Map render | **PARTIAL** | Build OK (#11), mock fixtures OK (#8); Playwright not run | Live mode cannot render (depends on 12) |
| 14 | Privacy filtering (k_min=5, no GPS) | **Mock WORKS / live MISSING** | 12 privacy tests pass (#8) | Live repo stub; speed side-channel |

Net result: mock-mode dashboard works on simulated fixtures, not edge-produced data. The edge pipeline works on a dev host from tracker to publish, but only when the 6-class model is hand-wired past the production guard. No real frame-to-map path exists or can exist today — it breaks at link 2 (model), link 12 (live repo), and at provisioning (no sensor rows or tokens).

### Integration mismatches

1. **Config version handshake is dead.** Edge: `https_publisher.py:155-160` reads `latest_config_version`; `ConfigPoller.check` (`config_poller.py:79-83`) fetches only when it differs. Dashboard: counts/daily/heartbeat routes return `latest_config_version: parsed.data.config_version` — the client's own value (`counts/route.ts:40,47`, `daily/route.ts:33,37`, `heartbeat/route.ts:33,37`). Result: `/config` is never fetched (e2e `applied=0`). The README and `sensor_deployment.md` claim hot-reload.
2. **Sensor id format.** HTTPS/simulation use `cam-dub-NN` (`configs/sensor.yaml:6`, `generate_mock_dublin.py:335`). LoRa requires a 3-byte camera id (`lora_codec.py:130-134`); the uplink route persists it as `sensor_id` (`uplink/route.ts:115`). No device_id→sensor mapping exists.
3. **Edge ↔ zod payloads: MATCH** (verified by run, #17). `CountsPayload`/`DailyPayload`/`HeartbeatPayload` match their zod schemas exactly, including `extra="forbid"` ↔ `.strict()`.
4. **Paths: code matches, docs don't.** Edge `base_url=https://camina.ucd.ie/api/ingest` + `/sensors/{id}/counts` = the real route (verified). `docs/PROTOCOL.md:36` and `docs/sensor_deployment.md:61` still say `/v1/sensors/...`.
5. **Config endpoint ↔ SensorConfig.** Mock config keys equal the edge field set exactly (#17). Live returns `{...sensors.config_json, config_version}` with no server-side schema; edge `extra="forbid"` would reject any extra key — unverified live.
6. **LoRa encoder ↔ decoder: MATCH** (Python pack → TS decode identical, #17; 20-byte layout). The simulation's `pack_lora_reference` is still the v1 17-byte format (stale).
7. **Class list consistency.** Canonical 9 classes agree across `configs/classes.yaml`, `configs/sensor.yaml`, `lora_codec.CLASSES`, `dashboard/src/lib/types.ts`, `export_ncnn.CAMINAV1_CLASSES`, test constants. Mismatches: `custom_model_train/all_camina_classes/data.yaml` uses a different name/order and an absolute macOS path; tracked labels contain only ids 0-5; the deployed model is 6-class in yet another order; `main_config.yaml:36-42` uses `motorcycle`; `docs/MODELS.md:40-47` shows a 6-class `classes.yaml` that no longer exists.
8. **imgsz contract:** `sensor.yaml:31` 480 and `DaemonConfig` default 480 vs NCNN exported at 640 → 300 garbage detections per image (#18).
9. **Replay rejection turns into silent loss.** Server rejects timestamps older than 7 days (422) and windows longer than 3600 s (400). Edge `publish_interval_minutes` allows up to 1440, and `outbox_max_rows` is documented as "~10 days". Non-408/425/429 4xx are treated as poison and deleted. So outages over 7 days, or windows over 60 min, lose data silently.
10. **Speeds:** the dashboard has a speed metric and a k-floor design, but the edge always sends `avg_speed_kmh: {}`.

---

## 3. Claims-vs-code matrix

Strength: DONE = asserted as achieved, IMPL = implied, FUT = explicit future. Code verdict is for `main` unless stated. Full claim text and IDs are in the Appendix.

| # | Capability | Claim (IDs, source, strength) | Code verdict | Evidence | Ruling |
|---|---|---|---|---|---|
| 1 | Pi 5 8 GB, CPU-only NCNN node | C06, C07 (P §2.5/§3.2, S6, S11) DONE | NOT VERIFIED on hardware | no Pi run recorded | Claim ahead of *recorded* evidence; hardware target is unchanged |
| 2 | Nine-class YOLO11n detector, single model | C15, C16, C17 (P, S8–S11) DONE | **NOT on main; COMPLETE on TRA2026** | §0.1; main dry-run fails (`evidence/dryrun.log`) | **Claim supported only on TRA2026 branch, not main.** Bring-up is a remap + config change, not a retrain |
| 3 | NCNN export, 640×640, ~10 MB | C39, C40 (P §2.5) DONE | COMPLETE on TRA2026 | `model.ncnn.bin` 10,503,980 B, imgsz 640 | Supported (branch). main's runtime imgsz 480 contradicts C40 → fix in S1 |
| 4 | mAP@0.5 0.563 (v11n) and comparison v5n/v8n | C33, C34 (P §3.2, S11) DONE | PARTIAL evidence | `results.csv` best 0.571 / last 0.549; no val artefact for 0.563 | Number is in the neighbourhood of the logs but not reproducible from the repo; see §6 |
| 5 | Per-class AP50 table | C35 (P Table 1, S10) DONE | NO artefact | no per-class file anywhere | Not reproducible; Table 1 mean 0.430 ≠ headline 0.563 (§6) |
| 6 | 15 FPS / 64.9 ms on Pi 5 | C37, C38 (P abstract/§3.2, S11–S12) DONE | NOT STARTED (no artefact) | §0.3 | **Claim ahead of code.** Must be re-measured in S6; end-to-end throughput with camera+tracker will be lower than single-image inference |
| 7 | Dataset 1,834 img / 13,148 inst on Roboflow v3; hybrid auto-labelling; cyclist IoU rule | C19–C26 (P §2.1–2.2) DONE | NOT in repo | dataset not tracked (any branch); labelling scripts on main are unrun | Supported only externally (Roboflow). Repo has two other corpora, neither matching. DECISION D8b: which corpus is canonical for retrain |
| 8 | Training config 150 ep / patience 75 / batch 16 / 640 | C30 (P §2.3) DONE | COMPLETE on TRA2026 | `results.csv` 150 rows ×4 | Supported (branch) |
| 9 | Custom lightweight tracker, ≥3 hits to confirm | C43, C44 (P §2.5, §3.1) DONE | COMPLETE (runs) | `tracker.py:159` `min_hits=3`; e2e | Supported. "Cheaper than DeepSORT" and ID robustness unmeasured |
| 10 | Real-time counting of road users | C02, C46 (S5, S7) IMPL | PARTIAL | WindowedCounter works; never run on a real stream; no ground truth | Claim ahead of code: the counter exists, counting *accuracy* has never been measured. Method (unique-track vs screenline) is DECISION D3 |
| 11 | "Flows" (direction) | C47 (S7) IMPL | NOT STARTED | no direction/zone logic; `detection_zone` unused | Aspirational — DECISION D3: implement screenline+direction or drop "flows" wording |
| 12 | Continuous fixed-node operation | C14 (P §2.5) IMPL; field test C60 (S12) FUT | NOT STARTED | no soak/field log; watchdog untested under systemd | Claim ahead of code; the salvaged 01-02/01-04 done-tests are the right gate (PLAN.md Appendix B) |
| 13 | On-device processing, no video egress, no storage | C49–C51 (P §1/§4, S6–S7) DONE | WORKS by inspection | no frame write/upload in `service/`, `io/`; payload bodies counts-only | Supported. Add a regression test asserting it |
| 14 | GDPR by design | C52 (P §4, S6, S12) DONE | PARTIAL | no DPIA, statement or signage (PRIV-01..05 unbuilt) | Asserted, not evidenced. Needed before a real street (S8, DECISION D9) |
| 15 | Metadata uplink to a backend | C55 (P §4, S7) IMPL | WORKS (mock transport) | HTTPS publisher → dashboard zod 200 | Supported end-to-end in mock; live DB write unverified |
| 16 | Dashboard receiving counts | C57 (S7) IMPL; C58 "Dashboard + 10+ sensors Jun 2026" FUT | PARTIAL (mock only) | mock map builds and tests pass; live read path is a stub; not deployed | **Claim ahead of code.** Dashboard exists but cannot show real data |
| 17 | ~€100 (S12) / €250 (P §4) device | C09–C11 DONE/IMPL | NO BOM | `docs/EQUIPMENTS.md` lists Pi 3/4 parts | Aspirational, internally inconsistent. DECISION D7: publish a BOM |
| 18 | 3D-printed case | C12 (S12) FUT | NOT STARTED | no CAD/STL in repo | Future per the slides; needed for a field install (S8) |
| 19 | Fleet 10+ (Jun) / 50+ (Sep 2026) | C61 (S12) FUT | NOT STARTED | 0 units in the field | Aspirational, dates past. DECISION D4: re-baseline |
| 20 | Improved model (Apr 2026), ≥500 inst/class | C62, C63 (S12, P §3.1) FUT | NOT STARTED | `dev_expanded_dataset` branch (intern, Apr 2026) is the only movement; truck 19 / delivery_van 28 instances there | Aspirational. Belongs to the S13 quality track, not M1 |
| 21 | Citizen-led / volunteer-hosted model | C03, C04 (P §1/§4) IMPL | NOT STARTED | no hosting/provisioning path for non-authors | Aspirational. M2 (S10) |
| 22 | Planning insights (e-scooter flows, conflict zones) | C65 (P §4) IMPL/FUT | NOT STARTED | needs trajectories; none stored by design | Aspirational; conflict zones conflicts with the counts-only privacy model — proposed closure, §4 of PLAN.md |
| 23 | Open code at `tree/TRA2026` | C66 DONE | COMPLETE | branch exists, 88 commits | Supported. Note `main` has diverged and no longer runs the paper's model |
| 24 | Validation across cities / robustness | C42, C64, C68 | NOT STARTED | — | Explicit limitation; out of scope for M1 |

---

## 4. Repo-only commitments (not promised by paper or slides)

| Commitment | Where promised | Verdict | Needed for the paper bar? | Disposition |
|---|---|---|---|---|
| LoRaWAN/TTN transport | README:18, PROJECT.md, LORA-01..08 | PARTIAL (codec islands, no radio, id mismatch) | **No** (§0/G-g: paper/slides never mention LoRa) | DECISION D1 — recommend M2-optional; HTTPS/cellular covers the paper bar |
| k-anonymity floor k_min=5 | README:19, DATA-06 | WORKS mock / MISSING live | No, but it is the concrete form of "anonymized metadata" and cheap | Keep; implement in live adapter (S4) |
| Windowed 15-min counts + daily totals + offline buffer | PROTOCOL.md | WORKS | Not specified by paper, but *some* aggregation is required for counts to exist | Keep |
| Remote config / hot-reload | README:74, sensor_deployment.md | BROKEN | No | Fix is < 1 day (S3); or drop the README claim |
| Admin console (8 reqs) | ADMIN-01..08, PROTOCOL.md:19-21 | STUB | No | DECISION D5 — replace with a provisioning CLI for M1 |
| Google OAuth admin auth | AUTH-01..06 | PARTIAL | No (public map needs no auth) | M2 (S11) |
| Crons (4) + reconciliation | CRON-01..05, RECONCILIATION.md | PARTIAL / 501 | No | M2 (S12); delete `reconcile-daily` or implement |
| Speed metric on dashboard | dashboard UI, SIM-03 | MISSING at edge (`{}`) | **No** (paper never mentions speed estimation) | DECISION D2 — recommend hide/descope |
| Sentry / BotID / Rolling Releases / Upstash | CLAUDE.md:54, SEC/OBS | MISSING (Upstash env-gated) | No | M2 optional; fix CLAUDE.md wording now |
| USB-SSD state, NTP gate, watchdog | EDGE-05..07 | code present, unrun | Not promised, but required for "continuous fixed node" (C14) in practice | S6 |
| DPIA / privacy statement / signage | PRIV-01..05 | MISSING | Not promised, but "GDPR by design" (C52) is asserted and a real-street install needs them | S8 prerequisite; DECISION D9 on scope |
| Simulated fleet (8 sensors) | SIM-01..07 | WORKS | No | Done; keep for UI dev |
| Dublin-only | PROJECT.md | n/a | Paper doesn't name a city | Keep (D8) |

---

## 5. Integration & deployment gaps

**Deployment (bench vs field):**

| Area | Status | Evidence |
|---|---|---|
| Power (mains/PoE/solar), enclosure, mounting, IP rating | undocumented; `EQUIPMENTS.md` lists Pi 3/4 parts; TODO.md open item for HARDWARE.md | §2 |
| Connectivity at the site (WiFi/4G) | untested; cellular is "HTTPS over a bearer" by assumption | CLAUDE.md |
| Provisioning a unit (OS image, venv, `ncnn`, `picamera2` apt, token, YAML) | manual, incomplete (`requirements.txt` lacks `ncnn`) | #12; `sensor_deployment.md:17-46` |
| Camera permissions / systemd hardening | `ProtectSystem=strict`, no video group; Ultralytics writes settings under `/opt/camina` | `camina-sensor.service:31-32` |
| Thermal | Active Cooler documented as prerequisite; never benchmarked | salvaged into S6 (PLAN.md Appendix B) |
| Clock | `After=time-sync.target` present; NTP gate in code; unverified | unit L6 |
| Updates / OTA | git pull + pip | `sensor_deployment.md:17-23` |
| Ethics / DPO / signage | not started | PRIV-01..05, S8 |
| Cold spare | not started | DEMO-03, S10 |

This is the same integration-mismatch material as §2 above, viewed from a deployment-readiness angle rather than a code-path angle; §2 is authoritative for what breaks and why, this table is the field-readiness checklist for S6/S8.

---

## 6. Paper-integrity issues (factual, not code gaps)

These affect what can be *claimed*, not what needs to be *built*. Listed so the PI can decide whether an erratum, a follow-up paper, or silence is appropriate (DECISION D13).

1. **Table 1 mean vs headline.** Unweighted mean of the nine per-class AP50 = 0.430; headline 0.563. Ultralytics mAP50 *is* the unweighted per-class mean, so both cannot come from one validation run. The training logs on TRA2026 give best 0.571 / last 0.549 for the same model (§0.2); no per-class artefact exists.
2. **Swapped percentages** (car 16.01 % vs cyclist 15.30 %; Table 1 prints them exchanged) — arithmetic verified against the raw counts.
3. **"Instances (train)" header** carries the full-dataset totals, not the 1,467-image training split.
4. **Unit cost €100 (S12) vs €250 (P §4)** — no BOM in the repo supports either (DECISION D7).
5. **"Four YOLO nano variants"** — four were trained (v10n run exists, best 0.540, §0.2) but only three reported. Cheap fix in any follow-up: report v10n.
6. **15 FPS basis** — single-image inference latency (3 imgs × 20 cycles, C38), not camera→detect→track throughput; and no artefact or matching script (§0.3). Re-measure end-to-end in S6 before repeating the number.
7. **Funding attribution.** Paper and slides credit **REALLOCATE, EU grant 101103924**. `CLAUDE.md` and `README.md` said **INTERREG**. Flagged, not resolved here — DECISION D11.
8. **Text vs table** ("COCO classes achieved the highest accuracy" while e-scooter 0.900 and cyclist 0.589 lead); **"proprietary" tracker vs open code**; **promised precision and training-time metrics never reported**. Minor.
9. **Author name** Rogers (paper) vs Rodgers (slides).

---

## 7. Planning review

Per-document verdicts for everything under the old `.planning/`, plus root `TODO.md`, `README.md` status lines, and `docs/production_readiness.md`. `old/` = `.planning/old/2026-09-15-gsd/`.

Verdict ∈ {still accurate, outdated, superseded, missing pieces}. `TODO.md`, `README.md` and `docs/production_readiness.md` were explicitly **out of scope for this update** (not edited or moved) — their rows below keep the verdict/reason from the review, with the disposition column overridden to reflect that they are flagged for the PI, not acted on here.

| File | Verdict | Reason (evidence) | Disposition |
|---|---|---|---|
| `STATE.md` | outdated | "Phase 1 ready to plan", "0 of 4 executed" contradicts `01-01-SUMMARY.md` `status: complete` and commits `ff6aadb/eaf9b5d/4dc7e80`; footer "Synced 2026-05-09" vs content dated 07-10; carries none of the 09-15 audit findings | rewritten in place (old copy in `old/`) |
| `PROJECT.md` | outdated | last updated 2026-04-23; M1/TRL-6 dates both past, never revisited; "60 tests" (now 144); decision "model already trained" false on main | rewritten in place (old copy in `old/`): identity/core value/constraints/out-of-scope kept, requirement lists pointered, decisions dated |
| `ROADMAP.md` | superseded | 11 phases / ~31 plans, progress table 0 % everywhere while the code shows Phases 2/5/8 scope largely delivered on 07-10; user chose a rebuilt plan | moved to `old/`; replaced by `PLAN.md` |
| `REQUIREMENTS.md` | superseded | 70 REQ-IDs, traceability table never filled; 0 checkboxes flipped though ≥20 are demonstrably done | moved to `old/`; REQ→stage crosswalk lives in `PLAN.md` Appendix A |
| `config.json` | superseded | GSD runtime config; GSD dropped from CLAUDE.md | moved to `old/` |
| `codebase/ARCHITECTURE.md` | outdated | day-1 (04-23) map; predates most of the current service/ and dashboard layers | moved to `old/`; this document is the current map |
| `codebase/CONCERNS.md` | outdated | its three HIGH items were fixed 07-10; the real HIGH items today (model unusable, live read stub, no provisioning) are absent | moved to `old/` |
| `codebase/CONVENTIONS.md` | still accurate (mostly) | naming/style rules unchanged; references to old layout are minor | kept, flagged stale (header note) |
| `codebase/INTEGRATIONS.md` | outdated | predates Neon-live code, LoRa webhook, GH-Actions cron; lists Sentry as present | moved to `old/` |
| `codebase/STACK.md` | outdated | Next/Python pins have moved since (Dependabot commits) | moved to `old/` |
| `codebase/STRUCTURE.md` | outdated | documents a `plan/` dir and a `bkp/` layout that no longer match; 07-10 reorg not reflected | moved to `old/` |
| `codebase/TESTING.md` | outdated | "60 pytest, 2 vitest files" vs 144 / 9 files | moved to `old/` |
| `research/ARCHITECTURE.md` | superseded | architecture decided and mostly built; LoRa section marked MEDIUM confidence and hardware still absent | moved to `old/` |
| `research/FEATURES.md` | missing pieces but durable | its DPIA/privacy-statement/signage gap is still open and now blocks S8 | kept, flagged stale; PRIV gaps carried into `PLAN.md` S8 |
| `research/PITFALLS.md` | still accurate (dates aside) | Pi 5 thermal throttling, picamera2 OOM, clock drift, SD corruption are exactly the S6/S9 gates | kept, flagged stale; re-pointed to S6/S8/S9 |
| `research/STACK.md` | superseded | stack chosen and in place; Python 3.11 recommendation never actioned | moved to `old/` |
| `research/SUMMARY.md` | superseded | W1–W5 plan for 04-24→05-31, fully elapsed | moved to `old/` |
| `phases/01-…/01-01-PLAN.md` + `01-01-SUMMARY.md` | done, with a bookkeeping defect | executed 2026-05-10; SUMMARY cites SHAs that no longer exist — same-subject commits are `ff6aadb/eaf9b5d/4dc7e80` (history rewritten) | moved to `old/`; SHA mismatch noted in `old/README.md` |
| `phases/01-…/01-02-PLAN.md` | not executed; salvaged | 30-min in-enclosure bench done-tests | moved to `old/`; reused verbatim in `PLAN.md` S6 |
| `phases/01-…/01-03-PLAN.md` | partially delivered outside GSD; drill salvaged | code landed 07-10; the drill (kill -9, SD-corruption rehearsal) never run | moved to `old/`; drills reused in S6 |
| `phases/01-…/01-04-PLAN.md` | not executed; salvaged | 48-h soak gates, heartbeat enrichment | moved to `old/`; gates reused in S9, heartbeat enrichment in S6 |
| `phases/01-…/PLAN-CHECK.md`, `REVISION-NOTES.md` | superseded | GSD plan-checker artefacts | moved to `old/` |
| root `TODO.md` | missing pieces | the maintainer block is code-true but reads as "live-ready"; misses the three real blockers and the TRA2026 model fact | **flagged — outside this update's scope; PI to decide** |
| root `README.md` status lines | outdated | L3 "runs a fine-tuned 9-class YOLO11 detector" false on main until S1; L5 funding + date; L18 LoRa "implemented code-side"; L74 "hot-reload via the config poller" dead | **flagged — outside this update's scope; PI to decide** |
| `docs/production_readiness.md` | superseded | 07-10 snapshot; contradicts current `utils/sqlite_integrity.py` state; "larger initiatives" table is now `PLAN.md` M2 | **flagged — outside this update's scope; PI to decide** |

---

## 8. Command log

Run on the dev host (x86, Python 3.12 scratch venv, CPU torch), 2026-09-15. Scratch script paths below refer to the durable copies in `audit-2026-09-15/evidence/` where retained; everything else was scratch-only and not retained.

| # | Command (abridged) | Outcome |
|---|---|---|
| 1 | `git ls-files`, `wc -l` over edge/dashboard | 2868 tracked files. Edge src ≈2.9k LOC. Dashboard ts/tsx/sql ≈5.7k LOC. No `pyproject.toml`, no `.venv`, no `dashboard/node_modules`, no `pnpm` on PATH in the repo itself. |
| 2 | `git log --oneline` (124 commits) + grep pi/benchmark/field/deploy/fps/ncnn | No commit records a Pi run, benchmark, soak or field test. |
| 3 | `uv venv --python 3.12` in scratch; `uv pip install` CPU torch 2.10 + `requirements.txt` + pytest **(scratch, not retained)** | OK. The repo has no `uv.lock`. |
| 4 | `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` (repo root) | **144 passed, 0 failed**, 1 warning (filterpy SyntaxWarning), 4.3 s. |
| 5 | Copied the tracked `dashboard/` to scratch **(scratch, not retained)**; `npx pnpm@9.12.0 install --frozen-lockfile` | OK, 1m20s. Lockfile honoured. |
| 6 | `pnpm test` (vitest), first run | 72 passed / 17 failed. All failures are `ENOENT …/data/mock/dublin/*.json` (fixtures gitignored and absent). |
| 7 | Copied `scripts/generate_mock_dublin.py` to scratch and ran it **(scratch, not retained)** | 8 sensors (`cam-dub-01..08`), 77,651 readings, 1,152 heartbeats, 112 daily rows. |
| 8 | `pnpm test`, rerun with fixtures | **89/89 passed** (9 files). |
| 9 | `pnpm typecheck` | exit 0. |
| 10 | `pnpm lint` | **FAILS.** `next lint` no longer exists in Next 16; no ESLint config. |
| 11 | `CAMINA_DATA_SOURCE=mock pnpm build` (no secrets) | exit 0. Next 16.2.10 Turbopack; 28 routes compiled. |
| 12 | `scripts/run_sensor.py --config <sensor.yaml → repo NCNN model> --dry-run` (before `ncnn` installed) | exit 1. `ModuleNotFoundError: No module named 'ncnn'`. Not in `requirements.txt`. |
| 13 | `uv pip install ncnn` (scratch venv), then rerun #12 | exit 1. `ValueError: Model classes ['bus','car','cyclist','motorcycle','person','truck'] do not match config [9 canonical]` (`detect_track.py:74-78`). Logged in `evidence/dryrun.log`. |
| 14 | `evidence/e2e_chain.py` on `custom_model_train/test_video.mp4` | Every downstream link returned zero counts — that clip is a flat grey synthetic frame, 0 detections in 200 frames. |
| 15 | Diagnostic run on `tests/test.mov` (416×416, 60 fps, 5988 frames) **(scratch)** | 200 frames: 1621 detections, 1580 tracker yields, 20 unique ids. The tracker works; the earlier clip was the problem. |
| 16 | `evidence/e2e_chain_mov.py` (same probe on `tests/test.mov`, 600 frames, `ncnn` installed) | Window counts `{person: 42, car: 9, others: 0}` from 51 unique tracks. |
| 17 | Scratch-only vitest `evidence/dash-tests/zz-edge-contract.test.ts` feeding the captured edge request bodies and the Python LoRa frame into the dashboard | **8/8 passed.** |
| 18 | NCNN vs PyTorch parity on 10 `test_images` (dets/image, conf 0.3) — `evidence/ncnn_parity.log` | `.pt@640` and `ncnn@640` parity OK; **`ncnn@480` → 300 dets/image ×10 (broken)**. |
| 19 | Labels histogram `custom_model_train/all_camina_classes/labels/*/*.txt` | ids 0:7361, 1:1761, 2:2116, 3:445, 4:309, 5:297. ids 6, 7, 8 (e-scooter, SUV, delivery_van) = 0 instances. |
| 20 | grep TODO/FIXME/NotImplementedError/stub markers | Only 3 hits: `streets-live.ts:9-21` (5× "not implemented"), `api/cron/reconcile-daily/route.ts:13` (501), `admin/streets/page.tsx:9` ("Implementation pending"). |
| 21 | `git status --short --ignored`, `find __pycache__` | Repo clean apart from the `.gitignore` edit that predates this audit. |

Not run: Playwright e2e (needs a dev server and browsers, not needed for the verdicts); `drizzle-kit migrate` and any live-mode route (no DB credentials); anything on Pi hardware.

---

## Appendix — Claims table and contradictions

Full extraction from the TRA 2026 paper (`bkp/TRA_2026_paper_896_adjusted_final.pdf`, 8pp) and slides (`bkp/TRA_2026_896.pdf`, 13 slides). Both files are gitignored and local-only. Strength: **DONE** = stated as achieved; **IMPL** = implied; **FUT** = explicit future. Consistency: **CONS** = paper and slides agree; **DIFF** = they disagree; **P-only** / **S-only** = one document only.

| ID | Category | Claim | Source / location | Strength | P↔S |
|---|---|---|---|---|---|
| C01 | Identity | CAMINA = "Citizen-led Automated Modal Infrastructure Analytics", "a community-driven approach that emphasizes active transportation modes" | P abstract, §1; S5 | DONE (definition) | CONS |
| C02 | Identity/scope | "An AI platform designed for real-time counting of road users using computer vision, running on edge devices" | S5 | IMPL | S-only |
| C03 | Citizen model | The project "leverages volunteer participation to collect continuous, high-quality data on modal share" | P §1 | IMPL/FUT | P-only; S12 "Citizen-led urban sensing" |
| C04 | Citizen model | "Practical feasibility for distributed, citizen-led monitoring using low-cost devices" | P abstract, §4; S12 | DONE (asserted) / IMPL | CONS |
| C05 | Scalability | "CAMINA offers a scalable and privacy-preserving approach" | P abstract, §1; S3 | IMPL | CONS |
| C06 | Hardware: board | Raspberry Pi 5 8 GB, Cortex-A76 2.4 GHz | P §2.5, §3.2; S6, S11 | DONE | CONS |
| C07 | Hardware: accelerator | No accelerator: CPU-only NCNN inference | P §2.5, §3.2 | IMPL (by omission) | CONS |
| C08 | Hardware: camera | Camera exists; model/lens/resolution not specified | S7 diagram; P §4 | IMPL | DIFF-ish |
| C09 | Hardware: cost | "~€100 device" | S12 | DONE | **DIFF** vs C10 |
| C10 | Hardware: cost | "comparable price point (€250)" | P §4 | IMPL | **DIFF** vs C09 |
| C11 | Hardware: cost | "Affordable for citizen science" | S6; P abstract | DONE (qualitative) | CONS |
| C12 | Hardware: enclosure | "3D printed case" | S12 "Next (May 2026)" | FUT | S-only |
| C13 | Hardware: power/mounting/weatherproofing | Not mentioned | — | none | gap |
| C14 | Hardware: role | Functions "as a continuous fixed-node sensor" | P §2.5 | IMPL | P-only |
| C15 | Detection: model | YOLO11n fine-tuned on nine classes | P abstract, §2.5, §3; S9, S11 | DONE | CONS |
| C16 | Detection: classes | Nine classes: person, cyclist, e-scooter, car, SUV, motorcycle, bus, delivery van, truck | P abstract, §1, Table 1; S8, S10 | DONE | CONS |
| C17 | Detection: single model | "CAMINA integrates these classes into a single lightweight architecture" | P §1, §2.5 | DONE | CONS |
| C18 | Detection: differentiator | Model distinguishes SUV/car, merges person+bike into "cyclist", detects e-scooter riders | S4 illustration | IMPL | S-only |
| C19 | Dataset: raw corpus | "1,895 images … from ImageNet … with an additional 600 … [Apurv 2021]" | P §2.1, Fig. 1; S9 | DONE | CONS on numbers |
| C20 | Dataset: auto-labelling | Hybrid: YOLO11l (COCO classes) + YOLOv8m-Worldv2 (text prompts) | P abstract, §1, §2.1, Fig. 1; S9 | DONE | CONS |
| C21 | Dataset: curation rules | Cyclists/e-scooters/motorcyclists annotated only when rider visible | P §2.1 | DONE | P-only |
| C22 | Dataset: manual review | Two-stage manual review (correction + independent double-blind validation) | P abstract, §2.1; S9 | DONE | CONS (S omits double-blind) |
| C23 | Dataset: final size | 1,834 images, 13,148 instances (breakdown by class) | P §2.1, §3, Table 1; S9, S10 | DONE | CONS |
| C24 | Dataset: label provenance | 74.8% COCO / 15.3% rule-based / 9.9% open-vocab | P §3.1 | DONE | P-only |
| C25 | Dataset: availability | Accessible via Roboflow (workspace URL, v3) | P §2.1 | DONE | P-only |
| C26 | Cyclist rule | IoU ≥ 0.20, 5px bottom-edge rule, one-to-one match, fused score | P §2.2, Eq. 1–2; S9 | DONE (labelling step) | CONS |
| C27 | Cyclist rule: purpose | Solves person/bicycle double-counting | P §1 | IMPL | P-only |
| C28 | Cyclist rule: configurable | "Configurable IoU thresholds and geometric constraints" | P §1 | IMPL | P-only |
| C29 | Training: split | 80/20 stratified → 1,467 train / 367 val | P §2.3, §3; S11 | DONE | CONS |
| C30 | Training: hyperparameters | 150 epochs, patience 75, batch 16, 640×640 | P §2.3 | DONE | P-only |
| C31 | Training: variants compared | "Four" nano variants named/shown, three reported | P §2.3, Fig. 1, §3.2; S9, S11 | DONE (3); YOLO10n IMPL, not reported | **DIFF** |
| C32 | Evaluation metrics | mAP@0.5 primary; FPS, size, training-time promised | P §2.4, §3.1 | DONE for mAP/FPS/size; training time and precision never reported | P-only |
| C33 | Metric: overall mAP | YOLO11n mAP@0.5 = 0.563 | P abstract, §3.2, Fig. 2, §4; S11 | DONE | CONS |
| C34 | Metric: comparison | v5n 0.550/66.4ms/9.7MB; v8n 0.560/64.8ms/11.6MB; v11n 0.563/64.9ms/10.0MB | P §3.2, Fig. 2, §4; S11 | DONE | CONS |
| C35 | Metric: per-class mAP@0.5 | Person 0.479, Cyclist 0.589, Car 0.412, E-scooter 0.900, SUV 0.402, Motorcycle 0.326, Bus 0.537, Delivery van 0.114, Truck 0.111 | P Table 1; S10 | DONE | CONS |
| C36 | Metric: interpretation | "Classes included in COCO achieved the highest accuracy" | P §3.1 | DONE (contradicted by Table 1; §6) | P-only |
| C37 | Inference speed | "15 fps" / "≈64–66 ms" | P abstract, §3.2, §4; S12 | DONE | CONS |
| C38 | Benchmark protocol | "3 validation images and 20 inference cycles per model" | P §3.2; S11 | DONE | CONS |
| C39 | Model size | "10 MB" (NCNN) | P abstract, §3.2 | DONE | P-only |
| C40 | Export format | PyTorch → NCNN, 640×640, nine-class | P §2.5; S11 | DONE (efficiency gain unquantified) | CONS |
| C41 | Edge optimisation | "Refining memory management and batch sizing" | P §1 | DONE (asserted, no detail) | P-only |
| C42 | Real-time claim | "Real-time detection"; "robust, real-time analytics" | S6; P §4, §1 | DONE (assertion) | CONS |
| C43 | Tracking: tracker | "Proprietary" lightweight tracker, lower CPU overhead than DeepSORT | P §2.5 | DONE (comparison unmeasured) | P-only |
| C44 | Tracking: confirmation | ≥3 positive detections before confirming class label | P §3.1 | DONE (unevaluated) | P-only |
| C45 | Tracking type details | Kalman/Hungarian/SORT-family, line-crossing: not specified | none | none | gap |
| C46 | Counting | Real-time counting output "Counts & Flows" | S5, S7 | IMPL | S-only |
| C47 | Flows/direction | "Flows" implies directional/movement data | S7 diagram | IMPL | S-only |
| C48 | Speed estimation | Not mentioned | none | none | gap |
| C49 | Privacy: on-device | Processing at monitoring locations, no centralized transmission | P §1; S7 | DONE | CONS |
| C50 | Privacy: no video egress | "No video feeds ever leave the device"; "Data Firewall" | S6, S7 | DONE | S-only |
| C51 | Privacy: no storage | Transmits only anonymized statistical metadata | P §4 | DONE (implies no raw footage stored) | CONS |
| C52 | Privacy: GDPR | "GDPR compliance by design" | P §4; S6, S12 | DONE (asserted, no DPIA) | CONS |
| C53 | Privacy: anonymity | "Fully protecting citizen privacy" | S7; P §1 | DONE (asserted) | CONS |
| C54 | Privacy: k-anonymity / location obfuscation | Not mentioned | none | none | gap |
| C55 | Transport: metadata transmission | Device transmits "only anonymized statistical metadata" to a dashboard | P §4; S7 | IMPL | CONS |
| C56 | Transport: bandwidth | "Reduces latency and bandwidth demands" | P §1 | IMPL | P-only |
| C57 | Dashboard | A "Dashboard" receives counts and flows | S7 | IMPL | S-only |
| C58 | Dashboard (scheduled) | "Dashboard + 10+ sensors (Jun 2026)" | S12 | FUT | S-only |
| C59 | Dashboard features | Map, colour-coded streets, public/admin views, APIs, open data: not mentioned | none | none | gap |
| C60 | Deployment: field test | "Field testing + 3D printed case (May 2026)" | S12 | FUT | S-only |
| C61 | Deployment: fleet size | "10+ sensors (Jun 2026)", "50+ sensors (Sep 2026)" | S12 | FUT | S-only |
| C62 | Model roadmap | "Improved model (Apr 2026)" | S12 | FUT | S-only |
| C63 | Dataset roadmap | "Curate at least 500 annotated instances per class" | P §3.1, §4 | FUT | P-only |
| C64 | Validation scope | "Broader validation across diverse city contexts remains necessary" | P abstract | FUT (limitation) | P-only |
| C65 | Urban planning use | "Quantifying e-scooter flows…" / "identifying conflict zones…" | P §4 | IMPL/FUT | P-only |
| C66 | Open code | Repository at `github.com/tamagusko/camina/tree/TRA2026` | P §2.5 | DONE | P-only |
| C67 | Remote config / OTA / provisioning / maintenance / cost at scale | Not mentioned | none | none | gap |
| C68 | Weather / night / occlusion robustness | Not mentioned | P §1 | IMPL (unsupported) | gap |
| C69 | Emerging micromobility coverage | E-scooter captured; e-bikes named as motivation but not a class | P §1 | DONE (e-scooter); IMPL (e-bikes) | CONS with S4 |
| C70 | Open-vocab infeasible on edge | Motivates distillation into YOLO11n | P §1 | background claim | P-only |

### Contradictions and discrepancies

**Between the paper and the slides**
- **D1. Unit cost.** S12 "~€100"; P §4 "comparable price point (€250)". 2.5× apart, neither itemised.
- **D2. Models compared.** P prose names three variants, Fig.1/S9 name four (incl. YOLO10n); results report only three. YOLO10n results are missing from the paper, though the training run exists on `origin/TRA2026` (§0.2).
- **D3. Author name.** "Brian Rogers" (P) vs "Brian Rodgers" (S2).
- **D4. Deployment and system scope.** P describes a detector + tracker + privacy-preserving edge node with no dashboard, counting or field test; S presents CAMINA as a counting "platform" with a Dashboard and schedules field test/case/dashboard/fleet as future work.

**Internal to the paper (slides repeat the table errors)**
- **D5.** Text says COCO classes scored highest; Table 1's two best classes are new classes (e-scooter 0.900, cyclist 0.589).
- **D6.** Unweighted mean of Table 1 = 0.430 vs headline mAP 0.563.
- **D7.** Swapped percentages: car should be 16.01%, cyclist 15.30%; table prints them exchanged.
- **D8.** "Instances (train)" header carries the full 1,834-image totals, not the 1,467-image split.
- **D9.** Abstract "1,895 urban images" vs body's final 1,834.
- **D10.** "Proprietary" tracker (§2.5) vs "all code available in our repository" (§2.5).
- **D11.** "80/20 train–test split" (§2.3) vs "1,467 training / 367 validation" (§3) — no independent test set described.
- **D12.** Promised training-time and precision metrics never reported; NCNN "substantial efficiency improvements" and DeepSORT CPU-overhead advantage unquantified.
- **D13.** 15 FPS derived from single-image inference latency, not end-to-end throughput, though presented as sensor capability.
- **D14.** §1 "robust, real-time analytics across diverse urban environments" vs abstract's "broader validation … remains necessary".
- **D15.** "Hybrid training approach" (§1) vs the hybrid being in auto-labelling only (§2); deployed model is a single YOLO11n.
- **D16.** "Refined memory management and batch sizing" (§1) has no corresponding method or result.

**Between these documents and the repo framing**
- **D17. Funding.** Both documents credit REALLOCATE (Horizon Europe grant 101103924). Neither mentions INTERREG — DECISION D11.
- **D18. Location, TRL, target date.** Neither document names Dublin (beyond UCD affiliation), a TRL, or 2026-05-31.
- **D19. Tracker and system details.** Neither document mentions Kalman+Hungarian, LoRa/TTN, windowed counts, colour-coded streets, k-anonymity or the Next.js dashboard — these are repo-side commitments, not paper/slide promises.
- **D20. Roadmap dates versus 2026-09-15.** Every S12 milestone (Apr/May/Jun/Sep 2026) is now due or past.

### Implied definition of "fully functional" (paper + slides together)

A reader of both documents would expect: a Pi 5 8GB camera node in a 3D-printed case, low-cost, running continuously as a fixed street sensor; an on-device nine-class YOLO11n→NCNN detector (~10MB, 640×640, ~15 FPS, mAP@0.5≈0.56); the full reproducible training pipeline (1,834-image Roboflow v3 dataset, hybrid auto-labelling, cyclist rule, training config, benchmark script) published on `TRA2026`; a lightweight custom tracker with ≥3-hit confirmation; real-time counting producing anonymised counts and flows; on-device-only privacy with no video egress and a GDPR-compliant design; metadata uplink to a backend; a dashboard displaying counts/flows; a field-tested network (≥1 site, 10+ then 50+ sensors) in a citizen-led model; an improved model with ≥500 instances/class; and planning-grade outputs (flow quantification, conflict zones).

Not promised by either document: power/solar design, weatherproofing rating, LoRa/LoRaWAN/TTN, cellular, payload format, offline buffering, speed estimation, aggregation windows, k-anonymity, location obfuscation, map with colour-coded streets, public/admin roles, OTA/remote config, night/weather performance, counting accuracy against ground truth, and TRL.
