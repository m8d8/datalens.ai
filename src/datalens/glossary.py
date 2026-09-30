"""
Glossary — what every Datalens score and check means, when it is computed and
exactly how.

This is the single source for the ⓘ tooltips in the HTML report, the "How
scores are calculated" panel and ``docs/METRICS.md`` (``datalens glossary
--markdown`` regenerates it; a test fails if the docs fall out of sync).
Numbers are read from the code's own constants, so the explanation can't drift
from the implementation.
"""

from __future__ import annotations

from typing import Any

from datalens.drift.rules import BUILTIN_DEFAULTS
from datalens.profiling.decision import (
    EXPOSURE_SCALE,
    FITNESS_CLEANUP_DQI,
    FITNESS_ML_CONSISTENCY,
    FITNESS_ML_DQI,
    FITNESS_REPORTING_COMPLETENESS,
    FITNESS_REPORTING_DQI,
    HEALTH_ATTENTION_MIN,
    HEALTH_HEALTHY_MIN,
    PII_SENSITIVITY,
)
from datalens.profiling.pii import HIGH_RISK_CONFIDENCE
from datalens.profiling.quality import DIMENSION_WEIGHTS, FIELD_SCORE_WEIGHTS, GRANULARITY_MIN_ROWS

_W = DIMENSION_WEIGHTS


def _pct(w: float) -> str:
    return f"{w:.2f}"


GLOSSARY: dict[str, dict[str, Any]] = {
    "health": {
        "title": "Health score",
        "short": (f"One number for 'can I trust this data today?': DQI minus penalties for PII, drift, "
                  f"expected-schema failures and mixed types. ≥{HEALTH_HEALTHY_MIN:g} healthy, "
                  f"≥{HEALTH_ATTENTION_MIN:g} needs attention, below is at risk."),
        "when": "Every run.",
        "how": [
            "start from the overall DQI (70 if quality could not be scored)",
            "− PII: 3 per high-risk PII field, max 15",
            "− drift vs the reference run: 0 none · 3 info only · 10 warnings · 20 any breach",
            "− expected schema (BYOS): 3 per failed check, max 15",
            "− mixed types: 1.5 per field holding more than one non-null type, max 10",
            f"status: ≥{HEALTH_HEALTHY_MIN:g} 🟢 healthy · ≥{HEALTH_ATTENTION_MIN:g} 🟡 attention · else 🔴 risk; "
            "a drift breach caps the status at 'attention'",
        ],
    },
    "dqi": {
        "title": "Data Quality Index (DQI)",
        "short": ("0–100 weighted mean of the quality dimensions (completeness, consistency, uniqueness, validity, "
                  "timeliness, granularity, accuracy) per object; the overall DQI is the mean over objects."),
        "when": "Every run, per object and overall.",
        "how": [
            "object DQI = Σ(dimension score × weight) / Σ(weights of the dimensions that could be scored)",
            "weights: " + ", ".join(f"{k} {_pct(v)}" for k, v in _W.items()),
            "a dimension that can't be scored (e.g. no date fields → no timeliness) is left out, "
            "and the remaining weights are re-normalised",
            "overall DQI = mean of object DQIs",
        ],
    },
    "completeness": {
        "title": "Completeness",
        "short": "Average share of rows where each field is present and not null/empty.",
        "when": f"Every object. Weight {_pct(_W['completeness'])} in the DQI.",
        "how": [
            "per field: (rows with the key present − null/empty values) / rows sampled × 100",
            "nested fields are measured against their parent: extras.wides counts only rows that have an "
            "`extras` object (optional sub-objects aren't penalised for being optional)",
            "object score: mean over all fields (nested fields included)",
            "fields below 50% are listed as problem fields",
        ],
    },
    "consistency": {
        "title": "Consistency",
        "short": "How reliably each field keeps one type: share of non-null values that have the field's main type.",
        "when": f"Every object. Weight {_pct(_W['consistency'])} in the DQI.",
        "how": [
            "per field: count of the dominant type / all non-null values × 100 (nulls don't count — "
            "they are a completeness matter)",
            "object score: mean over fields",
            "e.g. 950 ints + 50 strings → 95",
        ],
    },
    "uniqueness": {
        "title": "Uniqueness",
        "short": "Does each object have a unique identifier? Score = distinct ratio of its most unique id-like field.",
        "when": (f"Objects with at least one top-level identifier-shaped field (id, *_id, uuid, key, code…). "
                 f"Weight {_pct(_W['uniqueness'])}."),
        "how": [
            "candidates: top-level fields whose name has an identifier token (so 'video' ≠ 'id')",
            "score = 100 if the best candidate is ≥99% distinct, else distinct ratio × 100",
            "references to other objects (customer_id in orders) are expected to repeat and are not penalised",
            "no identifier field → 100 (nothing to check)",
        ],
    },
    "validity": {
        "title": "Validity",
        "short": "Penalises suspicious values: a text field with one repeated value, or fields mostly null/empty.",
        "when": f"Every object. Weight {_pct(_W['validity'])} in the DQI.",
        "how": [
            "per field start at 100",
            "−20 if a text field has exactly one distinct value over >10 rows (placeholder/default?)",
            "−30 if more than half of the present values are null/empty",
            "object score: mean over fields",
        ],
    },
    "timeliness": {
        "title": "Timeliness",
        "short": "How fresh the data is: age of the newest record in date fields (100 = today).",
        "when": f"Objects with date fields (by value type or name). Weight {_pct(_W['timeliness'])}.",
        "how": [
            "age = today − newest date found (ISO dates, tracked across every row read)",
            "score = 100 − 25·log10(age in days + 1): same day ≈100, a week ≈77, a month ≈63, a year ≈36",
            "− 5 per future-dated example, max −40",
            "dates that can't be parsed → neutral 70",
        ],
    },
    "granularity": {
        "title": "Granularity",
        "short": "Share of scalar fields whose cardinality is useful: not constant, and not unique-per-row unless an id.",
        "when": (f"Objects with ≥{GRANULARITY_MIN_ROWS} rows (fewer rows make every field look constant or unique). "
                 f"Weight {_pct(_W['granularity'])}."),
        "how": [
            "constant field (≤1 distinct value) → not healthy",
            "non-identifier field distinct on ≥99% of rows (free text / noise) → not healthy",
            "score = healthy fields / scalar fields × 100",
        ],
    },
    "accuracy": {
        "title": "Accuracy (pattern conformance)",
        "short": "How consistently values follow their field's dominant shape (UUID, email, date, code…).",
        "when": f"Objects where value patterns were detected. Weight {_pct(_W['accuracy'])}.",
        "how": [
            "per field: share of values matching the dominant detected pattern",
            "object score: mean over pattern-bearing fields × 100",
        ],
    },
    "field_score": {
        "title": "Field quality score",
        "short": "Per-field score used in the field explorer.",
        "when": "Every field.",
        "how": [" + ".join(f"{v:g}·{k}" for k, v in FIELD_SCORE_WEIGHTS.items())],
    },
    "coverage": {
        "title": "Coverage",
        "short": "Share of rows where the field exists and holds a non-empty value.",
        "when": "Every field, every run; tracked across runs for drift.",
        "how": [
            "(present − null/empty) / rows sampled × 100",
            "drift: drop/increase in percentage points (pts) or relative % vs the reference; changes within "
            "3 standard errors of sampling noise (√(p(1−p)/n)) are ignored",
        ],
    },
    "row_count": {
        "title": "Row count (volume)",
        "short": "Rows in the object. True count when the whole source was read, otherwise the sample size.",
        "when": "Every run; drift compares it with the reference or the learned band.",
        "how": ["default rule: warn at −10%, fail at −25%; warn at +50%, fail at +200%"],
    },
    "psi": {
        "title": "Distribution shift (PSI)",
        "short": ("Population Stability Index: how much a field's value mix moved. <0.10 stable, "
                  "0.10–0.25 moderate, >0.25 major."),
        "when": "Category-like and numeric fields present in both runs with enough rows (ids, references, dates excluded).",
        "how": [
            "PSI = Σ (new% − old%) · ln(new% / old%) over value bins",
            "categories: one bin per value; numbers: the reference run's deciles (+ below-min / above-max bins)",
            "noise floor: two samples of the same data give PSI ≈ (bins−1)·(1/n₁+1/n₂); shifts below 3× that are "
            "not reported",
            f"default thresholds: warn ≥{BUILTIN_DEFAULTS['distribution']['psi_warn']}, "
            f"fail ≥{BUILTIN_DEFAULTS['distribution']['psi_fail']}",
        ],
    },
    "rolling": {
        "title": "Rolling baseline (learned normal range)",
        "short": ("Each metric learns its own normal range from recent runs: median ± 3 robust sigmas, widened to "
                  "include every non-breached value seen. Alerts only when today falls outside."),
        "when": "--compare-to rolling (or drift.compare_to: rolling), once a metric has ≥3 earlier runs.",
        "how": [
            "M = median of the last N values (default N = 14)",
            "MAD = median(|xᵢ − M|); σ̂ = 1.4826·MAD (robust: one bad run can't inflate it)",
            "σ̂ₑ = max(σ̂, 5%·|M|, sampling noise for percentages, 1 for counts)",
            "band = [min(M − 3σ̂ₑ, min seen·0.95), max(M + 3σ̂ₑ, max seen·1.05)]",
            "outside the band → warn; also |x − M| > 3σ̂ₑ → fail",
            "runs that breached are left out of later baselines (a bad day can't become 'normal')",
            "fewer than 3 earlier values → cold start: the fixed rules apply and the report says so",
        ],
    },
    "orphan_pct": {
        "title": "Orphan rate (referential integrity)",
        "short": "Share of a foreign key's values that point to a row that doesn't exist in the parent object.",
        "when": "Fields whose values mostly (≥50%) resolve to another object's unique key.",
        "how": [
            "orphans = child occurrences whose value is not among the parent key's values",
            "orphan % = orphans / child occurrences × 100 (exact, from value hashes kept in memory only)",
        ],
    },
    "exposure": {
        "title": "PII exposure score & risk",
        "short": ("Share of fields holding PII, weighted by sensitivity. A confirmed direct identifier raises the "
                  "risk floor (email/phone → at least medium; SSN/card/passport → high)."),
        "when": "Every run.",
        "how": [
            "sensitivity: " + ", ".join(f"{k} {v}" for k, v in PII_SENSITIVITY.items()),
            f"exposure = min(100, Σ(sensitivity × PII fields) / all fields × {EXPOSURE_SCALE:g})",
            "risk: 0 none · <25 low · <60 medium · else high, then the direct-identifier floor",
            f"high-risk = detection confidence ≥ {HIGH_RISK_CONFIDENCE:.0%} (value match, strong field name, or "
            "pii_force); these are masked in every output",
        ],
    },
    "fitness": {
        "title": "Fitness for use",
        "short": "Per-object readiness badges for reporting and ML, derived from DQI, completeness, consistency, PII and drift.",
        "when": "Every object.",
        "how": [
            f"Ready for reporting: DQI ≥ {FITNESS_REPORTING_DQI:g} and completeness ≥ {FITNESS_REPORTING_COMPLETENESS:g}",
            f"Ready for ML/AI: DQI ≥ {FITNESS_ML_DQI:g}, consistency ≥ {FITNESS_ML_CONSISTENCY:g}, no high-risk PII",
            f"Needs cleanup: DQI < {FITNESS_CLEANUP_DQI:g} or ≥5 problem fields",
            "Recently changed: this object has drift vs the reference run",
        ],
    },
    "conformance": {
        "title": "Expected-schema conformance (BYOS)",
        "short": "Share of checks against your expected JSON Schema that pass (required, type, enum, range, pattern…).",
        "when": "When --schema / expected_schema is given.",
        "how": [
            "checks per declared field: required (coverage ≥ x-datalens.min_coverage, default 99%), type, format, "
            "enum, minimum/maximum, pattern",
            "undeclared fields: warn when additionalProperties is false, info otherwise",
            "conformance = passed / judged checks × 100 (info checks aren't judged)",
        ],
    },
}


def tip(key: str) -> str:
    """Short tooltip text for a glossary key ('' if unknown)."""
    entry = GLOSSARY.get(key)
    return entry["short"] if entry else ""


def to_markdown() -> str:
    """docs/METRICS.md content."""
    lines = [
        "# How Datalens scores your data",
        "",
        "Every number in the report is explained here: what it means, when it is computed, and exactly how.",
        "This file is generated from `src/datalens/glossary.py` (`datalens glossary --markdown > docs/METRICS.md`),",
        "which reads the same constants the code uses — so it always matches the implementation.",
        "",
    ]
    for entry in GLOSSARY.values():
        lines += [f"## {entry['title']}", "", entry["short"], "", f"**When:** {entry['when']}", "", "**How:**", ""]
        lines += [f"- {step}" for step in entry["how"]]
        lines.append("")
    lines += [
        "## Default drift rules",
        "",
        "Override any of these per dataset, object or field (see `docs/USAGE.md` → Drift rules).",
        "",
        "```yaml",
        "drift:",
        "  defaults:",
    ]
    for metric, rule in BUILTIN_DEFAULTS.items():
        lines.append(f"    {metric}: {_yaml_inline(rule)}")
    lines += ["```", ""]
    return "\n".join(lines)


def _yaml_inline(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_yaml_inline(v)}" for k, v in value.items()) + "}"
    return str(value)
