#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/08-ci-gate/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/08-ci-gate}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
set +e
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 \
  --detect-drift --fail-on fail --min-score health=70,dqi=85,completeness=70 --max-drop dqi=5 \
  --notify "file:$OUT/alerts.jsonl" --format json > "$OUT/summary.json"
echo "exit code: $?   (2 = breach / gate failed)"
set -e
# Re-check later without touching the data, e.g. after tuning thresholds:
datalens drift -o "$OUT" --fail-on fail --format json > /dev/null || echo "drift still failing"
datalens scores "$OUT"/day2_day2 --min-score health=40 || true
