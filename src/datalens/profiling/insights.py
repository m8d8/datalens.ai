"""
Insights — deterministic Data Story, SWOT, Content Universe, recommendations,
and AI-readiness checks.

This module never calls AI. It only summarizes deterministic findings from
other profiling modules into narrative + actions. AI providers may layer on
top via the optional AI section.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


# ─── Locale & Geographic Dimensions ──────────────────────────────────────────

_ISO_LOCALE_RE = re.compile(r'^[a-z]{2}(?:[_-][A-Z]{2})?$')  # en, en_US, en-US

def build_locale_dimensions(
    schema_json: dict[str, Any],
    patterns_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Detect locale and geographic dimensions in the data.
    
    Returns:
        locale_keyed_fields: Fields that are objects with ISO locale keys (e.g., title.en, title.fr)
        locale_fields: Scalar fields containing locale codes
        country_fields: Scalar fields containing country codes
        currency_fields: Scalar fields containing currency codes
        locales_found: Set of distinct locales detected
        countries_found: Set of distinct country codes detected
        currencies_found: Set of distinct currency codes detected
    """
    locale_keyed_fields: list[dict[str, Any]] = []
    locale_fields: list[dict[str, Any]] = []
    country_fields: list[dict[str, Any]] = []
    currency_fields: list[dict[str, Any]] = []
    locales_found: Counter[str] = Counter()
    countries_found: Counter[str] = Counter()
    currencies_found: Counter[str] = Counter()
    
    # Extract from patterns_data
    if patterns_data:
        for field_info in patterns_data.get("fields", []):
            matches = field_info.get("matches", [])
            obj_name = field_info.get("object", "")
            path = field_info.get("path", "")
            
            for m in matches:
                pattern = m.get("pattern", "")
                samples = m.get("sample_values", [])
                conformance = m.get("conformance", 0)
                
                if pattern == "locale_code" and conformance > 0.5:
                    locale_fields.append({
                        "object": obj_name,
                        "path": path,
                        "conformance": conformance,
                        "samples": samples[:5],
                    })
                    for v in samples:
                        if _ISO_LOCALE_RE.match(str(v)):
                            locales_found[str(v).lower().replace('-', '_')] += 1
                
                elif pattern == "country_code_iso2" and conformance > 0.5:
                    country_fields.append({
                        "object": obj_name,
                        "path": path,
                        "conformance": conformance,
                        "samples": samples[:5],
                    })
                    for v in samples:
                        if len(str(v)) == 2:
                            countries_found[str(v).upper()] += 1
                
                elif pattern == "currency_code" and conformance > 0.5:
                    currency_fields.append({
                        "object": obj_name,
                        "path": path,
                        "conformance": conformance,
                        "samples": samples[:5],
                    })
                    for v in samples:
                        if len(str(v)) == 3:
                            currencies_found[str(v).upper()] += 1
    
    # Detect locale-keyed nested objects (e.g., title.en, title.fr)
    # Look for parent fields that have children with ISO locale leaf names
    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "")
        fields = obj.get("fields", [])
        
        # Group fields by parent path
        parent_children: dict[str, list[str]] = {}
        for f in fields:
            path = f.get("path", "")
            if "." in path:
                parent = ".".join(path.split(".")[:-1])
                leaf = path.split(".")[-1]
                if parent not in parent_children:
                    parent_children[parent] = []
                parent_children[parent].append(leaf)
        
        # Check if children look like locales
        for parent, children in parent_children.items():
            locale_children = [c for c in children if _ISO_LOCALE_RE.match(c)]
            if len(locale_children) >= 2:  # At least 2 locale keys
                locale_keyed_fields.append({
                    "object": obj_name,
                    "path": parent,
                    "locales": sorted(set(locale_children)),
                    "locale_count": len(locale_children),
                })
                for loc in locale_children:
                    locales_found[loc.lower().replace('-', '_')] += 1
    
    return {
        "locale_keyed_fields": locale_keyed_fields,
        "locale_fields": locale_fields,
        "country_fields": country_fields,
        "currency_fields": currency_fields,
        "locales_found": locales_found.most_common(20),
        "countries_found": countries_found.most_common(30),
        "currencies_found": currencies_found.most_common(10),
        "has_localization": bool(locale_keyed_fields or locale_fields),
        "has_geo": bool(country_fields),
        "has_currency": bool(currency_fields),
    }


# ─── Content Universe ────────────────────────────────────────────────────────

def build_content_universe(schema_json: dict[str, Any]) -> dict[str, Any]:
    """
    Detect record-type segments suitable for a donut visualization.

    Strategy: find a low-cardinality string field commonly named like a
    type/category and present in most objects (`type`, `__type`, `kind`,
    `category`, `recordType`). For each detected object, count records per
    type value (from value_counts when available, else from sampled).

    Gracefully returns empty segments if no obvious type field is found.
    """
    type_keys = {"type", "__type", "kind", "category", "recordtype", "doctype"}
    segments: Counter[str] = Counter()
    found_field: str | None = None

    for obj in schema_json.get("objects", []):
        name = obj.get("object", "")
        for f in obj.get("fields", []):
            path = f.get("path", "")
            leaf = path.split(".")[-1].lower()
            if leaf not in type_keys:
                continue
            vc = f.get("value_counts") or {}
            if isinstance(vc, list):
                pairs = [(p[0], p[1]) for p in vc if isinstance(p, (list, tuple)) and len(p) == 2]
            elif isinstance(vc, dict):
                pairs = list(vc.items())
            else:
                pairs = []
            if not pairs:
                continue
            found_field = leaf
            for val, count in pairs:
                if val is None:
                    continue
                segments[str(val)] += int(count)
            break  # one type-like field per object is enough

    total = sum(segments.values())
    return {
        "field": found_field,
        "total_records": total,
        "segments": [
            {"label": k, "count": v, "pct": (v / total * 100) if total else 0.0}
            for k, v in segments.most_common(10)
        ],
    }


# ─── Data Story ──────────────────────────────────────────────────────────────

def build_data_story(
    schema_json: dict[str, Any],
    quality: Any | None,
    joins_data: dict[str, Any] | None,
    patterns_data: dict[str, Any] | None,
    universe: dict[str, Any] | None,
) -> str:
    objects = schema_json.get("objects", [])
    n_obj = len(objects)
    n_fields = sum(len(o.get("fields", [])) for o in objects)
    n_sampled = sum(o.get("sampled", 0) for o in objects)

    parts: list[str] = []
    parts.append(
        f"The dataset spans {n_obj} object(s) with {n_fields} field(s) across {n_sampled:,} sampled record(s)."
    )

    if universe and universe.get("segments"):
        seg_str = ", ".join(
            f"{s['label']} ({s['pct']:.0f}%)" for s in universe["segments"][:3]
        )
        parts.append(f"Detected content segments via `{universe['field']}`: {seg_str}.")

    if quality is not None:
        dqi = getattr(quality, "overall_dqi", None)
        if isinstance(dqi, (int, float)):
            grade_word = (
                "excellent" if dqi >= 90 else "good" if dqi >= 80 else
                "fair" if dqi >= 70 else "weak" if dqi >= 60 else "critical"
            )
            parts.append(f"Overall Data Quality Index is {dqi:.1f}/100 ({grade_word}).")

    if joins_data:
        totals = joins_data.get("totals", {})
        if totals.get("same_path_fk", 0) or totals.get("value_overlap", 0):
            parts.append(
                f"Discovered {totals.get('same_path_fk', 0)} same-path FK candidate(s) and "
                f"{totals.get('value_overlap', 0)} value-overlap join candidate(s) between objects."
            )
        if totals.get("primary_keys", 0):
            parts.append(
                f"Inferred a primary or composite key for {totals['primary_keys']} object(s)."
            )

    if patterns_data:
        counts = patterns_data.get("pattern_counts", {})
        if counts:
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
            parts.append(
                "Dominant value shapes: "
                + ", ".join(f"{p} ({n})" for p, n in top) + "."
            )

    return " ".join(parts)


# ─── SWOT ────────────────────────────────────────────────────────────────────

def build_swot(
    schema_json: dict[str, Any],
    quality: Any | None,
    joins_data: dict[str, Any] | None,
    patterns_data: dict[str, Any] | None,
    pii_summary: dict[str, Any] | None,
) -> dict[str, list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    opportunities: list[str] = []
    threats: list[str] = []

    objects = schema_json.get("objects", [])
    if quality is not None:
        for obj in getattr(quality, "objects", []):
            if obj.completeness.score >= 90:
                strengths.append(
                    f"`{obj.object_name}` has high completeness ({obj.completeness.score:.0f}/100)."
                )
            if obj.completeness.score < 60:
                weaknesses.append(
                    f"`{obj.object_name}` has low completeness ({obj.completeness.score:.0f}/100)."
                )
            if obj.consistency.score < 80:
                weaknesses.append(
                    f"`{obj.object_name}` has mixed types ({obj.consistency.score:.0f}/100 consistency)."
                )
            if obj.uniqueness.score < 60 and obj.uniqueness.details.get("id_fields_checked"):
                weaknesses.append(
                    f"`{obj.object_name}` ID-like fields lack uniqueness."
                )

    if joins_data:
        fk_count = joins_data.get("totals", {}).get("same_path_fk", 0)
        if fk_count >= len(objects):
            strengths.append(
                f"{fk_count} cross-object FK candidate(s) enable robust joins."
            )
        elif fk_count == 0 and len(objects) > 1:
            weaknesses.append("No reliable cross-object FK candidates detected.")
        if joins_data.get("nested_relationships"):
            opportunities.append(
                "Nested arrays detected — consider denormalizing or exposing as related entities for downstream consumers."
            )

    if patterns_data:
        idents = patterns_data.get("identifier_fields", [])
        if idents:
            strengths.append(f"{len(idents)} identifier field(s) detected by value-shape.")
        if patterns_data.get("pattern_counts", {}).get("iso_datetime"):
            opportunities.append(
                "ISO datetimes present — enable time-window partitioning and freshness monitoring."
            )

    if pii_summary and pii_summary.get("total_pii_fields", 0):
        threats.append(
            f"{pii_summary['total_pii_fields']} potential PII field(s) detected — review access and masking before sharing."
        )

    # Multi-type fields are a threat for downstream typing
    multi_type_fields = 0
    for obj in objects:
        for f in obj.get("fields", []):
            types = [t for t in f.get("types", {}).keys() if t != "null"]
            if len(types) > 1:
                multi_type_fields += 1
    if multi_type_fields:
        threats.append(
            f"{multi_type_fields} field(s) carry mixed types — risk of consumer parsing errors."
        )

    if not strengths:
        strengths.append("No prominent strengths detected — see recommendations to improve.")
    if not opportunities:
        opportunities.append("Increase distinct sampling or enable AI insights for deeper opportunities.")
    if not threats:
        threats.append("No critical threats detected.")

    return {
        "strengths": strengths,
        "weaknesses": weaknesses or ["No major weaknesses detected."],
        "opportunities": opportunities,
        "threats": threats,
    }


# ─── Recommendations ────────────────────────────────────────────────────────

def build_recommendations(
    schema_json: dict[str, Any],
    quality: Any | None,
    joins_data: dict[str, Any] | None,
    patterns_data: dict[str, Any] | None,
    pii_summary: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Concrete, actionable recommendations to improve data quality and usability."""
    recs: list[dict[str, str]] = []

    # Completeness improvements
    if quality is not None:
        for obj in getattr(quality, "objects", []):
            low = obj.completeness.details.get("low_coverage_fields", 0)
            if low:
                recs.append(
                    {
                        "category": "Completeness",
                        "severity": "medium",
                        "action": (
                            f"`{obj.object_name}`: investigate {low} field(s) "
                            "with <50% coverage — fix upstream collection or document as optional."
                        ),
                    }
                )
            if obj.consistency.details.get("multi_type_fields"):
                recs.append(
                    {
                        "category": "Consistency",
                        "severity": "high",
                        "action": (
                            f"`{obj.object_name}`: enforce a single type per field; "
                            "add a JSON Schema validation rule for mixed-type paths."
                        ),
                    }
                )

    # Primary key recommendations
    for pk in (joins_data or {}).get("primary_keys", []):
        if pk["is_composite"]:
            recs.append(
                {
                    "category": "Uniqueness",
                    "severity": "medium",
                    "action": (
                        f"`{pk['object']}`: no single unique key — enforce a unique compound index "
                        f"on {' + '.join('`' + f + '`' for f in pk['fields'])}."
                    ),
                }
            )

    # Pattern-driven recommendations
    if patterns_data:
        if patterns_data.get("pattern_counts", {}).get("integer_id") and not patterns_data.get(
            "pattern_counts", {}
        ).get("uuid"):
            recs.append(
                {
                    "category": "Identifiability",
                    "severity": "low",
                    "action": "Consider adopting globally-unique IDs (UUID) for cross-system joins.",
                }
            )

    # PII recommendations
    if pii_summary and pii_summary.get("high_risk_fields"):
        recs.append(
            {
                "category": "Compliance",
                "severity": "high",
                "action": (
                    f"{len(pii_summary['high_risk_fields'])} high-risk PII field(s) — "
                    "enable masking, restrict access, and document a retention policy."
                ),
            }
        )

    # Timeliness
    has_timestamps = any(
        any("date" in f.get("types", {}) or any(
            kw in f.get("path", "").lower() for kw in ("updated", "modified", "timestamp")
        ) for f in obj.get("fields", []))
        for obj in schema_json.get("objects", [])
    )
    if not has_timestamps:
        recs.append(
            {
                "category": "Timeliness",
                "severity": "medium",
                "action": "Add an `updatedAt` / `lastModified` timestamp per object to track freshness.",
            }
        )

    if not recs:
        recs.append(
            {
                "category": "General",
                "severity": "low",
                "action": "Quality looks healthy — establish daily DQI snapshots to detect drift.",
            }
        )

    return recs


# ─── AI-readiness ───────────────────────────────────────────────────────────

def build_ai_readiness(
    schema_json: dict[str, Any],
    quality: Any | None,
    pii_summary: dict[str, Any] | None,
    patterns_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Heuristic readiness assessment for AI/LLM consumption.

    Each check returns: name, status (pass|warn|fail), recommendation.
    """
    checks: list[dict[str, str]] = []
    objects = schema_json.get("objects", [])

    # Stable IDs
    has_ids = any(
        (patterns_data or {}).get("identifier_fields")
    )
    checks.append(
        {
            "name": "Stable record identifiers",
            "status": "pass" if has_ids else "warn",
            "recommendation": (
                "Detected identifier-shaped fields." if has_ids
                else "Add a stable, unique ID (UUID preferred) per record to support retrieval-augmented use cases."
            ),
        }
    )

    # Timestamps for freshness
    has_timestamps = any(
        any("date" in f.get("types", {}) or any(
            kw in f.get("path", "").lower() for kw in ("updated", "modified", "timestamp", "created")
        ) for f in obj.get("fields", []))
        for obj in objects
    )
    checks.append(
        {
            "name": "Freshness timestamps",
            "status": "pass" if has_timestamps else "warn",
            "recommendation": (
                "Per-record timestamps present."
                if has_timestamps else
                "Add `createdAt`/`updatedAt` to support incremental indexing and time-aware grounding."
            ),
        }
    )

    # Consistent types
    multi = 0
    for obj in objects:
        for f in obj.get("fields", []):
            types = [t for t in f.get("types", {}).keys() if t != "null"]
            if len(types) > 1:
                multi += 1
    checks.append(
        {
            "name": "Type stability",
            "status": "pass" if multi == 0 else "warn" if multi <= 5 else "fail",
            "recommendation": (
                "All fields are type-stable."
                if multi == 0 else
                f"{multi} mixed-type field(s) — coerce to a single type before AI ingestion."
            ),
        }
    )

    # PII safety
    high_pii = (pii_summary or {}).get("high_risk_fields", []) if pii_summary else []
    checks.append(
        {
            "name": "PII safety for AI ingestion",
            "status": "pass" if not high_pii else "fail",
            "recommendation": (
                "No high-risk PII fields detected."
                if not high_pii else
                f"Mask/strip {len(high_pii)} high-risk PII field(s) prior to embedding/training."
            ),
        }
    )

    # Documentation hints
    checks.append(
        {
            "name": "Field documentation tags",
            "status": "warn",
            "recommendation": (
                "Add field-level descriptions and units (where numeric) so LLMs ground answers correctly. "
                "Consider emitting a JSON Schema with `description` per property."
            ),
        }
    )

    # Granularity
    huge_objs = [o for o in objects if len(o.get("fields", [])) > 80]
    checks.append(
        {
            "name": "Granularity / chunking",
            "status": "warn" if huge_objs else "pass",
            "recommendation": (
                "Some objects exceed 80 fields — chunk records by sub-entity for RAG embeddings."
                if huge_objs else
                "Object size is reasonable for chunking."
            ),
        }
    )

    score = sum(1 for c in checks if c["status"] == "pass") / max(1, len(checks)) * 100
    return {"checks": checks, "score": round(score, 1)}


# ─── Top-level orchestrator ────────────────────────────────────────────────

def build_insights(
    schema_json: dict[str, Any],
    quality: Any | None,
    joins_data: dict[str, Any] | None,
    patterns_data: dict[str, Any] | None,
    pii_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    universe = build_content_universe(schema_json)
    locale_dims = build_locale_dimensions(schema_json, patterns_data)
    return {
        "content_universe": universe,
        "data_story": build_data_story(schema_json, quality, joins_data, patterns_data, universe),
        "swot": build_swot(schema_json, quality, joins_data, patterns_data, pii_summary),
        "recommendations": build_recommendations(
            schema_json, quality, joins_data, patterns_data, pii_summary
        ),
        "ai_readiness": build_ai_readiness(schema_json, quality, pii_summary, patterns_data),
        "locale_dimensions": locale_dims,
    }
