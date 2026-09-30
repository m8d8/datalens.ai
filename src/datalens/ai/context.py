"""
Build a compact analysis context for AI providers from schema + analytics.
"""

from __future__ import annotations

from typing import Any


def build_analysis_context(
    schema_json: dict[str, Any],
    *,
    patterns: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    joins: dict[str, Any] | None = None,
    relationships: dict[str, Any] | None = None,
    pii_summary: dict[str, Any] | None = None,
    insights: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    drift: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate deterministic findings for the AI prompt."""
    return {
        "drift": drift or {},
        "schema": schema_json,
        "patterns": patterns or {},
        "quality": quality or {},
        "joins": joins or {},
        "relationships": relationships or {},
        "pii_summary": pii_summary or {},
        "insights": insights or {},
        "decision": decision or {},
    }


def summarize_schema_for_prompt(objects: list[dict[str, Any]], *, max_fields: int = 25) -> str:
    """Create a concise text summary of objects and fields."""
    lines: list[str] = []
    for obj in objects:
        obj_name = obj.get("object", "Unknown")
        sampled = obj.get("sampled", 0)
        fields = obj.get("fields", [])
        total = obj.get("total_rows")
        rows = f"{total} rows, " if total is not None else ""
        lines.append(f"\n## {obj_name} ({rows}{sampled} records sampled, {len(fields)} fields)")
        for field in fields[:max_fields]:
            path = field.get("path", "")
            types = ", ".join(field.get("types", {}).keys())
            present = field.get("presence_count", 0)
            present_pct = present / max(sampled, 1) * 100
            filled_pct = max(0, present - field.get("null_empty_count", 0)) / max(sampled, 1) * 100
            distinct = field.get("distinct_count_in_sample", "?")
            if field.get("distinct_is_exact") is False:
                distinct = f">={distinct}"
            masked = " (PII, values masked)" if field.get("masked") else ""
            lines.append(
                f"- {path}: types=[{types}], key present={present_pct:.0f}%, "
                f"non-empty={filled_pct:.0f}%, distinct={distinct}{masked}"
            )
        if len(fields) > max_fields:
            lines.append(f"- ... and {len(fields) - max_fields} more fields")
    return "\n".join(lines)


def summarize_analytics_for_prompt(ctx: dict[str, Any]) -> str:
    """Summarize patterns, joins, quality, and PII for the prompt."""
    parts: list[str] = []

    quality = ctx.get("quality") or {}
    if quality:
        overall = quality.get("overall_dqi") or quality.get("overall", {})
        if isinstance(overall, dict):
            dqi = overall.get("dqi", overall.get("score", "N/A"))
        else:
            dqi = overall
        parts.append(f"Overall DQI: {dqi}")

    pii = ctx.get("pii_summary") or {}
    if pii:
        high_risk_count = len(pii.get('high_risk_fields', []))
        parts.append(
            f"PII fields: {pii.get('total_pii_fields', 0)}, "
            f"high risk: {high_risk_count}"
        )

    patterns = ctx.get("patterns") or {}
    if patterns:
        by_object = patterns.get("by_object", {}) if isinstance(patterns, dict) else {}
        pattern_counts = patterns.get("pattern_counts", {}) if isinstance(patterns, dict) else {}

        if by_object:
            parts.append("Detected field patterns (sample):")
            count = 0
            for obj_name, field_patterns in by_object.items():
                for fp in field_patterns[:5]:
                    if count >= 15:
                        break
                    path = fp.get("path", "")
                    dominant = fp.get("dominant_pattern", "")
                    if dominant:
                        parts.append(f"  - {obj_name}.{path}: {dominant}")
                        count += 1

        if pattern_counts:
            parts.append(f"Pattern summary: {len(pattern_counts)} distinct patterns detected")

    joins = ctx.get("joins") or {}
    pk = joins.get("primary_keys", []) if isinstance(joins, dict) else []
    fk = joins.get("referential_integrity", []) if isinstance(joins, dict) else []
    if pk:
        parts.append(f"Primary key candidates: {len(pk)}")
        for item in pk[:8]:
            fields = item.get("fields") or [item.get("field", item.get("path", ""))]
            parts.append(
                f"  - {item.get('object', '')}: ({', '.join(fields)}) "
                f"distinct ratio {item.get('distinct_ratio', 0):.0%}"
            )
    if fk:
        parts.append(f"Foreign keys (value-verified, with orphan rate): {len(fk)}")
        for item in fk[:12]:
            parts.append(
                f"  - {item.get('child')} → {item.get('parent')}: "
                f"{item.get('orphan_pct', 0)}% orphaned ({item.get('orphan_distinct', 0)} unknown values)"
            )
    shared = joins.get("shared_domains", []) if isinstance(joins, dict) else []
    if shared:
        parts.append("Fields sharing a value domain but differing per row (role-playing references):")
        for item in shared[:6]:
            parts.append(f"  - {item.get('object')}: {item.get('field_a')} / {item.get('field_b')}")

    drift = ctx.get("drift") or {}
    if drift:
        parts.append("Changes since the previous run (drift):")
        parts.append(_summarize_drift(drift))

    insights = ctx.get("insights") or {}
    recs = insights.get("recommendations", []) if isinstance(insights, dict) else []
    if recs:
        parts.append("Top deterministic recommendations:")
        for r in recs[:5]:
            if isinstance(r, dict):
                parts.append(f"  - [{r.get('severity', 'low')}] {r.get('action', '')}")
            else:
                parts.append(f"  - {r}")

    return "\n".join(parts)


def _summarize_drift(drift: dict[str, Any], limit: int = 25) -> str:
    """Compact text of schema/coverage drift so the model can reason about what changed."""
    lines: list[str] = []
    schema = drift.get("schema") or {}
    for obj in schema.get("added_objects", []):
        lines.append(f"  - object added: {obj}")
    for obj in schema.get("removed_objects", []):
        lines.append(f"  - object removed: {obj}")
    for obj, fields in (schema.get("added_fields") or {}).items():
        lines.append(f"  - {obj}: fields added {', '.join(fields)}")
    for obj, fields in (schema.get("removed_fields") or {}).items():
        lines.append(f"  - {obj}: fields removed {', '.join(fields)}")
    for tc in schema.get("type_changes", []):
        lines.append(
            f"  - {tc.get('object')}.{tc.get('field')}: type {tc.get('old_types')} → {tc.get('new_types')}"
        )
    for cc in (drift.get("coverage") or {}).get("coverage_changes", []):
        lines.append(
            f"  - {cc.get('object')}.{cc.get('field')}: coverage {cc.get('old_coverage', 0):.1f}% → "
            f"{cc.get('new_coverage', 0):.1f}%"
        )
    for item in drift.get("highlights", []):
        lines.append(f"  - {item}")
    if len(lines) > limit:
        lines = lines[:limit] + [f"  - ... and {len(lines) - limit} more changes"]
    return "\n".join(lines) if lines else "  - no changes detected"
