#!/usr/bin/env bash
# Run from the repository root:  bash examples/scenarios/10-mongodb-beyond-variety/run.sh
set -euo pipefail
command -v datalens >/dev/null 2>&1 || datalens() { uv run --quiet datalens "$@"; }
OUT=${OUT:-output/scenarios/10-mongodb-beyond-variety}
mkdir -p "$OUT"
# needs a reachable MongoDB; adjust URI, db and collections
datalens analyze --source mongodb --uri "${MONGO_URI:-mongodb://localhost:27017}" --db "${MONGO_DB:-shop}" \
  --collections "${MONGO_COLLECTIONS:-orders,customers}" --out-dir "$OUT" --detect-drift
