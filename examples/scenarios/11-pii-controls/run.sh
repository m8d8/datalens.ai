#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/11-pii-controls/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/11-pii-controls}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" \
  -c examples/scenarios/11-pii-controls/pii-config.yaml
grep -c "@example.com" "$OUT"/*/*-datalens-report.html || true   # masked: only a***@example.com forms remain
