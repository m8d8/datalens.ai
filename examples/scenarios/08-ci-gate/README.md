# Gate a pipeline and get notified

Run Datalens after every load and fail the job when quality drops or data drifts. Exit codes are stable: 0 ok · 1 warn (with `--fail-on warn`) · 2 breach or failed gate · 3 error.

## Run

```bash
bash examples/scenarios/08-ci-gate/run.sh
```

It runs:

```bash
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
```

## What you'll see

- `summary.json`: scores, drift status + highlights, expected-schema status, top actions, `exit_code`, `gate_reasons`.
- `alerts.jsonl`: one line per run (use `slack:<webhook-url>` or `webhook:<url>` in real pipelines).
- `github-actions.yml` in this folder is a ready-to-copy workflow; `cron.sh` runs the same daily with a rolling baseline.

## Files

- [`github-actions.yml`](github-actions.yml)
- [`cron.sh`](cron.sh)
