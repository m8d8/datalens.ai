# Quick Start Guide

Get from zero to your first interactive report in under 5 minutes.

> Setting up for real use (config folder, credentials, servers, CI)? See the [Setup Guide](SETUP.md).
> Installing on macOS or Windows: [Install](INSTALL.md). Questions? See the [FAQ](FAQ.md).

---

## 1. Install

Datalens uses [`uv`](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
# Install the CLI globally (run from anywhere)
uv tool install datalens-ai

# Verify
datalens --help
```

> **Working from a clone?** Run commands with `uv run datalens ...` from the project root, which uses the project's `.venv` and `pyproject.toml`.

---

## 2. Analyze your first file

Any CSV, JSON, or Excel file works. For example, given `data.csv`:

```bash
datalens analyze --source file --path data.csv --out-dir output
```

You'll see progress, then three files in `output/`:

| File | Purpose |
|---|---|
| `data-report.html` | **Open this in any browser** — the full interactive report. |
| `data-schema.json` | Machine-readable field statistics (for pipelines/tests). |
| `data-summary.md` | A short markdown summary (for PRs/tickets). |

Open the HTML report and start on the **Overview** tab — the **Executive Summary banner** at the top gives you a health verdict, the biggest risks, and the top 3 things to fix.

---

## 3. Analyze MongoDB

```bash
# A few specific collections
datalens analyze --source mongodb --db mydb \
  --collections users,orders,products \
  --uri "mongodb://localhost:27017" \
  --sample-size 10000 \
  --out-dir output/mydb
```

All access is **read-only**. Use `--sample-size` to bound how many records are scanned per collection (default `10000`).

---

## 4. Read the report (the 30-second tour)

1. **Overview** → the Executive Summary banner: is the data 🟢/🟡/🔴, what's the PII risk, what should I fix first?
2. **Data Quality** → the DQI breakdown and which fields drag it down.
3. **PII Detection** → what sensitive data exists and what to mask.
4. **Field Explorer** → search/sort every field; click a distinct count to see value distributions.
5. **Trends & Drift** (last tab) → what changed since the previous run (empty on a first run).

Full section-by-section walkthrough: **[Report Guide](REPORT_GUIDE.md)**.

---

## 5. Track changes over time (drift)

Run twice with the **same `--out-dir`** and add `--detect-drift` on the second run:

```bash
# Baseline
datalens analyze --source file --path data.csv --out-dir output --version-tag baseline

# Later, after the data changes
datalens analyze --source file --path data.csv --out-dir output --detect-drift
```

The **Trends & Drift** tab now shows added/removed fields, type changes, and coverage shifts, and the health verdict factors the drift in.

> `--detect-drift` compares with your **previous run**. Use `--compare-to baseline` for a **fixed baseline**, or
> `--compare-to rolling` to compare with a **normal range learned from recent runs** (quiet on normal day-to-day
> variation, loud on real breaks). See [Usage → Drift & history](USAGE.md#drift--history).

## 6. Know what to do next

- **Verdict → Action Plan** lists every finding as an action with evidence and a copy-ready fix.
- **Verdict → How scores work** (or hover any ⓘ) explains every number.
- Expected a certain schema? `datalens schema infer … -o expected.json`, edit, then `--schema expected.json`.
- Gate a pipeline: add `--fail-on fail --min-score health=70`; exit code 2 means "stop".
- Questions? `datalens serve <run-dir> --ai claude` to chat with the run.

## Next steps

- **All flags and source types** → [Usage Guide](USAGE.md)
- **Understand every chart and table** → [Report Guide](REPORT_GUIDE.md)
- **Turn on AI narratives** → [Usage Guide → AI providers](USAGE.md#ai-providers)
- **Use it in code or CI** → [Usage Guide → Library usage](USAGE.md#library-usage)
