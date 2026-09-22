#!/usr/bin/env bash
# Run the CAMINA dashboard locally in mock mode (no database, no credentials).
#
#   scripts/run_dashboard.sh          # set up if needed, then start the dev server
#   scripts/run_dashboard.sh prod     # production build, then serve it
#   scripts/run_dashboard.sh setup    # set up only (fixtures, .env.local, deps)
#
# Each step is skipped when it is already done, so re-running is cheap.
set -euo pipefail

cd "$(dirname "$0")/.."
MODE="${1:-dev}"

case "$MODE" in
  dev | prod | setup) ;;
  *)
    echo "usage: $0 [dev|prod|setup]" >&2
    exit 2
    ;;
esac

# pnpm is not always installed; npx fetches the pinned version on demand.
if command -v pnpm >/dev/null 2>&1; then
  PNPM=(pnpm)
else
  PNPM=(npx -y pnpm@9.12.0)
  echo "==> pnpm not found, using: ${PNPM[*]}"
fi

# 1. Mock fixtures (gitignored, stdlib-only generator).
if [ -z "$(ls -A data/mock/dublin 2>/dev/null || true)" ]; then
  echo "==> generating mock fixtures in data/mock/dublin"
  python3 scripts/generate_mock_dublin.py
fi

# 2. Basemap tiles (gitignored, ~500 Carto tiles / ~10 MB). Without these the
#    map area renders blank while the rest of the UI works.
if [ -z "$(ls -A dashboard/public/tiles 2>/dev/null || true)" ]; then
  echo "==> downloading Dublin basemap tiles (one-off, ~10 MB)"
  # Plain node: the script only uses node:fs/node:path, so this works before install.
  (cd dashboard && node scripts/download-dublin-tiles.mjs)
fi

# 3. Local env file. Mock mode works with the defaults in .env.example.
if [ ! -f dashboard/.env.local ]; then
  echo "==> creating dashboard/.env.local from .env.example"
  cp dashboard/.env.example dashboard/.env.local
fi

cd dashboard

# 4. Dependencies.
if [ ! -d node_modules ]; then
  echo "==> installing dashboard dependencies"
  "${PNPM[@]}" install
fi

# 5. Run.
export CAMINA_DATA_SOURCE=mock
case "$MODE" in
  setup)
    echo "==> setup complete; start it with: scripts/run_dashboard.sh"
    ;;
  prod)
    "${PNPM[@]}" build
    echo "==> serving the production build on http://localhost:3000"
    exec "${PNPM[@]}" start
    ;;
  dev)
    echo "==> starting the dev server on http://localhost:3000 (redirects to /dublin)"
    exec "${PNPM[@]}" dev
    ;;
esac
