# Production-Readiness Roadmap

Consolidated from the 2026-07-10 full audit (security, scalability-to-100-sensors,
pipeline correctness, ingestion, dashboard). Finding IDs reference the audit
findings table. Round-1 fixes (path mismatch, daily retry storm, poison-message
handling, heartbeat buffering, shutdown flush, fast-fail sends, dashboard
auto-refresh/gap-rendering/Dublin-time) are **done**.

## Quick wins (hours each, do before live mode) — **all done 2026-07-10**

| Item | Finding | Where |
|---|---|---|
| Fail closed in production: mock default, admin mock-bypass, OAuth empty allowlist, missing cron secret | H7, H8, M3 | `dashboard/src/lib/{data-source,auth,cron-auth}.ts`, `api/admin/streets/[id]/info/route.ts` |
| Build-time guard: `NEXT_PUBLIC_CAMINA_DEV_ADMIN` must not ship to prod | known | `dashboard/next.config.mjs` |
| Drop redundant index `idx_readings_sensor_window` (strict prefix of PK) | M18 | `drizzle/migrations/0000_init.sql:61` |
| Add FK `ON DELETE CASCADE` to `sensor_heartbeats` (right-to-erasure) | M2 | `drizzle/schema.ts:96-107` |
| Tighten zod: 9-class enum keys, count bounds, `window_end > window_start`, ±time-sanity | M4 | `dashboard/src/lib/schemas.ts` |
| Enforce `https://` scheme in edge `HttpClient`; document token file perms (`chmod 640`) | M16 | `src/camina/io/http_client.py`, `docs/sensor_deployment.md` |
| Timing-safe token compares | H6/M3 | `ingest-auth.ts`, `cron-auth.ts` |
| Heartbeat interval 300→600 s (halves invocation volume, restores Neon CU headroom) | M12 | `configs/sensor.yaml`, `sensor_daemon.py` |

## Medium effort (days, blocks live-mode flip)

| Item | Finding |
|---|---|
| Live ingest persistence: Drizzle `INSERT … ON CONFLICT DO UPDATE` on the composite PKs (counts fan-out 9 rows/window as one statement; `partial`-promotion rule: never overwrite `partial=false` with `partial=true`) | H2, H5 |
| Per-sensor tokens: `sensors.api_token_hash` lookup, SHA-256 (not bcrypt — token is already high-entropy; bcrypt wastes 50-250 ms CPU/request) | H6, M12 |
| `attachDatabasePool(client)` + `max: 1-2` + assert Neon `-pooler` URL | H13 |
| Retention job: raw readings ≤90 days, roll up into plain aggregate tables; bound the materialized views to the painted window (~48 h) | C1, H12 |
| Cron scheduling on Hobby: piggyback MV refresh on ingest (advisory-lock guarded) + external scheduler (GitHub Actions cron → `verifyCron` routes) for sub-daily jobs | H14 |
| Implement `detect-silent` + surface staleness publicly (distinct map style, `stale`/`lastSeen` in MetricValue) — silent sensor must not paint as quiet street | H11 |
| k-anonymity floor k_min=5 suppression in repo layer + extend privacy regression test (value patterns, all public routes) | M1 |
| Server-side timestamp skew rejection (60 s future bound; generous past bound for buffered replays) | H5-adjacent |
| Rate limiting (Upstash) on ingest routes | M17 |
| First-attempt publish jitter via worker-thread publish (also removes remaining in-loop blocking; round-1 fast-fail bounds it but does not remove it) | M11, M5 |
| NTP gate: `time-sync.target` in systemd unit; implement the documented `Type=notify` + `WatchdogSec=300` or fix CLAUDE.md | H5(clock), M8 |
| SQLite integrity check + recreate-on-corruption (referenced in STATE.md, not yet implemented) | M9 |
| Route-handler tests (auth, mismatch, 501) — currently only raw zod schemas are tested | — |

## Larger initiatives (weeks, phased)

| Item | Finding / phase |
|---|---|
| LoRaWAN transport: Python+TS 17-byte codec (widen busy classes to 2 bytes or add saturation flag — simulation showed `person` at UCD peaks hits 259-425 vs the 255 1-byte cap), TTN webhook `/api/ingest/lora/uplink` with HMAC verification, airtime budget gate | Phase 4; audit L* |
| Model retrain + promotion pipeline: **first reconcile the 4-way class-taxonomy conflict** (runtime 9-class vs toolchain 9-class-different-names vs deployed 6-class NCNN at imgsz 640 vs runtime-expected 480), frozen held-out set, per-class metrics, count-level metric, NCNN parity check | `docs/training_plan.md`, `docs/evaluation_plan.md` |
| Fleet provisioning at 100 sensors: per-device token issuance/rotation, config rollout, monitoring dashboards, alerting | Phase 9-10 |
| Observability: Sentry wiring, structured ingest metrics, reconciliation alerts | Phase 5+ |
| Neon paid tier or storage re-architecture decision point (~when fleet > ~10 sensors even with retention) | C1 |

## Deliberately deferred / accepted at TRL-6

- Mock `deriveNow` time-shift (honest via pill), zod issue echo in 400s,
  key-name-only privacy test breadth (extended in round 1), MapLibre StrictMode
  workarounds (v2 TECH-01..03).
