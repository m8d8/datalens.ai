# What changed since yesterday?

Save a baseline run, then compare the next load with it. Day 2 of the cricket demo carries 10 deliberate changes — see which ones Datalens catches.

## Run

```bash
bash examples/scenarios/03-day-over-day-drift/run.sh
```

It runs:

```bash
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1 --run-date 2026-05-29
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 --run-date 2026-05-31 \
  --detect-drift
```

## What you'll see

- Terminal: a **Scores & Drift** panel with the highlights.
- **Health → Trends & Drift**: every finding with the rule that fired (rename, type change, removed field, −40% volume, 30% nulls, distribution shift, new categories, new PII field, 2% orphaned ids).
- `*-datalens-drift-report.json` for pipelines. The injected changes are listed in `test_data/cricket/manifest.json`.
