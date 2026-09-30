#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/05-rolling-daily-baseline/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/05-rolling-daily-baseline}
mkdir -p "$OUT"
for mode in previous rolling; do
  echo "== $mode"
  for day in $(ls test_data/cricket/daily); do
    set +e
    datalens analyze -s file -p "test_data/cricket/daily/$day" --pattern "*.jsonl.gz" -o "$OUT/$mode" \
      --version-tag "$day" --run-date "$day" --compare-to "$mode" --fail-on fail --format json > "$OUT/$mode-$day.json" 2>/dev/null
    code=$?
    set -e
    python3 -c "import json,sys; s=json.load(open(sys.argv[1])); d=s['drift'] or {}; print(sys.argv[2], 'exit', sys.argv[3], d.get('status','(first run)'), (d.get('highlights') or [''])[0][:90])" \
      "$OUT/$mode-$day.json" "$day" "$code"
  done
done
