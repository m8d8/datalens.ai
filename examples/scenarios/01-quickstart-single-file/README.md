# Profile one file

The fastest way to see what Datalens does: one file in, one interactive report out.

## Run

```bash
bash examples/scenarios/01-quickstart-single-file/run.sh
```

It runs:

```bash
datalens analyze --source file --path test_data/orders_sample.jsonl --out-dir "$OUT"
```

## What you'll see

- `*-datalens-report.html` — open it: **Verdict → Overview** (health, top 3 fixes), **Action Plan**, **How scores work**.
- `*-datalens-run-summary.json` — the same scores in machine-readable form.
- Hover any ⓘ to see what a number means and how it was calculated.
