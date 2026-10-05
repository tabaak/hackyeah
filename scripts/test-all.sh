#!/usr/bin/env bash
# Every automated check in the repo, in one command.
#   scripts/test-all.sh          offline: backend (unit, contracts, Supabase migration in Docker),
#                                local LLM server (if local-models/ is set up), frontend lint + typecheck + build
#   scripts/test-all.sh --live   also calls real services: Serper (1 credit), local LLM, OpenAI, Supabase
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIVE=""
[ "${1:-}" = "--live" ] && LIVE="--live"
PG_IMAGE="${PG_TEST_IMAGE:-pgvector/pgvector:pg17}"
results=()
failed=0

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
record() { if [ "$2" -eq 0 ]; then results+=("PASS  $1"); else results+=("FAIL  $1"); failed=1; fi; }

step "Backend: unit, contract and Supabase migration tests"
BPY="$ROOT/backend/.venv/bin/python"
if [ -x "$BPY" ]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker image inspect "$PG_IMAGE" >/dev/null 2>&1 || docker pull -q "$PG_IMAGE" >/dev/null \
      || echo "could not pull $PG_IMAGE: migration tests will be skipped"
  else
    echo "Docker is not running: migration tests will be skipped"
  fi
  (cd "$ROOT/backend" && "$BPY" -m pytest $LIVE); record "backend" $?
else
  echo "missing backend/.venv: python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt"
  record "backend (no venv)" 1
fi

step "Local LLM server (Bonsai)"
SPY="$ROOT/local-models/.venv-bonsai/bin/python"
if [ -x "$SPY" ] && [ -d "$ROOT/local-models/server/tests" ]; then
  (cd "$ROOT/local-models/server" && "$SPY" -m pytest $LIVE); record "local LLM server" $?
else
  results+=("SKIP  local LLM server (local-models/ is not set up on this machine)")
fi

step "Frontend: lint, typecheck, build"
if [ -d "$ROOT/frontend/web/node_modules" ]; then
  (cd "$ROOT/frontend/web" && npm run --silent lint); record "frontend lint" $?
  (cd "$ROOT/frontend/web" && npm run --silent build); record "frontend typecheck + build" $?
else
  echo "missing frontend/web/node_modules: (cd frontend/web && npm ci)"
  record "frontend (no node_modules)" 1
fi

step "Summary"
printf '%s\n' "${results[@]}"
exit $failed
