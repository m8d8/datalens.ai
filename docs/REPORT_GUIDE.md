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

## Tab 12 — Trends & Drift 👥

What changed since a previous run (requires `--detect-drift` or `--compare-to`; see [Usage Guide](USAGE.md#schema-drift--history)).

- **Drift severity** — none / low / medium / high (high = breaking changes like removed fields or type changes).
- **New / Removed Objects**.
- **New / Removed Fields** — shown as **Field-Explorer-style tables** with coverage, types, distinct count, sample values, and an inline value distribution. Added fields are sourced from the current run; removed fields from the previous run (so you can still see what the removed data looked like).
- **Type Changes** — was → now, with **before/after value distributions** side by side.
- **Coverage Shifts** — was → now with the point delta (▲/▼), plus **before/after distributions**.
- **Cardinality Changes**.
- **Object filter** — one dropdown filters every drift table by object/collection.
- **Export Drift CSV** — download all drift changes (respecting the object filter) as a single CSV with a *Change Type* column — ready to hand to a content producer or upstream owner.
- **Empty state** — on a first run, it explains that this run becomes your baseline.

**How to use it:** make this part of monitoring. A removed field or a type change is a breaking change for consumers; a coverage drop often signals an upstream pipeline problem. Filter to the affected collection, eyeball the before/after distributions to see *how* values changed, then **Export Drift CSV** to share the exact changes with whoever owns the feed. The drift severity also feeds the Overview health verdict.

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
1. Schedule runs with `--detect-drift`.
2. Watch Trends & Drift; alert on `high` severity.

---

## How the scores are computed

- **DQI** is a weighted average of per-dimension scores (completeness, consistency, uniqueness, validity, timeliness, granularity, accuracy), averaged across objects. See the Data Quality tab for per-object weights and details.
- **Health verdict** starts from the overall DQI, then subtracts penalties for high-risk PII, schema drift, and mixed-type fields. Breaking drift caps the verdict below "Healthy". Drivers are listed in the banner so the number is never a black box.
- **Compliance exposure** is *ratio-based*: the share of fields that are sensitive, weighted by category sensitivity (gov-ID/payment > contact info > name) — so it's fair across dataset sizes.
- **Fitness-for-Use** combines DQI, completeness, type consistency, PII presence, and drift into per-object readiness badges.

All scores are deterministic and computed without AI; enabling an AI provider only adds labeled narrative on top.
