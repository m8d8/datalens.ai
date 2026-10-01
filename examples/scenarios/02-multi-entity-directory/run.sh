#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/02-multi-entity-directory/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/02-multi-entity-directory}
mkdir -p "$OUT"
datalens analyze --source file --path test_data/cricket/day1 --pattern "*.jsonl.gz" --out-dir "$OUT"
