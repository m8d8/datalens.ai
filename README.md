# Datalens.ai 🔍

**Advanced Schema Analysis & Data Profiling — with a decision layer for analysts and stakeholders.**

A domain-agnostic tool that profiles any dataset, scores its quality, detects PII, discovers relationships and drift, and turns it all into a single, self-contained, interactive HTML report that both **data analysts** and **business stakeholders** can act on.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Why Datalens

Most profilers tell you *what the data looks like*. Datalens also tells you **what to do about it**:

- a one-screen **health verdict** (🟢/🟡/🔴) and the reasons behind it,
- a prioritized **action plan** with business impact and effort,
- a **compliance/PII risk** read for governance, and
- **what changed since last run** (schema drift) — so you can trust the data before you ship it to a warehouse, a model, or a partner.

It learns from the data in front of it — no baked-in business vocabulary — so it works equally well on finance, retail, healthcare, IoT, media, or anything else.

---

## Features

### Profiling & analysis
- **Schema Analysis** — discover field types, coverage, cardinality, and nested structures across collections/tables/files.
- **Data Quality Index (DQI)** — transparent 0–100 score with sub-dimensions: completeness, consistency, uniqueness, validity, timeliness, granularity, and (optionally) pattern accuracy.
- **Pattern Detection** — recognize UUIDs, integer IDs, slugs, dates, URLs, emails, and other value shapes automatically.
- **PII Detection & Masking** — flag emails, phones, SSNs, payment data, IPs, names, addresses; mask sensitive values in the report (on by default).
- **Relationships & Join Keys** — infer primary/composite keys, cross-object join candidates, foreign keys by name and by value overlap, and nested hierarchies.
- **Numeric & Temporal Statistics** — min/max/mean/median/stddev/distribution for numbers; date ranges, span, and future-dated anomalies for timestamps.

### Decision layer (new in v2)
- **Executive Summary banner** — health verdict, headline KPIs, plain-language narrative, and the **Top 3 things to fix**.
- **Business-impact & effort** on every recommendation — so non-technical readers can prioritize.
- **Compliance / PII scorecard** — ratio-based exposure score, risk badge, and a "mask before sharing" list.
- **Fitness-for-Use ratings** — per object: *Ready for reporting* / *Ready for ML/AI* / *Needs cleanup*.
- **Functional-dependency hints** — fields that are always null together or share value sets.

### Trends & change tracking (new in v2)
- **Schema Drift** — compare any run against a previous one: added/removed objects & fields, type changes, coverage shifts, cardinality changes — rendered in a dedicated **Trends & Drift** tab.
- **Versioned history** — every run is saved so you can detect drift over time without any external store.

### Reporting
- **Single self-contained HTML** — no server, no CDN, no network calls; works offline and survives being emailed.
- **Interactive** — global search across tabs, sortable tables, CSV export, distinct-value modals, light/dark mode.
- **Optional AI** — enrich narratives via Anthropic, OpenAI (API keys), or Cursor / Copilot / Claude (logged-in CLI). Emits `*-ai-insights.md` and an **AI Insights** report tab. Fully functional with **no key and no network**.

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/datalens-ai/datalens.git
cd datalens

# Install with uv (recommended) or pip
uv sync
# or
pip install -e .
```

### Option 1: Direct CLI (quick one-off analysis)
```bash
# Analyze a local file — opens a self-contained HTML report
uv run datalens analyze --source file --path data.csv --out-dir output

# Analyze MongoDB collections
uv run datalens analyze --source mongodb --db mydb \
  --collections users,orders --uri "mongodb://localhost:27017"
```

### Option 2: Connection Configs (reusable, recommended for teams)
```bash
# Create a connection config once
mkdir -p .datalens/connections
cat > .datalens/connections/my_api.yaml << 'EOF'
name: my_api
source_type: http
params:
  uri: "https://api.example.com/v1"
  auth_type: bearer
  auth_token: "${API_TOKEN}"
EOF

# Create secrets file (git-ignored)
cat > .datalens/secrets.yaml << 'EOF'
# Keep actual credentials here (git-ignored)
http:
  default_headers:
    Authorization: "Bearer your_actual_token"
EOF

# Use it anytime (no more typing credentials!)
# Datalens auto-loads secrets from .datalens/secrets.yaml
uv run datalens analyze --cc my_api
uv run datalens connection-list --verbose
```

Each run writes three files to a structured output directory:
- `{source}_{timestamp}/{source}-datalens-report.html` — the interactive report (open in any browser)
- `{source}_{timestamp}/{source}-datalens-schema.json` — machine-readable schema
- `{source}_{timestamp}/{source}-datalens-summary.md` — markdown summary

👉 **New here? Start with the [Quick Start Guide](docs/QUICKSTART.md).**  
👉 **Want reusable configs? See the [Connection Config Guide](docs/CONNECTION_CONFIG.md) and [examples](examples/connection-configs/).**

---

## Documentation

| Guide | What it covers |
|---|---|
| 📘 [Quick Start](docs/QUICKSTART.md) | Install and produce your first report in under 5 minutes. |
| 🛠️ [Usage Guide](docs/USAGE.md) | Every CLI flag, all source types, drift detection, config & secrets, library and CI usage. |
| 📊 [Report Guide](docs/REPORT_GUIDE.md) | A tour of every report section — what it means and how to use it to make decisions. |
| 🔐 [Connection Config Guide](docs/CONNECTION_CONFIG.md) | Store & reuse credentials with YAML configs. Support for HTTP APIs, MongoDB, S3, local files with environment variable substitution. |
| 🤖 [AI Providers Guide](docs/AI_PROVIDERS.md) | Configure Claude Desktop, GitHub Copilot, Anthropic API, OpenAI, or Cursor for AI-powered insights. Choose models for Anthropic. |
| 📋 [Connection Config Examples](examples/connection-configs/README.md) | Ready-to-use examples for all source types (HTTP Bearer/Basic/API Key, MongoDB Atlas/Local, S3, CSV/JSON/Excel/XML). |
| 🤝 [Contributing](CONTRIBUTING.md) | Add a new connector via the `Connector` interface. |

---

## CLI at a glance

```bash
datalens analyze --source <file|mongodb|s3|http> [OPTIONS]
```

Common options: `--path`, `--db`, `--collections`, `--object`, `--uri`, `--sample-size`,
`--max-depth`, `--max-distinct`, `--out-dir`, `--version-tag`, `--detect-drift`,
`--compare-to`, `--ai`, `--mask-pii/--no-mask-pii`. See the [Usage Guide](docs/USAGE.md) for the full reference.

---

## Schema Drift in 30 seconds

```bash
# First run = baseline (saved to <out-dir>/.history)
datalens analyze --source mongodb --db mydb --collections users,orders \
  --out-dir output/mydb --version-tag baseline

# Later run = drift vs. the most recent previous run → see the Trends & Drift tab
datalens analyze --source mongodb --db mydb --collections users,orders \
  --out-dir output/mydb --detect-drift
```

Use the **same `--out-dir`** so runs share a history. Because object names (e.g. `users`, `orders`) are stable, you get field-level, type, and coverage drift — not just object add/remove.

`--detect-drift` compares against the **most recent previous run** (rolling); use `--compare-to <tag>` to compare against a **fixed baseline** instead. See [Usage → How drift comparison works](docs/USAGE.md#how-drift-comparison-works-rolling-vs-baseline).

---

## Library usage

```python
from datalens import analyze

result = analyze(
    source_spec={"source": "file", "path": "data.csv"},
    config=None,  # defaults
)

print(result.total_fields)
print(result.decision["health_verdict"])     # {'status': 'attention', 'score': 79.2, ...}
print(result.decision["compliance_scorecard"]["risk"])

with open("report.html", "w") as f:
    f.write(result.html_report)
```

See the [Usage Guide](docs/USAGE.md#library-usage) for drift, custom config, and the full `AnalysisResult` shape.

---

## License

MIT License — see [LICENSE](LICENSE).

---

**Datalens.ai** — Schema analysis that learns from your data, and tells you what to do next.
