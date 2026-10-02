# Usage Guide

Everything you can do with Datalens: every CLI flag and command, all source types, drift detection and rules, expected schemas, configuration, secrets, AI and chat, and library/CI usage.

- [Command structure](#command-structure)
- [Full CLI reference](#full-cli-reference)
- [Data sources](#data-sources)
  - [Files (CSV / JSON / XML / XLSX)](#files-csv--json--xml--xlsx)
  - [MongoDB](#mongodb)
  - [S3 / HTTP](#s3--http)
- [Sampling & depth](#sampling--depth)
- [Drift & history](#drift--history) — previous run, fixed baseline, learned rolling baseline, drift rules
- [Expected schema (BYOS)](#expected-schema-byos--bring-your-own-schema)
- [Configuration](#configuration)
- [Secrets](#secrets)
- [AI providers](#ai-providers)
- [PII masking](#pii-masking)
- [Outputs](#outputs)
- [Library usage](#library-usage)
- [CI/CD — gates, exit codes, notifications](#cicd--gates-exit-codes-notifications)
- [Chat with a run](#chat-with-a-run)
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

For details on creating and managing connection configs, see [Setup Guide](SETUP.md) and [Setup Connections](CONNECTION_CONFIG.md).

---

## Full CLI reference

| Option | Description | Default |
|---|---|---|
| `--cc, --connection-config` | Name or path to connection config (alternative to `--source`) | — |
| `-s, --source` | `file` \| `mongodb` \| `bigquery` \| `s3` \| `http` (required if no `--cc`) | — |
| `-p, --path` | Path to file (file source) | — |
| `--root` | Root element/path for JSON/XML | — |
| `--sheets` | Comma-separated Excel sheet names | all sheets |
| `--db` | Database name (MongoDB) | — |
| `--collections`, `--tables` | Comma-separated collections / tables, e.g. `users,orders` | all |
| `--project`, `--dataset`, `--location` | BigQuery project, dataset and location | — |
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
| `--compare-to` | Drift reference: `previous` \| `rolling` \| `baseline:<tag>` \| `<tag>` | — |
| `--detect-drift` | Compute drift vs `drift.compare_to` (default: previous run) | off |
| `--run-date` | Logical date of the data; orders history | now |
| `--drift-rules` | YAML file with drift rules | — |
| `--coverage-drop`, `--coverage-increase` | Global coverage rules, relative % change that is a breach | `25`, `50` |
| `--field-coverage-rule` | Per-field coverage rule: `OBJECT.FIELD=drop:5,increase:30` (or `change:20`), repeatable | — |
| `--schema` | Expected JSON Schema (`file.json` or `OBJECT=file.json`, repeatable) | — |
| `--fail-on` | `never` \| `warn` \| `fail` — exit non-zero on drift / schema breaches | `never` |
| `--min-score` | Score floors, e.g. `health=70,dqi=80` (exit 2 if below) | — |
| `--max-drop` | Max score drop vs the reference, e.g. `dqi=5` | — |
| `--notify` | `slack:<url>` \| `webhook:<url>` \| `file:<path>` (repeatable) | — |
| `--format` | `text` \| `json` (summary to stdout) | `text` |
| `--history-dir` | Where versioned runs are stored | `<out-dir>/.history` |
| `--ai` | `off` \| `anthropic` \| `openai` \| `cursor` \| `copilot` \| `claude` \| `auto` | `off` |
| `--ai-model` | Model for `--ai`; a rejected model falls back to `auto` (logged) | `auto` |
| `--mask-pii / --no-mask-pii` | Mask detected PII in the report | on |
| `--debug / --no-debug` | Verbose/debug output | off |

Other commands: `serve`, `ask` (chat), `drift`, `scores`, `history list` (CI), `schema infer|validate` (BYOS),
`glossary` (definitions), `compare` (two datasets), `connection-list`, `info`.

> See the live, authoritative list anytime with `datalens --help` and `datalens <command> --help`.

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

### Google BigQuery

```bash
pip install 'datalens-ai[bigquery]'            # or: uv sync --extra bigquery
gcloud auth application-default login          # or credentials_file: path/to/service-account.json

# every table and view in a dataset
datalens analyze --source bigquery --project my-proj --dataset sales
# chosen tables, a filtered table and a query, each profiled as its own object
datalens analyze --source bigquery --project my-proj --dataset sales --tables orders,customers \
  --object "orders|order_date >= '2026-01-01' -> orders_2026" \
  --object "query:SELECT * FROM sales.orders JOIN sales.refunds USING (order_id) -> refunds"
```

- **Read-only and cost-aware:** only single SELECT statements run (specs with `;` are rejected), labelled
  `tool=datalens`; tables are sampled with `TABLESAMPLE SYSTEM` so only sampled blocks are billed; every job is capped
  by `max_bytes_billed` (default 10 GiB, set in the connection config, 0 disables).
- Row counts come from table metadata, so volume drift uses the true count. STRUCT and ARRAY columns are profiled
  as nested fields (`ship.city`, `items[].sku`); NUMERIC → number, DATE/TIMESTAMP → ISO text.
- Least-privilege roles: BigQuery Data Viewer on the dataset and BigQuery Job User on the project.
- Reusable config: [`examples/connection-configs/bigquery.yaml`](../examples/connection-configs/bigquery.yaml).

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

- `--sample-size N` bounds how many records are profiled per object. For files the sample is a **uniform random
  (reservoir) sample over the whole file** by default, so rows appended at the end — today's load — are seen, and
  the true row count is known for volume drift. Set `sample_strategy: head` (first N, fastest) or `tail` (last N,
  newest rows of append-only feeds) in the config; `sample_seed` keeps runs reproducible.
- Distinct counts are **exact** (value hashes kept in memory only, up to `distinct_track_limit`, default 1M per
  field), so keys, foreign keys and orphans work on large objects; `--max-distinct` only caps the values *shown*.
- `--full-scan` (or `--sample-size 0`) reads everything — use for small/critical datasets.
- `--max-depth` controls how deep nested objects/arrays are traversed.
- `--max-distinct` caps how many distinct values are stored per field for display (distribution charts, category
  drift). Raise it for richer distributions, lower it for smaller reports.

---

## Drift & history

Every run is saved under `--history-dir` (default `<out-dir>/.history`): the masked schema, a flat set of
**metrics** (row counts, coverage, category counts, orphan rates, scores) and the values of category-like
fields. Drift is computed from these saved runs — **no external store required**. Use the **same `--out-dir`**
(or `--history-dir`) across runs, and keep object names stable (file names / collection names).

### Three ways to compare

| Flag | Compares this run with… | Answers |
|---|---|---|
| `--detect-drift` or `--compare-to previous` | the **previous run** | "What changed since yesterday?" |
| `--compare-to baseline:<tag>` (or just `<tag>`) | a **fixed saved run** | "How far are we from the load we validated?" |
| `--compare-to rolling` | a **normal range learned from recent runs** | "Is today unusual *for this feed*?" |

`--detect-drift` uses `drift.compare_to` from config when set (default `previous`). Add `--run-date YYYY-MM-DD`
so history is ordered by the data's date (back-fills land in the right place).

**Previous run** reports each change once — at the run where it appears — then it becomes the new normal.
**Fixed baseline** keeps reporting every difference from the reference. Tags in `history_protected_tags`
(default `baseline`) are never purged by `--history-retention-days`.

### The learned rolling baseline

For every metric, the last N runs (default 14) define its normal range:

```
M = median(values)          MAD = median(|x − M|)          σ̂ = 1.4826 · MAD   (robust σ)
σ̂ₑ = max(σ̂, rel_floor·|M|, sampling noise of a percentage, 1 for counts)
band = [ min(M − k·σ̂ₑ, min seen·(1−rel_floor)),  max(M + k·σ̂ₑ, max seen·(1+rel_floor)) ]
outside the band → warn;  also |x − M| > k·σ̂ₑ → fail                     (k = 3, rel_floor = 5%)
```

- The band always covers values seen recently, so recurring patterns (a double-header every few days, a
  weekly spike) are learned as normal instead of alerting every time.
- Runs that breached are left out of later baselines (`exclude_breaches`), so a bad day can't become "normal".
- Values that appeared in any run of the window aren't reported as "new" categories.
- **Cold start:** with fewer than `min_history` (3) earlier values the fixed rules below apply; the report says
  how many metrics were scored each way.

```yaml
drift:
  compare_to: rolling
  rolling: {window: 14, min_history: 3, k: 3.0, rel_floor: 0.05, exclude_breaches: true}
```

See it in action: [`examples/scenarios/05-rolling-daily-baseline`](../examples/scenarios/05-rolling-daily-baseline/README.md).

### What is compared

| Area | Findings |
|---|---|
| Schema | objects/fields added or removed, likely **renames** (same type, coverage and values), **type changes** (types ≥ 2% of values) |
| Volume | row count per object (true count when the whole source was read) |
| Coverage | % of rows with a non-empty value, per field |
| Categories | new / vanished values of category-like fields |
| Distribution | **PSI** of categorical (top values) or numeric (percentiles) fields |
| Integrity | orphan % of each detected foreign key |
| Scores | health, DQI and each DQI dimension |

Common-sense guards keep the report quiet on noise: changes within 3 standard errors of sampling noise are
ignored; PSI must exceed 3× its sampling-noise floor; objects with fewer than `min_rows` (20) rows aren't judged
on coverage/categories/distributions; identifier, foreign-key and date fields aren't judged on value mix (new
ids every day are growth, not drift); a sparse field that's merely absent today ("~0.1 rows expected") is info.

### Drift rules — thresholds per dataset, object and field

Put rules in the app config (`-c`), the connection config (`drift:` section) or a file passed with
`--drift-rules`. The most specific rule wins: **field → object → `defaults` → built-in**. Object names and field
paths accept wildcards.

```yaml
drift:
  compare_to: previous
  defaults:
    row_count: {drop_pct: {warn: 10, fail: 20}, increase_pct: {warn: 50}}
    coverage:  {change_pct: 20}                 # 20% variance either way
    distribution: {psi_warn: 0.1, psi_fail: 0.25}
    categories: {new: warn, vanished: info}
    schema: {field_removed: fail, field_added: info, type_changed: fail, field_renamed: warn}
  objects:
    orders:
      row_count: {drop_pct: 10, drop_message: "Orders feed looks truncated: {old} → {new} ({delta_pct})"}
      fields:
        id:      {coverage: {drop_pct: 5}}      # 5% drop in the id field
        title:   {coverage: {drop_pct: 10}}
        country: {coverage: {change_pct: 20}}   # either way
```

- `*_pct` = change **relative** to the old value (80% → 76% is a 5% drop); `*_pts` = **absolute** change in the
  metric's unit (80% → 76% is 4 points); `change_*` = either direction.
- **Coverage defaults:** a decrease of ≥ 25% or an increase of ≥ 50% (relative) is a breach; moves under 1 point
  are ignored. Quick overrides without a config file:
  `--coverage-drop 15 --coverage-increase 40 --field-coverage-rule "orders.id=drop:5"`.
- Health → Trends & Drift → **Coverage Shifts** lists every real coverage move with the rule that applies (and
  its scope) and whether it fired; **Change Summary → Rules in effect** lists every rule, highlighting the ones that
  fired.
- A number means breach (`fail`); `{warn: x, fail: y}` gives two levels; `min_delta` ignores tiny absolute moves.
- Separate `drop_message` / `increase_message` templates; variables: `{object} {field} {metric} {old} {new}
  {delta} {delta_pct} {threshold} {baseline}`.
- The old `coverage_thresholds` / `--coverage-threshold` flags keep working for the legacy coverage-drift JSON.

Full defaults: [METRICS.md → Default drift rules](METRICS.md#default-drift-rules). Re-evaluate rules on saved runs
without touching the data: `datalens drift -o <out-dir> --run <tag> --compare-to <tag> --drift-rules new.yaml`.

---

## Expected schema (BYOS — bring your own schema)

Declare what the data *should* look like as a JSON Schema and every run is checked against it:

```bash
datalens analyze -s file -p data/ --schema expected.json               # applies to matching objects
datalens analyze -s file -p data/ --schema orders=orders.schema.json --schema users=users.schema.json
datalens schema infer    -s file -p data/ -o expected.json             # bootstrap from a good load, then edit
datalens schema validate -s file -p data/ --schema expected.json       # exit 2 when a check fails
```

Supported: `type` (incl. `["string","null"]`), `required`, nested `properties`, array `items`, `enum`/`const`,
`minimum`/`maximum` (+ exclusive), `pattern`, `format` (date, date-time, email, uri, uuid),
`additionalProperties: false`. One file can hold several objects under an `objects` map (what `schema infer`
writes). In a connection config: `expected_schema: path.json`.

Thresholds go in `x-datalens` blocks — generic or per field — and become drift rules for that object:

```json
{"title": "orders", "type": "object", "required": ["id", "title"],
 "x-datalens": {"defaults": {"coverage": {"change_pct": 20}}},
 "properties": {
   "id":      {"type": "string", "x-datalens": {"coverage": {"drop_pct": 5}}},
   "title":   {"type": "string", "x-datalens": {"coverage": {"drop_pct": 10}, "min_coverage": 95}},
   "country": {"type": "string", "x-datalens": {"coverage": {"change_pct": 20}}}}}
```

`x-datalens.min_coverage` (default 99) is how populated a *required* field must be. Results appear in the
**Health → Expected Schema** tab, the Action Plan, the health score (−3 per failed check, max −15),
`*-datalens-contract.json` and the CI gates. Example: [`examples/scenarios/07-byos-expected-schema`](../examples/scenarios/07-byos-expected-schema/README.md).

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

When AI is enabled, Datalens writes `{source}-datalens-ai-insights.md` and adds a **Verdict → AI Review** tab to the HTML report.

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

PII is detected from **values** (e.g. real email/phone/card shapes in the observed values) and from **whole-word
field names** (`first_name`, `ssn`, `email`; `company` is not "pan", `hotel` is not "tel"). Each detection records
how it was found: `value`, `name`, `name+value` or `config`. Generic names (`name`, `contact`, `author`) are only
"possible" PII.

**Masking is on by default.** High-confidence detections (≥ 80%) are masked in *every* output — HTML, schema
JSON, history snapshots, AI prompts and the chat's SQL sample (`a***@domain.com`, `***-**-1234`); their
ranges and percentiles are dropped too. Control it in the app config:

```yaml
mask_pii: true
pii_ignore: ["teams.name", "venues.*"]       # never PII
pii_force:  {"players.unique_name": name}    # always PII of this type
```

`--no-mask-pii` turns masking off for trusted internal use (the compliance checklist then fails
"Sensitive identifiers masked"). A confirmed direct identifier sets a floor on the compliance risk
(email/phone → at least medium; SSN/card/passport → high), however few fields it is.

---

## Outputs

Written to `<out-dir>/<source>_<tag>/`:

| File | Use it for |
|---|---|
| `{source}-datalens-report.html` | Sharing, reviewing, decisions. Self-contained — works offline and over email. |
| `{source}-datalens-run-summary.json` | CI/CD: scores, drift status + highlights, expected-schema status, top actions. |
| `{source}-datalens-drift-report.json` | Every drift finding with the rule/band that fired (when compared). |
| `{source}-datalens-contract.json` | Expected-schema checks (with `--schema`). |
| `{source}-datalens-schema.json` | Masked field statistics — pipelines, tests, diffing. |
| `{source}-datalens-summary.md` | Pasting into PRs, tickets, or chat. |
| `{source}-datalens-ai-insights.md` | AI review (with `--ai`). |
| `{source}-datalens-run-manifest.json` | Source (no secrets) so `datalens serve` / `ask` can query the data. |
| `{source}-datalens-schema-drift.json`, `-coverage-drift.json` | Legacy drift artifacts (kept for compatibility). |

History runs are stored under `<out-dir>/.history/<version-tag>/` (`schema.json`, `metrics.json`, `metadata.json`).

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
result.decision["next_steps"]            # every action: evidence, fix, severity, source, priority
result.decision["top_actions"]           # top 3 of next_steps
result.decision["drift_severity"]        # none|low|medium|high

# drift, expected schema, metrics
result.drift_report                      # findings with the rule/band that fired, status, highlights
result.contract                          # expected-schema checks (config.expected_schemas)
result.metrics                           # flat metrics saved to history (rolling baseline input)

with open("report.html", "w") as f:
    f.write(result.html_report)
```

### Drift in code

```python
from datalens.history.store import HistoryStore

store = HistoryStore("output/.history")
runs = store.load_runs()                                  # newest first: tag, metrics, categories, …
result = analyze(spec, Config(drift={"compare_to": "rolling"}),
                 previous_schema=store.load(runs[0]["tag"]), reference_tag=runs[0]["tag"],
                 history_runs=runs, drift_mode="rolling")
print(result.drift_report["status"], result.drift_report["highlights"])
store.save("2026-05-31", result.schema_json, metrics=result.metrics, categories=result.categories,
           breached=result.drift_report["breached_metrics"], run_date="2026-05-31")
```

---

## CI/CD — gates, exit codes, notifications

Everything in the report is available from the CLI, so a pipeline can react to it:

```bash
datalens analyze --cc nightly_export -o output --version-tag "$(date +%F)" --run-date "$(date +%F)" \
  --compare-to rolling --schema expected.json \
  --fail-on fail --min-score health=70,dqi=85,completeness=90 --max-drop dqi=5 \
  --notify "slack:$SLACK_WEBHOOK" --format json > summary.json
```

| Option | Effect |
|---|---|
| `--fail-on never\|warn\|fail` | exit 2 on drift/expected-schema breaches (`fail`), also exit 1 on warnings (`warn`) |
| `--min-score health=70,dqi=80,…` | exit 2 if a score is below its floor (health, dqi or any DQI dimension) |
| `--max-drop dqi=5,health=10` | exit 2 if a score fell more than N points vs the drift reference |
| `--notify slack:<url>` / `webhook:<url>` / `file:<path.jsonl>` | send the outcome (repeatable) |
| `--format json` | the run summary on stdout (progress goes to stderr) |

**Exit codes:** `0` ok · `1` warnings with `--fail-on warn` · `2` breach or failed gate · `3` error.

Other commands for pipelines:

```bash
datalens scores <run-dir> --min-score health=70     # gate on a finished run
datalens drift -o output --compare-to rolling --fail-on fail --format json   # re-check from history only
datalens history list -o output                      # runs with status, health, DQI, drift
datalens glossary dqi                                # what a score means and how it's computed
```

A ready-to-copy GitHub Actions workflow and a cron script: [`examples/scenarios/08-ci-gate`](../examples/scenarios/08-ci-gate/README.md).

---

## Chat with a run

```bash
datalens serve output/orders_20260531 --ai claude     # report + chat panel on http://127.0.0.1:8765
datalens ask "Which customers have orphaned orders?" output/orders_20260531 --format md
```

The model sees the run's findings (scores, drift, expected-schema checks, actions — all masked) and can run
**read-only SQL** on a PII-masked sample of the data (SQLite; only SELECT; 5 s / 200-row caps). Every query is
shown with the answer. Answers can be downloaded (CSV / Markdown), added to the Action Plan, or the whole session
exported. The server binds to 127.0.0.1 only and requires a per-session token; the report file isn't changed.
Works with any configured provider (Claude CLI, Cursor, Copilot, Anthropic, OpenAI).

Both commands take `--ai <provider>` and `--ai-model <model>` (default `auto`), e.g.
`datalens serve <run-dir> --ai copilot --ai-model claude-opus-5`. The chat header shows the provider and model.
A report opened directly (no server) shows a dimmed **Ask Datalens · OFF** button that gives the exact command
to copy. Walkthrough: [scenario 13](../examples/scenarios/13-chat/README.md).

---

## Ways to use the product

| Scenario | How |
|---|---|
| **Onboard a new dataset** | Run once, read the Executive Summary, skim Field Explorer. |
| **Pre-warehouse / pre-ingest gate** | Check Fitness-for-Use ("Ready for reporting") and the Action Plan before loading. |
| **ML readiness check** | Look for "Ready for ML/AI" badges and the type-stability / PII drivers. |
| **Governance / sharing review** | Use the PII Detection tab + Compliance scorecard; keep masking on. |
| **Monitor a feed over time** | Schedule runs with `--compare-to rolling`; watch Trends & Drift; gate with `--fail-on fail`. |
| **Enforce a contract** | Write (or `schema infer`) an expected JSON Schema and pass `--schema`. |
| **Investigate a finding** | `datalens serve <run-dir>` and ask; add answers to the Action Plan. |
| **Brief a stakeholder** | Send the HTML report; point them at the Overview banner (or print to PDF). |
| **Automate quality gates** | `--fail-on`, `--min-score`, `--max-drop`, `--notify` — see CI/CD above. |

Next: understand exactly what each section means in the **[Report Guide](REPORT_GUIDE.md)**.
