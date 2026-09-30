# Report Guide

A complete tour of the Datalens HTML report — what every section means, how it's computed, and how to use it to make decisions. The report is a single self-contained file: it works offline, has light/dark mode, global search, sortable tables, and CSV export.

**Audiences:** sections are marked 👔 *business* / 🔬 *analyst* / 👥 *both* to help you focus.

- [Global features](#global-features)
- [Tab 1 — Overview](#tab-1--overview) 👥
- [Tab 2 — Insights](#tab-2--insights) 👔
- [Tab 3 — Data Quality](#tab-3--data-quality) 🔬
- [Tab 4 — PII Detection](#tab-4--pii-detection) 👔
- [Tab 5 — Field Explorer](#tab-5--field-explorer) 🔬
- [Tab 6 — Coverage](#tab-6--coverage) 🔬
- [Tab 7 — Distributions (+ Statistics)](#tab-7--distributions--statistics) 🔬
- [Tab 8 — Patterns](#tab-8--patterns) 🔬
- [Tab 9 — Type Warnings](#tab-9--type-warnings) 🔬
- [Tab 10 — Relationships](#tab-10--relationships) 🔬
- [Tab 11 — Cross-Object](#tab-11--cross-object) 🔬
- [Tab 12 — Trends & Drift](#tab-12--trends--drift) 👥
- [Recommended workflows](#recommended-workflows)
- [How the scores are computed](#how-the-scores-are-computed)

---

## Global features

| Feature | How to use |
|---|---|
| **Global search** | The header search box filters fields, objects, and values across every tab and highlights matches. |
| **Sortable tables** | Click any column header to sort; click again to reverse. |
| **CSV export** | Tables with an export button download exactly what you see. |
| **Distinct-value modal** | Click a field's distinct count to see its value distribution in a popup. |
| **Light / dark mode** | Toggle in the header; your choice is remembered. |
| **Offline** | No network is ever used — safe to email or archive. |

---

## Tab 1 — Overview 👥

The landing tab. It opens with the **Executive Summary banner** — the one screen most stakeholders need.

**Executive Summary banner**
- **Health verdict** — 🟢 *Healthy* / 🟡 *Needs attention* / 🔴 *At risk*, with a 0–100 score.
- **PII risk pill** — ratio-based risk (e.g. "Medium · 40% of fields") so small and large datasets compare fairly.
- **Change since last run** — drift status (or "No prior run" on a baseline).
- **What drives this score** — the specific factors (DQI, high-risk PII, mixed types, drift) and their point impact.
- **Top 3 things to fix** — the highest-priority actions, each with an **effort** badge and a plain-language **business impact**.

**KPI cards** — Objects, Fields, Records Sampled, plus the DQI and PII summary cards.

**Objects Summary table** — per object: field count, records sampled, high/low-coverage counts, and **Fitness-for-Use** badges (*Ready for reporting*, *Ready for ML/AI*, *Needs cleanup*, *Recently changed*).

**How to use it:** read the verdict, fix the top 3, and use the Fitness badges to decide what each dataset is ready for. If you only look at one screen, look at this one.

---

## Tab 2 — Insights 👔

Narrative and strategic synthesis of the findings.

- **Data Story** — a plain-language paragraph describing scale, content segments, quality, joins, and dominant value shapes.
- **Content Universe** — a donut of record types/categories when a type-like field is detected.
- **SWOT** — Strengths / Weaknesses / Opportunities / Threats derived from quality, joins, patterns, and PII.
- **Recommendations** — actionable items by severity and category (this also feeds the Overview "Top 3").
- **AI Readiness** — a checklist (stable IDs, freshness timestamps, type stability, PII safety, documentation, chunking) for using the data with LLMs.

**How to use it:** great for a written brief or a planning conversation; copy the Data Story and SWOT straight into a doc.

---

## Tab 3 — Data Quality 🔬

The full **Data Quality Index (DQI)** breakdown.

- **Overall DQI gauge** with a letter grade (A–F).
- **Schema Dimensions radar** — completeness, consistency, uniqueness, validity, timeliness, granularity, and (if patterns ran) accuracy.
- **Per-object dimension bars** — see exactly which dimension drags an object down.
- **Fields needing attention** — fields scoring under 70, with the specific issues (low completeness, mixed types, all-identical values, high null/empty rate).

**How to use it:** start at the radar to spot the weakest dimension, then drill into per-object bars and the "needs attention" list to find the exact fields to fix.

---

## Tab 4 — PII Detection 👔

What sensitive data exists and how exposed you are.

- **PII summary** — total PII fields and high-risk count.
- **Type badges** — counts by category (email, phone, SSN, credit card, IP, name, address, …).
- **High-risk table** — fields detected with ≥ 0.8 confidence.
- **Per-object detection tables** — every detected field with confidence; values are **masked** by default.
- **Compliance read** — exposure is also summarized as a ratio-based risk on the Overview banner; the "mask before sharing" list flags the most sensitive categories (SSN/payment/passport/DOB).

**How to use it:** before sharing or exporting data, clear the high-risk/must-mask list. Keep masking on for anything that leaves your team. *(Heuristic guidance — not legal advice.)*

---

## Tab 5 — Field Explorer 🔬

The workhorse tab: every field, fully searchable and sortable.

Columns: object, field path, coverage %, null/empty %, type distribution (multi-type badge), distinct count, cardinality, example values, and a PII badge where relevant.

- **Object filter** — narrow to one or more collections/tables.
- **Distinct modal** — click a distinct count to see the value distribution.
- **CSV export** — pull the whole field inventory into a spreadsheet.

**How to use it:** this is your day-to-day reference. Sort by coverage to find sparse fields; sort by distinct count to find constants or near-unique noise; search a field name to see it across all objects.

---

## Tab 6 — Coverage 🔬

A field × object **heat map** colored by coverage % (green 90%+ → red 0–25%).

**How to use it:** spot at a glance which fields are universally present (good join/identity candidates) and which are object-specific or sparse. A column of red usually means an optional or broken upstream field.

---

## Tab 7 — Distributions (+ Statistics) 🔬

**Value Distributions** — for low-cardinality fields, bar charts of the top values with counts and percentages, grouped by array ancestry.

**Statistics** (sub-tab here) —
- **Numeric fields:** min, max, mean, median, standard deviation, and a distribution shape.
- **Temporal fields:** min/max date, span in days, null count, and future-dated count (an anomaly signal).

**How to use it:** validate that categorical fields contain the expected values (and catch typos/dupes), and sanity-check numeric ranges and date spans. A non-zero "future count" on a timestamp is usually a data bug.

---

## Tab 8 — Patterns 🔬

Value-shape detection — no domain vocabulary, just structure.

- **Identifier-shaped fields** — UUIDs, integer IDs, slugs, prefixed codes, hashes.
- **Per-object pattern conformance** — the dominant format per field, its conformance %, other matched formats, and sample values.

**How to use it:** confirm that ID fields are consistently formatted, find candidate keys, and spot fields that *mostly* follow a format but have outliers (low conformance %).

---

## Tab 9 — Type Warnings 🔬

Fields where the same path holds **more than one type** (e.g. `string: 980, int: 20`).

**How to use it:** these are the top cause of downstream parsing/join failures. Each one is a concrete fix — enforce a single type upstream or add a validation rule. Mixed types also lower the DQI consistency dimension and the Overview health score.

---

## Tab 10 — Relationships 🔬

How objects relate.

- **ER-style diagram** — objects as boxes with inferred keys; edges carry confidence (solid = strong, dashed = weak).
- **Mermaid source** — copy/paste into mermaid.live for an editable diagram.
- **Detected relationships table** — source → target, type, confidence, and the evidence behind it.

**How to use it:** understand the data model before writing joins or designing a warehouse schema; the evidence column tells you *why* a relationship was inferred.

---

## Tab 11 — Cross-Object 🔬

Join and key intelligence across objects (this tab also covers the former Cross-Object/Similar-Fields content).

- **Primary / composite keys** — per object, with coverage, distinct ratio, and rationale.
- **Cross-object join candidates** — scored by value overlap, type compatibility, and name similarity (value-confirmed where possible).
- **Nested relationships** — parent→child structures within an object.
- **Similar / duplicate fields** — fields with overlapping value sets (potential redundancy or join keys), plus **functional-dependency hints** (fields always null together).

**How to use it:** pick join keys with confidence, find redundant columns to consolidate, and design denormalization based on the nested structures.

---

## Report layout

| Chapter | Tabs | Business view |
|---|---|---|
| **Verdict** — state and what to do | Overview · Action Plan · AI Review · How scores work | all |
| **Health** — can I trust it | Data Quality · Trends & Drift · Expected Schema · PII Detection · Type Warnings | all but Type Warnings |
| **Shape** — what's in it | Insights · Coverage | Insights |
| **Structure** — how it connects | Field Explorer · Relationships · Cross-Object | hidden |
| **Fingerprint** — value-level detail | Distributions · Patterns | hidden |

Switch views with **Business / Technical** in the header; the Business view keeps the decision-level tabs only.

## Verdict → AI Review 👥

Shown with `--ai`. Sections (Recommendations, Quality assessment, Key & domain fields, …) start **collapsed**, each
with its finding count, severity counts and the first titles as a preview; **Expand all** opens every section,
**Collapse all** closes everything. Inside, the review is shown as scannable finding cards: a title, a one-line gist, key numbers as
coloured chips and fields as chips, with the full reasoning under **Details** (Expand all / Collapse all at the
top). Recommendations are sorted by severity and also merged into the Action Plan (source: AI). The banner shows
the provider and the model used (`auto` unless configured).

## Verdict → Action Plan 👥

Every finding of the run turned into one action, highest priority first. Each card has:
**evidence** (the numbers and the rule that fired), **why it matters**, the affected fields, a **copy-ready
fix** (SQL / config), a severity, an effort estimate and its **source** (Drift, Expected schema, Privacy,
Integrity, Quality, AI, Chat). Related findings are merged (a rename explains "required field missing"; five
`season`-like fields with the same int/string mix become one fix). Filter by severity or source, tick items done
(kept in your browser), and export the plan as CSV, Markdown or JSON.

Priority = severity (high 3 · medium 2 · low 1) × 10 + breadth (share of rows/fields affected, 0–10).

## Verdict → How scores work 👥

This run's health score step by step (DQI − each penalty), the DQI of every object and dimension with its weight
(dimensions that couldn't be scored show `n/a` and why), and the full glossary. Every ⓘ in the report shows the
short version on hover. The same text is in [METRICS.md](METRICS.md) and `datalens glossary <term>`.

## Health → Expected Schema 👥

Shown when you pass `--schema`. Conformance % per object, and every check (required, type, format, enum, range,
pattern, undeclared fields) with expected vs observed.

## Tab 12 — Trends & Drift 👥

What changed versus the reference run — the previous run, a fixed baseline, or the learned rolling range
(see [Usage → Drift & history](USAGE.md#drift--history)).

- **Drift report** — breaches, warnings and info with a filter. Each finding says *where* (object.field), *what
  changed* in plain language with the numbers, and the **rule that fired**: its threshold, its scope (field /
  object / dataset / built-in / learned band) and, for the rolling baseline, the band and how many runs it was
  learned from. Notes explain anything skipped (e.g. objects too small to judge).
- **Timeline** — health, DQI and each object's row count across saved runs (sparkline, earlier range, this run),
  plus **Δ 1 day / Δ 7 days / Δ 1 month** columns: the change versus the newest run at least that long before this
  one (by `--run-date`). Only windows your history covers are shown; hover a cell for the run and value compared.
- **Field-level detail** — new/removed fields as Field-Explorer tables, type changes and coverage shifts with
  before/after value distributions, an object filter and **Export Drift CSV**.

**How to use it:** read the breaches top-down — structural and volume changes come first, derived scores last.
The same findings are in `*-datalens-drift-report.json` and in the Action Plan with fixes.

---

## Recommended workflows

**Onboarding a dataset (5 min)**
1. Overview → read the verdict and Top 3.
2. Field Explorer → sort by coverage, skim examples.
3. Relationships / Cross-Object → learn the model.

**Pre-warehouse / pre-ingest gate**
1. Overview → Fitness-for-Use ("Ready for reporting"?).
2. Type Warnings → resolve mixed types.
3. Action Plan → clear high-severity items.

**Governance / sharing review**
1. PII Detection → clear the high-risk/must-mask list.
2. Keep masking on; confirm the Compliance risk is acceptable.

**Ongoing monitoring**
1. Schedule runs with `--compare-to rolling --fail-on fail` (see [CI/CD](USAGE.md#cicd--gates-exit-codes-notifications)).
2. Watch Trends & Drift; work the Action Plan; `datalens serve` to investigate.

---

## How the scores are computed

Every score is deterministic and explained in the report itself (hover ⓘ, or **Verdict → How scores work**) and
in [METRICS.md](METRICS.md), which is generated from the same constants the code uses:

- **DQI** — weighted mean of completeness (0.30), consistency (0.25), uniqueness (0.20), validity (0.25),
  timeliness (0.10), granularity (0.10) and accuracy (0.15), over the dimensions that could be scored, per object;
  the overall DQI is the mean over objects.
- **Health** — DQI minus penalties for high-risk PII, drift, expected-schema failures and mixed types; a breach
  caps the status at "attention".
- **Compliance exposure** — share of sensitivity-weighted PII fields, with a floor for confirmed direct identifiers.
- **Fitness-for-Use** — per-object readiness gates on DQI, completeness, consistency, PII and drift.

Enabling AI never changes a score; it only adds labelled recommendations.
