#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/12-history-and-rescoring/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/12-history-and-rescoring}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2
datalens history list -o "$OUT"
datalens drift -o "$OUT" --run day2 --compare-to day1 || true
datalens drift -o "$OUT" --run day2 --compare-to day1 \
  --drift-rules examples/scenarios/06-custom-drift-rules/drift-rules.yaml --format json | head -40 || true
datalens glossary psi
