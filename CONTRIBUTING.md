# Contributing to CAMINA

Welcome. CAMINA is a privacy-first traffic-sensor network — Raspberry Pi sensors feeding a Next.js dashboard that colour-codes Dublin streets by count and speed. TRL-6 demo target: **2026-05-31**.

This doc is the ground rules. Pair it with [`TODO.md`](./TODO.md) to pick up work.

---

## Quick-start

```bash
git clone git@github.com:<org>/camina.git && cd camina

# Python edge-agent (repo root)
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv once
uv sync
uv run pytest tests/                              # 60 tests should pass

# Dashboard (./dashboard)
cd dashboard
pnpm install
pnpm exec node scripts/download-dublin-tiles.mjs  # one-time, ~60 MB
cp .env.example .env.local
pnpm dev                                          # → http://localhost:3000/dublin
```

Green `pytest` and a working `/dublin` map = you're set up.

---

## Project layout

| Path | What's there |
|------|--------------|
| `src/camina/` | Python edge-agent (`core/`, `io/`, `service/`) |
| `dashboard/` | Next.js 16 + Drizzle + MapLibre dashboard |
| `docs/` | Protocol, reconciliation, deployment |
| `tests/` | Python tests (pytest) |
| `.planning/` | Project memory — **read-only for contributors** |
| `TODO.md` | Your work queue |

---

## Claiming a task

1. Open [`TODO.md`](./TODO.md).
2. Pick a task tagged at your comfort level (★ / ★★ / ★★★).
3. Edit TODO.md: change `[ ]` → `[x]` and add your name in **Claimed by:** — commit that on the same branch as your work (`chore(todo): claim <task>`).
4. Open a **draft PR early**. Small is better than done.
5. Mark ready for review when tests pass locally.

One person per task. If you want to pair, coordinate first.

---

## Branches & commits

- Branch from `main`: `feat/<short>`, `fix/<short>`, `docs/<short>`, `test/<short>`, `chore/<short>`.
- **Conventional Commits** — scope is optional but helpful:
  - `feat(dashboard): add keyboard shortcuts to map`
  - `fix(edge): guard WindowedCounter against DST rollover`
  - `docs: add hardware BOM`
  - `test(edge): expand DailyAccumulator crash cases`
  - `chore(ci): add pytest to PR checks`
- Keep PRs under ~300 changed lines, one concern each.
- PR body: **what / why / how to test** + screenshots for UI.

---

## Python style

- Python 3.10, managed with `uv`.
- `ruff check .` and `mypy src/` must be clean.
- Type hints on every signature. Docstrings on public functions (Google style).
- `logger = logging.getLogger(__name__)` — never `print()`.
- Catch specific exceptions, not bare `except:`.

## TypeScript style

- `tsconfig` is strict (including `noUncheckedIndexedAccess`) — don't loosen it.
- Validate API-route input with `zod`.
- DB access via Drizzle — no raw SQL in routes.
- No `any`; prefer `unknown` + narrowing.
- Components PascalCase; hooks camelCase with `use` prefix.

---

## Tests

- Python: `uv run pytest tests/`
- Dashboard: `cd dashboard && pnpm test` (Vitest) + `pnpm exec playwright test` (E2E).
- New code without a test gets blocked in review unless explicitly exempted.
- **Privacy regression tests are non-negotiable.** Never disable them.

---

## Privacy & secrets — read this carefully

- **Never commit:** `.env`, `.env.local`, `settings.json`, `*.pem`, `credentials.json`, `state.db`, or anything with a token in the filename.
- **Never log PII:** no raw GPS, no user emails beyond the auth flow, no per-device timestamps on the public UI.
- **k-anonymity floor is `k_min = 5`.** The public dashboard never exposes a street with fewer than 5 contributing sensors. If you touch aggregation code, run `pytest tests/test_privacy_regression.py` and keep it green.
- `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` is **dev-only**. If you see it in a production config, stop and ping.
- Accidentally committed a secret? Tell @tamagusko immediately, rotate it, don't just delete the file.

---

## Docs

- Markdown, ≤100 char lines, no emojis unless the existing doc uses them.
- Diagrams go in `docs/img/<topic>.{png,svg}` with sources in `docs/img/src/`.
- Use repo-relative links: `[protocol](./docs/PROTOCOL.md)`.

---

## Getting help

- Stand-up: **TBD** (fill in)
- Async chat: **TBD**
- Stuck >30 minutes? Ping — don't spin.

---

## Commands cheat-sheet

```bash
# Python
uv run pytest tests/ -k <keyword>     # run matching tests
uv run ruff check . && uv run mypy src/
uv run pytest --cov=src/camina tests/ # coverage

# Dashboard
pnpm dev                              # hot-reload
pnpm test                             # vitest
pnpm exec playwright test             # E2E
pnpm exec playwright test --ui        # E2E with browser
pnpm lint                             # eslint + tsc

# Git
git switch -c feat/<name>
git commit -m "feat(scope): message"
git push -u origin feat/<name>
```
