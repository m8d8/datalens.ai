#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/03-day-over-day-drift/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/03-day-over-day-drift}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1 --run-date 2026-05-29
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 --run-date 2026-05-31 \
  --detect-drift
