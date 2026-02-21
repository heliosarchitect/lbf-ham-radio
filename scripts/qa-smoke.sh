#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[qa-smoke] repo: $ROOT"

fail=0
MODE="${1:-strict}"  # advisory | strict
step() { echo; echo "==> $*"; }
warn_or_fail() {
  local msg="$1"
  if [[ "$MODE" == "strict" ]]; then
    echo "[FAIL] $msg"
    fail=1
  else
    echo "[WARN] $msg"
  fi
}

step "Install dev deps in local venv"
if [[ ! -d .venv-dev ]]; then
  if command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv .venv-dev
  elif command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv .venv-dev
  else
    python3 -m venv .venv-dev
  fi
fi
. .venv-dev/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -e ".[dev]"

step "Lint (flake8)"
if ! flake8 src/ tests/; then warn_or_fail "flake8 issues detected"; fi

step "Format check (black)"
if ! black --check src/ tests/; then warn_or_fail "black formatting drift detected"; fi

step "Import sort check (isort)"
if ! isort --check-only --profile black src/ tests/; then warn_or_fail "isort drift detected"; fi

step "Type check (mypy)"
if ! mypy src/ft991a/ --ignore-missing-imports; then
  echo "[WARN] mypy issues detected (tracked debt; not strict-blocking yet)"
fi

step "Unit tests"
pytest -v --tb=short --maxfail=1 || fail=1

if [[ "$fail" -ne 0 ]]; then
  echo "[qa-smoke] FAIL (mode=$MODE)"
  exit 1
fi

echo "[qa-smoke] PASS (mode=$MODE)"
