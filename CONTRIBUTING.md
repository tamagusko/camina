# Contributing to CAMINA

CAMINA is a privacy-first traffic sensor: Raspberry Pis count road users and a Next.js map of
Dublin shows the counts. Pick work from [`TODO.md`](TODO.md); project status is in
[`.planning/STATE.md`](.planning/STATE.md) (read-only for contributors).

## Set up

```bash
git clone https://github.com/tamagusko/camina.git && cd camina
uv venv && uv pip install -r requirements.txt
.venv/bin/python -m pytest              # all green
scripts/run_dashboard.sh                # dashboard with mock data → http://localhost:3000/dublin
```

## Claiming a task

1. Put your name after a task in `TODO.md`.
2. Branch from `dev` and open a **draft PR into `dev`** early.
3. Mark it ready when checks pass, and delete the task from `TODO.md` in that PR.

## Branches and commits

| Branch | Role | Rules |
|---|---|---|
| `main` | Stable; what deployments and citations point at | Only PRs from `dev` (a release) or `hotfix/*`; tagged `vX.Y.Z` |
| `dev` | Integration | Feature branches start here and return by PR |
| `TRA2026` | Frozen code behind the TRA 2026 paper | Never merged, never rewritten |
| `feat/*`, `fix/*`, `docs/*`, `test/*`, `chore/*` | One piece of work | From `dev`, PR into `dev`; deleted on merge |
| `hotfix/*` | Urgent fix to `main` | From `main`, PR into `main`, then merge `main` into `dev` |

- Sync with `git rebase dev`; PRs merge with a merge commit (no squash).
- [Conventional Commits](https://www.conventionalcommits.org): `feat(counting): …`, `fix(dashboard): …`.
- One concern per PR, ideally under ~300 changed lines. PR body: what, why, how to test.
- Data enters `dev` or `main` only after an audit (labels, licence, privacy).

## Checks before a PR

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest
cd dashboard && pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

New code comes with tests; a bug fix comes with a test that reproduces it.

## Style

- **Python:** PEP 8 via ruff (`pyproject.toml`), type hints, Google-style docstrings on public
  functions, `logger = logging.getLogger(__name__)` instead of `print`, specific exceptions.
- **TypeScript:** strict (`noUncheckedIndexedAccess` on); zod at API boundaries; Drizzle for the
  database; no `any`.
- **Docs:** short, accurate, repo-relative links.

## Privacy and secrets

- The sensor publishes counts only; frames never leave the device and are never stored.
- The public UI and API never expose sensor locations or ids.
- Counts and speeds below 5 are suppressed (k_min = 5). Keep
  `dashboard/tests/unit/privacy-regression.test.ts` green; never disable it.
- Never commit `.env*`, keys, tokens or `state.db`. Committed a secret by accident? Tell
  @tamagusko, and rotate it; deleting the file is not enough.
- `NEXT_PUBLIC_CAMINA_DEV_ADMIN=true` is for development only.
