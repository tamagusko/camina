# Coding Conventions

**Analysis Date:** 2026-04-23

CAMINA has two code surfaces with different conventions:

1. **Python** — edge/ML side under `src/camina/`, `custom_model_train/`, `scripts/`, `main.py`, `tests/`
2. **TypeScript / React** — Next.js 15/16 dashboard under `dashboard/src/`

## Naming Patterns

### Python

**Files & modules:** `snake_case.py`
- `src/camina/io/offline_buffer.py`, `src/camina/core/counter.py`, `src/camina/io/https_publisher.py`

**Classes:** `PascalCase` — `WindowedCounter`, `DailyAccumulator`, `HttpsPublisher`, `ConfigPoller`, `OfflineBuffer`, `ModalShareCounterApp`

**Functions / variables:** `snake_case` — `load_config`, `maybe_rollover`, `add_window`, `post_counts`

**Constants:** `UPPER_SNAKE_CASE` — `DEFAULT_ANCHOR`, `SCHEMA_VERSION`, `RETRIABLE_STATUS`, `CLASSES`

**Private members:** single leading underscore — `_window_start`, `_snapshot_and_reset`, `_align_to_window`

**Section separators inside modules:** use comment banners to group public API vs internals.
```python
# ---------- Public API ----------
# ---------- Internal ----------
```
Seen in `src/camina/core/counter.py`, `src/camina/io/https_publisher.py`, `src/camina/io/config_poller.py`.

### TypeScript / React

**Component files:** `PascalCase.tsx` — `StreetMap.tsx`, `ClassFilter.tsx`, `TimeWindowPicker.tsx`, `StreetSidePanel.tsx`, `CityMapShell.tsx`, `MockDataPill.tsx`.

**Hooks:** `useXxx.ts` in the same directory as their consumers — `dashboard/src/components/map/useMapQuery.ts`, `dashboard/src/components/map/useMapHash.ts`.

**Non-component TS files:** `kebab-case.ts` — `dashboard/src/lib/data-source.ts`, `dashboard/src/lib/cron-auth.ts`, `dashboard/src/lib/ingest-auth.ts`, `dashboard/src/lib/cache-tags.ts`, `dashboard/src/lib/mock-loader.ts`.

**UI primitives:** lowercase in `dashboard/src/components/ui/` — `pill.tsx` exports `Pill`.

**Route segment files:** Next.js conventions are respected — `page.tsx`, `layout.tsx`, `route.ts`, dynamic segments as `[city]`, `[id]`, `[...nextauth]`, route groups as `(auth)`.

**React components:** `PascalCase` exported as named exports — `export function StreetMap(...)`, `export function ClassFilter(...)`. Default exports are only used for Next.js page / layout / route conventions.

**Types / interfaces:** `PascalCase` — `StreetSummary`, `MetricValue`, `StreetsRepo`, `RoadUserClass`, `TimeWindow`.

**String-literal union constants:** arrays frozen with `as const`, with the type derived from them.
```ts
// dashboard/src/lib/types.ts
export const ROAD_USER_CLASSES = ["person", "cyclist", ...] as const;
export type RoadUserClass = (typeof ROAD_USER_CLASSES)[number];
```

## Python Style

### PEP 8 + explicit typing

All signatures carry type hints; `from __future__ import annotations` is used at the top of every production module (`src/camina/core/counter.py:24`, `src/camina/io/http_client.py:7`, etc.) so PEP 604 / built-in generics work on Python 3.10.

### Module-level docstrings

Every production module begins with a triple-quoted module docstring describing purpose and (for tricky ones) semantics. Examples:
- `src/camina/core/counter.py:1-23` — documents window alignment, partial flag, day rollover
- `src/camina/io/https_publisher.py:1-7`
- `src/camina/io/config_poller.py:1-10`
- `src/camina/io/schemas.py:1-7`

### Function / class docstrings

Google-style sections (`Args:`, `Returns:`, `Raises:`). Examples: `src/camina/io/http_client.py:74-80`, `src/camina/core/counter.py:56-71`, `src/camina/io/config_poller.py:26-38`.

### Dataclasses for config and domain objects

Immutable payloads use `@dataclass(frozen=True)`:
- `WindowSnapshot`, `DailySnapshot` in `src/camina/core/counter.py:40` and `:176`
- `PublisherResult` in `src/camina/io/https_publisher.py:32`
- `RetryPolicy` in `src/camina/io/http_client.py:24`
- `OutboxItem` in `src/camina/io/offline_buffer.py`

Mutable internal state uses the default `@dataclass` with `field(init=False)` for hidden fields (see `WindowedCounter` at `src/camina/core/counter.py:54-96`).

### Pydantic for wire schemas

All ingest payloads and server responses use `pydantic.BaseModel` with `ConfigDict(extra="forbid")` and field validators. See `src/camina/io/schemas.py` — `CountsPayload`, `DailyPayload`, `HeartbeatPayload`, `SensorConfig`, `IngestResponse`. Matching Zod schemas live in `dashboard/src/lib/schemas.ts` and deliberately mirror the Python field names (snake_case on the wire).

### Module size

CLAUDE.md calls for 200-400 line files; production modules respect that band:
- `src/camina/core/counter.py`: 323 lines
- `src/camina/io/https_publisher.py`: 170 lines
- `src/camina/io/http_client.py`: 158 lines
- `src/camina/io/config_poller.py`: 154 lines
- `src/camina/io/offline_buffer.py`: 193 lines
- `src/camina/io/schemas.py`: 141 lines
- `src/camina/utils/calibration.py`: 425 lines (slightly over; tolerated)
- `src/camina/app.py`: 342 lines (mixed: contains 6 classes + the main loop)

### Public API declaration

Modules expose a `__all__` at the bottom. Examples: `src/camina/core/counter.py:317-323`, `src/camina/io/schemas.py:134-141`, `src/camina/io/http_client.py:158`, `src/camina/io/https_publisher.py:170`, `src/camina/io/config_poller.py:154`.

`__init__.py` docstrings describe the package's surface (`src/camina/io/__init__.py:1-9`) and re-export only the stable public types.

### Import order

Three-block layout used consistently in the ingest/edge code:
```python
# 1. stdlib
import json, logging, uuid
from dataclasses import dataclass

# 2. third-party
import httpx
from pydantic import BaseModel

# 3. project
from src.camina.core.counter import DailySnapshot, WindowSnapshot
```
See `src/camina/io/https_publisher.py:10-26`.

## TypeScript / React Conventions

### Strict TypeScript

`dashboard/tsconfig.json`:
- `"strict": true`
- `"noUncheckedIndexedAccess": true`
- `"noImplicitOverride": true`
- `"forceConsistentCasingInFileNames": true`
- `"target": "ES2022"`, `"module": "esnext"`, `"moduleResolution": "bundler"`
- `"jsx": "react-jsx"` — no React import needed for JSX

### Path aliases

Only `"@/*": ["./src/*"]` (see `dashboard/tsconfig.json:28-32`). Import style:
```ts
import { ROAD_USER_CLASSES, type RoadUserClass } from "@/lib/types";
import { streetsRepo } from "@/lib/repo";
import { Pill } from "@/components/ui/pill";
```
The same alias is mirrored in `dashboard/vitest.config.ts:5-7` so unit tests resolve `@/...`.

### `type` imports

Explicit `type` keyword when importing types to keep the runtime bundle lean:
```ts
import type { Map as MaplibreMap } from "maplibre-gl";
import type { MetricValue, StreetSummary } from "@/lib/types";
```

### Server-only modules

Modules that must never be bundled into the client begin with `import "server-only";`:
- `dashboard/src/lib/repo/index.ts:1`
- `dashboard/src/lib/repo/streets-mock.ts:1`
- `dashboard/src/lib/data-source.ts:1`
- `dashboard/src/lib/auth.ts:1`
- `dashboard/src/lib/ingest-auth.ts:1`

### `"use client"` boundary

Client components start with `"use client";` and own all interactive state and browser APIs:
- `dashboard/src/app/[city]/CityMapShell.tsx:1`
- `dashboard/src/components/map/StreetMap.tsx:1`
- `dashboard/src/components/map/ClassFilter.tsx:1`
- `dashboard/src/components/panels/StreetSidePanel.tsx:1`
- `dashboard/src/components/map/useMapQuery.ts:1`

Server components (default) load data via repositories and hand shaped props to a thin client shell — see the page → shell pattern in `dashboard/src/app/[city]/page.tsx` ↔ `dashboard/src/app/[city]/CityMapShell.tsx`.

### MapLibre dynamic import

`MapLibre` touches `window` at import time and would break SSR. The pattern is to isolate it in a client component then `dynamic(... , { ssr: false })` from a client shell:
```ts
// dashboard/src/app/[city]/CityMapShell.tsx:10-23
const StreetMap = dynamic(
  () => import("@/components/map/StreetMap").then((m) => m.StreetMap),
  { ssr: false, loading: () => <div>Loading map…</div> }
);
```

### Async `params` (Next.js 15+)

Dynamic route segment params are awaited:
```ts
// dashboard/src/app/[city]/page.tsx:7-12
interface Props { params: Promise<{ city: string }>; }
export default async function CityPage({ params }: Props) {
  const { city } = await params;
  ...
}
```
Same pattern in every API route: `dashboard/src/app/api/streets/[id]/route.ts:4-9`, `dashboard/src/app/api/streets/[id]/readings/route.ts:5-10`, `dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts:6-11`.

### Props typing

Inline `interface Props { ... }` defined right above the component it types:
```ts
// dashboard/src/components/map/ClassFilter.tsx:8-13
interface Props {
  selected: RoadUserClass[];
  onChange: (next: RoadUserClass[]) => void;
}
export function ClassFilter({ selected, onChange }: Props) { ... }
```

### Hooks

Custom hooks prefix `use` and live beside the component that consumes them:
- `dashboard/src/components/map/useMapQuery.ts`
- `dashboard/src/components/map/useMapHash.ts`

Cleanup patterns: return a disposer from `useEffect`; cancellation flag pattern for fetches:
```ts
// dashboard/src/components/map/StreetMap.tsx:50-60
let cancelled = false;
fetch(url).then(...).catch(...);
return () => { cancelled = true; };
```

### `cn` helper for class merging

Tailwind class composition goes through `dashboard/src/lib/cn.ts`, which wraps `clsx` + `tailwind-merge`:
```ts
import { cn } from "@/lib/cn";
className={cn("base classes", condition && "conditional", className)}
```
Seen in `dashboard/src/components/ui/pill.tsx`, `dashboard/src/components/map/ClassFilter.tsx`, `dashboard/src/components/panels/StreetSidePanel.tsx`.

### Repository pattern (data layer)

Data access is routed through an interface (`StreetsRepo` in `dashboard/src/lib/repo/types.ts`) with two implementations (`streets-mock.ts`, `streets-live.ts`). `dashboard/src/lib/repo/index.ts` selects one based on `CAMINA_DATA_SOURCE` via the `isMock` flag from `dashboard/src/lib/data-source.ts`. All API routes and server components import only `streetsRepo` — they never reference the concrete mock/live files directly.

## Tailwind Usage

### Utility-first with design tokens

The project is strictly utility-first; there are no CSS modules. Colour, spacing, radius, font and shadow tokens are centralized in `dashboard/tailwind.config.ts`:
- Brand colours (`hover-gray`, `chip-gray`, `body-gray`, `muted-gray`, `link-blue`)
- Typography scale (`text-display`, `text-section`, `text-card`, `text-sub`, `text-nav`, `text-body`, `text-caption`, `text-micro`)
- Radius (`rounded-pill`, `rounded-card`, `rounded-feature`)
- Shadows (`shadow-subtle`, `shadow-medium`, `shadow-float`)
- Font families: `display` (UberMove) / `body` (UberMoveText)

### Component classes via `@layer components`

Repeated patterns get named component classes in `dashboard/src/styles/globals.css`:
- `.btn-primary` — pill button
- `.card`, `.chip` — surfaces
- `.text-body`, `.text-section`, etc. (via Tailwind's font-size plugin)

### Hybrid Tailwind + inline style (MapLibre sizing)

Height/width sizing for MapLibre containers is set both with Tailwind *and* inline `style` to beat the library's `.maplibregl-map` CSS which would otherwise collapse the container:
```tsx
// dashboard/src/components/map/StreetMap.tsx:241-259
<div
  className="relative h-screen w-screen overflow-hidden bg-white"
  style={{ height: "100dvh", width: "100vw" }}
>
  <div
    ref={containerRef}
    style={{ position: "absolute", top: 0, right: 0, bottom: 0, left: 0, width: "100%", height: "100%" }}
  />
  ...
</div>
```
Same pattern in `dashboard/src/app/[city]/page.tsx:20-24` and `dashboard/src/app/[city]/CityMapShell.tsx:15-21`. The inline `style` is deliberate — comments on the call sites explain *why*, so do not "clean up" by removing it.

### Responsive & a11y

- Mobile-first breakpoints: `md:flex`, `md:hidden`, `md:right-0`, `md:w-[400px]`
- `prefers-reduced-motion` media query in `globals.css` disables animations
- `role="dialog"`, `aria-label`, `aria-expanded`, `role="menuitemcheckbox"`, `aria-checked` are used on interactive chrome (see `dashboard/src/components/panels/StreetSidePanel.tsx:68-83`, `dashboard/src/components/map/ClassFilter.tsx:27-54`)

## Error Handling

### Python

**Specific exceptions first, narrow except blocks.** The HTTP client catches explicit httpx error types rather than bare `Exception`:
```python
# src/camina/io/http_client.py:92-104
except (httpx.ConnectError, httpx.ReadError, httpx.WriteError,
        httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as exc:
    last_exc = exc
    ...
```

**Defensive `except Exception` is allowed at top-level boundaries** to keep the agent alive when a callback misbehaves, but it always logs with `logger.exception(...)`:
```python
# src/camina/io/https_publisher.py:117-120
try:
    self._outbox.drain(self._send_outbox_item, max_items=10)
except Exception:
    logger.exception("drain_outbox raised (ignored, continuing)")
```

**Validation via pydantic** — schemas raise `ValidationError` on `model_validate*`; callers catch it explicitly:
```python
# src/camina/io/config_poller.py:95-103
try:
    config = SensorConfig.model_validate_json(response.content)
except ValidationError as exc:
    logger.error("Invalid config payload for sensor %s: %s", ...)
    self._last_error = "invalid_payload"
    return False
```

**Retries** are implemented by hand in `HttpClient.request` (`src/camina/io/http_client.py:67-127`) with a `RetryPolicy` dataclass, jittered exponential backoff (`_backoff`), and respect for the `Retry-After` header (`_delay_for_response`).

**Raise narrow errors on invalid input:** `ValueError` for bad config (naive timestamps, non-positive window) — `src/camina/core/counter.py:86-89`, `:312`.

### TypeScript

**Zod parsing for inputs.** Every API route that reads user input validates with a Zod schema and returns `400` with the issues array on failure:
```ts
// dashboard/src/app/api/streets/[id]/readings/route.ts:11-23
const parsed = readingsQuerySchema.safeParse({...});
if (!parsed.success) {
  return NextResponse.json({ error: "bad_query", issues: parsed.error.issues }, { status: 400 });
}
```
Same pattern in `dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts:15-19`.

**Structured error envelope.** API routes return `{ error: "<slug>", ...extras }` with standard slugs:
- `bad_query`, `bad_payload` — 400
- `missing_token`, `invalid_token`, `unauth` — 401
- `forbidden` — 403
- `not_found` — 404
- `sensor_id_mismatch` — 400
- `live_mode_not_implemented` — 501

**Client fetches** silently swallow errors on non-critical paths (filter re-fetch in `dashboard/src/components/map/StreetMap.tsx:50-60`) but surface them on diagnostics paths (admin side-panel in `dashboard/src/components/panels/StreetSidePanel.tsx:38-50`).

**No React error boundaries yet.** Next.js-convention `error.tsx` / `global-error.tsx` files are not present in `dashboard/src/app/`. Routes rely on `notFound()` (`dashboard/src/app/[city]/page.tsx:13`) and Next's default error page.

## API Route Conventions

All route handlers live under `dashboard/src/app/api/` as `route.ts` files. Public groups:

**Public read API** — `GET` only, Zod-validated query strings, `Cache-Control: public, s-maxage=30…60, stale-while-revalidate=…`:
- `dashboard/src/app/api/streets/route.ts` — list streets for a city
- `dashboard/src/app/api/streets/[id]/route.ts` — single street summary
- `dashboard/src/app/api/streets/[id]/readings/route.ts` — time-series
- `dashboard/src/app/api/metrics/route.ts` — latest metric values for map paint
- `dashboard/src/app/api/health/route.ts` — health + data-source check

**Admin API** — gated by `requireAdmin()` from `dashboard/src/lib/auth.ts`, relaxed in `isMock` mode for dev previews:
- `dashboard/src/app/api/admin/streets/[id]/info/route.ts` — reveals sensor IDs and GPS

**Ingest API** — POST only, Bearer token via `verifyIngestToken` in `dashboard/src/lib/ingest-auth.ts`, Zod body validation, 501 in live mode until DB wiring lands:
- `dashboard/src/app/api/ingest/sensors/[id]/counts/route.ts`
- `dashboard/src/app/api/ingest/sensors/[id]/daily/route.ts`
- `dashboard/src/app/api/ingest/sensors/[id]/heartbeat/route.ts`
- `dashboard/src/app/api/ingest/sensors/[id]/config/route.ts`

**Cron API** — GET only, gated by `verifyCron()` from `dashboard/src/lib/cron-auth.ts`:
- `dashboard/src/app/api/cron/refresh-aggregates/route.ts`
- `dashboard/src/app/api/cron/reconcile-daily/route.ts`
- `dashboard/src/app/api/cron/detect-silent/route.ts`

**Auth** — `dashboard/src/app/api/auth/[...nextauth]/route.ts` delegates to Auth.js v5 `handlers` exported from `dashboard/src/lib/auth.ts`.

**Privacy invariant.** Public endpoints never return `sensor_id`, `latitude`, or `longitude`; this is enforced by a regression test — see TESTING.md and `dashboard/tests/unit/privacy-regression.test.ts`.

## Logger Usage vs print()

### Production modules under `src/camina/` use `logging`

Every ingest/edge module defines a module-level logger with `logger = logging.getLogger(__name__)` and uses `logger.info / warning / error / exception`:
- `src/camina/core/counter.py:35`
- `src/camina/io/http_client.py:18`
- `src/camina/io/config_poller.py:23`
- `src/camina/io/https_publisher.py:29`
- `src/camina/io/offline_buffer.py:20`

`logger.exception` is used in `except Exception:` blocks to preserve tracebacks; `%s`-style format strings (not f-strings) are used in log calls so formatting is deferred.

### `print()` persists in the older ML/app path

`src/camina/app.py` (342 lines, predates the HTTPS edge-agent work) still uses `print(...)` for camera-position alerts and final counts (`src/camina/app.py:164-184`, `:340-342`). `src/camina/utils/display.py:13`, `:36`, `:38`, `:41` also print. This is technical debt — new code should reach for `logger`.

### Dashboard logging

Client-side code uses `console.info`, `console.error` with a `[CAMINA]` prefix for diagnostics (`dashboard/src/components/map/StreetMap.tsx:77`, `:121`, `:177`, `:185`, `:197`). Server code relies on thrown errors + Next.js default logging.

## Python Config / Factory / Registry Patterns

### Config loading

`src/camina/utils/config.py` provides `load_config()` and `load_classes()` — plain YAML readers that resolve the project root by walking up from the file to find `configs/`. Application config is a `Dict[str, Any]` passed into `ModalShareCounterApp` at `main.py:11-15`.

Hydra / OmegaConf are **not** used in this repo. Schema-driven config on the wire is done with pydantic (`SensorConfig` in `src/camina/io/schemas.py:97`).

### No Factory / Registry pattern yet

The ML training side (`custom_model_train/run_camina_pipeline.py`, `scripts/train/...`) is script-oriented and does not define `DATASET_FACTORY`/`register_*` decorators. The `ModalShareCounterApp` in `src/camina/app.py:190` wires components with plain constructor calls. CLAUDE.md's registry pattern is a style goal, not yet adopted here.

## Comments & TODOs

### Block comments that explain *why*

Non-obvious decisions have short comment blocks justifying them. Examples:
- `dashboard/src/app/[city]/CityMapShell.tsx:7-10` — why `dynamic(..., { ssr: false })`
- `dashboard/src/components/map/StreetMap.tsx:82-99` — why CARTO Positron + local tiles
- `dashboard/src/components/map/StreetMap.tsx:246-248` — why inline `style` is needed
- `dashboard/src/components/map/useMapQuery.ts:1-12` — rationale for query-string (vs hash) viewport
- `dashboard/proxy.ts:1-7` — Next 16 `middleware.ts` → `proxy.ts` rename and scope

### TODO / FIXME

Grepping `TODO|FIXME|HACK` across `src/camina/` and `dashboard/src/` returns **zero hits**. Pending work is tracked as inline narrative comments (e.g., `dashboard/src/app/api/cron/refresh-aggregates/route.ts:11` — `// Live mode: REFRESH MATERIALIZED VIEW …`) and in top-level `TODO.md` at the repo root.

### Docstrings vs inline

Python: public classes and functions get Google-style docstrings (see `src/camina/core/counter.py:55-71`, `src/camina/io/http_client.py:32-42`). Trivial helpers (`_as_utc`) get a one-liner or none.

TS: JSDoc appears sparingly on interfaces with non-obvious contracts — e.g., `/** Admin-only: reveals sensor identifiers and GPS … */` on `StreetsRepo.adminInfo` (`dashboard/src/lib/repo/types.ts:30-32`).

## Linting / Formatting / Type Checking

### Dashboard

`dashboard/package.json:9-17` exposes:
- `pnpm lint` — `next lint` (Next.js's built-in ESLint config; no project-local `.eslintrc` or `eslint.config.*`)
- `pnpm typecheck` — `tsc --noEmit`
- `pnpm test` / `pnpm test:watch` — Vitest
- `pnpm test:e2e` — Playwright

No Prettier config is present; formatting is whatever the IDE produces (2-space indent, double quotes observed consistently).

Inline ESLint escape hatches are used surgically — `// eslint-disable-next-line react-hooks/exhaustive-deps` at `dashboard/src/components/map/StreetMap.tsx:212` with a justifying comment right above it.

### Python

No `pyproject.toml`, `ruff.toml`, `.flake8`, or `mypy.ini` found at the repo root. There is no enforced formatter or linter. Style is hand-maintained (PEP 8-ish, consistent 4-space indent, double-quoted strings, line lengths generally ≤100). Type hints are still used everywhere in `src/camina/`.

Dependencies are pinned in `requirements.txt` and `environment.yml` (Python 3.10 conda env); no `uv` lockfile. `requirements_calibration.txt` is a secondary pin set for the calibration path.

## Git / Commit Conventions

### Conventional Commits (partial)

`git log --oneline` shows a `type: subject` format is used, though the type vocabulary is mixed:
- `feat:` — feature work (`feat: HTTPS edge agent (Plan 01) + Vercel dashboard scaffold (Plan 02)`, `feat: complete project restructure with CAMINAv1 model integration`, `feat: add epaper display`)
- `fix:` — bug fixes (`fix: cleaning and adjusting the project structure`, `fix: adjust the display size`)
- `dev:` — in-progress development snapshots (`dev: 20250710 display and calibration implementation`)
- Date-prefixed snapshots: `20240904: update`

**Preferred going forward:** stick to `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` per CLAUDE.md and the user-global Conventional Commits rule. Avoid `dev:` and date-only prefixes for new work.

### Scope

Scope is used informally in parenthesised subjects (e.g., `(Plan 01)`, `(Plan 02)`) rather than `type(scope):`.

## File Organisation Rules

### Python

```
src/camina/
├── __init__.py            # empty
├── app.py                 # legacy ML loop (ModalShareCounterApp)
├── core/                  # domain logic (no I/O): counter, tracker
├── io/                    # HTTP client, publisher, offline buffer, config poller, schemas
├── service/               # sensor_daemon composes core + io
└── utils/                 # config, display, calibration
```
Tests live in top-level `tests/`, mirroring module names (`test_windowed_counter.py` ↔ `src/camina/core/counter.py`).

### Dashboard

```
dashboard/src/
├── app/                   # Next.js route tree
│   ├── (auth)/sign-in/    # route group
│   ├── [city]/            # public map
│   ├── admin/             # admin UI (layout gates via requireAdmin)
│   └── api/               # route handlers (public / admin / ingest / cron / auth)
├── components/
│   ├── charts/            # Recharts wrappers
│   ├── layout/            # MockDataPill etc.
│   ├── map/               # StreetMap + filters + hooks
│   ├── panels/            # side panel
│   └── ui/                # lowercase primitives (pill)
├── lib/
│   ├── repo/              # data layer (mock + live + types)
│   ├── schemas.ts         # Zod schemas mirroring Python pydantic
│   ├── types.ts           # shared TS types
│   ├── data-source.ts     # CAMINA_DATA_SOURCE switch
│   ├── auth.ts            # Auth.js v5 config + requireAdmin
│   ├── cron-auth.ts       # cron Bearer guard
│   ├── ingest-auth.ts     # ingest Bearer guard
│   ├── cache-tags.ts
│   ├── cn.ts, geo.ts, db.ts, mock-loader.ts
├── styles/globals.css
└── components/...
```

Tests for the dashboard live outside `src/` at `dashboard/tests/unit/` (Vitest) and `dashboard/tests/e2e/` (Playwright), per the respective config files.

---

*Convention analysis: 2026-04-23*
