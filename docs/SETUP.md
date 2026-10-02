# Setup Guide

Everything you need to go from `pip install` to a scheduled, version-controlled setup. Read the first section,
then only the parts you need.

**In this guide:** [Install](#1-install) · [First run, no config](#2-your-first-report-no-config-needed) ·
[The config folder](#3-the-config-folder) · [Create one](#4-create-a-config-folder) ·
[App config](#5-app-config-configyaml) · [Secrets](#6-secrets) · [Connections](#7-connections) ·
[Environments](#8-environments-dev-staging-prod) · [Servers and CI](#9-servers-ci-and-shared-setups) ·
[Check your setup](#10-check-what-is-in-use) · **Sub-page:** [Setup Connections](CONNECTION_CONFIG.md)

---

## 1. Install

```bash
pip install datalens-ai              # or: uv tool install datalens-ai  /  pipx install datalens-ai
datalens --help
```

Extras: `datalens-ai[ai]` (Anthropic/OpenAI SDKs), `[bigquery]`, `[cloud]` (S3, HTTP, SFTP), `[all]`.
Python 3.11 or newer.

## 2. Your first report: no config needed

Config is optional. Point Datalens at a file or folder and you get a report:

```bash
datalens analyze --source file --path orders.csv                   # one file
datalens analyze --source file --path ./exports --pattern "*.jsonl.gz"   # a folder: each file is an object
open output/*/*-datalens-report.html
```

Add a config folder when you want to stop repeating flags, keep credentials out of commands, or run the same
setup on a server.

## 3. The config folder

A config folder holds everything Datalens reads besides your data. Every file in it is optional:

```
<config folder>/
├── config.yaml            # app defaults: sample size, output folder, AI, drift rules …
├── config-prod.yaml       # optional overlay for --env prod (dev, staging … any name)
├── secrets.yaml           # API keys and passwords        ← never commit
├── .env                   # values for ${VAR} in connections ← never commit
└── connections/
    ├── orders_db.yaml     # one file per data source: datalens analyze --cc orders_db
    └── events_api.yaml
```

**Which folder is used:**

| How you run it | Folder(s) searched |
|---|---|
| `--config-dir /any/path` (or `export DATALENS_CONFIG_DIR=/any/path`) | **Only** `/any/path`. Nothing else is read. |
| Default | `./.datalens/` in the current directory, then `~/.datalens/`. For each file, the first folder that has it wins. |

- **Use `--config-dir` whenever you want certainty.** For example, if you run Datalens from inside a repo that has
  its own `.datalens/` (this repo ships demo connections there), `--config-dir` makes sure only *your* folder is used.
- The folder can be anywhere: `~/work/datalens-conf`, `/etc/datalens`, a mounted secret volume, a separate git repo.
- `--config-dir` works before or after the command: `datalens --config-dir X analyze …` or `datalens analyze --config-dir X …`.
- You can also skip folders and pass single files directly: `-c config.yaml`, `--secrets secrets.yaml`,
  `--cc path/to/orders_db.yaml`.

## 4. Create a config folder

```bash
datalens init                        # ~/.datalens: personal, used from any directory
datalens init ./.datalens            # per project: commit config.yaml and connections/, not secrets
datalens init /etc/datalens          # anywhere; then use --config-dir /etc/datalens
```

`init` writes a commented `config.yaml`, empty `secrets.yaml` and `.env` (readable only by you), a
`.gitignore` that keeps those two out of git, and an example connection, `connections/my_files.yaml`.
It never overwrites existing files (`--force` does).

Add your first data source and run it:

```bash
datalens connection-new orders --source file --path ./exports        # file | mongodb | http | s3 | bigquery
datalens analyze --cc orders
```

## 5. App config (`config.yaml`)

Defaults for every run. Any CLI flag overrides the same key.

| Key | Default | Same as flag | Meaning |
|---|---|---|---|
| `sample_size` | `10000` | `--sample-size` | Records per object. `0` reads everything (`--full-scan`). |
| `sample_strategy` | `reservoir` | — | `reservoir` (uniform random), `head` (first N) or `tail` (newest N, for append-only feeds). |
| `out_dir` | `output` | `-o`, `--out-dir` | Where reports and run history go. |
| `history_retention_days` | `0` | `--history-retention-days` | Delete saved runs older than N days. `0` keeps them forever. |
| `history_protected_tags` | `[baseline]` | `--history-protected-tag` | Runs with these tags are never deleted. |
| `ai_provider` | off | `--ai` | `claude`, `copilot`, `cursor`, `anthropic`, `openai` or `auto`. |
| `ai_model` | `auto` | `--ai-model` | Model for that provider. |
| `mask_pii` | `true` | `--mask-pii` / `--no-mask-pii` | Mask PII values in reports and anything sent to AI. |
| `drift` | built-in rules | `--compare-to`, … | Drift rules and the comparison mode: see [Drift rules](USAGE.md#drift-rules--thresholds-per-dataset-object-and-field). |

**Precedence**, lowest to highest: built-in defaults → `DATALENS_*` environment variables → `config.yaml` →
`config-<env>.yaml` → `-c file` → a connection's own `profiling:` / `drift:` / `history:` sections → CLI flags.

## 6. Secrets

Put credentials in `secrets.yaml` (or environment variables), never in commands or committed files:

```yaml
anthropic:
  api_key: "sk-ant-..."          # or ANTHROPIC_API_KEY
mongodb:
  uri: "mongodb+srv://<user>:<password>@<cluster>.mongodb.net"
```

Connection files reference secrets as `${VAR}`. Each value comes from the environment, or from `.env` in the config
folder:

```bash
# <config folder>/.env
ORDERS_DB_URI=mongodb+srv://reader:…@prod.mongodb.net
```

AI providers that use a CLI login (`claude`, `copilot`, `cursor`) need no secrets at all. See [AI Providers](AI_PROVIDERS.md).

## 7. Connections

A connection is one YAML file per data source in `connections/`. The file name must match its `name:`.

```yaml
# connections/orders_db.yaml
name: orders_db
source_type: mongodb
params:
  uri: "${ORDERS_DB_URI}"
  db: shop
  collections: "orders,customers"
profiling:
  sample_size: 20000
drift:
  compare_to: rolling
```

```bash
datalens connection-new orders_db --source mongodb      # writes a commented template
datalens connection-list                                # what's available
datalens analyze --cc orders_db
```

Every source type, auth option and per-connection setting is covered in the sub-page
**[Setup Connections](CONNECTION_CONFIG.md)**, with ready-made examples in
[`examples/connection-configs/`](https://github.com/m8d8/datalens.ai/tree/main/examples/connection-configs).

## 8. Environments (dev, staging, prod)

Keep one `config.yaml` with shared defaults, plus a small overlay per environment that holds only what differs:

```yaml
# config-prod.yaml
sample_size: 50000
history_retention_days: 90
```

```bash
datalens analyze --cc orders_db --env prod       # or: export DATALENS_ENV=prod
```

## 9. Servers, CI and shared setups

**A server or scheduled job:** keep the folder outside the code and point at it:

```bash
export DATALENS_CONFIG_DIR=/etc/datalens         # in the service or cron environment
datalens analyze --cc orders_db --compare-to rolling --fail-on fail
```

**CI (GitHub Actions and similar):** commit `config.yaml` and `connections/` (no secrets) in a folder such as
`datalens/`, and pass credentials as CI secrets through environment variables:

```yaml
- run: datalens --config-dir datalens analyze --cc orders_db --fail-on fail --format json
  env:
    ORDERS_DB_URI: ${{ secrets.ORDERS_DB_URI }}
```

A complete workflow with caching of run history is in
[scenario 08](https://github.com/m8d8/datalens.ai/blob/main/examples/scenarios/08-ci-gate/README.md).

**A team:** share `config.yaml` and `connections/` in git. Each person keeps their own `secrets.yaml` or `.env`
(both are git-ignored by the `.gitignore` that `init` writes).

## 10. Check what is in use

```bash
datalens config-show                  # the folder(s), which files were found, effective defaults
datalens config-show --env prod       # including the overlay
datalens --config-dir /etc/datalens config-show
```

Example output:

```
--config-dir / $DATALENS_CONFIG_DIR = /etc/datalens (only this folder)

/etc/datalens
  ✓ in use  config.yaml
  ✓ in use  secrets.yaml
  connections/: events_api, orders_db

Effective defaults  sample_size=10000 · sample_strategy=reservoir · out_dir=output · ai=off · history_retention_days=0
```

**Something not picked up?** Run `config-show`. The most common causes: running from a directory that has its own
`.datalens/` (fix: `--config-dir`), a connection file whose name doesn't match its `name:`, or a `${VAR}` that isn't
set (the error names the variable).

---

Next: [Setup Connections](CONNECTION_CONFIG.md) · [FAQ](FAQ.md) · [Usage Guide](USAGE.md) · [Report Guide](REPORT_GUIDE.md)
