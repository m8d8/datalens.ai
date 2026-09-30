# Coming from variety.js (MongoDB)

`variety.js` answers *which keys exist, with which types, in what % of documents*. That's Datalens's starting point, not its end:

| | variety.js | Datalens |
|---|---|---|
| Keys, types, occurrence % | ✅ | ✅ (nested paths, arrays) |
| Value distributions, examples | – | ✅ |
| Quality scores (DQI, health) with explanations | – | ✅ |
| PII detection + masking | – | ✅ |
| Keys, foreign keys, orphans across collections | – | ✅ |
| Drift vs yesterday / baseline / learned normal range | – | ✅ |
| Expected schema (BYOS) checks | – | ✅ |
| Prioritised action plan, CI exit codes, alerts | – | ✅ |
| Optional AI review | – | ✅ |

## Run

```bash
bash examples/scenarios/10-mongodb-beyond-variety/run.sh
```

It runs:

```bash
# needs a reachable MongoDB; adjust URI, db and collections
datalens analyze --source mongodb --uri "${MONGO_URI:-mongodb://localhost:27017}" --db "${MONGO_DB:-shop}" \
  --collections "${MONGO_COLLECTIONS:-orders,customers}" --out-dir "$OUT" --detect-drift
```

## What you'll see

- Same report as for files; run it daily with `--compare-to rolling` to learn each collection's normal volume and coverage.
- A reusable connection: `examples/connection-configs/mongodb-local.yaml` → `datalens analyze --cc mongodb_local`.
