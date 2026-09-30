# Control what counts as PII

PII is detected from values (e.g. real email shapes) and whole-word field names. High-confidence detections are masked in the HTML, schema JSON, history and AI prompt. You can silence false positives and force fields the detector can't know about.

## Run

```bash
bash examples/scenarios/11-pii-controls/run.sh
```

It runs:

```bash
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" \
  -c examples/scenarios/11-pii-controls/pii-config.yaml
grep -c "@example.com" "$OUT"/*/*-datalens-report.html || true   # masked: only a***@example.com forms remain
```

## What you'll see

- **Health → PII Detection**: each detection shows *how* it was found (`value`, `name`, `name+value`, `config`).
- `players.contact_email` is masked everywhere; `teams.name` / `venues.name` no longer flagged; `players.unique_name` forced as a name.
- `--no-mask-pii` turns masking off (the compliance checklist then fails "Sensitive identifiers masked").

## Files

- [`pii-config.yaml`](pii-config.yaml)
