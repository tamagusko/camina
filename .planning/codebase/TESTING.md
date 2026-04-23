# Testing Patterns

**Analysis Date:** 2026-04-23

CAMINA has three independent test surfaces:

1. **Python unit / integration tests** — `tests/` at the repo root, pytest
2. **Dashboard unit tests** — `dashboard/tests/unit/`, Vitest
3. **Dashboard end-to-end tests** — `dashboard/tests/e2e/`, Playwright

There is also a lightweight manual-testing toolkit under `dashboard/scripts/` (headless Chromium diagnostics + headed preview).

## Python — pytest

### Framework

**Runner:** `pytest` (not pinned in a requirements file; comes from a dev shell / system install).
**Cache:** `.pytest_cache/` is present at the repo root, confirming pytest is the active runner.
**Config:** No `pytest.ini`, `pyproject.toml`, `setup.cfg`, or `tox.ini` — defaults are used.
**Assertion library:** native `assert` (pytest rewrites assertions).

### Run commands

```bash
pytest                                  # run all tests
pytest tests/test_windowed_counter.py   # run a single file
pytest -k "rollover"                    # filter by keyword
pytest tests/test_https_publisher.py::test_client_retries_on_500_then_succeeds  # single test
```

The `tests/` directory is marked as an importable package (`tests/__init__.py` exists), so tests can share helpers if needed. Imports use the repo-absolute form `from src.camina.… import …` — there is no `conftest.py` yet.

### File layout

Co-located one-to-one with the module under test:

```
tests/
├── __init__.py                      (empty, marks package)
├── test_windowed_counter.py         → src/camina/core/counter.py (WindowedCounter)
├── test_daily_accumulator.py        → src/camina/core/counter.py (DailyAccumulator)
├── test_offline_buffer.py           → src/camina/io/offline_buffer.py
├── test_config_poller.py            → src/camina/io/config_poller.py
├── test_https_publisher.py          → src/camina/io/http_client.py + https_publisher.py
├── test_sensor_daemon.py            → src/camina/service/sensor_daemon.py (integration)
├── test_display.pi                  (legacy, not a valid test module — .pi extension)
└── test.mov                         (fixture video, 24 MB)
```

### Naming

- Files: `test_<module>.py`
- Tests: `test_<behaviour>()`, snake_case, one clause per test.
- Section separators inside a test file use comment banners matching the production code's style:
  ```python
  # ---------- Construction ----------
  # ---------- Counting semantics ----------
  # ---------- Rollover ----------
  # ---------- Snapshot immutability ----------
  ```
  See `tests/test_windowed_counter.py`, `tests/test_offline_buffer.py`, `tests/test_https_publisher.py`.

### Test structure

Module docstring states what is being tested:
```python
# tests/test_windowed_counter.py:1
"""Unit tests for WindowedCounter."""
```

Then: module-level constants (`CLASSES`, `UTC`), tiny helper factories (`_start_counter`, `_window`, `_fast_retry`), fixtures, then tests grouped by concern.

### Fixtures

`@pytest.fixture()` + `tmp_path` for anything touching SQLite / file I/O. Always closed in a `try/finally` so a failing test still releases the DB:
```python
# tests/test_offline_buffer.py:13-19
@pytest.fixture()
def buf(tmp_path: Path) -> Iterator[OfflineBuffer]:
    b = OfflineBuffer(db_path=tmp_path / "state.db", max_rows=100)
    try:
        yield b
    finally:
        b.close()
```
Same pattern in `tests/test_daily_accumulator.py:21-26` and `tests/test_https_publisher.py:42-48`.

### Assertion style

Native `assert` with a single-fact check per assertion. Multiple assertions per test are fine when they check different facets of the same behaviour:
```python
# tests/test_https_publisher.py:154-176
assert result.delivered is True
assert result.enqueued is False
assert result.latest_config_version == "v2"
assert received[-1]["sensor_id"] == "cam-01"
```

Exceptions are checked with `pytest.raises`:
```python
# tests/test_windowed_counter.py:33-35
def test_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError):
        WindowedCounter(classes=CLASSES, window_seconds=0)
```

Typed signatures on tests (`-> None`) are used throughout.

### Timezone-aware UTC across the suite

Every test that touches time uses `tzinfo=UTC`. The production code raises `ValueError` on naive datetimes, so tests exercise both the positive path and the naive-rejection path:
- `tests/test_windowed_counter.py:44-48` (`test_rejects_naive_timestamps_in_add`)
- `tests/test_windowed_counter.py:38-41` (`test_rejects_naive_anchor`)

Hard-coded dates in tests are in **2026** (e.g., `datetime(2026, 4, 21, …)`) so they never drift.

## Mocking — Python

### httpx.MockTransport (preferred)

All network is intercepted with `httpx.MockTransport` passed into the production `HttpClient` constructor (the production code exposes a `transport=` kwarg specifically for this; see `src/camina/io/http_client.py:50`). Pattern:
```python
# tests/test_https_publisher.py:54-66
def test_client_returns_success_without_retry() -> None:
    calls: list[httpx.Request] = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True, "latest_config_version": "v1"})
    transport = httpx.MockTransport(handler)
    with HttpClient("https://api.test", token="t", retry=_fast_retry(), transport=transport) as c:
        response = c.request("POST", "/v1/sensors/1/counts", content=b"{}")
    assert response.status_code == 200
```

Retry and backoff timing is kept fast in tests via a `_fast_retry()` helper that sets `base_delay_s=0` / `max_delay_s=0` / `jitter=0`:
```python
# tests/test_https_publisher.py:25-27
def _fast_retry() -> RetryPolicy:
    return RetryPolicy(max_attempts=3, base_delay_s=0.0, max_delay_s=0.0, jitter=0.0)
```
Reused in `tests/test_config_poller.py:15-17`.

### unittest.mock.patch for module-level datetime

Frozen time is applied by patching `datetime` in the production module:
```python
# tests/test_windowed_counter.py:16-27
def _start_counter(start: datetime, window_seconds: int = 900) -> WindowedCounter:
    with patch("src.camina.core.counter.datetime", wraps=datetime) as dt:
        dt.now.return_value = start
        return WindowedCounter(classes=list(CLASSES), window_seconds=window_seconds, anchor=DEFAULT_ANCHOR)
```

The `DailyAccumulator` boot-recovery test uses a fake `datetime` subclass to freeze a later "now":
```python
# tests/test_daily_accumulator.py:106-113
class _FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return fake_now if tz else fake_now.replace(tzinfo=None)

with patch("src.camina.core.counter.datetime", _FakeDT):
    acc2 = DailyAccumulator(...)
```

### Callback injection for side-effect callables

`ConfigPoller` takes `apply=` and `persist=` callables as constructor args so tests inject `list.append` capture helpers instead of mocking:
```python
# tests/test_config_poller.py:49-55
applied: list[SensorConfig] = []
persisted: list[str] = []
poller = ConfigPoller(
    sensor_id="cam-01",
    http_client=client,
    current_version=current_version,
    apply=applied.append,
    persist=persisted.append,
)
```
This is a deliberate design choice — the production code makes callbacks pluggable so tests don't need to monkeypatch.

### What is NOT mocked

- **SQLite** is exercised as a real dependency against `tmp_path` — offline buffer and daily accumulator tests hit real DB files (`tests/test_offline_buffer.py:147-156`, `tests/test_daily_accumulator.py:94-133`). Persistence across reopen is tested by closing and re-instantiating the class.
- **Pydantic validators** are exercised against real payloads, not mocked.
- **Thread safety** in `OfflineBuffer` is tested with a real `ThreadPoolExecutor` (`tests/test_offline_buffer.py:162-169`).

## Dashboard — Vitest (unit)

### Framework

**Runner:** `vitest` ^2.1.5 (from `dashboard/package.json:50`).
**Environment:** `node` (no jsdom yet — `dashboard/vitest.config.ts:9`). This is enough for the current repository-pattern tests; DOM-dependent component tests would need `environment: "jsdom"`.
**Config:** `dashboard/vitest.config.ts`
```ts
export default defineConfig({
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "node", include: ["tests/unit/**/*.test.ts"], globals: false },
});
```
- `globals: false` means `describe`, `it`, `expect` are imported explicitly per file.
- The `@/...` alias mirrors `tsconfig.json` so test imports look identical to production code.

### Run commands

```bash
pnpm --filter camina-dashboard test         # single run
pnpm --filter camina-dashboard test:watch   # watch mode
# Or from inside dashboard/:
pnpm test
pnpm test:watch
```

### File layout

```
dashboard/tests/
├── unit/
│   ├── schemas.test.ts              → dashboard/src/lib/schemas.ts
│   └── privacy-regression.test.ts   → dashboard/src/lib/repo/streets-mock.ts
└── e2e/
    └── public-map.spec.ts           → Playwright
```

Unit test files end in `.test.ts`; e2e specs end in `.spec.ts` (Playwright convention).

### Test structure (Vitest)

BDD-style with `describe` + `it`, one assertion cluster per case:
```ts
// dashboard/tests/unit/schemas.test.ts:9-36
import { describe, expect, it } from "vitest";
import { countsPayloadSchema } from "@/lib/schemas";

describe("countsPayloadSchema", () => {
  const valid = { ... };

  it("accepts a complete payload", () => {
    expect(() => countsPayloadSchema.parse(valid)).not.toThrow();
  });

  it("rejects negative counts", () => {
    const bad = { ...valid, counts: { person: -1 } };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });
});
```

Boundary behaviour is exercised per schema (`countsPayloadSchema`, `dailyPayloadSchema`, `heartbeatPayloadSchema`, `readingsQuerySchema` — all in `dashboard/src/lib/schemas.ts`). Fixtures are built inline per test via spread (`{ ...valid, counts: { person: -1 } }`) — there is no shared factory file yet.

### Privacy regression test (binding)

`dashboard/tests/unit/privacy-regression.test.ts` is the critical invariant test for the public API. It walks the objects returned by `mockStreetsRepo.list`, `.get`, `.readings`, `.latestMetrics` and fails CI if the key `sensor_id`, `sensorId`, `latitude`, or `longitude` appears anywhere in the result:
```ts
// dashboard/tests/unit/privacy-regression.test.ts:8-22
const FORBIDDEN_KEYS = ["sensor_id", "sensorId", "latitude", "longitude"];

function assertClean(value: unknown, path = "$") {
  ...
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (FORBIDDEN_KEYS.includes(k)) {
      throw new Error(`Privacy leak at ${path}.${k}: forbidden key`);
    }
    assertClean(v, `${path}.${k}`);
  }
}
```
**This test exercises the mock repository directly; it does not spin up a dev server.** The equivalent server-level check runs in Playwright (see below).

## Mocking — Dashboard

### Repository pattern as the mock boundary

The dashboard's data layer (`dashboard/src/lib/repo/`) exposes a single `StreetsRepo` interface (`dashboard/src/lib/repo/types.ts`) with two implementations:
- `dashboard/src/lib/repo/streets-mock.ts` — reads JSON fixtures via `dashboard/src/lib/mock-loader.ts`
- `dashboard/src/lib/repo/streets-live.ts` — reads Postgres via Drizzle

`dashboard/src/lib/repo/index.ts` picks the implementation based on `CAMINA_DATA_SOURCE`. Tests import the mock directly and exercise it as the real object under test — no additional mocking library is needed.

Fixtures are seeded under `dashboard/scripts/` / `dashboard/drizzle/` and loaded via `dashboard/src/lib/mock-loader.ts`. The Playwright webServer sets `CAMINA_DATA_SOURCE: "mock"` so the e2e suite hits the same mock repo through real API routes.

### No `vi.mock` usage yet

The current suite does not call `vi.mock(...)` — the repository pattern and injected callbacks (Python side) mean prod code is test-shaped without runtime mocking.

## Dashboard — Playwright (e2e)

### Config

`dashboard/playwright.config.ts`:
```ts
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000", trace: "on-first-retry" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile",  use: { ...devices["Pixel 7"] } },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : { command: "pnpm dev", url: "http://localhost:3000",
        reuseExistingServer: !process.env.CI,
        env: { CAMINA_DATA_SOURCE: "mock" } },
});
```
Key points:
- Dual desktop / mobile projects (Pixel 7).
- Spawns `pnpm dev` and forces `CAMINA_DATA_SOURCE=mock` so the dev server uses fixtures.
- Respects an external `PLAYWRIGHT_BASE_URL` (preview deployment).

### Run commands

```bash
pnpm test:e2e                                    # runs both projects
pnpm exec playwright test tests/e2e/public-map.spec.ts --project=desktop
pnpm exec playwright test --ui                   # watch / debug
```

### Tests present

`dashboard/tests/e2e/public-map.spec.ts` — three smoke tests:
1. Public map renders for `/dublin` (checks `Mock data` pill + `.maplibregl-map` visible).
2. Street detail page renders for seeded street `dame-st`.
3. **Privacy smoke at the HTTP layer** — `GET /api/streets?city=dublin` is scanned for the forbidden key strings `"sensor_id"`, `"latitude"`, `"longitude"`. This catches any leak that bypasses the mock repo (e.g., an API route that reaches into `sensors` directly).

## Manual testing / diagnostics

### Playwright-driven scripts under `dashboard/scripts/`

These are not part of any test suite; they are manual tools run by hand:

- **`dashboard/scripts/inspect-map.mjs`** — launches headless Chromium, navigates to `http://localhost:3000/dublin` (or `$URL`), captures console logs, measures the MapLibre canvas and every ancestor element's computed size, logs tile requests, and writes `dashboard/scripts/camina-preview.png`. Invoke with:
  ```bash
  pnpm exec node scripts/inspect-map.mjs
  ```
  It is the tool used to diagnose the MapLibre sizing issue documented in the hybrid Tailwind + inline-style pattern (see `CONVENTIONS.md`).

- **`dashboard/scripts/open-preview.mjs`** — launches a *headed* Chromium at the same URL and keeps it open, streaming console logs to the terminal until Ctrl+C. Useful for interactive manual testing with live logs:
  ```bash
  pnpm exec node scripts/open-preview.mjs
  ```

- **`dashboard/scripts/download-dublin-tiles.mjs`** — pre-downloads OpenStreetMap raster tiles into `public/tiles/{z}/{x}/{y}.png` for offline/local dev map rendering (referenced by `dashboard/src/components/map/StreetMap.tsx:94`).

Both scripts import from `@playwright/test` and use `process.env.URL` as an override — Playwright is a manual testing dependency here, not only an e2e runner.

### `.playwright-mcp/` at the repo root

`.playwright-mcp/` stores captured traces / console logs / page snapshots from prior manual sessions:
```
.playwright-mcp/console-2026-04-21T13-47-47-193Z.log
.playwright-mcp/console-2026-04-21T13-57-17-336Z.log
.playwright-mcp/page-2026-04-21T13-47-47-532Z.yml
.playwright-mcp/page-2026-04-21T13-57-17-678Z.yml
```
These are artefacts from Claude / MCP-assisted browsing sessions used to diagnose frontend issues — they are not machine-generated by the test suite. Treat as debug captures, not test fixtures.

## Coverage

No coverage tool is configured:
- Python: no `pytest-cov`, no `.coveragerc`.
- Dashboard: Vitest supports `--coverage` via `@vitest/coverage-v8`, but it is not in `dashboard/package.json` dependencies and `vitest.config.ts` does not set a coverage block.

If coverage becomes a gate, the minimum wiring is:
```bash
# Python
pytest --cov=src/camina --cov-report=term-missing

# Dashboard
pnpm add -D @vitest/coverage-v8
# then `pnpm test -- --coverage`
```

## CI

**No CI configuration is present.** There is no `.github/workflows/`, `.circleci/`, `.gitlab-ci.yml`, or similar at the repo root. `playwright.config.ts` already branches on `process.env.CI` (`forbidOnly`, `retries: 2`) so the suite is CI-ready, but nothing is wired to run it yet.

When adding CI, cover these three jobs:
1. **Python tests** — `pytest tests/` on Python 3.10 with `requirements.txt` installed.
2. **Dashboard unit + typecheck + lint** — `pnpm install --frozen-lockfile && pnpm --filter camina-dashboard run lint typecheck test`.
3. **Dashboard e2e** — install Playwright browsers, then `pnpm --filter camina-dashboard test:e2e` with `CAMINA_DATA_SOURCE=mock`.

## Representative test files (quick reference)

| Test file | What it exercises |
|---|---|
| `tests/test_windowed_counter.py` | Window alignment, dedupe, rollover, partial flag, snapshot immutability |
| `tests/test_daily_accumulator.py` | Day rollover, late-publication recovery, SQLite persistence |
| `tests/test_offline_buffer.py` | FIFO order, drain-on-failure, size cap, crash recovery, concurrency |
| `tests/test_config_poller.py` | Version gating, fetch failure, validation failure, apply failure |
| `tests/test_https_publisher.py` | Retries, backoff, outbox drain, Bearer auth header |
| `tests/test_sensor_daemon.py` | End-to-end integration across counter + publisher + config poller |
| `dashboard/tests/unit/schemas.test.ts` | Zod boundaries on ingest / query schemas |
| `dashboard/tests/unit/privacy-regression.test.ts` | Forbidden keys never appear in public repo outputs |
| `dashboard/tests/e2e/public-map.spec.ts` | Map renders; street detail renders; `/api/streets` is privacy-safe |

---

*Testing analysis: 2026-04-23*
