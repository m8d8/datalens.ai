# BYOS — bring your own expected schema

Tell Datalens what the data *should* look like with a JSON Schema: required fields, types, allowed values, ranges, patterns — plus per-field or generic drift thresholds in `x-datalens` blocks. Don't have one? Infer it from a good load, edit it, and own it.

## Run

```bash
bash examples/scenarios/07-byos-expected-schema/run.sh
```

It runs:

```bash
# 1) learn a starting point from a known-good load
datalens schema infer -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT/inferred.schema.json"
# 2) check a new load against the hand-written contract (exit 2 on failures)
set +e
datalens schema validate -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" \
  --schema deliveries=examples/scenarios/07-byos-expected-schema/deliveries.schema.json
set -e
# 3) or use it in a full analysis: adds the Health → Expected Schema tab and the thresholds as drift rules
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 --detect-drift \
  --schema deliveries=examples/scenarios/07-byos-expected-schema/deliveries.schema.json
```

## What you'll see

- `schema validate`: failed checks per field (required `runs.extras` missing, `over` has strings, `non_striker_id` only 70% populated, …).
- **Health → Expected Schema** tab with conformance %, and the same failures in the **Action Plan**.
- The `x-datalens` thresholds (`match_id` −5%, `non_striker_id` −10 pts, generic ±20%) drive the drift report for that object.

Several objects: repeat `--schema OBJECT=file.json`, or one file with an `objects` map (what `schema infer` writes). In a connection config: `expected_schema: path.json`.

## Files

- [`deliveries.schema.json`](deliveries.schema.json)
