# Profile several related entities at once

Point Datalens at a directory: every file becomes an object, and keys, foreign keys and orphans *between* them are found from the values themselves.

## Run

```bash
bash examples/scenarios/02-multi-entity-directory/run.sh
```

It runs:

```bash
datalens analyze --source file --path test_data/cricket/day1 --pattern "*.jsonl.gz" --out-dir "$OUT"
```

## What you'll see

- **Structure → Cross-Object**: `deliveries.match_id → matches.match_id`, `deliveries.batter_id → players.player_id`, … each with its orphan rate.
- **Structure → Relationships**: fields that share a value domain but differ per row (e.g. `batter_id` / `non_striker_id` — two roles, not duplicates).
- Primary keys are chosen by exact distinct counts (not a sample cap) and preferring the key other objects reference.
