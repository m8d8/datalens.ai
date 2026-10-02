"""
`datalens init` and `datalens connection-new`: write a ready-to-edit config folder.

Templates live here as strings (not files) so they ship inside the wheel.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

CONFIG_TEMPLATE = """\
# Datalens app config: defaults for every run that uses this folder.
# Any key can be overridden by a CLI flag. Overlays: config-<env>.yaml (select with --env <env>).
# Full list of keys: https://github.com/m8d8/datalens.ai/blob/main/docs/SETUP.md

# Sampling
sample_size: 10000          # records per object; 0 = read everything (same as --full-scan)
sample_strategy: reservoir  # reservoir (uniform random) | head (first N) | tail (newest N, for append-only feeds)

# Output and history
out_dir: output             # where reports go (same as -o / --out-dir)
history_retention_days: 0   # delete saved runs older than N days; 0 = keep forever
history_protected_tags: [baseline]   # never deleted

# AI (optional): claude | copilot | cursor | anthropic | openai | auto ("" = off)
# ai_provider: claude
# ai_model: auto

# Drift rules (optional): https://github.com/m8d8/datalens.ai/blob/main/docs/USAGE.md#drift-rules--thresholds-per-dataset-object-and-field
# drift:
#   compare_to: previous       # previous | rolling | baseline:<tag>
#   defaults:
#     row_count: {drop_pct: 20, increase_pct: 50}
#     coverage:  {drop_pct: 25, increase_pct: 50}
"""

SECRETS_TEMPLATE = """\
# Datalens secrets. KEEP THIS FILE OUT OF GIT.
# Uncomment only what you use. Environment variables work too (shown next to each key).

# anthropic:
#   api_key: "sk-ant-..."        # or ANTHROPIC_API_KEY
#   model: auto
# openai:
#   api_key: "sk-..."            # or OPENAI_API_KEY
# copilot:
#   model: auto                  # e.g. claude-opus-5; login via the `copilot` CLI, no key needed
# claude:
#   model: auto                  # login via the `claude` CLI, no key needed
# mongodb:
#   uri: "mongodb+srv://<user>:<password>@<cluster>.mongodb.net"
# s3:
#   access_key_id: "AKIA..."     # or AWS_ACCESS_KEY_ID
#   secret_access_key: "..."     # or AWS_SECRET_ACCESS_KEY
#   region: us-east-1
"""

ENV_TEMPLATE = """\
# Values for ${VAR} placeholders in connections/*.yaml. KEEP THIS FILE OUT OF GIT.
# DATA_DIR=/data/exports
# API_TOKEN=...
"""

GITIGNORE_TEMPLATE = """\
# Never commit credentials from this config folder
secrets.yaml
.env
.tmp/
"""

_PARAMS = {
    "file": """\
params:
  path: "{path}"               # a file (.csv .json .jsonl .xml .xlsx, optionally .gz/.zip) or a folder
  # pattern: "*.jsonl.gz"      # when path is a folder: which files (each file = one object)
  # recursive: false
""",
    "mongodb": """\
params:
  uri: "{uri}"                 # e.g. mongodb://localhost:27017 or ${{MONGO_URI}} (keep passwords in .env)
  db: "my_database"
  # collections: "users,orders"   # default: all collections
""",
    "http": """\
params:
  uri: "{uri}"                 # JSON, JSONL, CSV or XML endpoint
  # auth_type: bearer          # none | bearer | basic | api_key
  # auth_token: "${{API_TOKEN}}"
  timeout: 30
""",
    "s3": """\
params:
  uri: "{uri}"                 # e.g. s3://my-bucket/raw/
  region: us-east-1
  # access_key_id: "${{AWS_ACCESS_KEY_ID}}"        # default: the standard AWS credential chain
  # secret_access_key: "${{AWS_SECRET_ACCESS_KEY}}"
""",
    "bigquery": """\
params:
  project: "{project}"         # default: your credentials' project
  dataset: "my_dataset"
  # tables: "orders,customers" # default: every table and view
  max_bytes_billed: 10737418240   # 10 GiB safety cap
""",
}

CONNECTION_TEMPLATE = """\
# Connection "{name}" ({source}). Use it with:  datalens analyze --cc {name}
# Values like ${{VAR}} are read from the environment or this folder's .env file.
# More examples: https://github.com/m8d8/datalens.ai/tree/main/examples/connection-configs

name: {name}
source_type: {source}
description: "{description}"

{params}
profiling:
  sample_size: 10000           # 0 = full scan

# drift:                       # per-connection drift rules (override config.yaml)
#   compare_to: rolling
# history:
#   retention_days: 30

metadata:
  created: "{today}"
"""

SOURCES = tuple(_PARAMS)


def connection_yaml(name: str, source: str, *, path: str | None = None, uri: str | None = None,
                    project: str | None = None, description: str | None = None) -> str:
    defaults = {
        "path": path or "/path/to/data",
        "uri": uri or {"mongodb": "mongodb://localhost:27017", "http": "https://api.example.com/v1/items",
                       "s3": "s3://my-bucket/raw/"}.get(source, ""),
        "project": project or "${GCP_PROJECT}",
    }
    params = _PARAMS[source].format(**defaults)
    return CONNECTION_TEMPLATE.format(name=name, source=source, params=params, today=date.today().isoformat(),
                                      description=description or f"{source} source")


def _write(path: Path, text: str, *, force: bool, private: bool = False) -> str:
    if path.exists() and not force:
        return "kept"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if private:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return "created"


def init_config_dir(folder: Path, *, force: bool = False, example: bool = True) -> list[tuple[Path, str]]:
    """Create the folder layout. Existing files are kept unless ``force``. Returns (path, status)."""
    folder = folder.expanduser()
    results = [
        (folder / "config.yaml", _write(folder / "config.yaml", CONFIG_TEMPLATE, force=force)),
        (folder / "secrets.yaml", _write(folder / "secrets.yaml", SECRETS_TEMPLATE, force=force, private=True)),
        (folder / ".env", _write(folder / ".env", ENV_TEMPLATE, force=force, private=True)),
        (folder / ".gitignore", _write(folder / ".gitignore", GITIGNORE_TEMPLATE, force=force)),
    ]
    (folder / "connections").mkdir(parents=True, exist_ok=True)
    if example:
        p = folder / "connections" / "my_files.yaml"
        results.append((p, _write(p, connection_yaml("my_files", "file", description="Local files"), force=force)))
    return results


def write_connection(folder: Path, name: str, source: str, *, force: bool = False, **kwargs: str | None) -> tuple[Path, str]:
    path = folder.expanduser() / "connections" / f"{name}.yaml"
    return path, _write(path, connection_yaml(name, source, **kwargs), force=force)
