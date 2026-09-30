# Inspect history and re-score past runs

Every run is saved with its schema, metrics and categories. Look back, compare any two runs, or re-evaluate drift with new rules — without reading the data again.

## Run

```bash
bash examples/scenarios/12-history-and-rescoring/run.sh
```

It runs:

```bash
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2
datalens history list -o "$OUT"
datalens drift -o "$OUT" --run day2 --compare-to day1 || true
datalens drift -o "$OUT" --run day2 --compare-to day1 \
  --drift-rules examples/scenarios/06-custom-drift-rules/drift-rules.yaml --format json | head -40 || true
datalens glossary psi
```

## What you'll see

- `history list`: tag, run date, status, health, DQI and drift status per run.
- `drift`: the full report from stored snapshots — ideal for tuning thresholds on real history.
- `glossary <term>`: the definition, when it applies and the exact formula of any score.
