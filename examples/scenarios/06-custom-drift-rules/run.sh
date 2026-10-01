#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/06-custom-drift-rules/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/06-custom-drift-rules}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 \
  --detect-drift --drift-rules examples/scenarios/06-custom-drift-rules/drift-rules.yaml
