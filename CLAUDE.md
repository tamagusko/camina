# CLAUDE.md

## Project — CAMINA

Privacy-first traffic-sensor network. Fine-tuned 9-class YOLO11n (NCNN) on Raspberry Pi 5 8GB — the TRA 2026 model lives on `origin/TRA2026` and is being brought to `main` (PLAN.md S1). Research at UCD Spatial Dynamics Lab, funded by REALLOCATE (EU grant 101103924). TRL-6 target 2026-05-31 was missed; M1 re-baselined to 2026-12-31 (PLAN.md D12).

**Core value:** one Pi on one real Dublin street, counting nine road-user classes, feeding a live public dashboard — demonstrably privacy-preserving, lightweight, reproducible.

## Where state lives

Authoritative project state is in `.planning/`:

- `.planning/STATE.md` — current stage, verified-working list, blockers, open decisions, next action (has a `Last verified` date; trust it over chat)
- `.planning/PLAN.md` — the staged plan: M1 (first fully functional unit) and M2 (deployment-ready fleet), stages S1–S14 with done-tests
- `.planning/PROJECT.md` — identity, core value, constraints, out-of-scope, dated decisions
- `.planning/audit-2026-09-15/AUDIT.md` — code-maturity audit and claims-vs-code matrix (the current codebase map)
- `.planning/old/` — superseded planning (GSD roadmap, phases, requirements); read-only history

If a fact in chat contradicts `.planning/`, trust `.planning/` and offer to update it. A stage is done only when its done-test in PLAN.md has passed and the evidence is committed (`docs/benchmarks/` for measurements).

## Tech stack (summary)

Current component status in `.planning/audit-2026-09-15/AUDIT.md` §1; the 2026-04 stack snapshots are archived in `.planning/old/2026-09-15-gsd/{codebase,research}/STACK.md`.

**Edge (Python 3.10, `uv` preferred):**
- Ultralytics YOLO11n (CAMINAv1 = TRA 2026 model, NCNN 640×640, 9 classes in alphabetical model order remapped to `configs/classes.yaml` by name)
- Custom SORT-style Kalman + Hungarian tracker (`filterpy` + `scipy`, `core/tracker.py`) — no DeepSORT / appearance features
- `src/camina/core/` (WindowedCounter, DailyAccumulator, OfflineBuffer, Tracker)
- `src/camina/io/` (HttpClient, HttpsPublisher, ConfigPoller)
- `src/camina/service/sensor_daemon.py` (composed orchestrator)
- Runs on Pi 5 8GB ARM64 via `systemd` (`deploy/systemd/camina-sensor.service`: `Type=notify`, `WatchdogSec=300`, `After=time-sync.target`; never yet run on a Pi — PLAN.md S6)

**Dashboard (`dashboard/`, pnpm):**
- Next.js 16 App Router + React 19 + TypeScript 5 (strict, `noUncheckedIndexedAccess`)
- Tailwind + hand-rolled UI, Uber-inspired monochrome (`DESIGN.md`)
- MapLibre GL (local Carto tiles dev; Protomaps PMTiles prod)
- Drizzle ORM + Neon Postgres + PostGIS via Vercel Marketplace
- Auth.js v5 + Google OAuth (UCD Workspace internal) — required before the first live deploy (D6, PLAN.md S5)
- Vercel Fluid Compute (**not** Edge runtime); Upstash Ratelimit (env-gated, skipped when unset). No Sentry, BotID or Rolling Releases in the code (closed 2026-09-15 — PLAN.md §4).
- **Critical:** `attachDatabasePool(client)` from `@vercel/functions` in `dashboard/src/lib/db.ts` (in place, `db.ts:33`)

**Transport:**
- P0: WiFi/HTTPS (primary) — 144 edge pytest passing on the dev host; cellular = HTTPS over a cellular bearer (bearer-agnostic edge, untested in the field)
- P1 (M2-optional, D1): LoRaWAN codec (20-byte schema-v2, `docs/lora.md`) + TTN webhook exist as tested code; not wired to the daemon, no radio, sensor-id format (`LNN` vs `cam-dub-NN`) unresolved

## Load-bearing constraints

- **Privacy is non-negotiable.** Public UI never exposes exact sensor GPS. k-anonymity floor k_min=5. `ON DELETE CASCADE` from `sensors` for right-to-erasure. Enforced by regression test. k_min=5 is enforced in the mock adapter and tested; the live adapter must enforce it before `CAMINA_DATA_SOURCE=live` (S4). Speeds are published (D2) and must be suppressed together with counts below k_min.
- **Dublin only in v1.** Data model keyed by city; multi-city is a v2 concern.
- **TRL-6 bar, not industrial SLA.** Research-grade reliability. Pi benchmarks and ground-truth counts are M1 evidence (PLAN.md S6/S9); paper artefacts stay out of scope.
- **Solo developer.** Planning and review pacing must suit solo cognitive load.
- **Budget.** Vercel Hobby + Neon free + TTN community. No paid tiers for v1.
- LoRa payload is the 20-byte schema-v2 binary frame (`docs/lora.md`), relevant only if LoRa is taken up in M2 (D1).
- **`NEXT_PUBLIC_CAMINA_DEV_ADMIN` must not ship to production** (build-time guard in `dashboard/next.config.mjs`, in place since 2026-07-10 — keep it).

## Conventions

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- **Python:** PEP 8, type hints, `logger = logging.getLogger(__name__)` (no `print`), dataclass configs preferred immutable.
- **TypeScript:** strict mode; zod at API boundaries; Drizzle for DB.
- **Secrets:** never commit `.env*`, `settings.json`, `*.pem`, `credentials.json`. `dashboard/.env.local` is gitignored. `AUTH_SECRET` was rotated 2026-04-23 — do not reuse the old value.
- **Tests:** pytest on edge (144 pass); Vitest 89 unit tests across 9 files (require `data/mock/dublin` fixtures generated by `scripts/generate_mock_dublin.py`; gitignored) + Playwright (3 specs × 2 projects, not run in CI). CI gate: PLAN.md S2.
- **MapLibre tech-debt:** Strict Mode is disabled as a safety net for a canvas sizing race; re-enable only after the race is properly guarded (tracked as v2 TECH-01..03).

---

## Behavioural guidelines

Reduce common LLM coding mistakes. Merge with the project context above.

**Tradeoff:** these guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
