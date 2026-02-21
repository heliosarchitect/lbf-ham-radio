# lbf-ham-radio QA Baseline — 2026-02-21

## Run
Command:
```bash
cd ~/Projects/lbf-ham-radio
bash scripts/qa-smoke.sh strict
```

Result: **PASS (strict mode)**

## Test Health
- `pytest`: **117 passed, 1 skipped**

## Static Analysis / Hygiene Debt
- `flake8`: **PASS**
- `black --check`: **PASS**
- `isort --check-only`: **PASS**
- `mypy`: **~178 errors** (tracked debt; currently advisory / non-blocking)

## Interpretation
- Functional behavior is healthy (tests green).
- Style/lint/type gates are not yet at strict-clean baseline.
- Repo is suitable for **advisory QA now**, with a path to strict gating once formatting/import cleanup is done and mypy environment is pinned.

## Next Steps
1. Keep mypy advisory until the error count is reduced module-by-module.
2. Keep CI in sync with `pyproject.toml` tool config (avoid ad-hoc line-length flags).
3. Make packaging validation blocking in CI (twine check should fail if metadata is invalid).
4. Add an install+entrypoint smoke step in CI to catch packaging/console_scripts drift.
