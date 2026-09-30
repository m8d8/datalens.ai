#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/04-fixed-baseline/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/04-fixed-baseline}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag baseline
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 --compare-to baseline
