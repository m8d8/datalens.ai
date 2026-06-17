# Usage Guide

Everything you can do with Datalens: every CLI flag, all source types, drift detection, configuration, secrets, AI providers, and library/CI usage.

- [Command structure](#command-structure)
- [Full CLI reference](#full-cli-reference)
- [Data sources](#data-sources)
  - [Files (CSV / JSON / XML / XLSX)](#files-csv--json--xml--xlsx)
  - [MongoDB](#mongodb)
  - [S3 / HTTP](#s3--http)
- [Sampling & depth](#sampling--depth)
- [Schema drift & history](#schema-drift--history)
- [Configuration](#configuration)
- [Secrets](#secrets)
- [AI providers](#ai-providers)
- [PII masking](#pii-masking)
- [Outputs](#outputs)
- [Library usage](#library-usage)
- [Using it in CI](#using-it-in-ci)
- [Ways to use the product](#ways-to-use-the-product)

---

## Command structure

```bash
# Option 1: Using connection configs (recommended for teams)
datalens analyze --cc <connection_name> [OPTIONS]

# Option 2: Direct analysis (quick one-off)
datalens analyze --source <file|mongodb|s3|http> [OPTIONS]
```

Either `--cc` (connection config) or `--source` is required. The other required inputs depend on the source (a `--path` for files, a `--db` for MongoDB, a `--uri` for remote sources).

---

## Two Approaches to Analysis

Datalens supports both **reusable connection configs** (recommended for teams) and **quick one-off analysis**. Choose what works best for your workflow:

| Approach | Command | Output Directory | Best For |
|----------|---------|------------------|----------|
| **Connection Config** (Recommended) | `datalens analyze --cc my_api` | `my_api_0611_040438/` | Teams, reusable, tracking credentials |
| **Direct HTTP** | `datalens analyze --source http --uri https://api.example.com/data` | `api_example_com_0611_040438/` | Quick one-off API analysis |
| **Direct File** | `datalens analyze --source file --path data.csv` | `data_0611_040438/` | Quick one-off file analysis |
| **Direct MongoDB** | `datalens analyze --source mongodb --db mydb --uri mongodb://...` | `mydb_0611_040438/` | Quick one-off database analysis |

### Key Differences

**Connection Config (`--cc`):**
- Store credentials once, reuse everywhere
- Cleaner command line (just `--cc my_api`)
- Easy to share with team
- Output directory uses config name (more meaningful)
- Metadata tracking (owner, tags, created date)

**Direct Analysis (`--source`):**
- No setup needed — analyze immediately
- Perfect for quick exploration
- Output directory extracted from source (URI domain, filename, db name, etc.)
- Full backward compatibility

### Output Directory Naming

Each analysis creates a timestamped subdirectory under `--out-dir` (default: `output/`). The directory name format is `{identifier}_{MMDD_HHMMSS}`:

- **Connection Config**: Uses the connection name → `my_api_0611_040438/`
- **Direct HTTP**: Extracts domain from URI → `api_example_com_0611_040438/`
- **Direct File**: Uses filename → `data_0611_040438/`
- **Direct MongoDB**: Uses database name → `analytics_0611_040438/`
- **Direct S3**: Uses bucket/prefix → `bucket_prefix_0611_040438/`

For details on creating and managing connection configs, see [Connection Config Guide](CONNECTION_CONFIG.md).

---

## Full CLI reference

| Option | Description | Default |
|---|---|---|
| `--cc, --connection-config` | Name or path to connection config (alternative to `--source`) | — |
| `-s, --source` | `file` \| `mongodb` \| `s3` \| `http` (required if no `--cc`) | — |
| `-p, --path` | Path to file (file source) | — |
| `--root` | Root element/path for JSON/XML | — |
| `--sheets` | Comma-separated Excel sheet names | all sheets |
| `--db` | Database name (MongoDB) | — |
| `--collections` | Comma-separated collections, e.g. `users,orders` | — |
| `--object` | Object spec `"coll\|{query} -> tag"` (repeatable) | — |
| `--uri` | Connection URI (`mongodb://`, `s3://`, `http://`) | — |
| `--sample-size` | Records to sample per object (`0` = full scan) | `10000` |
| `--full-scan` | Process all records (same as `--sample-size 0`) | off |
| `--max-depth` | Max nesting depth to traverse | `10` |
| `--max-distinct` | Max distinct values tracked per field | `100` |
| `-c, --config` | Config file (YAML) | — |
| `--secrets` | Secrets file (YAML) | — |
| `-o, --out-dir` | Output directory | `output` |
| `--version-tag` | Version tag for this run | timestamp |
| `--compare-to` | Compare against a specific saved run (version tag) | — |
| `--detect-drift` | Compare against the most recent saved run | off |
| `--history-dir` | Where versioned runs are stored | `<out-dir>/.history` |
| `--ai` | `off` \| `anthropic` \| `openai` \| `cursor` \| `copilot` \| `claude` \| `auto` | `off` |
| `--mask-pii / --no-mask-pii` | Mask detected PII in the report | on |
| `--debug / --no-debug` | Verbose/debug output | off |

> See the live, authoritative list anytime with `datalens analyze --help`.

---

## Data sources

### Files (CSV / JSON / XML / XLSX)

```bash
# CSV (headers auto-inferred; missing headers become col_1..col_n and are flagged)
datalens analyze --source file --path data.csv

# JSON — point --root at the array/record root if records are nested
datalens analyze --source file --path data.json --root items

# XML — name the repeating record element
datalens analyze --source file --path feed.xml --root record

# Excel — all sheets by default, or pick some (each sheet profiled as an object)
datalens analyze --source file --path workbook.xlsx
datalens analyze --source file --path workbook.xlsx --sheets "Customers,Orders"
```

### MongoDB

```bash
# Specific collections
datalens analyze --source mongodb --db mydb \
  --collections users,orders --uri "mongodb://localhost:27017"

# Collection with a query filter
datalens analyze --source mongodb --db mydb \
  --object 'products|{"active": true}' --uri "mongodb://localhost:27017"

# Query + a friendly tag/label (flows into the report and the schema JSON `label`)
datalens analyze --source mongodb --db mydb \
  --object 'products|{"active": true} -> ActiveProducts' \
  --object 'orders|{"status":"open"} -> OpenOrders' \
  --uri "mongodb://localhost:27017"
```

`--object` is repeatable, so you can profile several filtered slices in one run. All MongoDB access is **read-only**.

### S3 / HTTP

```bash
# Remote file over HTTP(S) — parsed by content type (JSON/CSV/XML)
datalens analyze --source http --url https://example.com/data.json

# S3 object/prefix (credentials via secrets/env)
datalens analyze --source s3 --uri s3://bucket/prefix/
```

Remote files are fetched read-only and parsed with the same file parsers.

---

## Sampling & depth

- `--sample-size N` bounds how many records are read per object. Larger samples = more accurate cardinality/coverage, slower runs. `10000` is a good default for wide collections.
- `--full-scan` (or `--sample-size 0`) reads everything — use for small/critical datasets.
- `--max-depth` controls how deep nested objects/arrays are traversed.
- `--max-distinct` caps how many distinct values are tracked per field (powers distribution charts and value-overlap detection). Raise it for richer distributions, lower it for speed/size.

---

## Schema drift & history

Every run is saved (schema + metadata) under `--history-dir` (default `<out-dir>/.history`). Drift is computed purely from these saved runs — **no external store required**.

```bash
# 1) Establish a baseline
datalens analyze --source mongodb --db mydb --collections users,orders \
  --out-dir output/mydb --version-tag baseline

# 2) Drift vs. the most recent saved run
datalens analyze --source mongodb --db mydb --collections users,orders \
  --out-dir output/mydb --detect-drift

# Or drift vs. a specific saved run
datalens analyze --source mongodb --db mydb --collections users,orders \
  --out-dir output/mydb --compare-to baseline
```

**Tips**
- Use the **same `--out-dir`** across runs so they share history.
- Object names must be stable across runs to get field-level drift (collection names usually are; for files, keep the filename stable).
- The **Trends & Drift** tab (last tab) shows the change log; the **Executive Summary** verdict factors drift severity in.

### How drift comparison works (rolling vs. baseline)

There are two comparison modes, and they answer different questions:

| Flag | Compares this run to… | Mode | Best for |
|---|---|---|---|
| `--detect-drift` | the **most recent previous run** | **Rolling** | "What changed since I last looked?" |
| `--compare-to <tag>` | a **specific saved run** (that version tag) | **Baseline** | "How far have we drifted from a known-good schema?" |

**Order of operations (per run):** the comparison schema is loaded *before* analysis, drift is computed against it, and *then* the current run is saved to history. So a run never compares against itself, and "most recent previous run" means the chronologically last run saved in that `--history-dir`.

**Rolling mode consumes changes.** Because `--detect-drift` always compares to the *immediately preceding* run, a given change is reported **once** — at the run where it first appears — and then becomes the new normal:

```
Run 1 (baseline):  field X present
Run 2:             X removed   →  vs Run 1  →  reports "removed X"
Run 3:             X still gone →  vs Run 2  →  reports nothing (Run 2 is now "previous")
```

This is why two unchanged back-to-back runs correctly show **no drift**, even though the schema differs from your original baseline — the difference was already reported earlier and absorbed.

**Baseline mode shows cumulative drift.** If you want every difference from a fixed reference point (even ones that appeared several runs ago), pin a baseline once and always compare to it:

```bash
# pin a baseline once
datalens analyze ... --out-dir output/mydb --version-tag baseline

# every later run: cumulative drift vs. that fixed baseline
datalens analyze ... --out-dir output/mydb --compare-to baseline
```

Every run is still saved to history regardless of mode, so the `baseline` tag remains available for `--compare-to`.

**Sampling noise is suppressed.** Type-change detection ignores value-shapes that make up less than ~2% of a field's non-null values. This prevents phantom "type changes" when random sampling (e.g. MongoDB `$sample`) happens to catch a rare value-shape in one run but not another — for example, a handful of UUID-shaped values among thousands of numeric IDs will **not** be reported as drift, but a genuine shift (the shape crossing ~2%) still will.

**Drift severity** rolls up to `none` / `low` / `medium` / `high`:
- `high` — breaking changes: removed objects/fields, type changes, or a large coverage drop.
- `medium` — notable coverage/cardinality movement.
- `low` — additive only (new objects/fields).

Severity feeds the Executive Summary health verdict (and a `high` drift caps the verdict below "Healthy").

---

## Configuration

Precedence: **CLI flag > config file > built-in default.**

`config.yaml`:

```yaml
sample_size: 10000
max_depth: 10
max_distinct_values: 100
low_cardinality_threshold: 50
mask_pii: true
ai_provider: "off"   # off | anthropic | openai | cursor | copilot | claude | auto
```

```bash
datalens analyze --source file --path data.csv --config config.yaml
```

---

## Secrets

Keep credentials in a separate, git-ignored secrets file (or environment variables). Never inline secrets in the main config; they are never logged.

### Secrets Lookup (automatic)

Datalens automatically searches for secrets in:

1. **Project-local** (if exists) — `.datalens/secrets.yaml` ← checked first
2. **User-global** (fallback) — `~/.datalens/secrets.yaml`
3. **Environment variables** (always available)

No `--secrets` flag needed; pick a location and create the file there.

**Best practice:** Keep `.datalens/secrets.yaml` in your project but add it to `.gitignore` (already done).

### Secrets File Format

`.datalens/secrets.yaml`:

```yaml
mongodb:
  uri: "mongodb://user:pass@host:27017"
anthropic:
  api_key: "sk-ant-..."
openai:
  api_key: "sk-..."
```

Then just run analysis — secrets are loaded automatically:

```bash
datalens analyze --source mongodb --db mydb --collections users
```

### Explicit Path (Optional)

If you need to use a different path:

```bash
datalens analyze --source mongodb --db mydb --collections users --secrets /custom/path/secrets.yaml
```

### Environment Variables (Always Work)

Override or supplement secrets file with env vars:

```bash
export DATALENS_MONGO_URI="mongodb://localhost:27017"
export DATALENS_SAMPLE_SIZE=2000
export ANTHROPIC_API_KEY="sk-ant-..."

datalens analyze --source mongodb --db mydb --collections users
```

---

## AI providers

AI insights are **optional** and **off by default**. All non-AI features work with no key and no network. When enabled, AI adds clearly-labeled narrative enrichment on top of the deterministic analysis.

### Available Providers

| Provider | Authentication | Enable | Model Config |
|---|---|---|---|
| Anthropic (Claude API) | `ANTHROPIC_API_KEY` env or secrets | `--ai anthropic` | `secrets.yaml` or env var |
| OpenAI | `OPENAI_API_KEY` env or secrets | `--ai openai` | N/A (uses `gpt-4-turbo`) |
| **Claude Desktop / Claude Code** | `claude` CLI (local license) | `--ai claude` | Chosen by desktop app |
| **GitHub Copilot** | `gh auth login` + subscription | `--ai copilot` | Chosen by GitHub (typically Gpt-4) |
| Cursor | `cursor-agent login` (license) or `CURSOR_API_KEY` | `--ai cursor` | Chosen by Cursor |
| Auto-detect | Tries license providers first, then API keys | `--ai auto` | Provider-specific |

When AI is enabled, Datalens writes `{source}-datalens-ai-insights.md` and adds an **AI Insights** tab to the HTML report.

### Using Claude Desktop (License)

**Prerequisites:**
- Claude Code or Claude Desktop installed
- Authenticated via `claude auth login` or IDE

**Setup:**
```bash
# No secrets needed — uses local CLI session
# Just run with the flag:
datalens analyze --source file --path data.csv --ai claude

# Or use in connection config workflow:
datalens analyze --cc my_api --ai claude
```

**What happens:**
- Datalens calls `claude -p "<prompt>"` with your analysis
- Claude Desktop chooses the model (based on your account)
- No API key needed — runs locally through your authenticated CLI

### Using GitHub Copilot (License)

**Prerequisites:**
- GitHub CLI (`gh`) installed
- Authenticated: `gh auth login`
- Copilot subscription active

**Setup:**
```bash
# Run with copilot flag:
datalens analyze --source file --path data.csv --ai copilot

# Or use in connection config workflow:
datalens analyze --cc my_api --ai copilot
```

**What happens:**
- Datalens calls `gh copilot -p "<prompt>"`
- GitHub Copilot chooses the model (typically GPT-4)
- Uses your GitHub subscription

### Anthropic API with Model Selection

For Anthropic (Claude API), you can **choose which Claude model** to use:

**Option 1: Secrets file** (`.datalens/secrets.yaml`)

```yaml
anthropic:
  api_key: "sk-ant-..."
  model: "claude-opus-4-1"    # Choose model here
```

**Option 2: Environment variable**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export DATALENS_ANTHROPIC_MODEL="claude-opus-4-1"

datalens analyze --source file --path data.csv --ai anthropic
```

**Available Claude models:**
- `claude-opus-4-1` — Most capable (best for complex analysis)
- `claude-sonnet-4-20250514` — Default (balanced speed/quality)
- `claude-haiku-4-5-20251001` — Fastest (good for simple insights)

**Example with model selection:**
```bash
# Using Opus for deep analysis
datalens analyze --source file --path data.csv --ai anthropic
# (assumes DATALENS_ANTHROPIC_MODEL=claude-opus-4-1 in secrets or env)

# Or override from CLI via secrets:
echo 'DATALENS_ANTHROPIC_MODEL=claude-opus-4-1' >> .env
datalens analyze --source file --path data.csv --ai anthropic
```

---

## PII masking

PII detection is always on; **masking is on by default** so sensitive values are obscured in the report (e.g. `a***@domain.com`, `***-**-1234`). Disable masking only for trusted, internal use:

```bash
datalens analyze --source file --path data.csv --no-mask-pii
```

The **PII Detection** tab and the **Compliance scorecard** summarize exposure either way.

---

## Outputs

Written to `--out-dir` (named from the file stem or database name):

| File | Use it for |
|---|---|
| `{source}-datalens-report.html` | Sharing, reviewing, decisions. Self-contained — works offline and over email. |
| `{source}-datalens-schema.json` | Pipelines, tests, diffing, feeding other tools. |
| `{source}-datalens-summary.md` | Pasting into PRs, tickets, or chat. |

Where `{source}` is the identifier (file name, database name, connection config name, or API domain).

History runs are stored under `<out-dir>/.history/<version-tag>/`.

---

## Library usage

The engine is library-first — the CLI is just one caller.

```python
from datalens import analyze
from datalens.config import Config

result = analyze(
    source_spec={"source": "file", "path": "data.csv"},
    config=Config(sample_size=5000, mask_pii=True),
)

# Core artifacts
result.schema_json          # field statistics (the JSON contract)
result.summary_md           # markdown summary
result.html_report          # self-contained HTML string

# Analytics
result.quality              # DQI per object + overall (dict)
result.pii_summary          # PII counts + high-risk fields
result.statistics           # numeric/temporal stats
result.relationships        # detected relationships
result.joins                # primary keys, join candidates, nested rels
result.patterns             # value-shape / identifier patterns
result.insights             # data story, SWOT, recommendations, AI-readiness

# v2 decision layer
result.decision["health_verdict"]        # {'status','score','drivers'}
result.decision["compliance_scorecard"]  # exposure score, risk, must-mask
result.decision["fitness_for_use"]       # per-object readiness badges
result.decision["action_plan"]           # recommendations + impact + effort
result.decision["top_actions"]           # top 3
result.decision["drift_severity"]        # none|low|medium|high

with open("report.html", "w") as f:
    f.write(result.html_report)
```

### Drift in code

```python
prev = analyze({"source": "file", "path": "data.csv"}).schema_json
# ... data changes ...
result = analyze({"source": "file", "path": "data.csv"}, previous_schema=prev)
print(result.decision["drift_severity"])  # e.g. "high"
print(result.diff)                          # {'summary': '...', 'has_drift': True}
```

---

## Using it in CI

Gate a pipeline on data health or drift:

```bash
datalens analyze --source mongodb --db prod --collections users,orders \
  --uri "$MONGO_URI" --out-dir artifacts --detect-drift
```

```python
# fail the build if quality drops or breaking drift appears
from datalens import analyze
r = analyze({"source": "file", "path": "data.csv"}, previous_schema=prev)
verdict = r.decision["health_verdict"]
if verdict["status"] == "risk" or r.decision["drift_severity"] == "high":
    raise SystemExit(f"Data health failed: {verdict}")
```

Publish `{name}-report.html` as a build artifact so reviewers can open it.

---

## Ways to use the product

| Scenario | How |
|---|---|
| **Onboard a new dataset** | Run once, read the Executive Summary, skim Field Explorer. |
| **Pre-warehouse / pre-ingest gate** | Check Fitness-for-Use ("Ready for reporting") and the Action Plan before loading. |
| **ML readiness check** | Look for "Ready for ML/AI" badges and the type-stability / PII drivers. |
| **Governance / sharing review** | Use the PII Detection tab + Compliance scorecard; keep masking on. |
| **Monitor a feed over time** | Schedule runs with `--detect-drift`; watch the Trends & Drift tab. |
| **Brief a stakeholder** | Send the HTML report; point them at the Overview banner (or print to PDF). |
| **Automate quality gates** | Use the library + `decision` in CI as shown above. |

Next: understand exactly what each section means in the **[Report Guide](REPORT_GUIDE.md)**.
