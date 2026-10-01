#!/usr/bin/env bash
# Reproduce every run shown in the README (cricket demo data in test_data/cricket).
#   bash examples/demo/run_demo.sh            # deterministic runs only
#   AI=claude bash examples/demo/run_demo.sh  # also the AI-reviewed run (claude | anthropic | openai | …)
set -uo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/demo}
rm -rf "$OUT"

echo "== 1. Day 1 → Day 2 (13 injected changes) with an expected schema"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT/day-over-day" \
  --version-tag day1 --run-date 2026-05-29 > /dev/null
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT/day-over-day" \
  --version-tag day2 --run-date 2026-05-31 --detect-drift \
  --schema deliveries=examples/scenarios/07-byos-expected-schema/deliveries.schema.json \
  ${AI:+--ai "$AI"} --fail-on fail
echo "exit code: $? (2 = drift breach — expected for day 2)"

echo "== 2. Daily feed with a learned (rolling) baseline"
for day in $(ls test_data/cricket/daily); do
  datalens analyze -s file -p "test_data/cricket/daily/$day" --pattern "*.jsonl.gz" -o "$OUT/daily" \
    --version-tag "$day" --run-date "$day" --compare-to rolling --format json > /dev/null 2>&1
  printf "%s exit %s\n" "$day" "$?"
done
datalens history list -o "$OUT/daily"

echo "Reports:"
ls "$OUT"/*/*/*-datalens-report.html
echo "Chat with a run:  datalens serve $OUT/day-over-day/day2_day2"
