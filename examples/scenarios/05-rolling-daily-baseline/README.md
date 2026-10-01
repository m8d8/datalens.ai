# Daily drift that learns what normal looks like

Real feeds wobble: some days have one match, some two. Fixed day-over-day thresholds cry wolf on every double-header. The rolling baseline learns each metric's normal range from recent runs and only alerts when a day falls outside it.

This replays 12 real IPL 2026 match days and one broken load (truncated feed + 30% nulls) through both modes.

## Run

```bash
bash examples/scenarios/05-rolling-daily-baseline/run.sh
```

It runs:

```bash
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
```

## What you'll see

Typical result: with `previous`, most normal days warn or fail (a double-header is "+100% rows"); with `rolling`, after a 3-run cold start every normal day is **ok** — including the second double-header, already learned — and only the broken day fails (row count far outside its learned range, `non_striker_id` coverage outside 85–100%, `innings` lost value '2').

**How the band is learned** (per metric, last N=14 runs, breached runs excluded):

```
M = median(values)        MAD = median(|x − M|)        σ̂ = 1.4826·MAD
σ̂ₑ = max(σ̂, 5%·|M|, sampling noise)
band = [min(M − 3σ̂ₑ, min seen·0.95),  max(M + 3σ̂ₑ, max seen·1.05)]
outside the band → warn;  also |x − M| > 3σ̂ₑ → fail
```

Tune it in config: `drift: {compare_to: rolling, rolling: {window: 14, min_history: 3, k: 3}}`. See `datalens glossary rolling`.
