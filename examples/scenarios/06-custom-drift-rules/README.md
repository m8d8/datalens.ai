# Your own thresholds per dataset, object and field

Every drift rule is configurable, most specific first: field → object → dataset defaults → built-ins. Drops and increases get separate thresholds and messages.

## Run

```bash
bash examples/scenarios/06-custom-drift-rules/run.sh
```

It runs:

```bash
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 \
  --detect-drift --drift-rules examples/scenarios/06-custom-drift-rules/drift-rules.yaml
```

## What you'll see

- The row-count finding uses your custom message ("Deliveries feed looks truncated …").
- Each finding's **Rule that fired** column shows the scope (`field`, `object`, `dataset`, `builtin`).
- Units: `*_pct` = relative change (80% → 76% is −5%); `*_pts` = absolute points (80% → 76% is −4 pts); `change_*` = either direction.

## Files

- [`drift-rules.yaml`](drift-rules.yaml)
