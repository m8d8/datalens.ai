#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/07-byos-expected-schema/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/07-byos-expected-schema}
mkdir -p "$OUT"
# 1) learn a starting point from a known-good load
datalens schema infer -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT/inferred.schema.json"
# 2) check a new load against the hand-written contract (exit 2 on failures)
set +e
datalens schema validate -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" \
  --schema deliveries=examples/scenarios/07-byos-expected-schema/deliveries.schema.json
set -e
# 3) or use it in a full analysis: adds the Health → Expected Schema tab and the thresholds as drift rules
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 --detect-drift \
  --schema deliveries=examples/scenarios/07-byos-expected-schema/deliveries.schema.json
