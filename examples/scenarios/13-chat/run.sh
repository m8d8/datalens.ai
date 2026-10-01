#!/usr/bin/env bash
# Run from the repository root:
#   bash examples/scenarios/13-chat/run.sh                                  # auto-detect provider
#   AI=copilot MODEL=claude-opus-5 bash examples/scenarios/13-chat/run.sh   # pick provider + model
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/13-chat}
AI=${AI:-auto}
MODEL=${MODEL:-auto}
mkdir -p "$OUT"

# 1. Two runs so there is drift to talk about (chat works on any run folder, with or without --ai)
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1 > /dev/null
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 \
  --detect-drift > /dev/null || true   # exit 2 = drift breach, expected for day 2

# 2. One scripted question (no browser) — handy in CI or a notebook
datalens ask "Which 2 fields in each object have the lowest coverage? Show a table." "$OUT/day2_day2" \
  --ai "$AI" --ai-model "$MODEL" --format md

# 3. The report with the chat panel on http://127.0.0.1:8765 (Ctrl+C to stop)
datalens serve "$OUT/day2_day2" --ai "$AI" --ai-model "$MODEL"
