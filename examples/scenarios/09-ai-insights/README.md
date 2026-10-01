# Add an AI reviewer

Datalens is fully useful offline. With `--ai`, a model reviews the deterministic findings — schema summary, keys, orphans, drift — and adds domain-aware recommendations to the Action Plan (marked **AI**). Sample values are never sent, and PII fields are flagged as masked.

## Run

```bash
bash examples/scenarios/09-ai-insights/run.sh
```

It runs:

```bash
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day1
# pick one: claude (logged-in Claude CLI), anthropic (ANTHROPIC_API_KEY), openai, cursor, copilot, auto
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o "$OUT" --version-tag day2 \
  --detect-drift --ai claude
```

## What you'll see

- **Verdict → AI Review** tab and `*-datalens-ai-insights.md`.
- AI recommendations merged into **Verdict → Action Plan** with an `AI` source chip (filter by source).
- No key / no network → the run still completes; the tab just isn't shown. See `docs/AI_PROVIDERS.md`.
