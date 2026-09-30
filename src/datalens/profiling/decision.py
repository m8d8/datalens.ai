"""
Decision Layer (v2) — turn deterministic analytics into audience-facing signals.

This module converts raw profiling output (quality, PII, joins) and optional
schema drift into the decision-support signals the v2 HTML report renders:

  • health_verdict          → the 🟢/🟡/🔴 Executive Summary traffic light
  • compliance_scorecard    → the reframed PII / governance card (ratio-based)
  • fitness_for_use         → per-object "Ready for reporting / ML / cleanup" badges
  • action_plan             → recommendations enriched with business impact + effort
  • functional_dependencies → "always-null-together / value-overlap" hints
  • drift_severity          → feeds the verdict and the alerts banner

CONTRACT
  - Pure & deterministic. No AI, no network, no filesystem, no print.
  - Consumes the *serialized* analytics dicts (the same forms the report gets),
    plus an optional ``history.diff.SchemaDiff``. AI may rephrase outputs later,
    but is never required to produce them.
  - All thresholds are module-level constants so they can later be made
    config-driven without touching call sites.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ─── Tunable thresholds (later: lift into Config) ────────────────────────────

HEALTH_HEALTHY_MIN = 80.0        # health score >= → 🟢
HEALTH_ATTENTION_MIN = 60.0      # health score >= → 🟡 ; below → 🔴

DRIFT_COVERAGE_HIGH_DROP = 25.0  # pts of coverage loss that counts as severe
DRIFT_COVERAGE_MED_SHIFT = 10.0  # pts of any coverage move that counts as notable

FITNESS_REPORTING_DQI = 75.0
FITNESS_REPORTING_COMPLETENESS = 70.0
FITNESS_ML_DQI = 80.0
FITNESS_ML_CONSISTENCY = 90.0
FITNESS_CLEANUP_DQI = 70.0

# PII category → sensitivity weight (drives the compliance exposure score).
PII_SENSITIVITY = {
    "ssn": 3, "credit_card": 3, "passport": 3, "driver_license": 3, "date_of_birth": 3,
    "email": 2, "phone": 2, "ip_address": 2, "address": 2,
    "name": 1,
}

# Exposure scoring (ratio-based): a dataset whose fields are *entirely* made of
# average-sensitivity (=2) PII scores 100. exposure = min(100, density * SCALE)
# where density = weighted_sensitive_fields / total_fields.
EXPOSURE_SCALE = 50.0

# Recommendation category → (impact phrasing, remediation effort).
_IMPACT_LIBRARY: dict[str, tuple[str, str]] = {
    "Completeness":    ("Missing values reduce the share of records usable for reporting, "
                        "segmentation, and outreach.", "low"),
    "Consistency":     ("Mixed types in one field break downstream parsing, joins, and BI "
                        "tools — every consumer must special-case it.", "high"),
    "Uniqueness":      ("Without a reliable unique key, records can be duplicated or "
                        "double-counted in aggregates.", "medium"),
    "Compliance":      ("Unmasked sensitive fields create regulatory and reputational "
                        "exposure if the data is shared or breached.", "medium"),
    "Identifiability": ("Non-global IDs make cross-system joins fragile and slow to build.",
                        "low"),
    "Timeliness":      ("No freshness signal means stale data can silently drive decisions.",
                        "medium"),
    "General":         ("General data-health improvement.", "low"),
}


@runtime_checkable
class _ResultLike(Protocol):
    """Duck-typed view of ``core.AnalysisResult`` — only the attrs we read."""

    schema_json: dict[str, Any]
    quality: dict[str, Any] | None
    pii_summary: dict[str, Any] | None
    joins: dict[str, Any] | None
    insights: dict[str, Any] | None
    statistics: dict[str, Any] | None


def _total_fields(schema_json: dict[str, Any]) -> int:
    return sum(len(o.get("fields", [])) for o in schema_json.get("objects", []))


def _count_multi_type_fields(schema_json: dict[str, Any]) -> int:
    n = 0
    for obj in schema_json.get("objects", []):
        for f in obj.get("fields", []):
            if len([t for t in f.get("types", {}) if t != "null"]) > 1:
                n += 1
    return n


# ─── Drift severity ──────────────────────────────────────────────────────────

def drift_severity(diff: Any | None, drift_report: dict[str, Any] | None = None) -> str:
    """
    Map drift to ``none|low|medium|high``.

    With a drift report (``datalens.drift``): any "fail" finding → high, any
    "warn" → medium, only "info" findings → low. Otherwise the legacy
    ``history.diff.SchemaDiff`` mapping below applies.

    high   — breaking: removed objects/fields, type changes, or a large coverage drop.
    medium — notable: meaningful coverage/cardinality movement.
    low    — additive only (new objects/fields).
    none   — no diff or no drift.
    """
    if drift_report is not None:
        summary = drift_report.get("summary", {})
        if summary.get("fail"):
            return "high"
        if summary.get("warn"):
            return "medium"
        return "low" if summary.get("info") else "none"

    if diff is None or not getattr(diff, "has_drift", False):
        return "none"

    if (
        getattr(diff, "removed_objects", None)
        or getattr(diff, "removed_fields", None)
        or getattr(diff, "type_changes", None)
    ):
        return "high"

    coverage_changes = getattr(diff, "coverage_changes", []) or []

    # A user-configured breach (coverage_thresholds) always counts as at least
    # "high" for a reduction, or "medium" for an increase.
    if any(ch.get("breach") and ch.get("direction") == "decrease" for ch in coverage_changes):
        return "high"

    for ch in coverage_changes:
        drop = ch.get("old_coverage", 0.0) - ch.get("new_coverage", 0.0)
        if drop >= DRIFT_COVERAGE_HIGH_DROP:
            return "high"

    notable_coverage = any(
        abs(ch.get("new_coverage", 0.0) - ch.get("old_coverage", 0.0)) >= DRIFT_COVERAGE_MED_SHIFT
        for ch in coverage_changes
    )
    has_increase_breach = any(
        ch.get("breach") and ch.get("direction") == "increase" for ch in coverage_changes
    )
    if notable_coverage or has_increase_breach or getattr(diff, "cardinality_changes", None):
        return "medium"

    # Only additions remain.
    return "low"


# ─── Health verdict (Executive Summary traffic light) ────────────────────────

def health_verdict(
    schema_json: dict[str, Any],
    quality: dict[str, Any] | None,
    pii_summary: dict[str, Any] | None,
    diff: Any | None = None,
    drift_report: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Composite 0–100 health score + status + the drivers that set it.

    status: ``"healthy"`` (🟢) | ``"attention"`` (🟡) | ``"risk"`` (🔴)
    """
    drivers: list[str] = []

    if quality:
        base = float(quality.get("overall_dqi") or 0.0)
        drivers.append(f"Data Quality Index is {base:.0f}/100.")
    else:
        base = 70.0
        drivers.append("Quality scoring unavailable — using a neutral baseline.")

    score = base

    # PII penalty (up to −15).
    high_pii = len((pii_summary or {}).get("high_risk_fields", []))
    if high_pii:
        pen = min(15.0, 3.0 * high_pii)
        score -= pen
        drivers.append(f"{high_pii} high-risk PII field(s) detected (−{pen:.0f}).")

    # Drift penalty.
    sev = drift_severity(diff, drift_report)
    drift_pen = {"none": 0.0, "low": 3.0, "medium": 10.0, "high": 20.0}[sev]
    if drift_pen:
        score -= drift_pen
        if drift_report is not None:
            summ = drift_report.get("summary", {})
            drivers.append(
                f"Drift vs {_reference_label(drift_report)} is {sev}: {summ.get('fail', 0)} breach(es), "
                f"{summ.get('warn', 0)} warning(s) (−{drift_pen:.0f})."
            )
        else:
            drivers.append(f"Schema drift since last run is {sev} (−{drift_pen:.0f}).")

    # Expected-schema (BYOS) penalty: 3 per failed check, up to −15.
    contract_pen = 0.0
    if contract:
        failed = (contract.get("summary") or {}).get("fail", 0)
        if failed:
            contract_pen = min(15.0, 3.0 * failed)
            score -= contract_pen
            drivers.append(
                f"Expected schema: {failed} check(s) failed, conformance "
                f"{contract.get('conformance_pct', 0):.0f}% (−{contract_pen:.0f})."
            )

    # Type-stability penalty (up to −10).
    multi = _count_multi_type_fields(schema_json)
    if multi:
        pen = min(10.0, 1.5 * multi)
        score -= pen
        drivers.append(f"{multi} mixed-type field(s) (−{pen:.0f}).")

    score = max(0.0, min(100.0, score))

    if score >= HEALTH_HEALTHY_MIN:
        status = "healthy"
    elif score >= HEALTH_ATTENTION_MIN:
        status = "attention"
    else:
        status = "risk"

    # Severe drift can't be "healthy" no matter the score.
    if sev == "high" and status == "healthy":
        status = "attention"
        drivers.append("Capped to 'needs attention' due to breaking changes since the reference run.")

    return {
        "status": status,
        "score": round(score, 1),
        "drivers": drivers,
        "base_dqi": round(base, 1),
        "penalties": {
            "pii": round(min(15.0, 3.0 * high_pii), 1) if high_pii else 0.0,
            "drift": drift_pen,
            "contract": contract_pen,
            "mixed_types": round(min(10.0, 1.5 * multi), 1) if multi else 0.0,
        },
    }


def refresh_drift_driver(decision: dict[str, Any], drift_report: dict[str, Any] | None) -> None:
    """Keep the health driver's drift counts in step with the final drift report."""
    if not drift_report:
        return
    drivers = decision.get("health_verdict", {}).get("drivers", [])
    summ = drift_report.get("summary", {})
    for i, text in enumerate(drivers):
        if text.startswith("Drift vs "):
            head, _, tail = text.partition(": ")
            penalty = tail[tail.rfind("("):] if "(" in tail else ""
            drivers[i] = (f"{head}: {summ.get('fail', 0)} breach(es), {summ.get('warn', 0)} warning(s) "
                          f"{penalty}").strip()


def _reference_label(drift_report: dict[str, Any]) -> str:
    mode = str(drift_report.get("mode", "previous"))
    tag = (drift_report.get("reference") or {}).get("tag")
    if mode.startswith("rolling"):
        return "the rolling baseline"
    if mode.startswith("baseline"):
        return f"baseline '{tag}'" if tag else "the baseline"
    return f"previous run '{tag}'" if tag else "the previous run"


# ─── Compliance / PII scorecard (ratio-based) ────────────────────────────────

def compliance_scorecard(
    pii_summary: dict[str, Any] | None,
    total_fields: int,
) -> dict[str, Any]:
    """
    Reframe PII detections as a governance-facing risk card.

    Scoring is *ratio-based*, not count-based, so large and small datasets
    compare fairly: exposure rises with the **share** of fields that are
    sensitive, weighted by category sensitivity.

    Returns exposure_score (0–100), a risk badge, the PII share, per-category
    counts, the fields that must be masked before sharing, and a readiness
    checklist. Heuristic only — not legal advice (labeled as such).
    """
    by_type: dict[str, int] = dict((pii_summary or {}).get("by_type", {}))
    high_risk: list[dict[str, Any]] = list((pii_summary or {}).get("high_risk_fields", []))
    total_pii = int((pii_summary or {}).get("total_pii_fields", 0))
    denom = max(1, total_fields)

    pii_field_ratio = min(1.0, total_pii / denom)

    # Density of *sensitivity-weighted* PII relative to all fields.
    weighted = sum(PII_SENSITIVITY.get(cat, 1) * cnt for cat, cnt in by_type.items())
    density = weighted / denom
    exposure_score = min(100.0, density * EXPOSURE_SCALE)

    avg_sensitivity = (weighted / total_pii) if total_pii else 0.0

    if exposure_score == 0:
        risk = "none"
    elif exposure_score < 25:
        risk = "low"
    elif exposure_score < 60:
        risk = "medium"
    else:
        risk = "high"
    risk_reason = f"Exposure score {exposure_score:.1f} (share of sensitivity-weighted PII fields)."

    # Common-sense floor: a single confirmed direct identifier matters no matter
    # how many other fields the dataset has, so the ratio alone can't call it "low".
    order = ["none", "low", "medium", "high"]
    for f in high_risk:
        weight = PII_SENSITIVITY.get(f.get("type", ""), 1)
        floor = "high" if weight >= 3 else "medium" if weight >= 2 else "low"
        if order.index(floor) > order.index(risk):
            risk = floor
            risk_reason = (
                f"Raised to {floor}: `{f.get('object')}.{f.get('field')}` holds {f.get('type')} "
                f"values (confidence {f.get('confidence', 0):.0%})."
            )

    # Every high-confidence detection must be masked before the data is shared.
    must_mask = list(high_risk)
    masked = {(m.get("object"), m.get("field")) for m in (pii_summary or {}).get("masked_fields", [])}
    unmasked = [f for f in must_mask if (f.get("object"), f.get("field")) not in masked]

    if not must_mask:
        mask_status, mask_note = "pass", "No high-confidence PII detected."
    elif not unmasked:
        mask_status = "pass"
        mask_note = (f"{len(must_mask)} field(s) masked in this report. The source data still "
                     f"contains them — mask or tokenize before sharing raw extracts.")
    else:
        mask_status = "fail"
        mask_note = (f"{len(unmasked)} field(s) shown unmasked: "
                     + ", ".join(f"{f.get('object')}.{f.get('field')}" for f in unmasked[:5])
                     + ". Re-run with --mask-pii.")

    checklist = [
        {
            "name": "Sensitive identifiers masked",
            "status": mask_status,
            "note": mask_note,
        },
        {
            "name": "PII inventory documented",
            "status": "pass" if not total_pii else "warn",
            "note": ("No PII detected to inventory."
                     if not total_pii else
                     "Document purpose and lawful basis for each PII field."),
        },
        {
            "name": "Access restricted",
            "status": "pass" if not total_pii else "warn",
            "note": ("No restriction needed."
                     if not total_pii else
                     "Restrict raw access; expose masked views to broad audiences."),
        },
        {
            "name": "Retention policy defined",
            "status": "pass" if not total_pii else "warn",
            "note": ("Not applicable."
                     if not total_pii else
                     "Define and enforce a retention/expiry policy for PII."),
        },
    ]

    return {
        "exposure_score": round(exposure_score, 1),
        "risk": risk,
        "risk_reason": risk_reason,
        "pii_field_ratio": round(pii_field_ratio, 3),
        "avg_sensitivity": round(avg_sensitivity, 2),
        "total_pii_fields": total_pii,
        "total_fields": total_fields,
        "by_category": by_type,
        "must_mask": must_mask,
        "checklist": checklist,
        "disclaimer": "Heuristic guidance for prioritization — not legal/compliance advice.",
    }


# ─── Fitness for use (per-object badges) ─────────────────────────────────────

def _high_pii_objects(pii_summary: dict[str, Any] | None) -> set[str]:
    return {f.get("object") for f in (pii_summary or {}).get("high_risk_fields", [])}


def _object_changed(diff: Any, name: str) -> bool:
    """True when this specific object has schema or coverage drift (not just the dataset)."""
    if name in getattr(diff, "added_objects", []) or name in getattr(diff, "removed_objects", []):
        return True
    if getattr(diff, "added_fields", {}).get(name) or getattr(diff, "removed_fields", {}).get(name):
        return True
    changes = list(getattr(diff, "type_changes", [])) + list(getattr(diff, "coverage_changes", []))
    return any(c.get("object") == name for c in changes)


def fitness_for_use(
    obj_quality: dict[str, Any],
    pii_summary: dict[str, Any] | None,
    diff: Any | None = None,
) -> list[dict[str, str]]:
    """
    Per-object 'fitness' badges derived from quality dimensions + PII + drift.

    ``obj_quality`` is one entry of ``quality["objects"]``:
      ``{"object", "dqi", "dimensions": {"completeness": {"score"}, ...}, "problem_fields": [...]}``
    """
    name = obj_quality.get("object", "")
    dqi = float(obj_quality.get("dqi", 0.0))
    dims = obj_quality.get("dimensions", {})
    completeness = float(dims.get("completeness", {}).get("score", 0.0))
    consistency = float(dims.get("consistency", {}).get("score", 0.0))
    problem_fields = len(obj_quality.get("problem_fields", []))
    has_high_pii = name in _high_pii_objects(pii_summary)

    badges: list[dict[str, str]] = []

    if dqi >= FITNESS_REPORTING_DQI and completeness >= FITNESS_REPORTING_COMPLETENESS:
        badges.append({"label": "Ready for reporting", "status": "pass"})
    else:
        badges.append({"label": "Reporting: review first", "status": "warn"})

    if dqi >= FITNESS_ML_DQI and consistency >= FITNESS_ML_CONSISTENCY and not has_high_pii:
        badges.append({"label": "Ready for ML/AI", "status": "pass"})
    elif has_high_pii:
        badges.append({"label": "ML/AI: mask PII first", "status": "warn"})
    else:
        badges.append({"label": "ML/AI: not ready", "status": "warn"})

    if dqi < FITNESS_CLEANUP_DQI or problem_fields >= 5:
        badges.append({"label": "Needs cleanup", "status": "fail"})

    if diff is not None and _object_changed(diff, name):
        badges.append({"label": "Recently changed", "status": "warn"})

    return badges


# ─── Business impact + effort on recommendations ─────────────────────────────

def business_impact(recommendation: dict[str, Any]) -> dict[str, str]:
    """
    Enrich one insights recommendation (``{category, severity, action}``) with a
    plain-language business impact and an effort estimate.
    """
    category = recommendation.get("category", "General")
    impact_text, effort = _IMPACT_LIBRARY.get(category, _IMPACT_LIBRARY["General"])
    # A high-severity item is rarely low-effort to ignore safely.
    if recommendation.get("severity") == "high" and effort == "low":
        effort = "medium"
    return {"impact_text": impact_text, "effort": effort}


def action_plan(insights: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Build the sorted, business-facing Action Plan from ``insights.recommendations``.
    Highest severity first; ties broken by lower effort (quick wins up).
    """
    recs = list((insights or {}).get("recommendations", []))
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    eff_rank = {"low": 0, "medium": 1, "high": 2}

    enriched = [{**r, **business_impact(r)} for r in recs]
    enriched.sort(key=lambda x: (sev_rank.get(x.get("severity"), 3), eff_rank.get(x["effort"], 3)))
    return enriched


# ─── Functional-dependency / correlation hints ───────────────────────────────

def functional_dependencies(
    joins: dict[str, Any] | None,
    schema_json: dict[str, Any],
    *,
    max_hints: int = 50,
) -> list[dict[str, Any]]:
    """
    Surface 'likely related' field hints:
      • value-overlap / duplicate fields already computed in ``joins``
      • fields within an object that are *always present and absent together*
        (co-null signature) — a classic functional-dependency tell.
    """
    hints: list[dict[str, Any]] = []

    # 1) Reuse join intelligence (intra-object duplicates + cross value overlaps).
    for d in (joins or {}).get("intra_duplicates", []):
        hints.append({
            "fields": [f"{d['object']}.{d['field_a']}", f"{d['object']}.{d['field_b']}"],
            "kind": d.get("kind", "value_duplicate"),
            "confidence": d.get("confidence", 0.0),
            "evidence": d.get("evidence", []),
        })
    for c in (joins or {}).get("value_overlap", []):
        hints.append({
            "fields": [c["left"], c["right"]],
            "kind": "value_overlap",
            "confidence": c.get("confidence", 0.0),
            "evidence": c.get("evidence", []),
        })

    # 2) Co-null signature within each object.
    for obj in schema_json.get("objects", []):
        sampled = obj.get("sampled", 0) or 0
        if sampled < 20:  # too small to trust a co-occurrence signal
            continue
        groups: dict[tuple[int, int], list[str]] = {}
        for f in obj.get("fields", []):
            if {"object", "array"} & set(f.get("types", {}).keys()):
                continue
            presence = f.get("presence_count", 0)
            nulls = f.get("null_empty_count", 0)
            # only interesting when partially present (not always present, not absent)
            if 0 < presence < sampled or nulls > 0:
                groups.setdefault((presence, nulls), []).append(f.get("path", ""))
        for (presence, nulls), paths in groups.items():
            if len(paths) >= 2:
                coverage = (max(0, presence - nulls) / sampled) if sampled else 0.0
                hints.append({
                    "fields": [f"{obj.get('object')}.{p}" for p in paths[:6]],
                    "kind": "co_null",
                    "confidence": round(1.0 - abs(0.5 - coverage), 3),  # peaks for partial fields
                    "evidence": [f"Identical presence/null signature across {len(paths)} fields "
                                 f"({coverage:.0%} coverage)"],
                })

    hints.sort(key=lambda h: h.get("confidence", 0.0), reverse=True)
    return hints[:max_hints]


# ─── Top-level orchestrator ──────────────────────────────────────────────────

def build_decision_layer(result: _ResultLike, diff: Any | None = None) -> dict[str, Any]:
    """
    Assemble the full decision layer from a (pre-computed) ``AnalysisResult``
    and an optional ``SchemaDiff``. This is what ``core.analyze()`` passes to
    the report.
    """
    schema_json = result.schema_json
    quality = result.quality
    pii_summary = result.pii_summary
    joins = result.joins
    insights = result.insights

    drift_report = getattr(result, "drift_report", None)
    verdict = health_verdict(schema_json, quality, pii_summary, diff, drift_report,
                             getattr(result, "contract", None))
    plan = action_plan(insights)

    fitness = {
        obj.get("object"): fitness_for_use(obj, pii_summary, diff)
        for obj in (quality or {}).get("objects", [])
    }

    decision = {
        "drift_severity": drift_severity(diff, drift_report),
        "health_verdict": verdict,
        "compliance_scorecard": compliance_scorecard(pii_summary, _total_fields(schema_json)),
        "fitness_for_use": fitness,
        "action_plan": plan,
        "top_actions": plan[:3],
        "functional_dependencies": functional_dependencies(joins, schema_json),
    }
    refresh_next_steps(result, decision)
    return decision


def refresh_next_steps(result: Any, decision: dict[str, Any]) -> None:
    """(Re)build the specific next-step actions and the Top 3 from every finding of the run."""
    from datalens.profiling.next_steps import build_next_steps

    steps = build_next_steps(result, decision)
    decision["next_steps"] = steps
    if steps:
        decision["top_actions"] = [
            {"severity": a["severity"], "category": a["category"], "action": a["title"],
             "impact_text": a.get("impact", ""), "effort": a.get("effort", "medium"), "id": a["id"],
             "source": a["source"]}
            for a in steps[:3]
        ]
