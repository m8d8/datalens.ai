# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/m8d8/datalens.ai/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/m8d8/datalens.ai/releases/tag/v1.0.0
