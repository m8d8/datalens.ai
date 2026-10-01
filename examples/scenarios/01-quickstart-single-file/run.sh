#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/01-quickstart-single-file/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/01-quickstart-single-file}
mkdir -p "$OUT"
datalens analyze --source file --path test_data/orders_sample.jsonl --out-dir "$OUT"
