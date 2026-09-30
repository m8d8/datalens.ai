#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/09-ai-insights/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/09-ai-insights}
mkdir -p "$OUT"
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
# pick one: claude (logged-in Claude CLI), anthropic (ANTHROPIC_API_KEY), openai, cursor, copilot, auto
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 \
  --detect-drift --ai claude
