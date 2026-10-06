# FAQ

Short answers, with links to the details.

**About Datalens:** [What is it?](#what-is-datalens) · [What sources?](#which-data-sources-does-it-support) ·
[Do I need AI?](#do-i-need-ai) · [Does my data leave my machine?](#does-my-data-leave-my-machine)

**Getting started:** [Fastest start](#whats-the-fastest-way-to-try-it) · ["No matching distribution"](#pip-install-says-no-matching-distribution-found-for-datalens-ai) · [Do I need config?](#do-i-need-a-config-file) ·
[Where does config live?](#where-does-datalens-look-for-config) · [Use my own folder](#how-do-i-use-a-config-folder-somewhere-else)

**Running it:** [Sample size](#how-do-i-change-the-sample-size) · [Full dataset](#how-do-i-run-on-the-full-dataset) ·
[Output folder](#how-do-i-change-the-output-folder) · [Keep history](#how-do-i-keep-or-limit-run-history)

**Drift and CI:** [How drift is checked](#how-does-it-check-drift) · [Change thresholds](#how-do-i-change-the-drift-thresholds) ·
[Hook into CI/CD](#how-do-i-hook-it-into-cicd) · [Get notified](#can-it-notify-me)

**Reading results:** [Health vs DQI](#whats-the-difference-between-health-and-dqi) ·
[Why is a field flagged?](#why-is-a-field-flagged-as-pii-or-mixed-type) · [Ask questions](#can-i-ask-questions-about-my-data)

---

## About Datalens

### What is Datalens?
A command-line tool, and a Python library, that profiles your data and tells you whether you can trust it. You
point it at files, MongoDB, BigQuery, S3 or an HTTP API. You get:
- an offline HTML report: a health score, quality scores per field and object, keys and orphans, PII, and a
  prioritised **Action Plan**;
- **drift** detection against earlier runs, including a baseline it learns from your own history;
- checks against **your expected schema** (BYOS);
- exit codes and JSON output for **CI/CD**, plus optional AI review and chat.

### Which data sources does it support?
- **Files:** CSV, JSON, JSONL, XML and Excel, optionally `.gz`/`.zip`. A file or a whole folder.
- **Databases and services:** MongoDB, Google BigQuery (`datalens-ai[bigquery]`), Amazon S3 and HTTP/REST APIs
  (`datalens-ai[cloud]`).

See [Setup Connections](CONNECTION_CONFIG.md).

### Do I need AI?
No. Every score, drift check, schema check and action comes from deterministic rules you can read in
[Metrics](METRICS.md). AI is an optional reviewer (`--ai claude|copilot|cursor|anthropic|openai`) and powers the
chat. See [AI Providers](AI_PROVIDERS.md).

### Does my data leave my machine?
Not unless you turn on AI. The report is a single offline HTML file.
- With `--ai`, the model gets the *findings* (field names, types, scores, drift), not your rows. PII fields are
  flagged as masked.
- With chat (`datalens serve`), the model can run read-only SQL on a **PII-masked sample**, and the results go
  to the model.
- PII values are masked in reports by default (`--no-mask-pii` turns that off).

---

## Getting started

### What's the fastest way to try it?
```bash
pip install datalens-ai
datalens analyze --source file --path your_data.csv
```
Then open `output/<name>_<tag>/<tag>-datalens-report.html`. Want a demo with real drift? Clone the repo and run
`bash examples/demo/run_demo.sh`.

### `pip install` says "No matching distribution found for datalens-ai"
Your `pip` belongs to a Python older than 3.11. The message includes *"Ignored the following versions that require a
different python version"*. On macOS this is usually the built-in Python 3.9. Check with `pip --version`, then:
```bash
pipx install datalens-ai                 # or: uv tool install datalens-ai (both choose a suitable Python)
python3.12 -m venv .venv && source .venv/bin/activate && pip install datalens-ai   # or a venv with 3.11+
```
No Python 3.11+ installed? The [Install guide](INSTALL.md) covers every method on macOS and Windows.

### Do I need a config file?
No. Every option is also a CLI flag. A config folder saves you repeating flags, keeps credentials out of your
commands, and lets you name data sources (`--cc orders_db`). Create one with `datalens init`.
See the [Setup Guide](SETUP.md).

### Where does Datalens look for config?
In a **config folder** (`config.yaml`, `secrets.yaml`, `.env`, `connections/`):
1. the folder from `--config-dir` or `DATALENS_CONFIG_DIR`, and nothing else; otherwise
2. `./.datalens/` in the current directory, then `~/.datalens/`.

Run `datalens config-show` to see exactly which files are being used.

### How do I use a config folder somewhere else?
```bash
datalens init /path/to/my-config                      # create it (any location)
datalens analyze --config-dir /path/to/my-config --cc orders_db
export DATALENS_CONFIG_DIR=/path/to/my-config         # or set it once for the shell, server or CI job
```
This also stops a project's own `.datalens/` from being used by accident. You can pass single files instead:
`-c config.yaml`, `--secrets secrets.yaml`, `--cc path/to/orders_db.yaml`.

### How do I add a data source?
```bash
datalens connection-new orders --source file --path ./exports      # or mongodb, http, s3, bigquery
datalens analyze --cc orders
```
This writes `connections/orders.yaml`, which you can edit. Every option is in [Setup Connections](CONNECTION_CONFIG.md).

---

## Running it

### How do I change the sample size?
Datalens profiles a sample of each object: 10,000 records by default, chosen uniformly at random (reservoir
sampling). Set it, from highest to lowest priority, with:
- `--sample-size 50000` on the command line;
- `profiling: {sample_size: 50000}` in a connection file;
- `sample_size: 50000` in `config.yaml`.

To profile the **newest** records of an append-only feed, set `sample_strategy: tail` in `config.yaml`
(`head` takes the first N). Row counts are always counted in full for files, so volume drift stays exact.

### How do I run on the full dataset?
`--full-scan`, which is the same as `--sample-size 0` or `sample_size: 0` in config. Expect it to be slower and to
use more memory on large sources. For BigQuery, keep the `max_bytes_billed` cap in the connection.

### How do I change the output folder?
- `-o reports` / `--out-dir reports`, or `out_dir: reports` in `config.yaml`.
- Each run gets its own sub-folder, `<out_dir>/<source>_<tag>/`, holding the HTML report, the JSON run summary,
  the drift report and the schema.
- Name runs with `--version-tag day1` (the default is a timestamp), and set the data's date with
  `--run-date 2026-05-31`.

### How do I keep or limit run history?
Every run is saved automatically under `<out_dir>/.history/`. That's what drift compares against.
- **Where:** `--history-dir /shared/datalens-history` keeps it in one place across output folders, which is
  useful on servers and in CI caches.
- **How long:** `--history-retention-days 30` (or `history_retention_days: 30` in config) deletes older runs.
  The default, `0`, keeps everything.
- **Keep a run forever:** tag it `baseline`, or protect any tag with `--history-protected-tag golden`.
- **Look back:** `datalens history list`. Re-check two saved runs without the data: `datalens drift --run day2 --compare-to day1`.

---

## Drift and CI

### How does it check drift?
Each run saves metrics per object and field. The next run compares against a **reference**:

| `--compare-to` | Compares with |
|---|---|
| `previous` (default with `--detect-drift`) | the last saved run |
| `baseline:<tag>` or `<tag>` | a fixed run, e.g. your first good load |
| `rolling` | a **learned normal range** from recent runs |

It checks:
- **schema:** fields added, removed or renamed, and type changes;
- **volume:** row counts;
- **coverage:** how often each field holds a real value;
- **values:** distinct counts, new or vanished categories, and distribution shift (PSI);
- **integrity:** orphaned foreign keys;
- **scores:** DQI and health.

Each finding names the rule that fired and its scope (field, object, dataset or built-in).

**Rolling baseline:** for each metric, over the last 14 runs: median ± 3 × 1.4826 × MAD, widened to include every
normal value seen so far. Runs that breached are left out, so one bad day can't make bad look normal. With fewer
than 3 runs it falls back to the fixed rules. The result: a feed that normally swings between one and two matches a
day doesn't alert every day, but a truncated load still does. The formula is in [Metrics](METRICS.md).

Small samples are protected from false alarms. Objects under 20 rows aren't judged on coverage or distributions,
and coverage changes within sampling noise are ignored.

### How do I change the drift thresholds?
Under `drift:` in `config.yaml` or a connection file. The most specific rule wins: field → object → dataset → built-in.
```yaml
drift:
  compare_to: rolling
  defaults:
    row_count: {drop_pct: {warn: 10, fail: 25}, increase_pct: 50}
    coverage:  {drop_pct: 25, increase_pct: 50}
  objects:
    orders:
      fields:
        email: {coverage: {drop_pct: 5, drop_message: "Emails missing on {delta_pct} more orders"}}
```
- `_pct` means a relative change and `_pts` an absolute one (percentage points).
- Drops and increases have separate thresholds and messages.

Built-in defaults, and the expected-schema route (`x-datalens` thresholds per field), are covered in the
[Usage Guide](USAGE.md#drift-rules--thresholds-per-dataset-object-and-field) and
[scenario 07](https://github.com/m8d8/datalens.ai/blob/main/examples/scenarios/07-byos-expected-schema/README.md).

### How do I hook it into CI/CD?
Run it after each load and let the exit code decide. Without `--fail-on`, drift is reported but never fails the job:

```bash
datalens analyze --cc orders_db --compare-to rolling \
  --fail-on fail --min-score health=70,dqi=80 --max-drop dqi=5 \
  --format json > datalens-summary.json
```

| Exit code | Meaning |
|---|---|
| `0` | OK |
| `1` | Warnings, only with `--fail-on warn` |
| `2` | A failed score gate (`--min-score`, `--max-drop`), or, with `--fail-on fail`, a drift breach or expected-schema failure |
| `3` | Error: bad config, source unreachable |

To keep drift working in CI, persist `<out_dir>/.history` between jobs, for example with a cache. Pass
credentials as CI secrets through environment variables used by `${VAR}` in connection files. A complete GitHub
Actions workflow is in [scenario 08](https://github.com/m8d8/datalens.ai/blob/main/examples/scenarios/08-ci-gate/README.md).
To gate on an existing run without re-reading the data, use `datalens scores <run_dir> --min-score …`.

### Can it notify me?
Yes. `--notify slack:<webhook-url>`, `--notify webhook:<url>` or `--notify file:alerts.jsonl` (repeatable) send
the outcome and each breach, using the rule's message.

---

## Reading results

### What's the difference between health and DQI?
- **DQI** (Data Quality Index) is the weighted mean of seven quality dimensions: completeness, consistency,
  uniqueness, validity, timeliness, granularity and accuracy.
- **Health** is DQI minus penalties: PII exposure, drift, expected-schema failures and mixed types.
- Health of 80 or more is Healthy, 60 or more Needs attention, and below 60 At risk.
- **Verdict → How scores work** shows this run's arithmetic, and every ⓘ explains its number.
  `datalens glossary <term>` prints the same text.

### Why is a field flagged as PII or mixed-type?
- **PII:** detected from values (for example real email shapes) and whole-word field names. Tune it in
  [scenario 11](https://github.com/m8d8/datalens.ai/blob/main/examples/scenarios/11-pii-controls/README.md).
- **Mixed type:** the field holds more than one type, for example int and string seasons. The Action Plan says
  which fields and how to fix them.

### Can I ask questions about my data?
Yes. `datalens serve <run folder> --ai claude` opens the report with a chat panel, and `datalens ask "…" <run folder>`
answers one question in the terminal. See [scenario 13](https://github.com/m8d8/datalens.ai/blob/main/examples/scenarios/13-chat/README.md).

### Can I use it from Python?
```python
from datalens import analyze
result = analyze({"source": "file", "path": "orders.csv"})
result.decision["health_verdict"], result.decision["next_steps"], result.drift_report
```

---

More: [Setup Guide](SETUP.md) · [Usage Guide](USAGE.md) · [Report Guide](REPORT_GUIDE.md) · [Metrics](METRICS.md)
