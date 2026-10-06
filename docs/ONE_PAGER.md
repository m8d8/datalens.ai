# Datalens.ai: one page

**Datalens tells you when your data changed, what broke, and what to do about it, before your dashboards or models do.**

Point it at files, MongoDB, BigQuery, S3 or an HTTP API. It profiles, scores, compares against yesterday (or a learned normal, or a certified baseline), and hands back a prioritised fix list in one offline HTML report, a JSON summary for CI/CD, and an optional AI chat.

## The problem

The pipeline ran green, but the data was wrong: rows dropped, a field vanished, a type changed. Nobody noticed for days. Profilers show a snapshot; rule-based tests only catch what someone thought to write down.

## What you get

| Capability | Why it matters |
|---|---|
| **Drift vs previous, rolling or tagged baseline** | Catches changes against yesterday, a learned normal range, or a certified release. Learned bands stop false alarms on normal wobble. |
| **Health score + 7-dimension DQI** | One number for executives; completeness, validity, timeliness and more for engineers. Every score shows its formula. |
| **Schema and coverage drift** | Vanished fields, type changes, null spikes, new categories, likely renames, orphaned foreign keys. |
| **Bring your own schema (BYOS)** | Validate against a JSON Schema contract, or infer one from good data and enforce it. |
| **Action Plan** | Every finding becomes one prioritised action with evidence, impact and a copy-ready fix. |
| **AI review and chat** | Plain-English explanations; ask the report questions (`serve`, `ask`). Claude, OpenAI, Cursor, Copilot, or off. |
| **CI/CD gate + Slack** | `--fail-on`, `--min-score`, `--max-drop`: bad data fails the step like a failing test. |
| **PII masking** | Detected PII is masked in every output by default. |
| **Compare** | Schema- or record-level diff of two datasets, for migrations. |
| **Many sources** | File (JSON, JSONL, CSV, XML, Excel), MongoDB, S3, HTTP, BigQuery. |

## Who it helps

- **Data engineers:** fewer 2am surprises; a quality gate on pipeline output.
- **Analysts and BI:** know what changed before the numbers move.
- **ML teams:** feature drift and coverage drops caught before model quality slips.
- **Governance and platform:** contracts, audit history, protected baselines, offline mode.
- **Migrations and vendor feeds:** prove two systems match; validate third-party data.

## See it in 3 minutes

The bundled cricket demo (160K rows, five related entities, 13 injected problems):

1. Day 1 scores **87, Healthy**.
2. Day 2 drops to **62, At risk**, with specific findings: `deliveries` rows down 40%, `toss.decision` gone, `over` changed type, `extras` renamed to `extra_runs`, 2% orphaned `bowler_id`.
3. The Action Plan lists what to fix first; `datalens ask` explains why.

```bash
pip install datalens-ai
datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o output/demo --version-tag day1
datalens analyze -s file -p test_data/cricket/day2 --pattern "*.jsonl.gz" -o output/demo --version-tag day2 --detect-drift
```

## Why not just write tests?

Tests need rules written up front. Datalens finds what you didn't think to test, then lets you promote the findings into a contract (`datalens schema infer`) and a CI gate.

## Safe and light

AI is optional (`--ai off`); drift re-evaluation (`datalens drift`) runs on saved metrics with no access to the data. Sampling by default, `--full-scan` when you need it. One `pip install`, one command.

[Install](INSTALL.md) · [Quick Start](QUICKSTART.md) · [Usage Guide](USAGE.md) · [FAQ](FAQ.md)
