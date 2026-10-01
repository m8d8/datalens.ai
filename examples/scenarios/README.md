# Scenarios

One runnable example per use case. Run them from the repository root, e.g. `bash examples/scenarios/03-day-over-day-drift/run.sh`.
Outputs go to `output/scenarios/<name>/` (git-ignored). The data is the cricket demo in `test_data/cricket/` (see its `ATTRIBUTION.md`).

| # | Scenario | What it shows |
|---|---|---|
| 01 | [Profile one file](01-quickstart-single-file/README.md) | The fastest way to see what Datalens does: one file in, one interactive report out. |
| 02 | [Profile several related entities at once](02-multi-entity-directory/README.md) | Point Datalens at a directory: every file becomes an object, and keys, foreign keys and orphans *between* them |
| 03 | [What changed since yesterday?](03-day-over-day-drift/README.md) | Save a baseline run, then compare the next load with it. Day 2 of the cricket demo carries 13 deliberate chang |
| 04 | [Compare every run with the original load](04-fixed-baseline/README.md) | Instead of day-over-day, measure how far each run has moved from a fixed reference (e.g. the load your reports |
| 05 | [Daily drift that learns what normal looks like](05-rolling-daily-baseline/README.md) | Real feeds wobble: some days have one match, some two. Fixed day-over-day thresholds cry wolf on every double- |
| 06 | [Your own thresholds per dataset, object and field](06-custom-drift-rules/README.md) | Every drift rule is configurable, most specific first: field → object → dataset defaults → built-ins. Drops an |
| 07 | [BYOS — bring your own expected schema](07-byos-expected-schema/README.md) | Tell Datalens what the data *should* look like with a JSON Schema: required fields, types, allowed values, ran |
| 08 | [Gate a pipeline and get notified](08-ci-gate/README.md) | Run Datalens after every load and fail the job when quality drops or data drifts. Exit codes are stable: 0 ok  |
| 09 | [Add an AI reviewer](09-ai-insights/README.md) | Datalens is fully useful offline. With `--ai`, a model reviews the deterministic findings — schema summary, ke |
| 10 | [Coming from variety.js (MongoDB)](10-mongodb-beyond-variety/README.md) | `variety.js` answers *which keys exist, with which types, in what % of documents*. That's Datalens's starting  |
| 11 | [Control what counts as PII](11-pii-controls/README.md) | PII is detected from values (e.g. real email shapes) and whole-word field names. High-confidence detections ar |
| 12 | [Inspect history and re-score past runs](12-history-and-rescoring/README.md) | Every run is saved with its schema, metrics and categories. Look back, compare any two runs, or re-evaluate dr |
| 13 | [Chat with your data](13-chat/README.md) | Ask follow-up questions in plain English with `datalens serve`. Answers use read-only SQL on a PII-masked sample. Shows login vs API providers and how to pick a model. |
