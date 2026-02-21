# lbf-ham-radio QA Process

## Objective
Keep `ft991a-control` shippable with repeatable, low-friction checks.

## Cadence
- On change: run `scripts/qa-smoke.sh` before merge/release
- CI: `.github/workflows/ci.yml` runs on push + PR to `main`
- Weekly: record one QA baseline note in `qa/` with failures/fixes

## QA Gates
1. flake8 (`src/`, `tests/`) — strict blocking
2. black --check — strict blocking
3. isort --check-only — strict blocking
4. mypy (`src/ft991a/`) — advisory (tracked debt)
5. pytest (`tests/`) — strict blocking

## Command
```bash
cd ~/Projects/lbf-ham-radio
bash scripts/qa-smoke.sh          # default strict mode
# or: bash scripts/qa-smoke.sh advisory
```

## Safety Notes (Radio)
- No TX actions without Matthew physically present.
- QA focuses on software behavior, mocks, API/CLI correctness, and packaging.
- Hardware-facing checks should default to non-transmit paths.

## Release Rule
No release bump unless qa-smoke passes and CI is green.
