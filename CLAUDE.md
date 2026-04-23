# CLAUDE.md

## Project — CAMINA

Privacy-first traffic-sensor network. Fine-tuned 9-class YOLO11 detector on Raspberry Pi 5 8GB, custom Kalman + Hungarian tracker, windowed on-device counts, published to a Next.js dashboard that colour-codes Dublin streets by count/speed. INTERREG-funded research at UCD. TRL-6 target: **2026-05-31**.

**Core value:** one Pi on one real Dublin street, counting nine road-user classes, feeding a live public dashboard — demonstrably privacy-preserving, lightweight, reproducible.

## Where state lives

Authoritative project state is in `.planning/`. Always consult these before planning or coding:

- `.planning/STATE.md` — current phase, progress, blockers, accumulated context
- `.planning/PROJECT.md` — identity, core value, validated / active / out-of-scope requirements, key decisions
- `.planning/ROADMAP.md` — 11 phases across 2 milestones, ~31 plans, REQ-ID mapping
- `.planning/REQUIREMENTS.md` — 70 v1 requirements across 12 categories
- `.planning/codebase/` — structured codebase map (stack, architecture, conventions, testing, concerns)
- `.planning/research/` — stack lock-in, features, architecture directives, pitfalls, summary
- `.planning/phases/<NN>/` — per-phase PLAN.md + execution artefacts (created by `/gsd-plan-phase`)

If a fact in chat contradicts `.planning/`, trust `.planning/` and offer to update it.

## GSD workflow

The project runs on GSD (Get Shit Done) slash commands. Do not reinvent planning manually:

- `/gsd-plan-phase N` — produce PLAN.md for phase N (research → planner → plan-checker)
- `/gsd-execute-phase N` — executor applies PLAN.md atomically with deviation handling
- `/gsd-verify-work` / `/gsd-validate-phase` — goal-backward verification
- `/gsd-transition` — close out a phase, update PROJECT.md + STATE.md
- `/gsd-complete-milestone` — milestone review
- `/gsd-check-todos`, `/gsd-add-todo`, `/gsd-note` — lightweight capture

Config lives in `.planning/config.json` (mode: YOLO, granularity: standard, parallelization on, commit docs on, balanced model profile).

## Tech stack (summary)

Full detail in `.planning/codebase/STACK.md` and `.planning/research/STACK.md`.

**Edge (Python 3.10, `uv` preferred):**
- Ultralytics YOLO11 (fine-tuned CAMINAv1, NCNN export for Pi)
- Custom Kalman + Hungarian tracker (`filterpy` + `scipy`) — **not** SORT
- `src/camina/core/` (WindowedCounter, DailyAccumulator, OfflineBuffer, Tracker)
- `src/camina/io/` (HttpClient, HttpsPublisher, ConfigPoller)
- `src/camina/service/sensor_daemon.py` (composed orchestrator)
- Runs on Pi 5 8GB ARM64 via `systemd` (`Type=notify`, `WatchdogSec=300`)

**Dashboard (`dashboard/`, pnpm):**
- Next.js 16 App Router + React 19 + TypeScript 5 (strict, `noUncheckedIndexedAccess`)
- Tailwind + hand-rolled UI, Uber-inspired monochrome (`DESIGN.md`)
- MapLibre GL (local Carto tiles dev; Protomaps PMTiles prod)
- Drizzle ORM + Neon Postgres + PostGIS via Vercel Marketplace
- Auth.js v5 + Google OAuth (UCD Workspace internal)
- Vercel Fluid Compute (**not** Edge runtime), Rolling Releases, BotID, Upstash Ratelimit, Sentry
- **Critical (M2):** `attachDatabasePool(client)` from `@vercel/functions` in `dashboard/src/lib/db.ts`

**Transport:**
- P0: WiFi/HTTPS (primary) — 60 tests passing
- P1: LoRaWAN → TTN webhook → `/api/ingest/lora/uplink`, 17-byte binary codec (3B cam ID + 4B epoch + 9B counts + 1B schema)

## Load-bearing constraints

- **Privacy is non-negotiable.** Public UI never exposes exact sensor GPS. k-anonymity floor k_min=5. `ON DELETE CASCADE` from `sensors` for right-to-erasure. Enforced by regression test.
- **Dublin only in v1.** Data model keyed by city; multi-city is a v2 concern.
- **TRL-6 bar, not industrial SLA.** Research-grade reliability. Paper/benchmarks deferred.
- **Solo developer.** Planning and review pacing must suit solo cognitive load.
- **Budget.** Vercel Hobby + Neon free + TTN community. No paid tiers for v1.
- **LoRa payload ≤ 200 chars** carrying camera ID (`LNN`, e.g. `D01`), timestamp (`YYMMDDHHMM`), nine class counts. Every character earns its place.
- **`NEXT_PUBLIC_CAMINA_DEV_ADMIN` must not ship to production** (HIGH concern — build-time guard in Phase 7).

## Conventions

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- **Python:** PEP 8, type hints, `logger = logging.getLogger(__name__)` (no `print`), dataclass configs preferred immutable.
- **TypeScript:** strict mode; zod at API boundaries; Drizzle for DB.
- **Secrets:** never commit `.env*`, `settings.json`, `*.pem`, `credentials.json`. `dashboard/.env.local` is gitignored. `AUTH_SECRET` was rotated 2026-04-23 — do not reuse the old value.
- **Tests:** pytest on edge (60 tests currently pass); Vitest + Playwright on dashboard.
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
