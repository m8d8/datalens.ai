# Compare every run with the original load

Instead of day-over-day, measure how far each run has moved from a fixed reference (e.g. the load your reports were validated on). Tags listed in `history_protected_tags` (default `baseline`) are never purged.

## Run

```bash
bash examples/scenarios/04-fixed-baseline/run.sh
```

It runs:

```bash
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag baseline
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 --compare-to baseline
```

## What you'll see

- The drift report header says *compared with the fixed baseline `baseline`*.
- `--compare-to baseline:<tag>` and a bare `--compare-to <tag>` are equivalent.
