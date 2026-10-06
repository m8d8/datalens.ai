# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.1] - 2026-10-02

### Added
- The console now says when results come from a sample (per object: sampled of total) and how to get exact numbers:
  `--full-scan`, or a larger `--sample-size`.
- Data Story "Content Universe" now picks up to 3 fields by their values instead of by name: text, not an id, 2–50
  distinct values, filled in ≥90% of records. A field present in every object ranks first. Each field gets one chart per
  object, side by side, plus a combined chart summing the counts across objects. Under 10 values is a pie; 10–50 is a
  colourful vertical bar chart. Nothing is shown when no field qualifies.
- `pii_detection` setting (`--no-pii-detection`, `DATALENS_PII_DETECTION`): turn PII detection off entirely.
  Default stays on. The lock badge's hover text now suggests it.
- Install guide (`docs/INSTALL.md`): every way to install on macOS and Windows (pipx, uv, venv, conda, from source,
  WSL), extras, upgrade and uninstall, and fixes for common errors.

### Fixed
- CSV and Excel: empty columns that are out of line with the file's header convention are skipped: a blank header, or
  a generated name (`col_6`, `Column1`, `Unnamed: 3`) in a file whose other headers are real names. If most headers are
  generated (`Column1, Column2, Column3`), that is the convention and an empty column is kept. Named columns and
  columns holding data are always kept.
- PII false positives: a bare `name` field (channel, team, product) is no longer flagged; 9-digit ids are no longer
  read as SSNs (SSN, phone and passport values need separators or a matching field name; SSNs must be structurally
  valid; card numbers must pass Luhn).
- Docs: the base install covers files and MongoDB; HTTP/REST APIs need the `cloud` extra.
- Docs: install troubleshooting for an old default `pip` ("No matching distribution found") and
  "externally-managed-environment".

## [1.0.0] - 2026-10-02

First stable release, and the first on PyPI. From here on, the CLI commands and flags, exit codes,
config and drift-rule formats, and the run-summary JSON follow Semantic Versioning: breaking changes only in a
new major version.

### Added
- **Drift engine**: configurable rules per dataset, object and field, with separate drop and increase thresholds
  and messages. Compare with the previous run, a fixed baseline, or a learned rolling baseline (median ± MAD band).
- **Coverage shifts**: global rules (decrease 25%, increase 50%) plus per-field overrides; fired rules are highlighted
  in the Change Summary.
- **BYOS**: bring your own JSON Schema with `x-datalens` thresholds; `datalens schema infer|validate`.
- **CI/CD**: stable exit codes (0 ok, 1 warn, 2 fail, 3 error), score gates, Slack/webhook notifications;
  `datalens drift`, `scores`, `history`.
- **Action Plan** tab: every finding as a prioritised action with evidence and a fix, exportable.
- **AI review** (Claude CLI, GitHub Copilot CLI, Cursor, Anthropic, OpenAI) with model `auto` and fallback on
  a rejected model; `--ai-model`.
- **Chat**: `datalens serve` / `datalens ask`, read-only SQL on a PII-masked sample.
- **BigQuery** connector (`datalens-ai[bigquery]`).
- Glossary, ⓘ tooltips and `docs/METRICS.md` explaining every score.
- 13 runnable example scenarios and a reproducible cricket demo dataset.
- **Config folder** for every setting: `--config-dir` / `DATALENS_CONFIG_DIR` uses only that folder (anywhere on
  disk), otherwise `./.datalens` then `~/.datalens`. New commands: `datalens init` (scaffold a folder),
  `datalens connection-new` (write a connection from a template), `datalens config-show` (what's in use).
- Setup Guide (`docs/SETUP.md`, with Setup Connections as its sub-page) and an FAQ (`docs/FAQ.md`).

### Changed
- Coverage is true coverage everywhere: nulls, empty values and missing fields all count as not covered.
- Report regrouped into Verdict / Health / Shape / Structure / Fingerprint, with a Business view.

### Fixed
- `out_dir` in `config.yaml` was ignored because `--out-dir` always defaulted to `output`.
- `connection-list` hid connections whose `${VAR}` placeholders weren't set.
- PII leaking into schema JSON and history; exact distinct counts; reservoir sampling instead of head-only.

[Unreleased]: https://github.com/m8d8/datalens.ai/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/m8d8/datalens.ai/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/m8d8/datalens.ai/releases/tag/v1.0.0

## [0.2.0] - 2026-10-02
### Added
- deep schema analysis
- schema profiling
- trusted data quality score
- interactive report
- cli support
- optional AI Insights