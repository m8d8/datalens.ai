"""
HTML Report Generator — Professional self-contained interactive schema analysis report.

Features:
- Day/Night mode toggle with smooth transitions
- Professional typography (Inter font family)
- Modern color scheme with accessibility
- Data Quality Index (DQI) visualization
- PII detection warnings
- Numeric/Temporal statistics
- Relationship graph
- Global search across all tabs
- Sortable, filterable tables
- Export functionality
"""

from __future__ import annotations

import base64
import html
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datalens.config import Config

from datalens.profiling.pii import PIIType, detect_pii_in_schema, get_pii_summary
from datalens.profiling.quality import compute_schema_quality, get_quality_color, get_quality_grade
from datalens.profiling.relationships import analyze_relationships, generate_relationship_graph
from datalens.profiling.statistics import compute_statistics_summary
from datalens.profiling.patterns import analyze_patterns
from datalens.profiling.joins import analyze_joins
from datalens.profiling.insights import build_insights
from datalens.report._logo import LOGO_ICON_DARK_SVG, LOGO_ICON_LIGHT_SVG


def _svg_data_uri(svg: str) -> str:
    """Base64 data URI for an SVG — isolates gradient IDs and keeps the report self-contained."""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def generate_html_report(
    schema_json: dict[str, Any],
    config: "Config",
    *,
    patterns_data: dict[str, Any] | None = None,
    quality_data: Any | None = None,
    pii_data: dict[str, Any] | None = None,
    pii_summary: dict[str, Any] | None = None,
    relationships_data: dict[str, Any] | None = None,
    statistics_data: dict[str, Any] | None = None,
    joins_data: dict[str, Any] | None = None,
    insights_data: dict[str, Any] | None = None,
    diff: Any | None = None,
    previous_schema: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    ai_insights: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    include_pii: bool = True,
    include_quality: bool = True,
    include_relationships: bool = True,
    include_statistics: bool = True,
) -> str:
    """
    Generate a professional self-contained interactive HTML report.

    Analytics are computed once by ``core.analyze`` and passed in via the
    keyword arguments below; this function renders them and MUST NOT recompute
    work the caller already did. As a back-compat shim, any analytics argument
    left as ``None`` is computed here so legacy callers — ``generate_html_report
    (schema_json, config)`` — keep working unchanged.

    Args:
        schema_json: Schema analysis JSON from profiling.
        config: Configuration object.
        patterns_data, quality_data, pii_data, pii_summary, relationships_data,
        statistics_data, joins_data, insights_data: Pre-computed analytics from
            ``core.analyze``. Each is computed here only if left ``None`` (shim).
        diff: Optional ``history.diff.SchemaDiff`` for the Trends & Drift view.
        history: Optional list of prior run metadata for trend sparklines.
        ai_insights: Optional AI-enriched narrative (rendered only when present).
        decision: Optional v2 decision layer (verdict, compliance, fitness, actions).
        include_pii: Include PII detection analysis.
        include_quality: Include Data Quality Index.
        include_relationships: Include relationship analysis.
        include_statistics: Include numeric/temporal statistics.

    Returns:
        Complete HTML document as a string.
    """
    objects = schema_json.get("objects", [])

    # Compute overview stats
    total_objects = len(objects)
    total_fields = sum(len(obj.get("fields", [])) for obj in objects)
    total_sampled = sum(obj.get("sampled", 0) for obj in objects)

    # Advanced analytics: use what the caller already computed; only fall back
    # to recomputing for any value left as None (legacy / back-compat callers).
    if patterns_data is None:
        patterns_data = analyze_patterns(schema_json)
    if quality_data is None and include_quality:
        quality_data = compute_schema_quality(schema_json, patterns_data=patterns_data)
    if pii_data is None and include_pii:
        pii_data = detect_pii_in_schema(schema_json)
    if pii_summary is None and pii_data:
        pii_summary = get_pii_summary(pii_data)
    if relationships_data is None and include_relationships:
        relationships_data = analyze_relationships(schema_json)
    if statistics_data is None and include_statistics:
        statistics_data = compute_statistics_summary(schema_json)
    if joins_data is None:
        joins_data = analyze_joins(schema_json)
    if insights_data is None:
        insights_data = build_insights(
            schema_json, quality_data, joins_data, patterns_data, pii_summary,
        )

    # Generate HTML sections
    overview_html = _render_overview(
        objects, total_objects, total_fields, total_sampled,
        quality_data, pii_summary, decision
    )
    quality_html = _render_quality_tab(quality_data) if quality_data else ""
    trends_html = _render_trends_drift(diff, decision, schema_json, previous_schema)
    pii_html = _render_pii_tab(pii_data, pii_summary) if pii_data else ""
    field_explorer_html = _render_field_explorer(objects, pii_data, config.max_distinct_values)
    coverage_html = _render_coverage_heatmap(objects)
    distributions_html = _render_distributions(objects, schema_json, statistics_data)
    type_warnings_html = _render_type_warnings(objects)
    relationships_html = _render_relationships_tab(relationships_data, joins_data, objects) if relationships_data else _render_relationships_tab({}, joins_data, objects)
    insights_html = _render_insights_tab(insights_data, joins_data)
    ai_insights_html = _render_ai_insights_tab(ai_insights) if ai_insights else ""
    patterns_html = _render_patterns_tab(patterns_data)
    joins_html = _render_joins_tab(joins_data, objects)
    # Build field value distributions for modal viewer
    field_distributions = _build_field_distributions(objects)

    # Build chapter-grouped tabs
    chapter_tabs = _build_tabs(
        include_quality,
        include_pii,
        include_relationships,
        include_statistics,
        include_ai_insights=bool(ai_insights and ai_insights.get("enabled")),
    )

    # Assemble the full report
    html_content = _HTML_TEMPLATE.format(
        title="Datalens Schema Analysis Report",
        logo_icon_light=_svg_data_uri(LOGO_ICON_LIGHT_SVG),
        logo_icon_dark=_svg_data_uri(LOGO_ICON_DARK_SVG),
        version_tag=config.version_tag,
        overview=overview_html,
        trends=trends_html,
        quality=quality_html,
        pii=pii_html,
        field_explorer=field_explorer_html,
        coverage=coverage_html,
        distributions=distributions_html,
        type_warnings=type_warnings_html,
        relationships=relationships_html,
        insights=insights_html,
        ai_insights=ai_insights_html,
        patterns=patterns_html,
        joins=joins_html,
        schema_json=html.escape(json.dumps(schema_json, indent=2)),
        total_objects=total_objects,
        total_fields=total_fields,
        total_sampled=total_sampled,
        tabs_verdict=chapter_tabs["verdict"],
        tabs_shape=chapter_tabs["shape"],
        tabs_health=chapter_tabs["health"],
        tabs_structure=chapter_tabs["structure"],
        tabs_fingerprint=chapter_tabs["fingerprint"],
        dqi_score=round(quality_data.overall_dqi, 1) if quality_data else "N/A",
        dqi_grade=get_quality_grade(quality_data.overall_dqi) if quality_data else "N/A",
        pii_count=pii_summary.get("total_pii_fields", 0) if pii_summary else 0,
        field_distributions_json=json.dumps(field_distributions),
        max_distinct_configured=config.max_distinct_values,
    )

    return html_content


def _build_field_distributions(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build field value distributions for the modal viewer.

    Returns a dict mapping 'objectName.fieldPath' to distribution data:
    {
        "collectionName.fieldPath": {
            "distinct_count": 42,
            "values": {"value1": 10, "value2": 5, ...}
        }
    }
    """
    distributions: dict[str, Any] = {}

    for obj in objects:
        obj_name = obj.get("object", "Unknown")

        for field in obj.get("fields", []):
            path = field.get("path", "")
            value_counts = field.get("value_counts", {})

            if value_counts:
                key = f"{obj_name}.{path}"
                distributions[key] = {
                    "distinct_count": field.get("distinct_count_in_sample", len(value_counts)),
                    "values": value_counts,
                }

    return distributions


def _build_tabs(
    include_quality: bool,
    include_pii: bool,
    include_relationships: bool,
    include_statistics: bool,
    *,
    include_ai_insights: bool = False,
) -> dict[str, str]:
    """Build chapter-grouped tabs HTML based on enabled features.
    
    Returns a dict with keys: verdict, shape, health, structure, fingerprint
    Each value is the HTML for the tabs in that chapter.
    """
    # Define chapters and their tabs
    # Format: (tab_id, label, icon, persona_hide)
    # persona_hide: space-separated personas to hide from (e.g., "business" or "business technical")
    
    chapters: dict[str, list[tuple[str, str, str, str]]] = {
        "verdict": [
            ("overview", "Overview", "📊", ""),
        ],
        "shape": [
            ("insights", "Insights", "💡", ""),
        ],
        "health": [],
        "structure": [
            ("field-explorer", "Field Explorer", "🔍", "business"),
        ],
        "fingerprint": [
            ("distributions", "Distributions", "📉", ""),
            ("patterns", "Patterns", "🧩", ""),
            ("trends", "Trends & Drift", "🕒", ""),
        ],
    }
    
    if include_ai_insights:
        chapters["shape"].append(("ai-insights", "AI Insights", "✨", ""))
    chapters["shape"].append(("coverage", "Coverage", "📈", ""))

    # Add conditional tabs
    if include_quality:
        chapters["health"].append(("quality", "Data Quality", "✅", ""))
    if include_pii:
        chapters["health"].append(("pii", "PII Detection", "🔒", ""))
    chapters["health"].append(("type-warnings", "Type Warnings", "⚠️", "business"))
    
    if include_relationships:
        chapters["structure"].append(("relationships", "Relationships", "🔗", ""))
    chapters["structure"].append(("join-keys", "Cross-Object", "🔀", ""))
    
    # Build HTML for each chapter
    result: dict[str, str] = {}
    first_overall = True
    
    for chapter, tabs in chapters.items():
        tab_html = []
        for i, (tab_id, label, icon, persona_hide) in enumerate(tabs):
            active = "active" if first_overall else ""
            if first_overall:
                first_overall = False
            
            persona_attr = f' data-persona-hide="{persona_hide}"' if persona_hide else ""
            tab_html.append(
                f'<button class="tab {active}" data-tab="{tab_id}"{persona_attr}>'
                f'<span class="tab-icon">{icon}</span>'
                f'<span class="tab-label">{label}</span>'
                f'</button>'
            )
        result[chapter] = "\n".join(tab_html)
    
    return result


def _render_overview(
    objects: list[dict[str, Any]],
    total_objects: int,
    total_fields: int,
    total_sampled: int,
    quality_data: Any,
    pii_summary: dict[str, Any] | None,
    decision: dict[str, Any] | None = None,
) -> str:
    """Render the Overview tab content."""
    # Cover Summary Band — hero-style overview at the top
    verdict = (decision or {}).get("health_verdict", {})
    health_score = round(verdict.get("score", 0))
    health_status = verdict.get("status", "attention")
    dqi = round(quality_data.overall_dqi, 1) if quality_data else 0
    dqi_grade = get_quality_grade(quality_data.overall_dqi) if quality_data else "N/A"
    pii_count = pii_summary.get("total_pii_fields", 0) if pii_summary else 0
    
    cover_html = f"""
        <section class="cover-band">
            <div class="cover-verdict">
                <div class="cover-verdict-ring {health_status}">
                    <span class="cover-verdict-score">{health_score}</span>
                    <span class="cover-verdict-label">Health</span>
                </div>
            </div>
            <div class="cover-info">
                <h2 class="cover-title">Schema Analysis Report</h2>
                <p class="cover-subtitle">
                    <span class="biz-lang">Analysis of your data structure, quality, and relationships</span>
                    <span class="tech-lang">Profiling {total_objects} collections with {total_fields} fields across {total_sampled:,} sampled records</span>
                </p>
                <div class="cover-meta">
                    <div class="cover-meta-item">
                        <span class="cover-meta-value">{dqi:.0f}</span>
                        <span class="cover-meta-label">DQI Score ({dqi_grade})</span>
                    </div>
                    <div class="cover-meta-item">
                        <span class="cover-meta-value">{pii_count}</span>
                        <span class="cover-meta-label">PII Fields</span>
                    </div>
                </div>
            </div>
            <div class="cover-kpis">
                <div class="cover-kpi">
                    <span class="cover-kpi-value">{total_objects}</span>
                    <span class="cover-kpi-label">Objects</span>
                </div>
                <div class="cover-kpi">
                    <span class="cover-kpi-value">{total_fields}</span>
                    <span class="cover-kpi-label">Fields</span>
                </div>
                <div class="cover-kpi">
                    <span class="cover-kpi-value">{total_sampled:,}</span>
                    <span class="cover-kpi-label">Sampled</span>
                </div>
            </div>
        </section>
    """
    
    # Executive Summary banner (v2 decision layer) — leads the Overview.
    exec_summary_html = _render_executive_summary(decision)
    # DQI card
    dqi_html = ""
    if quality_data:
        dqi = quality_data.overall_dqi
        grade = get_quality_grade(dqi)
        color_class = get_quality_color(dqi)

        dqi_html = f"""
            <div class="metric-card dqi-card {color_class}">
                <div class="metric-header">
                    <span class="metric-icon">✅</span>
                    <span class="metric-title">Data Quality Index</span>
                </div>
                <div class="dqi-display">
                    <span class="dqi-score">{dqi:.1f}</span>
                    <span class="dqi-grade">{grade}</span>
                </div>
                <div class="dqi-bar-container">
                    <div class="dqi-bar" style="width: {dqi}%"></div>
                </div>
            </div>
        """

    # PII alert card
    pii_html = ""
    if pii_summary and pii_summary.get("total_pii_fields", 0) > 0:
        pii_count = pii_summary["total_pii_fields"]
        high_risk = len(pii_summary.get("high_risk_fields", []))

        pii_html = f"""
            <div class="metric-card pii-card {'pii-warning' if high_risk > 0 else ''}">
                <div class="metric-header">
                    <span class="metric-icon">🔒</span>
                    <span class="metric-title">PII Detection</span>
                </div>
                <div class="pii-stats">
                    <div class="pii-stat">
                        <span class="pii-value">{pii_count}</span>
                        <span class="pii-label">PII Fields</span>
                    </div>
                    <div class="pii-stat">
                        <span class="pii-value {'high-risk' if high_risk > 0 else ''}">{high_risk}</span>
                        <span class="pii-label">High Risk</span>
                    </div>
                </div>
            </div>
        """

    # Summary cards
    cards = [f"""
        <div class="overview-grid">
            <div class="metric-card">
                <div class="metric-header">
                    <span class="metric-icon">📦</span>
                    <span class="metric-title">Objects</span>
                </div>
                <div class="metric-value">{total_objects}</div>
            </div>
            <div class="metric-card">
                <div class="metric-header">
                    <span class="metric-icon">📋</span>
                    <span class="metric-title">Fields</span>
                </div>
                <div class="metric-value">{total_fields}</div>
            </div>
            <div class="metric-card">
                <div class="metric-header">
                    <span class="metric-icon">📊</span>
                    <span class="metric-title">Records Sampled</span>
                </div>
                <div class="metric-value">{total_sampled:,}</div>
            </div>
            {dqi_html}
            {pii_html}
        </div>
    """]

    # Per-object summary
    fitness_map = (decision or {}).get("fitness_for_use", {})
    _fit_badge_class = {"pass": "badge-success", "warn": "badge-warning", "fail": "badge-danger"}
    obj_rows = []
    for obj in objects:
        obj_raw_name = obj.get("object", "Unknown")
        obj_name = html.escape(obj_raw_name)
        obj_label = html.escape(obj.get("label") or "")

        fitness_badges = fitness_map.get(obj_raw_name, [])
        fitness_cell = " ".join(
            f'<span class="badge {_fit_badge_class.get(b.get("status"), "badge-info")}">'
            f'{html.escape(str(b.get("label", "")))}</span>'
            for b in fitness_badges
        ) or '<span style="color:var(--text-tertiary)">—</span>'
        obj_sampled = obj.get("sampled", 0)
        obj_fields = len(obj.get("fields", []))

        # Effective coverage stats (presence − null/empty)
        fields = obj.get("fields", [])
        def _eff_cov(f: dict, s: int) -> float:
            eff = max(0, f.get("presence_count", 0) - f.get("null_empty_count", 0))
            return eff / s if s else 0.0
        high_cov = sum(1 for f in fields if _eff_cov(f, max(obj_sampled, 1)) >= 0.9)
        low_cov  = sum(1 for f in fields if _eff_cov(f, max(obj_sampled, 1)) < 0.5)

        label_badge = f'<span class="badge badge-info">{obj_label}</span>' if obj_label else ""

        obj_rows.append(f"""
            <tr>
                <td><span class="object-name">{obj_name}</span> {label_badge}</td>
                <td class="text-center">{obj_fields}</td>
                <td class="text-center">{obj_sampled:,}</td>
                <td class="text-center"><span class="badge badge-success">{high_cov}</span></td>
                <td class="text-center"><span class="badge badge-danger">{low_cov}</span></td>
                <td>{fitness_cell}</td>
            </tr>
        """)

    cards.append(f"""
        <div class="card">
            <div class="card-header">
                <h3>Objects Summary</h3>
            </div>
            <div class="card-body">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Object</th>
                            <th class="text-center">Fields</th>
                            <th class="text-center">Sampled</th>
                            <th class="text-center">High Coverage</th>
                            <th class="text-center">Low Coverage</th>
                            <th>Fitness for Use</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(obj_rows)}
                    </tbody>
                </table>
            </div>
        </div>
    """)

    return cover_html + exec_summary_html + "\n".join(cards)


# Status → (emoji, CSS color var, label) for verdict / badge rendering.
_VERDICT_META = {
    "healthy": ("🟢", "var(--color-success)", "Healthy"),
    "attention": ("🟡", "var(--color-warning)", "Needs attention"),
    "risk": ("🔴", "var(--color-danger)", "At risk"),
}
_RISK_META = {
    "none": ("var(--color-success)", "No exposure"),
    "low": ("var(--color-success)", "Low"),
    "medium": ("var(--color-warning)", "Medium"),
    "high": ("var(--color-danger)", "High"),
}
_EFFORT_BADGE = {
    "low": "badge-success",
    "medium": "badge-warning",
    "high": "badge-danger",
}


def _render_executive_summary(decision: dict[str, Any] | None) -> str:
    """
    Render the v2 Executive Summary banner: a one-screen, plain-language verdict
    for business stakeholders — health traffic light, drivers, compliance risk,
    and the top actions to take. Renders nothing if no decision layer is present.
    """
    if not decision:
        return ""

    verdict = decision.get("health_verdict", {})
    status = verdict.get("status", "attention")
    score = verdict.get("score", 0.0)
    drivers = verdict.get("drivers", [])
    emoji, color, label = _VERDICT_META.get(status, _VERDICT_META["attention"])

    drivers_html = "".join(
        f'<li>{html.escape(str(d))}</li>' for d in drivers[:5]
    )

    # Compliance risk pill
    cs = decision.get("compliance_scorecard", {})
    risk = cs.get("risk", "none")
    risk_color, risk_label = _RISK_META.get(risk, _RISK_META["none"])
    pii_ratio = cs.get("pii_field_ratio", 0.0)

    drift = decision.get("drift_severity", "none")
    drift_label = {
        "none": "No prior run / no drift",
        "low": "Minor additions",
        "medium": "Notable changes",
        "high": "Breaking changes",
    }.get(drift, drift)

    # Top actions
    top_actions = decision.get("top_actions", [])
    if top_actions:
        action_items = "".join(
            f"""
            <li>
                <span class="badge {_EFFORT_BADGE.get(a.get('effort', 'medium'), 'badge-info')}">
                    {html.escape(str(a.get('effort', 'medium')).title())} effort</span>
                <strong>{html.escape(str(a.get('category', 'General')))}:</strong>
                {html.escape(str(a.get('action', '')))}
                <div class="exec-impact">{html.escape(str(a.get('impact_text', '')))}</div>
            </li>
            """
            for a in top_actions
        )
        actions_block = f"""
            <div class="exec-actions">
                <h4>Top {len(top_actions)} things to fix</h4>
                <ol class="exec-action-list">{action_items}</ol>
            </div>
        """
    else:
        actions_block = """
            <div class="exec-actions">
                <h4>Top things to fix</h4>
                <p class="exec-muted">No priority actions — data health looks solid.</p>
            </div>
        """

    return f"""
        <style>
            .exec-summary {{
                background: var(--bg-card); border: 1px solid var(--border-primary);
                border-left: 6px solid {color}; border-radius: var(--radius-lg);
                padding: var(--space-lg); margin-bottom: var(--space-lg);
            }}
            .exec-top {{ display: flex; flex-wrap: wrap; gap: var(--space-xl); align-items: center; }}
            .exec-verdict {{ display: flex; align-items: center; gap: var(--space-md); }}
            .exec-verdict .emoji {{ font-size: 2.4rem; line-height: 1; }}
            .exec-verdict .v-label {{ font-size: 1.4rem; font-weight: 700; color: {color}; }}
            .exec-verdict .v-score {{ color: var(--text-secondary); font-size: .9rem; }}
            .exec-pills {{ display: flex; flex-wrap: wrap; gap: var(--space-sm); }}
            .exec-pill {{
                padding: var(--space-xs) var(--space-md); border-radius: var(--radius-xl);
                font-size: .8rem; font-weight: 600; border: 1px solid var(--border-primary);
                color: var(--text-secondary); background: var(--bg-secondary);
            }}
            .exec-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-xl);
                          margin-top: var(--space-lg); }}
            @media (max-width: 820px) {{ .exec-body {{ grid-template-columns: 1fr; }} }}
            .exec-summary h4 {{ margin: 0 0 var(--space-sm); color: var(--text-primary); }}
            .exec-drivers {{ margin: 0; padding-left: 1.1rem; color: var(--text-secondary);
                             font-size: .9rem; line-height: 1.7; }}
            .exec-action-list {{ margin: 0; padding-left: 1.1rem; color: var(--text-primary); }}
            .exec-action-list li {{ margin-bottom: var(--space-md); }}
            .exec-impact {{ color: var(--text-secondary); font-size: .85rem; margin-top: 2px; }}
            .exec-muted {{ color: var(--text-tertiary); }}
        </style>
        <section class="exec-summary" aria-label="Executive summary">
            <div class="exec-top">
                <div class="exec-verdict">
                    <span class="emoji">{emoji}</span>
                    <div>
                        <div class="v-label">{label}</div>
                        <div class="v-score">Data health score {score:.0f}/100</div>
                    </div>
                </div>
                <div class="exec-pills">
                    <span class="exec-pill" style="border-color:{risk_color};color:{risk_color}">
                        PII risk: {risk_label} ({pii_ratio:.0%} of fields)</span>
                    <span class="exec-pill">Change since last run: {html.escape(drift_label)}</span>
                </div>
            </div>
            <div class="exec-body">
                <div>
                    <h4>What drives this score</h4>
                    <ul class="exec-drivers">{drivers_html}</ul>
                </div>
                {actions_block}
            </div>
        </section>
    """


_DRIFT_BADGE = {
    "none": ("badge-success", "No drift"),
    "low": ("badge-info", "Minor additions"),
    "medium": ("badge-warning", "Notable changes"),
    "high": ("badge-danger", "Breaking changes"),
}


def _index_fields(schema_json: dict[str, Any] | None) -> dict[tuple[str, str], tuple[dict[str, Any], int]]:
    """Index a schema as {(object, path): (field_dict, sampled)} for quick lookup."""
    index: dict[tuple[str, str], tuple[dict[str, Any], int]] = {}
    for obj in (schema_json or {}).get("objects", []):
        name = obj.get("object", "")
        sampled = obj.get("sampled", 0) or 0
        for f in obj.get("fields", []):
            index[(name, f.get("path", ""))] = (f, sampled)
    return index


def _inline_distribution(field: dict[str, Any], top: int = 5) -> str:
    """Render a compact, self-contained value distribution for a field (no JS/modal)."""
    vc = field.get("value_counts") or {}
    pairs: list[tuple[str, int]] = []
    if isinstance(vc, dict) and vc:
        pairs = [(str(k), int(v)) for k, v in vc.items()]
    elif isinstance(vc, list) and vc:
        pairs = [(str(p[0]), int(p[1])) for p in vc if isinstance(p, (list, tuple)) and len(p) == 2]
    if not pairs:
        dv = field.get("distinct_values") or field.get("examples") or []
        return html.escape(", ".join(str(v)[:24] for v in dv[:top])) or '<span style="color:var(--text-tertiary)">—</span>'

    pairs.sort(key=lambda kv: -kv[1])
    total = sum(c for _, c in pairs) or 1
    bars = []
    for label, count in pairs[:top]:
        pct = count / total * 100
        bars.append(
            f'<div class="mini-dist-row">'
            f'<span class="mini-dist-label" title="{html.escape(label)}">{html.escape(label[:28])}</span>'
            f'<span class="mini-dist-bar"><span class="mini-dist-fill" style="width:{pct:.0f}%"></span></span>'
            f'<span class="mini-dist-count">{count:,}</span>'
            f'</div>'
        )
    more = len(pairs) - top
    if more > 0:
        bars.append(f'<div class="mini-dist-more">+{more:,} more</div>')
    return f'<div class="mini-dist">{"".join(bars)}</div>'


def _before_after_dist(
    obj_name: str,
    path: str,
    prev_index: dict[tuple[str, str], tuple[dict[str, Any], int]],
    cur_index: dict[tuple[str, str], tuple[dict[str, Any], int]],
) -> str:
    """Side-by-side Before/After value distributions for a field present in both runs."""
    prev_entry = prev_index.get((obj_name, path))
    cur_entry = cur_index.get((obj_name, path))
    before = _inline_distribution(prev_entry[0]) if prev_entry else '<span style="color:var(--text-tertiary)">—</span>'
    after = _inline_distribution(cur_entry[0]) if cur_entry else '<span style="color:var(--text-tertiary)">—</span>'
    return (
        '<div class="ba-dist">'
        f'<div class="ba-col"><div class="ba-label">Before</div>{before}</div>'
        f'<div class="ba-col"><div class="ba-label">After</div>{after}</div>'
        '</div>'
    )


def _drift_field_table(
    title: str,
    paths: list[tuple[str, str]],
    index: dict[tuple[str, str], tuple[dict[str, Any], int]],
    badge_cls: str,
) -> str:
    """Field-Explorer-style table for added/removed fields, with samples + distribution."""
    if not paths:
        return ""
    rows = []
    for obj_name, path in paths:
        entry = index.get((obj_name, path))
        if entry is None:
            # Field metadata unavailable (e.g. schema not retained) — show path only.
            rows.append(
                f'<tr><td><span class="object-name">{html.escape(obj_name)}</span></td>'
                f'<td><span class="field-path">{html.escape(path)}</span></td>'
                f'<td colspan="5" style="color:var(--text-tertiary)">metadata unavailable</td></tr>'
            )
            continue
        field, sampled = entry
        presence = field.get("presence_count", 0)
        nulls = field.get("null_empty_count", 0)
        eff = max(0, presence - nulls)
        coverage_pct = (eff / sampled * 100) if sampled else 0.0
        cov_class = "coverage-high" if coverage_pct >= 90 else "coverage-medium" if coverage_pct >= 50 else "coverage-low"
        types = field.get("types", {})
        type_badges = " ".join(
            f'<span class="type-badge type-{t}">{t}</span>'
            for t in sorted(types.keys()) if t != "null"
        ) or "—"
        non_null_types = set(types.keys()) - {"null"}
        is_container = bool(non_null_types) and non_null_types <= {"object", "array"}
        distinct = field.get("distinct_count_in_sample", 0)
        distinct_cell = "—" if is_container else f"{distinct:,}"
        examples = field.get("examples", [])
        example_str = html.escape(", ".join(str(e)[:40] for e in examples[:3]))
        rows.append(f"""
            <tr>
                <td><span class="object-name">{html.escape(obj_name)}</span></td>
                <td><span class="field-path">{html.escape(path)}</span></td>
                <td><span class="coverage-badge {cov_class}">{coverage_pct:.1f}%</span></td>
                <td>{type_badges}</td>
                <td class="text-center">{distinct_cell}</td>
                <td class="example-cell" title="{example_str}">{example_str}</td>
                <td>{_inline_distribution(field)}</td>
            </tr>
        """)
    return f"""
        <div class="card">
            <div class="card-header"><h3>{title}
                <span class="badge {badge_cls}">{len(paths)}</span></h3></div>
            <div class="card-body">
                <div class="table-container">
                    <table class="data-table sortable drift-table">
                        <thead><tr>
                            <th>Object</th><th>Field Path</th><th>Coverage</th><th>Types</th>
                            <th class="text-center">Distinct</th><th>Examples</th>
                            <th>Value Distribution</th>
                        </tr></thead>
                        <tbody>{"".join(rows)}</tbody>
                    </table>
                </div>
            </div>
        </div>
    """


def _render_trends_drift(
    diff: Any | None,
    decision: dict[str, Any] | None,
    schema_json: dict[str, Any] | None = None,
    previous_schema: dict[str, Any] | None = None,
) -> str:
    """
    Render the Trends & Drift tab from a ``history.diff.SchemaDiff``.

    Added/removed fields are shown as Field-Explorer-style tables (types,
    coverage, distinct counts, sample values, and an inline value distribution)
    — sourced from the current schema for additions and the previous schema for
    removals. Type changes, coverage shifts, and cardinality changes follow.
    Renders a clear empty state when there is no prior run to compare against.
    """
    if diff is None:
        return """
            <div class="card">
                <div class="card-body" style="text-align:center;padding:var(--space-2xl)">
                    <div style="font-size:2.5rem">🕒</div>
                    <h3>No prior run to compare</h3>
                    <p style="color:var(--text-secondary)">
                        This run becomes your baseline. Re-run with
                        <code>--detect-drift</code> (or <code>--compare-to &lt;version&gt;</code>)
                        to see what changed since a previous run.
                    </p>
                </div>
            </div>
        """

    severity = (decision or {}).get("drift_severity", "none")
    badge_cls, _ = _DRIFT_BADGE.get(severity, _DRIFT_BADGE["none"])

    if not getattr(diff, "has_drift", False):
        return f"""
            <div class="card">
                <div class="card-header"><h3>Schema Drift
                    <span class="badge {badge_cls}">{severity}</span></h3></div>
                <div class="card-body" style="text-align:center;padding:var(--space-2xl)">
                    <div style="font-size:2.5rem">✅</div>
                    <h3>No changes detected</h3>
                    <p style="color:var(--text-secondary)">
                        The schema is identical to the previous run.</p>
                </div>
            </div>
        """

    def _list_card(title: str, items: list[str], cls: str = "badge-info") -> str:
        if not items:
            return ""
        rows = "".join(f'<li><span class="badge {cls}">{html.escape(str(i))}</span></li>'
                       for i in items)
        return f"""
            <div class="card">
                <div class="card-header"><h3>{title} <span class="badge {cls}">{len(items)}</span></h3></div>
                <div class="card-body"><ul class="drift-list">{rows}</ul></div>
            </div>
        """

    sections: list[str] = []

    # Severity rollup header
    drivers = (decision or {}).get("health_verdict", {}).get("drivers", [])
    drift_driver = next((d for d in drivers if "drift" in d.lower()), "")
    sections.append(f"""
        <div class="card">
            <div class="card-header"><h3>Schema Drift
                <span class="badge {badge_cls}">{severity}</span></h3></div>
            <div class="card-body">
                <p style="color:var(--text-secondary)">
                    {html.escape(drift_driver) or "Changes were detected since the previous run."}
                </p>
            </div>
        </div>
    """)

    # Controls: object filter (shared across all drift tables) + CSV export for producers.
    sections.append("""
        <div class="table-controls">
            <div class="object-filter-dropdown" id="trendsObjectFilterDropdown">
                <button type="button" class="object-filter-toggle" id="trendsObjectFilterToggle" aria-expanded="false">
                    Objects: All
                </button>
                <div class="object-filter-menu" id="trendsObjectFilterMenu">
                    <label class="object-filter-option object-filter-select-all">
                        <input type="checkbox" id="trendsObjectSelectAll" checked>
                        <span>Select All</span>
                    </label>
                    <div class="object-filter-divider"></div>
                    <div id="trendsObjectFilterOptions"></div>
                </div>
            </div>
            <button class="btn btn-secondary" onclick="exportDriftChanges()">
                📥 Export Drift CSV
            </button>
        </div>
    """)

    # Added / removed objects
    sections.append(_list_card("New Objects", getattr(diff, "added_objects", []), "badge-success"))
    sections.append(_list_card("Removed Objects", getattr(diff, "removed_objects", []), "badge-danger"))

    # Added / removed fields — rendered as Field-Explorer-style tables.
    # Added fields exist in the current schema; removed fields in the previous one.
    cur_index = _index_fields(schema_json)
    prev_index = _index_fields(previous_schema)
    added_pairs = [(o, p) for o, ps in getattr(diff, "added_fields", {}).items() for p in ps]
    removed_pairs = [(o, p) for o, ps in getattr(diff, "removed_fields", {}).items() for p in ps]
    sections.append(_drift_field_table("New Fields", added_pairs, cur_index, "badge-success"))
    sections.append(_drift_field_table("Removed Fields", removed_pairs, prev_index, "badge-danger"))

    # Type changes (field exists in both runs → show before/after distributions)
    type_changes = getattr(diff, "type_changes", [])
    if type_changes:
        rows = "".join(
            f"""<tr>
                <td><span class="object-name">{html.escape(c.get('object',''))}</span></td>
                <td><code>{html.escape(c.get('field',''))}</code></td>
                <td><span class="badge badge-info">{html.escape(', '.join(c.get('old_types', [])))}</span>
                    &nbsp;→&nbsp;
                    <span class="badge badge-warning">{html.escape(', '.join(c.get('new_types', [])))}</span></td>
                <td>{_before_after_dist(c.get('object',''), c.get('field',''), prev_index, cur_index)}</td>
            </tr>"""
            for c in type_changes
        )
        sections.append(f"""
            <div class="card">
                <div class="card-header"><h3>Type Changes
                    <span class="badge badge-danger">{len(type_changes)}</span></h3></div>
                <div class="card-body"><div class="table-container">
                    <table class="data-table sortable drift-table"><thead><tr>
                    <th>Object</th><th>Field</th><th>Type change</th><th>Value Distribution</th>
                </tr></thead><tbody>{rows}</tbody></table></div></div>
            </div>
        """)

    # Coverage changes (field exists in both runs → show before/after distributions)
    cov_changes = getattr(diff, "coverage_changes", [])
    if cov_changes:
        rows = ""
        for c in cov_changes:
            old, new = c.get("old_coverage", 0.0), c.get("new_coverage", 0.0)
            delta = new - old
            arrow = "▲" if delta > 0 else "▼"
            color = "var(--color-success)" if delta > 0 else "var(--color-danger)"
            rows += f"""<tr>
                <td><span class="object-name">{html.escape(c.get('object',''))}</span></td>
                <td><code>{html.escape(c.get('field',''))}</code></td>
                <td class="text-center">{old:.0f}%</td>
                <td class="text-center">{new:.0f}%</td>
                <td class="text-center" style="color:{color};font-weight:600">{arrow} {abs(delta):.0f} pts</td>
                <td>{_before_after_dist(c.get('object',''), c.get('field',''), prev_index, cur_index)}</td>
            </tr>"""
        sections.append(f"""
            <div class="card">
                <div class="card-header"><h3>Coverage Shifts
                    <span class="badge badge-warning">{len(cov_changes)}</span></h3></div>
                <div class="card-body"><div class="table-container">
                    <table class="data-table sortable drift-table"><thead><tr>
                    <th>Object</th><th>Field</th><th class="text-center">Was</th>
                    <th class="text-center">Now</th><th class="text-center">Change</th>
                    <th>Value Distribution</th>
                </tr></thead><tbody>{rows}</tbody></table></div></div>
            </div>
        """)

    # Cardinality changes (best-effort generic rendering)
    card_changes = getattr(diff, "cardinality_changes", [])
    if card_changes:
        items = [
            f"{c.get('object','')}.{c.get('field','')}: "
            f"{c.get('old_distinct','?')} → {c.get('new_distinct','?')}"
            for c in card_changes
        ]
        sections.append(_list_card("Cardinality Changes", items, "badge-warning"))

    drift_css = """
        <style>
            .drift-list { list-style:none; margin:0; padding:0; display:flex;
                          flex-wrap:wrap; gap:var(--space-sm); }
            .drift-list li { margin:0; }
            .mini-dist { display:flex; flex-direction:column; gap:3px; min-width:220px; }
            .mini-dist-row { display:flex; align-items:center; gap:var(--space-sm);
                             font-size:.8rem; }
            .mini-dist-label { flex:0 0 90px; white-space:nowrap; overflow:hidden;
                               text-overflow:ellipsis; color:var(--text-secondary); }
            .mini-dist-bar { flex:1; height:8px; background:var(--bg-tertiary);
                             border-radius:var(--radius-sm); overflow:hidden; }
            .mini-dist-fill { display:block; height:100%; background:var(--accent-primary); }
            .mini-dist-count { flex:0 0 auto; color:var(--text-secondary);
                               font-variant-numeric:tabular-nums; }
            .mini-dist-more { font-size:.75rem; color:var(--text-tertiary); }
            .ba-dist { display:flex; gap:var(--space-md); }
            .ba-col { flex:1; min-width:0; }
            .ba-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.04em;
                        color:var(--text-tertiary); margin-bottom:2px; }
        </style>
    """
    return drift_css + "\n".join(s for s in sections if s)


def _render_quality_tab(quality_data: Any) -> str:
    """Render the Data Quality Index tab content."""
    if not quality_data:
        return "<p>Data quality analysis not available.</p>"

    radar_html = _render_schema_dimensions_radar(quality_data.schema_dimensions)

    rows = []
    for obj in quality_data.objects:
        # Build dimension list dynamically — core + any extras (accuracy, granularity, …)
        core = [
            ("Completeness", obj.completeness),
            ("Consistency", obj.consistency),
            ("Uniqueness", obj.uniqueness),
            ("Validity", obj.validity),
        ]
        if obj.timeliness:
            core.append(("Timeliness", obj.timeliness))
        for name, dim in obj.extra_dimensions.items():
            core.append((name.capitalize(), dim))

        dim_bars = []
        for dim_name, dim in core:
            color = _get_score_color(dim.score)
            dim_bars.append(f"""
                <div class="dimension-row">
                    <span class="dimension-name">{dim_name}</span>
                    <div class="dimension-bar-container">
                        <div class="dimension-bar" style="width: {dim.score}%; background: {color}"></div>
                    </div>
                    <span class="dimension-score">{dim.score:.0f}</span>
                </div>
            """)

        grade = get_quality_grade(obj.dqi)
        color_class = get_quality_color(obj.dqi)

        rows.append(f"""
            <div class="quality-card {color_class}">
                <div class="quality-header">
                    <h4>{html.escape(obj.object_name)}</h4>
                    <div class="quality-score">
                        <span class="score-value">{obj.dqi:.1f}</span>
                        <span class="score-grade">{grade}</span>
                    </div>
                </div>
                <div class="quality-dimensions">
                    {"".join(dim_bars)}
                </div>
            </div>
        """)

    return f"""
        <div class="quality-overview">
            <div class="overall-dqi">
                <div class="overall-dqi-circle {get_quality_color(quality_data.overall_dqi)}">
                    <span class="overall-score">{quality_data.overall_dqi:.1f}</span>
                    <span class="overall-label">Overall DQI</span>
                </div>
            </div>
            {radar_html}
        </div>
        <div class="quality-grid">
            {"".join(rows)}
        </div>
        {_render_attention_section(quality_data.objects)}
    """


def _render_attention_section(objects: list) -> str:
    """Render a standalone section grouping fields needing attention per object."""
    blocks = []
    total_problem = 0
    for obj in objects:
        problem_fields = sorted(
            [f for f in obj.fields if f.overall < 70],
            key=lambda f: f.overall,
        )
        if not problem_fields:
            continue
        total_problem += len(problem_fields)
        items = []
        for f in problem_fields:
            items.append(f"""
                <div class="problem-field">
                    <span class="problem-path">{html.escape(f.path)}</span>
                    <span class="problem-score">{f.overall:.0f}</span>
                    <span class="problem-issues">{', '.join(f.issues[:3])}</span>
                </div>
            """)
        blocks.append(f"""
            <div class="attention-block">
                <div class="attention-block-header">
                    <h4>{html.escape(obj.object_name)}</h4>
                    <span class="badge badge-warn">{len(problem_fields)} field{'s' if len(problem_fields) != 1 else ''}</span>
                </div>
                <div class="problem-fields">{"".join(items)}</div>
            </div>
        """)

    if not blocks:
        return """
            <div class="card attention-section">
                <div class="card-header"><h3>⚠️ Fields Needing Attention</h3></div>
                <div class="card-body"><div class="no-issues">✅ No fields below the quality threshold across any object.</div></div>
            </div>
        """

    return f"""
        <div class="card attention-section">
            <div class="card-header">
                <h3>⚠️ Fields Needing Attention</h3>
                <span class="card-subtitle">{total_problem} field{'s' if total_problem != 1 else ''} scoring below 70 across {len(blocks)} object{'s' if len(blocks) != 1 else ''}</span>
            </div>
            <div class="card-body">
                <div class="attention-grid">
                    {"".join(blocks)}
                </div>
            </div>
        </div>
    """


def _get_score_color(score: float) -> str:
    """Get color for a quality score."""
    if score >= 90:
        return "var(--color-success)"
    if score >= 80:
        return "var(--color-info)"
    if score >= 70:
        return "var(--color-warning)"
    if score >= 60:
        return "var(--color-caution)"
    return "var(--color-danger)"


# ─── Schema Dimensions radar ────────────────────────────────────────────────

def _render_schema_dimensions_radar(dimensions: dict[str, float]) -> str:
    """Render an SVG radar chart for the schema-level dimension scores."""
    if not dimensions:
        return ""
    items = sorted(dimensions.items())
    n = len(items)
    if n < 3:
        # Degenerate radar — show as bars instead
        bars = "".join(
            f'<div class="dimension-row"><span class="dimension-name">{html.escape(k.capitalize())}</span>'
            f'<div class="dimension-bar-container"><div class="dimension-bar" '
            f'style="width:{v:.0f}%;background:{_get_score_color(v)}"></div></div>'
            f'<span class="dimension-score">{v:.0f}</span></div>'
            for k, v in items
        )
        return f'<div class="schema-dimensions"><h4>Schema Dimensions</h4>{bars}</div>'

    import math
    cx, cy, r = 230, 170, 115
    width, height = 460, 340
    angles = [(-math.pi / 2) + (2 * math.pi * i / n) for i in range(n)]

    # Ring guides
    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r * pct / 100:.1f}" fill="none" '
        f'stroke="var(--border-primary)" stroke-dasharray="2 4" opacity="0.5" />'
        for pct in (25, 50, 75, 100)
    )
    # Axes + labels
    axes = []
    labels = []
    for (name, score), angle in zip(items, angles):
        x2 = cx + r * math.cos(angle)
        y2 = cy + r * math.sin(angle)
        axes.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="var(--border-primary)" opacity="0.6" />'
        )
        lx = cx + (r + 22) * math.cos(angle)
        ly = cy + (r + 22) * math.sin(angle)
        anchor = "middle" if abs(math.cos(angle)) < 0.3 else ("start" if math.cos(angle) > 0 else "end")
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" fill="var(--text-secondary)" font-size="11">'
            f'<tspan font-weight="600">{html.escape(name.capitalize())}</tspan>'
            f'<tspan dx="4" fill="var(--accent-primary)" font-weight="700">{score:.0f}</tspan>'
            f'</text>'
        )

    # Polygon of scores
    pts = []
    for (name, score), angle in zip(items, angles):
        rr = r * max(0.0, min(100.0, score)) / 100
        pts.append(f"{cx + rr * math.cos(angle):.1f},{cy + rr * math.sin(angle):.1f}")
    poly = " ".join(pts)

    return f"""
        <div class="schema-dimensions">
            <h4>Schema Dimensions</h4>
            <svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px;height:auto;"
                 role="img" aria-label="Schema dimensions radar">
                {rings}
                {"".join(axes)}
                <polygon points="{poly}" fill="var(--accent-primary)" fill-opacity="0.25"
                         stroke="var(--accent-primary)" stroke-width="2" />
                {"".join(labels)}
            </svg>
        </div>
    """


# ─── Insights / SWOT / Recommendations / AI-readiness ──────────────────────

def _render_insights_tab(insights_data: dict[str, Any], joins_data: dict[str, Any]) -> str:
    if not insights_data:
        return "<p>No insights generated.</p>"

    story = insights_data.get("data_story", "")
    swot = insights_data.get("swot", {}) or {}
    recs = insights_data.get("recommendations", []) or []
    ai_ready = insights_data.get("ai_readiness", {}) or {}
    universe = insights_data.get("content_universe", {}) or {}
    locale_dims = insights_data.get("locale_dimensions", {}) or {}

    swot_card = lambda title, color, items: (
        f'<div class="swot-card swot-{color}"><h4>{html.escape(title)}</h4>'
        f'<ul>{"".join(f"<li>{html.escape(i)}</li>" for i in items) or "<li>—</li>"}</ul></div>'
    )
    swot_grid = (
        '<div class="swot-grid">'
        + swot_card("Strengths", "good", swot.get("strengths", []))
        + swot_card("Weaknesses", "warn", swot.get("weaknesses", []))
        + swot_card("Opportunities", "info", swot.get("opportunities", []))
        + swot_card("Threats", "danger", swot.get("threats", []))
        + "</div>"
    )

    rec_rows = "".join(
        f'<tr><td><span class="severity sev-{html.escape(r.get("severity", "low"))}">'
        f'{html.escape(r.get("severity", "low").upper())}</span></td>'
        f'<td>{html.escape(r.get("category", ""))}</td>'
        f'<td>{html.escape(r.get("action", ""))}</td></tr>'
        for r in recs
    )
    rec_table = (
        '<table class="data-table"><thead><tr><th>Severity</th><th>Category</th><th>Action</th></tr></thead>'
        f'<tbody>{rec_rows}</tbody></table>'
    )

    ai_rows = "".join(
        f'<tr><td><span class="severity sev-{_ai_status_to_sev(c["status"])}">'
        f'{html.escape(c["status"].upper())}</span></td>'
        f'<td>{html.escape(c["name"])}</td>'
        f'<td>{html.escape(c["recommendation"])}</td></tr>'
        for c in ai_ready.get("checks", [])
    )
    ai_table = (
        f'<div class="ai-readiness-header">'
        f'<h4>AI-Consumption Readiness</h4>'
        f'<div class="ai-readiness-score">Readiness score: <strong>{ai_ready.get("score", 0):.1f}/100</strong></div>'
        f'</div>'
        '<table class="data-table"><thead><tr><th>Status</th><th>Check</th><th>Recommendation</th></tr></thead>'
        f'<tbody>{ai_rows}</tbody></table>'
    )

    universe_html = _render_content_universe(universe)
    locale_html = _render_locale_dimensions(locale_dims)

    return f"""
        <div class="insights-section">
            <div class="data-story">
                <h3>📖 Data Story</h3>
                <p>{html.escape(story)}</p>
            </div>
            {universe_html}
            {locale_html}
            <h3>🧭 SWOT Analysis</h3>
            {swot_grid}
            <h3>🛠 Recommendations</h3>
            {rec_table}
            <h3>🤖 AI Readiness</h3>
            {ai_table}
        </div>
    """


def _render_ai_insights_tab(ai_insights: dict[str, Any]) -> str:
    """Render the AI Insights tab — model-generated findings and recommendations."""
    if not ai_insights or not ai_insights.get("enabled"):
        return (
            '<div class="ai-insights-empty">'
            "<p>AI insights were not generated for this run.</p>"
            f"<p class=\"ai-insights-hint\">{html.escape(str(ai_insights.get('error', '')))}</p>"
            "</div>"
        )

    provider = html.escape(str(ai_insights.get("provider", "AI")))
    model = html.escape(str(ai_insights.get("model") or "default"))
    auth_mode = html.escape(str(ai_insights.get("auth_mode", "")))

    section_defs = [
        ("data_story", "Data Story", "📖", "narrative"),
        ("unique_id_patterns", "Unique ID Patterns", "🔑", "patterns"),
        ("key_domain_fields", "Key & Domain Fields", "🏷️", "domain"),
        ("structural_value_patterns", "Structural & Value Patterns", "📐", "structure"),
        ("cross_object_patterns", "Cross-Object Patterns", "🔗", "cross"),
        ("domain_field_assessments", "Domain Assessments", "🎯", "assess"),
        ("hidden_value_relationships", "Hidden Relationships", "💎", "hidden"),
        ("quality_assessment", "Quality Assessment", "✅", "quality"),
    ]

    sections = ai_insights.get("sections") or {}
    cards: list[str] = []
    for key, title, icon, css_class in section_defs:
        body = sections.get(key) or ai_insights.get(key)
        if not body:
            continue
        if isinstance(body, list):
            inner = "".join(
                f"<li>{html.escape(str(item) if not isinstance(item, dict) else '; '.join(f'{k}: {v}' for k, v in item.items()))}</li>"
                for item in body
            )
            content = f"<ul class=\"ai-insight-list\">{inner}</ul>"
        elif isinstance(body, dict):
            content = "".join(
                f"<p><strong>{html.escape(str(k))}:</strong> {html.escape(str(v))}</p>"
                for k, v in body.items()
            )
        else:
            paragraphs = [html.escape(p.strip()) for p in str(body).split("\n") if p.strip()]
            content = "".join(f"<p>{p}</p>" for p in paragraphs) or f"<p>{html.escape(str(body))}</p>"

        cards.append(
            f'<article class="ai-insight-card ai-insight-{css_class}">'
            f'<header><span class="ai-insight-icon">{icon}</span>'
            f"<h4>{html.escape(title)}</h4></header>"
            f'<div class="ai-insight-body">{content}</div></article>'
        )

    recs = ai_insights.get("recommendations") or []
    rec_cards = ""
    if recs:
        rec_items = []
        for r in recs:
            if isinstance(r, dict):
                sev = html.escape(r.get("severity", "low"))
                cat = html.escape(r.get("category", "general"))
                action = html.escape(r.get("action", ""))
                rec_items.append(
                    f'<div class="ai-rec-card sev-{sev}">'
                    f'<span class="ai-rec-severity">{sev.upper()}</span>'
                    f'<span class="ai-rec-category">{cat}</span>'
                    f'<p class="ai-rec-action">{action}</p></div>'
                )
            else:
                rec_items.append(f'<div class="ai-rec-card"><p>{html.escape(str(r))}</p></div>')
        rec_cards = (
            '<section class="ai-recommendations">'
            "<h3>🛠 AI Recommendations</h3>"
            f'<div class="ai-rec-grid">{"".join(rec_items)}</div></section>'
        )

    return f"""
        <div class="ai-insights-section">
            <div class="ai-insights-banner">
                <div class="ai-insights-badge">✨ AI-Generated</div>
                <p class="ai-insights-meta">
                    Provider: <strong>{provider}</strong> ·
                    Auth: <strong>{auth_mode}</strong> ·
                    Model: <code>{model}</code>
                </p>
                <p class="ai-insights-disclaimer">
                    Findings are model-generated from schema profiling signals.
                    Validate before production or compliance decisions.
                </p>
            </div>
            <div class="ai-insight-grid">{"".join(cards) or "<p>No section content returned.</p>"}</div>
            {rec_cards}
        </div>
    """


def _render_locale_dimensions(locale_dims: dict[str, Any]) -> str:
    """Render the locale/geographic dimensions section."""
    if not locale_dims:
        return ""
    
    has_loc = locale_dims.get("has_localization", False)
    has_geo = locale_dims.get("has_geo", False)
    has_curr = locale_dims.get("has_currency", False)
    
    if not (has_loc or has_geo or has_curr):
        return ""
    
    sections = []
    
    # Locale-keyed fields (nested objects with locale keys)
    locale_keyed = locale_dims.get("locale_keyed_fields", [])
    if locale_keyed:
        rows = "".join(
            f'<tr><td>{html.escape(f["object"])}</td>'
            f'<td class="field-path">{html.escape(f["path"])}</td>'
            f'<td>{", ".join(html.escape(loc) for loc in f.get("locales", [])[:8])}'
            f'{"..." if len(f.get("locales", [])) > 8 else ""}</td>'
            f'<td><span class="badge badge-info">{f.get("locale_count", 0)}</span></td></tr>'
            for f in locale_keyed
        )
        sections.append(f'''
            <div class="locale-section">
                <h4>🌐 Locale-Keyed Fields ({len(locale_keyed)})</h4>
                <p class="section-desc">Fields containing nested locale objects (e.g., title.en, title.fr)</p>
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Field</th><th>Locales</th><th>Count</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        ''')
    
    # Locale/language code fields
    locale_fields = locale_dims.get("locale_fields", [])
    if locale_fields:
        rows = "".join(
            f'<tr><td>{html.escape(f["object"])}</td>'
            f'<td class="field-path">{html.escape(f["path"])}</td>'
            f'<td>{f.get("conformance", 0)*100:.0f}%</td>'
            f'<td>{", ".join(html.escape(str(s)) for s in f.get("samples", []))}</td></tr>'
            for f in locale_fields
        )
        sections.append(f'''
            <div class="locale-section">
                <h4>🗣️ Language/Locale Fields ({len(locale_fields)})</h4>
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Field</th><th>Conformance</th><th>Samples</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        ''')
    
    # Country code fields
    country_fields = locale_dims.get("country_fields", [])
    if country_fields:
        rows = "".join(
            f'<tr><td>{html.escape(f["object"])}</td>'
            f'<td class="field-path">{html.escape(f["path"])}</td>'
            f'<td>{f.get("conformance", 0)*100:.0f}%</td>'
            f'<td>{", ".join(html.escape(str(s)) for s in f.get("samples", []))}</td></tr>'
            for f in country_fields
        )
        sections.append(f'''
            <div class="locale-section">
                <h4>🌍 Country Code Fields ({len(country_fields)})</h4>
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Field</th><th>Conformance</th><th>Samples</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        ''')
    
    # Currency fields
    currency_fields = locale_dims.get("currency_fields", [])
    if currency_fields:
        rows = "".join(
            f'<tr><td>{html.escape(f["object"])}</td>'
            f'<td class="field-path">{html.escape(f["path"])}</td>'
            f'<td>{f.get("conformance", 0)*100:.0f}%</td>'
            f'<td>{", ".join(html.escape(str(s)) for s in f.get("samples", []))}</td></tr>'
            for f in currency_fields
        )
        sections.append(f'''
            <div class="locale-section">
                <h4>💰 Currency Fields ({len(currency_fields)})</h4>
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Field</th><th>Conformance</th><th>Samples</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        ''')
    
    # Summary of detected values
    locales = locale_dims.get("locales_found", [])
    countries = locale_dims.get("countries_found", [])
    currencies = locale_dims.get("currencies_found", [])
    
    summary_items = []
    if locales:
        locale_str = ", ".join(f"{loc}" for loc, _ in locales[:10])
        if len(locales) > 10:
            locale_str += f" (+{len(locales) - 10} more)"
        summary_items.append(f'<span class="dim-badge"><strong>Locales:</strong> {html.escape(locale_str)}</span>')
    if countries:
        country_str = ", ".join(f"{c}" for c, _ in countries[:15])
        if len(countries) > 15:
            country_str += f" (+{len(countries) - 15} more)"
        summary_items.append(f'<span class="dim-badge"><strong>Countries:</strong> {html.escape(country_str)}</span>')
    if currencies:
        curr_str = ", ".join(f"{c}" for c, _ in currencies)
        summary_items.append(f'<span class="dim-badge"><strong>Currencies:</strong> {html.escape(curr_str)}</span>')
    
    summary_html = ""
    if summary_items:
        summary_html = f'''
            <div class="dims-summary">
                {"".join(summary_items)}
            </div>
        '''
    
    return f'''
        <div class="locale-dimensions-section">
            <h3>🌍 Locale & Geographic Dimensions</h3>
            {summary_html}
            {"".join(sections)}
        </div>
        <style>
            .locale-dimensions-section {{ margin: var(--space-lg) 0; }}
            .locale-section {{ margin: var(--space-md) 0; }}
            .locale-section h4 {{ margin-bottom: var(--space-sm); }}
            .section-desc {{ color: var(--text-secondary); font-size: 0.875rem; margin-bottom: var(--space-sm); }}
            .dims-summary {{
                display: flex; flex-wrap: wrap; gap: var(--space-md);
                padding: var(--space-sm) var(--space-md);
                background: var(--bg-secondary); border-radius: var(--radius-md);
                margin-bottom: var(--space-md);
            }}
            .dim-badge {{ font-size: 0.875rem; color: var(--text-secondary); }}
            .dim-badge strong {{ color: var(--text-primary); }}
        </style>
    '''


def _ai_status_to_sev(status: str) -> str:
    return {"pass": "low", "warn": "medium", "fail": "high"}.get(status, "low")


def _render_content_universe(universe: dict[str, Any]) -> str:
    segments = universe.get("segments") or []
    if not segments:
        return ""
    import math
    total = universe.get("total_records", 0) or 1
    palette = [
        "#4f8cff", "#ff7f50", "#7ed957", "#ffd166", "#c77dff",
        "#06d6a0", "#ef476f", "#118ab2", "#f78c6b", "#8ac926",
    ]
    cx, cy, r_outer, r_inner = 130, 130, 110, 60
    paths = []
    legend = []
    angle = -math.pi / 2
    for i, seg in enumerate(segments):
        portion = seg["count"] / total
        sweep = portion * 2 * math.pi
        a2 = angle + sweep
        large = 1 if sweep > math.pi else 0
        x1 = cx + r_outer * math.cos(angle); y1 = cy + r_outer * math.sin(angle)
        x2 = cx + r_outer * math.cos(a2);   y2 = cy + r_outer * math.sin(a2)
        x3 = cx + r_inner * math.cos(a2);   y3 = cy + r_inner * math.sin(a2)
        x4 = cx + r_inner * math.cos(angle); y4 = cy + r_inner * math.sin(angle)
        color = palette[i % len(palette)]
        paths.append(
            f'<path d="M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {large} 1 {x2:.1f} {y2:.1f} '
            f'L {x3:.1f} {y3:.1f} A {r_inner} {r_inner} 0 {large} 0 {x4:.1f} {y4:.1f} Z" '
            f'fill="{color}" />'
        )
        legend.append(
            f'<div class="legend-row"><span class="legend-swatch" style="background:{color}"></span>'
            f'{html.escape(seg["label"])} — {seg["count"]:,} ({seg["pct"]:.1f}%)</div>'
        )
        angle = a2

    return f"""
        <div class="content-universe">
            <h3>🌌 Content Universe ({html.escape(universe.get("field") or "")})</h3>
            <div class="universe-layout">
                <svg viewBox="0 0 260 260" width="260" height="260" role="img" aria-label="Content universe donut">
                    {"".join(paths)}
                </svg>
                <div class="universe-legend">{"".join(legend)}</div>
            </div>
        </div>
    """


# ─── Patterns tab ──────────────────────────────────────────────────────────

def _render_patterns_tab(patterns_data: dict[str, Any]) -> str:
    if not patterns_data or not patterns_data.get("by_object"):
        return "<p>No value patterns detected. Try increasing the sample size.</p>"

    counts = patterns_data.get("pattern_counts", {}) or {}
    counts_html = "".join(
        f'<span class="pattern-pill">{html.escape(p)}: {n}</span>'
        for p, n in sorted(counts.items(), key=lambda kv: -kv[1])
    )

    idents = patterns_data.get("identifier_fields", [])
    ident_rows = "".join(
        f'<tr><td>{html.escape(i["object"])}</td><td class="field-path">{html.escape(i["path"])}</td>'
        f'<td>{html.escape(i["pattern"] or "")}</td><td>{i["distinct"]:,}</td><td>{i["presence"]:,}</td></tr>'
        for i in idents
    )

    obj_sections = []
    for obj_name, rows in patterns_data["by_object"].items():
        body = "".join(
            f'<tr><td class="field-path">{html.escape(r["path"])}</td>'
            f'<td><span class="pattern-pill">{html.escape(r["dominant_pattern"] or "—")}</span></td>'
            f'<td>{(r["dominant_conformance"] * 100):.0f}%</td>'
            f'<td>{html.escape(", ".join(m["pattern"] for m in r["matches"][1:4]))}</td>'
            f'<td>{html.escape(", ".join(str(v) for v in (r["matches"][0]["sample_values"][:3] if r["matches"] else [])))}</td>'
            f'</tr>'
            for r in rows
        )
        obj_sections.append(
            f'<div class="pii-object-section"><h4>{html.escape(obj_name)}</h4>'
            '<table class="data-table"><thead><tr><th>Field</th><th>Dominant Pattern</th>'
            '<th>Conformance</th><th>Also Matches</th><th>Sample Values</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>'
        )

    return f"""
        <div class="patterns-section">
            <h3>Detected Patterns</h3>
            <div class="pill-row">{counts_html}</div>
            <h3>Identifier-Shaped Fields ({len(idents)})</h3>
            <table class="data-table">
                <thead><tr><th>Object</th><th>Field</th><th>Pattern</th><th>Distinct</th><th>Presence</th></tr></thead>
                <tbody>{ident_rows or '<tr><td colspan="5">None detected.</td></tr>'}</tbody>
            </table>
            {"".join(obj_sections)}
        </div>
    """


# ─── Join Keys tab ─────────────────────────────────────────────────────────

def _render_joins_tab(joins_data: dict[str, Any], objects: list | None = None) -> str:
    if not joins_data:
        return "<p>No join analysis available.</p>"

    pk_rows = "".join(
        f'<tr><td>{html.escape(p["object"])}</td>'
        f'<td>{"Composite" if p["is_composite"] else "Single"}</td>'
        f'<td class="field-path">{html.escape(" + ".join(p["fields"]))}</td>'
        f'<td>{p["coverage"] * 100:.0f}%</td>'
        f'<td>{p["distinct_ratio"] * 100:.0f}%</td>'
        f'<td>{html.escape(p["rationale"])}</td></tr>'
        for p in joins_data.get("primary_keys", [])
    )

    nested_rows = "".join(
        f'<tr><td>{html.escape(n["object"])}</td>'
        f'<td class="field-path">{html.escape(n["parent_path"])}</td>'
        f'<td>{n["child_count"]}</td>'
        f'<td>{n["avg_coverage"] * 100:.0f}%</td>'
        f'<td class="field-path">{html.escape(", ".join(n["children"]))}</td></tr>'
        for n in joins_data.get("nested_relationships", [])
    )

    all_joins = joins_data.get("all_value_joins", [])
    if not all_joins:
        all_joins = joins_data.get("same_path_fk", []) + joins_data.get("value_overlap", [])
        all_joins.sort(key=lambda c: -c.get("confidence", 0))

    value_confirmed_count = sum(1 for c in all_joins if "value_confirmed" in c.get("kind", ""))
    structural_count = sum(1 for c in all_joins if "structural" in c.get("kind", ""))

    def _join_row(c: dict) -> str:
        kind = c.get("kind", "")
        is_structural = "structural" in kind
        badge_cls = "badge-info" if is_structural else ("badge-good" if c["confidence"] >= 0.7 else "badge-warn")
        kind_label = kind.replace("_", " ")
        row_style = ' style="opacity:0.88"' if is_structural else ""
        caution_icon = " ⚠" if is_structural else ""
        return (
            f'<tr{row_style}>'
            f'<td class="field-path">{html.escape(c["left"])}</td>'
            f'<td class="field-path">{html.escape(c["right"])}</td>'
            f'<td><span class="badge {badge_cls}">{c["confidence"] * 100:.0f}%</span></td>'
            f'<td><span class="type-badge">{kind_label}{caution_icon}</span></td>'
            f'<td style="font-size:0.8rem;color:var(--text-tertiary)">'
            f'{html.escape("; ".join(c.get("evidence", [])[:2]))}</td>'
            f'</tr>'
        )

    join_rows = "".join(_join_row(c) for c in all_joins)

    # ── Intra-object duplicate / redundant fields ──────────────────────────
    duplicates = joins_data.get("intra_duplicates", [])

    def _dup_row(d: dict) -> str:
        rec = d.get("recommend", "either")
        keep_a = rec in ("a", "either")
        keep_b = rec in ("b", "either")
        ka = ' style="font-weight:700;color:var(--color-success)"' if rec == "a" else ""
        kb = ' style="font-weight:700;color:var(--color-success)"' if rec == "b" else ""
        is_struct = d.get("kind") == "structural_duplicate"
        badge_cls = "badge-info" if is_struct else ("badge-good" if d["confidence"] >= 0.7 else "badge-warn")
        kind_label = ("structural ⚠" if is_struct else f"value match {d.get('jaccard', 0):.0%}")
        ev = html.escape(d.get("evidence", [""])[0])
        rec_html = (
            f'<span{ka}>{html.escape(d["field_a"])}</span>'
            if rec == "a" else
            f'<span{kb}>{html.escape(d["field_b"])}</span>'
            if rec == "b" else
            "either"
        )
        return (
            f'<tr>'
            f'<td>{html.escape(d["object"])}</td>'
            f'<td class="field-path">{html.escape(d["field_a"])}</td>'
            f'<td class="field-path">{html.escape(d["field_b"])}</td>'
            f'<td><span class="badge {badge_cls}">{kind_label}</span></td>'
            f'<td>{d["coverage_a"] * 100:.0f}%</td>'
            f'<td>{d["coverage_b"] * 100:.0f}%</td>'
            f'<td class="field-path">{rec_html}</td>'
            f'<td style="font-size:0.8rem;color:var(--text-tertiary)">{ev}</td>'
            f'</tr>'
        )

    dup_rows = "".join(_dup_row(d) for d in duplicates)

    pk_count     = len(joins_data.get("primary_keys", []))
    nested_count = len(joins_data.get("nested_relationships", []))
    dup_count    = len(duplicates)

    # ── Common fields across objects (formerly the standalone Cross-Object tab) ──
    common_fields: list[tuple[str, list[str]]] = []
    if objects and len(objects) >= 2:
        field_to_objects: dict[str, list[str]] = {}
        for obj in objects:
            obj_name = obj.get("object", "Unknown")
            for field in obj.get("fields", []):
                path = field.get("path", "")
                if path not in field_to_objects:
                    field_to_objects[path] = []
                field_to_objects[path].append(obj_name)
        common_fields = [(p, objs) for p, objs in field_to_objects.items() if len(objs) > 1]
        common_fields.sort(key=lambda x: -len(x[1]))

    common_rows_list = []
    for p, objs in common_fields[:50]:
        badges = " ".join(f'<span class="object-badge">{html.escape(o)}</span>' for o in objs)
        common_rows_list.append(
            f'<tr>'
            f'<td class="field-path">{html.escape(p)}</td>'
            f'<td class="text-center">{len(objs)}</td>'
            f'<td>{badges}</td>'
            f'</tr>'
        )
    common_rows = "".join(common_rows_list)

    subtabs = [
        ("jk-keys",    f"🔑 Keys",           f"({pk_count})"),
        ("jk-joins",   f"🔗 Join Candidates", f"({len(all_joins)})"),
        ("jk-common",  f"🔀 Common Fields",   f"({len(common_fields)})"),
        ("jk-dupes",   f"🔄 Duplicates",      f"({dup_count})"),
        ("jk-nested",  f"🪺 Nested",          f"({nested_count})"),
    ]

    tab_btns = "\n".join(
        f'<button class="jk-subtab-btn{"  jk-active" if i == 0 else ""}" '
        f'data-target="{sid}" onclick="jkSwitch(this)">'
        f'<span class="jk-label">{label}</span>'
        f'<span class="jk-count">{count}</span>'
        f'</button>'
        for i, (sid, label, count) in enumerate(subtabs)
    )

    return f"""
        <div class="joins-section">
            <nav class="jk-subtab-bar">{tab_btns}</nav>

            <div id="jk-keys" class="jk-pane">
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Type</th><th>Fields</th><th>Coverage</th>
                    <th>Distinct Ratio</th><th>Rationale</th></tr></thead>
                    <tbody>{pk_rows or '<tr><td colspan="6">No primary key candidates detected.</td></tr>'}</tbody>
                </table>
            </div>

            <div id="jk-joins" class="jk-pane" style="display:none">
                <p style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:var(--space-md)">
                    <strong style="color:var(--color-success)">Value-confirmed ({value_confirmed_count})</strong>: Jaccard overlap verified on sampled values.
                    &nbsp;|&nbsp;
                    <strong style="color:var(--color-info)">Structural ⚠ ({structural_count})</strong>: High-cardinality identifier fields — value comparison
                    not possible from stored sample cap; run with <code>--max-distinct 500</code> to confirm.
                    Audit, temporal, and noise fields are excluded.
                </p>
                <table class="data-table">
                    <thead><tr><th>Left</th><th>Right</th><th>Confidence</th><th>Kind</th><th>Evidence</th></tr></thead>
                    <tbody>{join_rows or '<tr><td colspan="5">No join candidates found.</td></tr>'}</tbody>
                </table>
            </div>

            <div id="jk-dupes" class="jk-pane" style="display:none">
                <p style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:var(--space-md)">
                    Fields within the same object whose value sets show strong overlap —
                    likely redundant copies. <strong style="color:var(--color-success)">Highlighted field</strong> is the recommended one to keep (better coverage, fewer nulls).
                    Audit and noise fields are excluded.
                </p>
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Field A</th><th>Field B</th><th>Match</th>
                    <th>Cov A</th><th>Cov B</th><th>Keep</th><th>Evidence</th></tr></thead>
                    <tbody>{dup_rows or '<tr><td colspan="8">No duplicate field patterns detected.</td></tr>'}</tbody>
                </table>
            </div>

            <div id="jk-common" class="jk-pane" style="display:none">
                <p style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:var(--space-md)">
                    Fields present in multiple objects — potential join keys or shared attributes.
                </p>
                <table class="data-table sortable">
                    <thead><tr><th>Field Path</th><th class="text-center">Object Count</th><th>Objects</th></tr></thead>
                    <tbody>{common_rows or '<tr><td colspan="3">No common fields found across objects.</td></tr>'}</tbody>
                </table>
            </div>

            <div id="jk-nested" class="jk-pane" style="display:none">
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Parent Path</th><th>Children</th>
                    <th>Avg Coverage</th><th>Child Fields</th></tr></thead>
                    <tbody>{nested_rows or '<tr><td colspan="5">No nested relationships detected.</td></tr>'}</tbody>
                </table>
            </div>
        </div>
        <script>
        function jkSwitch(btn) {{
            var bar = btn.closest('.jk-subtab-bar');
            bar.querySelectorAll('.jk-subtab-btn').forEach(function(b) {{
                b.classList.remove('jk-active');
            }});
            btn.classList.add('jk-active');
            var section = btn.closest('.joins-section');
            section.querySelectorAll('.jk-pane').forEach(function(p) {{
                p.style.display = 'none';
            }});
            document.getElementById(btn.getAttribute('data-target')).style.display = '';
        }}
        </script>
    """


# ─── Similar Low-Cardinality Fields tab ────────────────────────────────────

def _render_dist_similarity_section(schema_json: dict | None) -> str:
    """Render the Distribution Similarity section (embedded in Distributions tab)."""
    if not schema_json:
        return ""
    return (
        '<hr style="border:none;border-top:1px solid var(--border-primary);margin:var(--space-xl) 0">'
        '<h3 style="margin-bottom:var(--space-md)">Distribution Similarity</h3>'
        '<p style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:var(--space-lg)">'
        'Low-cardinality fields shared across objects — same path, overlapping value sets.'
        '</p>'
        + _render_similar_fields_tab(schema_json)
    )


def _render_similar_fields_tab(schema_json: dict[str, Any]) -> str:
    """Group low-cardinality scalar fields that appear across multiple objects by value-set overlap."""
    from collections import defaultdict

    # Collect (object, path, distinct values, sampled, coverage) for low-cardinality scalars
    low_card: list[tuple[str, str, set[Any], int, float]] = []
    for obj in schema_json.get("objects", []):
        name = obj.get("object", "")
        sampled = obj.get("sampled", 0)
        if sampled <= 0:
            continue
        for f in obj.get("fields", []):
            types = set(f.get("types", {}).keys()) - {"null"}
            if not types or ({"object", "array"} & types):
                continue
            distinct = f.get("distinct_count_in_sample", 0)
            if distinct == 0 or distinct > 50:
                continue
            vc = f.get("value_counts") or {}
            if isinstance(vc, dict) and vc:
                vals = set(vc.keys())
            elif isinstance(vc, list) and vc:
                vals = {e[0] for e in vc if isinstance(e, (list, tuple)) and e}
            else:
                continue
            presence  = f.get("presence_count", 0)
            null_empty = f.get("null_empty_count", 0)
            eff = max(0, presence - null_empty)
            cov = eff / sampled if sampled else 0
            low_card.append((name, f.get("path", ""), vals, distinct, cov))

    if not low_card:
        return "<p>No low-cardinality fields detected.</p>"

    # Group by path signature first
    groups: dict[str, list[tuple[str, str, set[Any], int, float]]] = defaultdict(list)
    for entry in low_card:
        sig = entry[1].replace("[]", "").lower()
        groups[sig].append(entry)

    # Only keep groups present in ≥2 objects
    sections = []
    for sig, members in sorted(groups.items()):
        if len({m[0] for m in members}) < 2:
            continue

        # Build value overlap matrix
        objs = [m[0] for m in members]
        header = "<th>Value</th>" + "".join(f"<th>{html.escape(o)}</th>" for o in objs)

        all_values = sorted({v for m in members for v in m[2]}, key=lambda v: str(v))[:30]
        body_rows = []
        for v in all_values:
            cells = "".join(
                f'<td>{"✓" if v in m[2] else ""}</td>' for m in members
            )
            body_rows.append(f"<tr><td>{html.escape(str(v))}</td>{cells}</tr>")

        # Coverage / cardinality summary row
        summary_rows = []
        max_cov = max((m[4] for m in members), default=0)
        best = max(members, key=lambda m: (m[3], m[4]))
        for m in members:
            badges = []
            if m is best:
                badges.append('<span class="badge badge-good">Recommended</span>')
            if (max_cov - m[4]) > 0.4:
                badges.append('<span class="badge badge-warn">Coverage Cliff</span>')
            summary_rows.append(
                f'<tr><td>{html.escape(m[0])}</td>'
                f'<td class="field-path">{html.escape(m[1])}</td>'
                f'<td>{m[3]}</td><td>{m[4] * 100:.0f}%</td>'
                f'<td>{" ".join(badges)}</td></tr>'
            )

        sections.append(f"""
            <div class="similar-group">
                <h4 class="field-path">{html.escape(sig)}</h4>
                <table class="data-table">
                    <thead><tr><th>Object</th><th>Path</th><th>Distinct</th><th>Coverage</th><th>Tag</th></tr></thead>
                    <tbody>{"".join(summary_rows)}</tbody>
                </table>
                <details><summary>Value Overlap Matrix ({len(all_values)} value(s))</summary>
                    <table class="data-table">
                        <thead><tr>{header}</tr></thead>
                        <tbody>{"".join(body_rows)}</tbody>
                    </table>
                </details>
            </div>
        """)

    if not sections:
        return "<p>No shared low-cardinality fields across objects.</p>"

    return f'<div class="similar-fields-section">{"".join(sections)}</div>'


def _render_pii_tab(pii_data: dict, pii_summary: dict) -> str:
    """Render the PII Detection tab content."""
    if not pii_data:
        return "<p>No PII detected in the analyzed data.</p>"

    # Summary section
    by_type = pii_summary.get("by_type", {})
    type_badges = " ".join(
        f'<span class="pii-type-badge pii-{pii_type}">{pii_type}: {count}</span>'
        for pii_type, count in sorted(by_type.items(), key=lambda x: -x[1])
    )

    # High risk fields
    high_risk = pii_summary.get("high_risk_fields", [])
    high_risk_rows = []
    for field in high_risk:
        high_risk_rows.append(f"""
            <tr class="high-risk-row">
                <td>{html.escape(field['object'])}</td>
                <td class="field-path">{html.escape(field['field'])}</td>
                <td><span class="pii-type-badge pii-{field['type']}">{field['type']}</span></td>
                <td>{field['confidence']:.0%}</td>
            </tr>
        """)

    # All detections by object
    obj_sections = []
    for obj_name, detections in pii_data.items():
        detection_rows = []
        for d in detections:
            detection_rows.append(f"""
                <tr>
                    <td class="field-path">{html.escape(d.field_path)}</td>
                    <td><span class="pii-type-badge pii-{d.pii_type.value}">{d.pii_type.value}</span></td>
                    <td>{d.confidence:.0%}</td>
                </tr>
            """)

        obj_sections.append(f"""
            <div class="pii-object-section">
                <h4>{html.escape(obj_name)}</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Field</th>
                            <th>PII Type</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(detection_rows)}
                    </tbody>
                </table>
            </div>
        """)

    return f"""
        <div class="pii-summary">
            <div class="pii-summary-header">
                <h3>🔒 PII Detection Summary</h3>
                <div class="pii-total">
                    <span class="pii-total-count">{pii_summary.get('total_pii_fields', 0)}</span>
                    <span class="pii-total-label">Fields with potential PII</span>
                </div>
            </div>
            <div class="pii-types">
                {type_badges}
            </div>
        </div>

        {f'''
        <div class="card high-risk-card">
            <div class="card-header">
                <h3>🚨 High Risk Fields</h3>
            </div>
            <div class="card-body">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Object</th>
                            <th>Field</th>
                            <th>PII Type</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(high_risk_rows)}
                    </tbody>
                </table>
            </div>
        </div>
        ''' if high_risk_rows else ''}

        <div class="pii-objects">
            {"".join(obj_sections)}
        </div>
    """


def _render_field_explorer(objects: list[dict[str, Any]], pii_data: dict | None, max_distinct: int = 100) -> str:
    """Render the Field Explorer tab content."""
    # Build PII lookup
    pii_lookup: dict[str, str] = {}
    if pii_data:
        for obj_name, detections in pii_data.items():
            for d in detections:
                key = f"{obj_name}.{d.field_path}"
                pii_lookup[key] = d.pii_type.value

    rows = []
    for obj in objects:
        obj_name = html.escape(obj.get("object", "Unknown"))
        sampled = obj.get("sampled", 1) or 1

        for field in obj.get("fields", []):
            path = field.get("path", "")
            path_escaped = html.escape(path)
            presence = field.get("presence_count", 0)
            null_empty = field.get("null_empty_count", 0)
            coverage_pct = (presence / sampled * 100) if sampled > 0 else 0
            null_pct = (null_empty / presence * 100) if presence > 0 else 0

            types = field.get("types", {})
            type_badges = " ".join(
                f'<span class="type-badge type-{t}">{t}</span>'
                for t in sorted(types.keys()) if t != "null"
            )

            distinct = field.get("distinct_count_in_sample", 0)
            # Non-leaf nodes (object/array containers) have no scalar distinct values.
            non_null_types = set(types.keys()) - {"null"}
            is_container = bool(non_null_types) and non_null_types <= {"object", "array"}
            is_capped = max_distinct > 0 and distinct >= max_distinct

            # Cardinality is descriptive (how unique a field is), not a quality
            # problem — high cardinality is expected for IDs. Use a neutral scale.
            if is_container:
                cardinality_badge = '<span class="badge card-na">n/a</span>'
            elif field.get("low_cardinality", False):
                cardinality_badge = '<span class="badge card-low">Low</span>'
            elif is_capped or (presence > 0 and distinct / presence > 0.30):
                cardinality_badge = '<span class="badge card-high">High</span>'
            else:
                cardinality_badge = '<span class="badge card-med">Medium</span>'

            examples = field.get("examples", [])
            example_str = html.escape(", ".join(str(e)[:40] for e in examples[:3]))

            # PII badge
            pii_key = f"{obj.get('object', '')}.{path}"
            pii_badge = ""
            if pii_key in pii_lookup:
                pii_type = pii_lookup[pii_key]
                pii_badge = f'<span class="pii-badge">🔒 {pii_type}</span>'

            # Coverage styling
            if coverage_pct >= 90:
                cov_class = "coverage-high"
            elif coverage_pct >= 50:
                cov_class = "coverage-medium"
            else:
                cov_class = "coverage-low"

            # Null/Empty styling (highlight cells with any null/empty values)
            if null_pct == 0:
                null_class = "null-none"
            elif null_pct <= 10:
                null_class = "null-low"
            elif null_pct <= 30:
                null_class = "null-medium"
            elif null_pct < 100:
                null_class = "null-high"
            else:
                null_class = "null-critical"

            # Distinct values button — show N+ when at the tracking cap.
            # Containers (object/array) are non-leaf: show "—", not a misleading 0.
            value_counts = field.get("value_counts", {})
            obj_raw = obj.get("object", "")
            if is_container:
                distinct_btn = '<span style="color:var(--text-tertiary)">—</span>'
            else:
                distinct_label = f"{distinct}+" if (max_distinct > 0 and distinct >= max_distinct) else str(distinct)
                if value_counts:
                    distinct_btn = f'''<button class="distinct-view-btn" onclick="showDistinctValues('{obj_raw}', '{path}')">
                        <span class="icon">📊</span> {distinct_label}
                    </button>'''
                else:
                    distinct_btn = distinct_label

            rows.append(f"""
                <tr>
                    <td><span class="object-name">{obj_name}</span></td>
                    <td><span class="field-path">{path_escaped}</span> {pii_badge}</td>
                    <td><span class="coverage-badge {cov_class}">{coverage_pct:.1f}%</span></td>
                    <td class="text-center"><span class="null-cell {null_class}">{null_pct:.1f}%</span></td>
                    <td>{type_badges}</td>
                    <td class="text-center">{distinct_btn}</td>
                    <td class="text-center">{cardinality_badge}</td>
                    <td class="example-cell" title="{example_str}">{example_str}</td>
                </tr>
            """)

    return f"""
        <div class="table-controls">
            <div class="object-filter-dropdown" id="objectFilterDropdown">
                <button type="button" class="object-filter-toggle" id="objectFilterToggle" aria-expanded="false">
                    Objects: All
                </button>
                <div class="object-filter-menu" id="objectFilterMenu">
                    <label class="object-filter-option object-filter-select-all">
                        <input type="checkbox" id="objectSelectAll" checked>
                        <span>Select All</span>
                    </label>
                    <div class="object-filter-divider"></div>
                    <div id="objectFilterOptions"></div>
                </div>
            </div>
            <button class="btn btn-secondary" onclick="exportTable('field-explorer-table')">
                📥 Export CSV
            </button>
        </div>
        <div class="table-container">
            <table class="data-table sortable" id="field-explorer-table">
                <thead>
                    <tr>
                        <th>Object</th>
                        <th>Field Path</th>
                        <th>Coverage</th>
                        <th class="text-center">Null/Empty</th>
                        <th>Types</th>
                        <th class="text-center">Distinct</th>
                        <th class="text-center">Cardinality</th>
                        <th>Examples</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
    """


def _render_coverage_heatmap(objects: list[dict[str, Any]]) -> str:
    """Render the Coverage Heat Map tab content."""
    all_paths: set[str] = set()
    for obj in objects:
        for field in obj.get("fields", []):
            all_paths.add(field.get("path", ""))

    sorted_paths = sorted(all_paths)

    header_cells = ["<th class='sticky-col'>Field Path</th>"]
    for obj in objects:
        obj_name = html.escape(obj.get("object", "Unknown"))
        header_cells.append(f"<th>{obj_name}</th>")

    rows = []
    for path in sorted_paths:
        cells = [f"<td class='sticky-col field-path'>{html.escape(path)}</td>"]

        for obj in objects:
            sampled = obj.get("sampled", 1) or 1
            field = next(
                (f for f in obj.get("fields", []) if f.get("path") == path),
                None,
            )

            if field:
                presence   = field.get("presence_count", 0)
                null_empty = field.get("null_empty_count", 0)
                eff_count  = max(0, presence - null_empty)
                coverage_pct = (eff_count / sampled * 100) if sampled > 0 else 0
                color = _get_coverage_color(coverage_pct)
                text_color = "#fff" if coverage_pct < 60 else "#000"
                cells.append(
                    f"<td class='heatmap-cell' style='background-color: {color}; color: {text_color}'>"
                    f"{coverage_pct:.0f}%</td>"
                )
            else:
                cells.append("<td class='heatmap-cell heatmap-empty'>—</td>")

        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
        <div class="heatmap-legend">
            <span>Coverage:</span>
            <span class="legend-item" style="background: var(--color-danger)">0-25%</span>
            <span class="legend-item" style="background: var(--color-caution)">25-50%</span>
            <span class="legend-item" style="background: var(--color-warning)">50-75%</span>
            <span class="legend-item" style="background: var(--color-info)">75-90%</span>
            <span class="legend-item" style="background: var(--color-success)">90-100%</span>
        </div>
        <div class="heatmap-container">
            <table class="heatmap-table">
                <thead>
                    <tr>{''.join(header_cells)}</tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
    """


def _get_coverage_color(pct: float) -> str:
    """Get heatmap color for coverage percentage."""
    if pct >= 90:
        return "#22c55e"  # Green
    if pct >= 75:
        return "#3b82f6"  # Blue
    if pct >= 50:
        return "#eab308"  # Yellow
    if pct >= 25:
        return "#f97316"  # Orange
    return "#ef4444"  # Red


def _render_distributions(objects: list[dict[str, Any]], schema_json: dict | None = None, statistics_data: dict | None = None) -> str:
    """Render the Value Distributions tab content."""
    def _array_group_key(path: str) -> str:
        """Group nested fields under their nearest array ancestor path."""
        if "[]" not in path:
            return "__top_level__"

        segments = path.split(".")
        last_array_idx = max(i for i, seg in enumerate(segments) if "[]" in seg)
        return ".".join(segments[: last_array_idx + 1])

    def _group_id(group_name: str) -> str:
        if group_name == "__top_level__":
            return "dist-group-top-level"
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in group_name).strip("-")
        while "--" in safe:
            safe = safe.replace("--", "-")
        return f"dist-group-{safe}"

    grouped_charts: dict[str, list[str]] = {}

    for obj in objects:
        obj_raw = obj.get("object", "Unknown")
        obj_name = html.escape(obj_raw)
        obj_attr = html.escape(obj_raw, quote=True)

        for field in obj.get("fields", []):
            if not field.get("low_cardinality"):
                continue

            path = html.escape(field.get("path", ""))
            value_counts = field.get("value_counts", {})

            if not value_counts or len(value_counts) < 2:
                continue

            sorted_values = sorted(value_counts.items(), key=lambda x: -x[1])[:15]
            max_count = max(c for _, c in sorted_values) if sorted_values else 1
            total = sum(c for _, c in sorted_values)

            bars = []
            for value, count in sorted_values:
                pct = (count / max_count) * 100
                value_pct = (count / total) * 100
                value_escaped = html.escape(str(value)[:25])
                bars.append(f"""
                    <div class="dist-bar-row">
                        <span class="dist-label" title="{html.escape(str(value))}">{value_escaped}</span>
                        <div class="dist-bar-container">
                            <div class="dist-bar" style="width: {pct}%">
                                <span class="dist-bar-text">{count} ({value_pct:.1f}%)</span>
                            </div>
                        </div>
                    </div>
                """)

            group_key = _array_group_key(field.get("path", ""))
            grouped_charts.setdefault(group_key, []).append(f"""
                <div class="distribution-card" data-object="{obj_attr}">
                    <div class="distribution-header">
                        <span class="distribution-object">{obj_name}</span>
                        <span class="distribution-field">{path}</span>
                    </div>
                    <div class="distribution-chart">
                        {''.join(bars)}
                    </div>
                </div>
            """)

    if not grouped_charts:
        return """
            <div class="empty-state">
                <span class="empty-icon">📊</span>
                <p>No low-cardinality fields with value distributions found.</p>
            </div>
        """

    sorted_group_keys = []
    if "__top_level__" in grouped_charts:
        sorted_group_keys.append("__top_level__")
    sorted_group_keys.extend(sorted(k for k in grouped_charts.keys() if k != "__top_level__"))

    nav_links = []
    group_sections = []
    for key in sorted_group_keys:
        title = "Top-level / Non-array fields" if key == "__top_level__" else key
        gid = _group_id(key)
        nav_links.append(f'<a class="distribution-group-link" href="#{gid}">{html.escape(title)}</a>')
        group_sections.append(f"""
            <section class="distribution-group" id="{gid}">
                <h4 class="distribution-group-title">{html.escape(title)}</h4>
                <div class="distributions-grid">
                    {''.join(grouped_charts[key])}
                </div>
            </section>
        """)

    total_charts = sum(len(v) for v in grouped_charts.values())
    similarity_html = _render_similar_fields_tab(schema_json) if schema_json else "<p>No schema data available.</p>"
    stats_html = _render_statistics_tab(statistics_data) if statistics_data else "<p>No statistical analysis available.</p>"
    num_fields = statistics_data.get('total_numeric_fields', 0) + statistics_data.get('total_temporal_fields', 0) if statistics_data else 0

    return f"""
        <div class="dist-section">
            <nav class="jk-subtab-bar">
                <button class="jk-subtab-btn  jk-active" data-target="dist-charts" onclick="distSwitch(this)">
                    <span class="jk-label">📊 Value Distributions</span>
                    <span class="jk-count">({total_charts})</span>
                </button>
                <button class="jk-subtab-btn" data-target="dist-similarity" onclick="distSwitch(this)">
                    <span class="jk-label">📑 Distribution Similarity</span>
                </button>
                <button class="jk-subtab-btn" data-target="dist-stats" onclick="distSwitch(this)">
                    <span class="jk-label">📐 Field Stats</span>
                    <span class="jk-count">({num_fields})</span>
                </button>
            </nav>

            <div id="dist-charts" class="jk-pane">
                <div class="table-controls">
                    <div class="object-filter-dropdown" id="distObjectFilterDropdown">
                        <button type="button" class="object-filter-toggle" id="distObjectFilterToggle" aria-expanded="false">
                            Objects: All
                        </button>
                        <div class="object-filter-menu" id="distObjectFilterMenu">
                            <label class="object-filter-option object-filter-select-all">
                                <input type="checkbox" id="distObjectSelectAll" checked>
                                <span>Select All</span>
                            </label>
                            <div class="object-filter-divider"></div>
                            <div id="distObjectFilterOptions"></div>
                        </div>
                    </div>
                </div>
                <div class="distribution-group-nav" id="distributionGroupNav">
                    {''.join(nav_links)}
                </div>
                <div id='distributions-grid'>
                    {''.join(group_sections)}
                </div>
            </div>

            <div id="dist-similarity" class="jk-pane" style="display:none">
                {similarity_html}
            </div>

            <div id="dist-stats" class="jk-pane" style="display:none">
                {stats_html}
            </div>
        </div>
        <script>
        function distSwitch(btn) {{
            var bar = btn.closest('.jk-subtab-bar');
            bar.querySelectorAll('.jk-subtab-btn').forEach(function(b) {{
                b.classList.remove('jk-active');
            }});
            btn.classList.add('jk-active');
            var section = btn.closest('.dist-section');
            section.querySelectorAll('.jk-pane').forEach(function(p) {{
                p.style.display = 'none';
            }});
            document.getElementById(btn.getAttribute('data-target')).style.display = '';
        }}
        </script>
    """


def _render_statistics_tab(statistics_data: dict) -> str:
    """Render the Statistics tab content."""
    if not statistics_data:
        return "<p>No statistical analysis available.</p>"

    sections = []

    for obj_data in statistics_data.get("objects", []):
        obj_name = html.escape(obj_data.get("object", "Unknown"))

        # Numeric fields
        numeric_fields = obj_data.get("numeric_fields", [])
        numeric_rows = []
        for nf in numeric_fields:
            min_val = f"{nf['min']:.2f}" if nf.get('min') is not None else '—'
            max_val = f"{nf['max']:.2f}" if nf.get('max') is not None else '—'
            mean_val = f"{nf['mean']:.2f}" if nf.get('mean') is not None else '—'
            median_val = f"{nf['median']:.2f}" if nf.get('median') is not None else '—'
            stddev_val = f"{nf['stddev']:.2f}" if nf.get('stddev') is not None else '—'
            dist_val = nf.get('distribution', '—')
            numeric_rows.append(f"""
                <tr>
                    <td class="field-path">{html.escape(nf['path'])}</td>
                    <td class="text-right">{min_val}</td>
                    <td class="text-right">{max_val}</td>
                    <td class="text-right">{mean_val}</td>
                    <td class="text-right">{median_val}</td>
                    <td class="text-right">{stddev_val}</td>
                    <td class="text-center">{dist_val}</td>
                </tr>
            """)

        numeric_html = ""
        if numeric_rows:
            numeric_html = f"""
                <div class="stats-section">
                    <h4>📐 Numeric Fields</h4>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Field</th>
                                <th class="text-right">Min</th>
                                <th class="text-right">Max</th>
                                <th class="text-right">Mean</th>
                                <th class="text-right">Median</th>
                                <th class="text-right">Std Dev</th>
                                <th class="text-center">Distribution</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(numeric_rows)}
                        </tbody>
                    </table>
                </div>
            """

        # Temporal fields
        temporal_fields = obj_data.get("temporal_fields", [])
        temporal_rows = []
        for tf in temporal_fields:
            temporal_rows.append(f"""
                <tr>
                    <td class="field-path">{html.escape(tf['path'])}</td>
                    <td>{tf['min_date'] or '—'}</td>
                    <td>{tf['max_date'] or '—'}</td>
                    <td class="text-right">{tf['span_days'] or '—'}</td>
                    <td class="text-right">{tf['null_count']}</td>
                    <td class="text-right">{tf['future_count']}</td>
                </tr>
            """)

        temporal_html = ""
        if temporal_rows:
            temporal_html = f"""
                <div class="stats-section">
                    <h4>📅 Temporal Fields</h4>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Field</th>
                                <th>Min Date</th>
                                <th>Max Date</th>
                                <th class="text-right">Span (days)</th>
                                <th class="text-right">Nulls</th>
                                <th class="text-right">Future</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join(temporal_rows)}
                        </tbody>
                    </table>
                </div>
            """

        if numeric_html or temporal_html:
            sections.append(f"""
                <div class="stats-object">
                    <h3>{obj_name}</h3>
                    {numeric_html}
                    {temporal_html}
                </div>
            """)

    if not sections:
        return """
            <div class="empty-state">
                <span class="empty-icon">📐</span>
                <p>No numeric or temporal fields found for statistical analysis.</p>
            </div>
        """

    return f"""
        <div class="stats-summary">
            <div class="stats-metric">
                <span class="stats-metric-value">{statistics_data.get('total_numeric_fields', 0)}</span>
                <span class="stats-metric-label">Numeric Fields</span>
            </div>
            <div class="stats-metric">
                <span class="stats-metric-value">{statistics_data.get('total_temporal_fields', 0)}</span>
                <span class="stats-metric-label">Temporal Fields</span>
            </div>
        </div>
        {"".join(sections)}
    """


def _render_type_warnings(objects: list[dict[str, Any]]) -> str:
    """Render the Type Warnings tab content."""
    warnings = []

    for obj in objects:
        obj_name = html.escape(obj.get("object", "Unknown"))

        for field in obj.get("fields", []):
            types = field.get("types", {})
            non_null_types = {k: v for k, v in types.items() if k != "null"}

            if len(non_null_types) > 1:
                path = html.escape(field.get("path", ""))
                type_badges = " ".join(
                    f'<span class="type-badge type-{t}">{t}: {c}</span>'
                    for t, c in sorted(non_null_types.items(), key=lambda x: -x[1])
                )

                warnings.append(f"""
                    <tr>
                        <td><span class="object-name">{obj_name}</span></td>
                        <td class="field-path">{path}</td>
                        <td>{type_badges}</td>
                        <td class="text-center">{len(non_null_types)}</td>
                    </tr>
                """)

    if not warnings:
        return """
            <div class="empty-state success">
                <span class="empty-icon">✅</span>
                <p>All fields have consistent types. No warnings.</p>
            </div>
        """

    return f"""
        <div class="warning-summary">
            <span class="warning-icon">⚠️</span>
            <span>{len(warnings)} fields have mixed types</span>
        </div>
        <table class="data-table sortable">
            <thead>
                <tr>
                    <th>Object</th>
                    <th>Field Path</th>
                    <th>Types</th>
                    <th class="text-center">Count</th>
                </tr>
            </thead>
            <tbody>
                {''.join(warnings)}
            </tbody>
        </table>
    """


def _render_relationships_tab(relationships_data: dict, joins_data: dict | None = None, objects: list | None = None) -> str:
    """Render the Relationships tab with ER diagram, type-filter buttons, and a filterable table."""
    er_html = _render_er_diagram(relationships_data or {}, joins_data or {}, objects or [])

    if not relationships_data:
        return er_html or "<p>No relationship analysis available.</p>"

    total = relationships_data.get("total_relationships", 0)
    by_type = {k: v for k, v in relationships_data.get("by_type", {}).items() if v > 0}

    if total == 0:
        return f"""
            {er_html}
            <div class="empty-state">
                <span class="empty-icon">🔗</span>
                <p>No detailed relationships detected — links above are inferred from key fields.</p>
            </div>
        """

    # Build rows with data-rel-type attributes for JS filtering
    rel_rows = []
    for rel in relationships_data.get("relationships", []):
        confidence = rel.get("confidence", 0)
        conf_class = "high" if confidence >= 0.8 else "medium" if confidence >= 0.6 else "low"
        rel_type = rel.get("type", "unknown")
        is_structural = rel_type == "structural_candidate"
        badge_style = ' style="background:var(--color-info);color:#fff"' if is_structural else ""
        row_style = ' style="opacity:0.88"' if is_structural else ""
        rel_rows.append(f"""
            <tr data-rel-type="{html.escape(rel_type)}"{row_style}>
                <td>{html.escape(rel.get("source", ""))}</td>
                <td>→</td>
                <td>{html.escape(rel.get("target", ""))}</td>
                <td><span class="rel-type-badge rel-{rel_type}"{badge_style}>{html.escape(rel_type)}</span></td>
                <td><span class="confidence-badge conf-{conf_class}">{confidence:.0%}</span></td>
                <td class="evidence-cell" style="font-size:0.8rem">{html.escape("; ".join(rel.get("evidence", [])[:2]))}</td>
            </tr>
        """)

    rows_html = "\n".join(rel_rows)

    # Type-order: structural_candidate first, then value_join, then others
    type_order = ["structural_candidate", "value_join", "shared_enum", "hierarchy"]
    sorted_types = sorted(by_type.keys(), key=lambda t: (type_order.index(t) if t in type_order else 99, t))

    filter_buttons = "\n".join(
        f'<button class="rel-filter-btn" data-type="{t}" onclick="filterRelationships(this)">'
        f'<span class="rel-type-name">{t.replace("_", " ")}</span>'
        f'<span class="rel-filter-count">{by_type[t]}</span>'
        f'</button>'
        for t in sorted_types
    )

    # JS for filtering
    filter_js = """
    <script>
    (function() {
        // Default: select structural_candidate on load
        function filterRelationships(btn) {
            var selected = btn.getAttribute('data-type');
            document.querySelectorAll('.rel-filter-btn').forEach(function(b) {
                b.classList.toggle('active', b.getAttribute('data-type') === selected);
            });
            document.querySelectorAll('#rel-table-body tr').forEach(function(row) {
                var t = row.getAttribute('data-rel-type');
                row.style.display = (t === selected) ? '' : 'none';
            });
            // Update visible count badge
            var shown = document.querySelectorAll('#rel-table-body tr[data-rel-type="' + selected + '"]').length;
            var badge = document.querySelector('.rel-visible-count');
            if (badge) badge.textContent = 'Showing ' + shown + ' of ' + TOTAL_RELS;
        }
        window.filterRelationships = filterRelationships;
        var TOTAL_RELS = """ + str(total) + """;
        // Auto-click structural_candidate on page ready (debounced to ensure DOM is ready)
        setTimeout(function() {
            var defaultBtn = document.querySelector('.rel-filter-btn[data-type="structural_candidate"]');
            if (!defaultBtn) defaultBtn = document.querySelector('.rel-filter-btn');
            if (defaultBtn) filterRelationships(defaultBtn);
        }, 50);
    })();
    </script>
    """

    return f"""
        {er_html}

        <h3>📊 Detected Relationships</h3>
        <div class="relationships-summary">
            <div class="rel-total">
                <span class="rel-total-value">{total}</span>
                <span class="rel-total-label">Total Detected</span>
            </div>
            <div class="rel-filter-bar">
                {filter_buttons}
            </div>
        </div>
        <p class="rel-visible-count" style="color:var(--text-secondary);font-size:0.82rem;margin-bottom:var(--space-sm)">Showing all</p>

        <table class="data-table sortable">
            <thead>
                <tr>
                    <th>Source</th>
                    <th></th>
                    <th>Target</th>
                    <th>Type</th>
                    <th>Confidence</th>
                    <th>Evidence</th>
                </tr>
            </thead>
            <tbody id="rel-table-body">
                {rows_html}
            </tbody>
        </table>
        {filter_js}
    """


def _render_er_diagram(
    relationships_data: dict,
    joins_data: dict,
    objects: list[dict[str, Any]],
) -> str:
    """Render an inline-SVG ER-style diagram.

    Key design rules:
    - Only structural_candidate and value_join relationship types generate links.
      (shared_enum / hierarchy are excluded — they produce too many noisy lines.)
    - Object boxes show ONLY the fields actually used in connections, not all PK fields.
    - Each link is labelled with the connecting field name (truncated).
    - Audit/temporal fields are never used for links.
    """
    obj_names = [o.get("object", "Unknown") for o in objects]
    if not obj_names:
        return ""

    # ── Build link set: only real join connections ──────────────────────────
    # Maps frozenset(obj_a, obj_b) → {left, right, field_label, confidence}
    links: dict[frozenset, dict[str, Any]] = {}
    # Track which fields on each object are used in connections
    obj_link_fields: dict[str, set[str]] = {n: set() for n in obj_names}

    LINK_TYPES = {"structural_candidate", "value_join"}

    for rel in relationships_data.get("relationships", []):
        if rel.get("type") not in LINK_TYPES:
            continue
        src = rel.get("source", "")
        tgt = rel.get("target", "")
        if not src or not tgt:
            continue
        # source/target format is "object.field"
        src_parts = src.split(".", 1)
        tgt_parts = tgt.split(".", 1)
        s_obj = src_parts[0]
        t_obj = tgt_parts[0]
        if s_obj == t_obj or s_obj not in obj_names or t_obj not in obj_names:
            continue
        s_fld = src_parts[1] if len(src_parts) > 1 else ""
        t_fld = tgt_parts[1] if len(tgt_parts) > 1 else ""
        # Label: use common field name if same, else "a→b"
        if s_fld and t_fld:
            label = s_fld if s_fld == t_fld else f"{s_fld}↔{t_fld}"
        else:
            label = s_fld or t_fld or rel.get("type", "join")
        # Truncate
        label = label[:24] + ("…" if len(label) > 24 else "")
        key = frozenset({s_obj, t_obj})
        prior = links.get(key)
        conf = rel.get("confidence", 0)
        if not prior or conf > prior.get("confidence", 0):
            links[key] = {
                "left": s_obj,
                "right": t_obj,
                "label": label,
                "confidence": conf,
                "type": rel.get("type", ""),
            }
        if s_fld:
            obj_link_fields[s_obj].add(s_fld)
        if t_fld:
            obj_link_fields[t_obj].add(t_fld)

    # Also pull from all_value_joins in joins_data (structural + value-confirmed)
    for jc in joins_data.get("all_value_joins", []) if joins_data else []:
        left_str = jc.get("left", "")
        right_str = jc.get("right", "")
        left_parts = left_str.split(".", 1)
        right_parts = right_str.split(".", 1)
        if len(left_parts) < 2 or len(right_parts) < 2:
            continue
        l_obj, l_fld = left_parts[0], left_parts[1]
        r_obj, r_fld = right_parts[0], right_parts[1]
        if l_obj == r_obj or l_obj not in obj_names or r_obj not in obj_names:
            continue
        key = frozenset({l_obj, r_obj})
        conf = jc.get("confidence", 0)
        if key not in links or conf > links[key].get("confidence", 0):
            label = l_fld if l_fld == r_fld else f"{l_fld}↔{r_fld}"
            label = label[:24] + ("…" if len(label) > 24 else "")
            links[key] = {
                "left": l_obj,
                "right": r_obj,
                "label": label,
                "confidence": conf,
                "type": jc.get("kind", ""),
            }
        obj_link_fields[l_obj].add(l_fld)
        obj_link_fields[r_obj].add(r_fld)

    # ── Layout ──────────────────────────────────────────────────────────────
    box_w, row_h = 230, 22
    header_h = 34
    h_gap, v_gap = 90, 60
    padding = 44
    max_field_rows = 5
    cols = min(3, max(1, int(len(obj_names) ** 0.5 + 0.5)))

    obj_field_lines: dict[str, list[str]] = {}
    for name in obj_names:
        flds = sorted(obj_link_fields.get(name, set()))[:max_field_rows]
        obj_field_lines[name] = flds

    obj_heights = {
        n: header_h + max(1, len(obj_field_lines[n])) * row_h + 10
        for n in obj_names
    }

    positions: dict[str, tuple[int, int, int]] = {}
    max_row_h = max(obj_heights.values()) if obj_heights else header_h + row_h
    max_y = 0
    for idx, name in enumerate(obj_names):
        r, c = divmod(idx, cols)
        x = padding + c * (box_w + h_gap)
        y = padding + r * (max_row_h + v_gap)
        h = obj_heights[name]
        positions[name] = (x, y, h)
        max_y = max(max_y, y + h)

    svg_w = padding * 2 + cols * box_w + (cols - 1) * h_gap
    svg_h = max_y + padding

    # ── Draw links ──────────────────────────────────────────────────────────
    link_svg = []
    for link in links.values():
        l, r = link["left"], link["right"]
        if l not in positions or r not in positions:
            continue
        lx, ly, lh = positions[l]
        rx, ry, rh = positions[r]
        if lx <= rx:
            x1, x2 = lx + box_w, rx
        else:
            x1, x2 = lx, rx + box_w
        y1 = ly + lh / 2
        y2 = ry + rh / 2
        mid_x = (x1 + x2) / 2
        path_d = f"M{x1},{y1} C{mid_x},{y1} {mid_x},{y2} {x2},{y2}"
        conf = link.get("confidence", 0)
        is_structural = "structural" in link.get("type", "")
        color = "var(--color-success)" if conf >= 0.75 else "var(--color-info)"
        dash = "5,3" if is_structural else "0"
        label = link.get("label", "")
        mid_y = (y1 + y2) / 2
        link_svg.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-dasharray="{dash}" opacity="0.9"/>'
        )
        # Field label on link midpoint
        if label:
            link_svg.append(
                f'<rect x="{mid_x - len(label) * 3.5}" y="{mid_y - 9}" '
                f'width="{len(label) * 7 + 4}" height="16" rx="3" '
                f'fill="var(--bg-secondary)" opacity="0.92"/>'
            )
            link_svg.append(
                f'<text x="{mid_x}" y="{mid_y + 3}" text-anchor="middle" '
                f'fill="var(--text-secondary)" font-size="9.5" '
                f'font-family="ui-monospace,monospace">{html.escape(label)}</text>'
            )

    # ── Draw boxes ──────────────────────────────────────────────────────────
    box_svg = []
    for name in obj_names:
        x, y, h = positions[name]
        flds = obj_field_lines[name]
        has_links = bool(obj_link_fields.get(name))
        border_color = "var(--accent-primary)" if has_links else "var(--border-primary)"
        box_svg.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{h}" rx="7" '
            f'fill="var(--bg-tertiary)" stroke="{border_color}" stroke-width="1.8"/>'
        )
        # Header
        box_svg.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{header_h}" rx="7" '
            f'fill="var(--accent-primary)" opacity="0.9"/>'
        )
        box_svg.append(
            f'<rect x="{x}" y="{y + header_h - 6}" width="{box_w}" height="6" '
            f'fill="var(--accent-primary)" opacity="0.9"/>'  # square bottom of header
        )
        box_svg.append(
            f'<text x="{x + box_w / 2}" y="{y + header_h / 2 + 5}" '
            f'text-anchor="middle" fill="white" font-size="12.5" '
            f'font-weight="700">{html.escape(name)}</text>'
        )
        # Connection fields
        if flds:
            for i, fld in enumerate(flds):
                fy = y + header_h + 15 + i * row_h
                short = fld if len(fld) <= 26 else fld[:24] + "…"
                box_svg.append(
                    f'<text x="{x + 10}" y="{fy}" fill="var(--color-info)" '
                    f'font-size="10.5" font-family="ui-monospace,monospace">'
                    f'⟷ {html.escape(short)}</text>'
                )
        else:
            fy = y + header_h + 15
            box_svg.append(
                f'<text x="{x + box_w / 2}" y="{fy}" text-anchor="middle" '
                f'fill="var(--text-tertiary)" font-size="10" font-style="italic">'
                f'no connections detected</text>'
            )

    svg = (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" '
        f'style="max-width:{svg_w}px;display:block" xmlns="http://www.w3.org/2000/svg">'
        + "".join(link_svg)
        + "".join(box_svg)
        + "</svg>"
    )

    # ── Mermaid source ───────────────────────────────────────────────────────
    mermaid_lines = ["erDiagram"]
    for name in obj_names:
        mermaid_lines.append(f"    {name} {{")
        flds = obj_field_lines.get(name, [])
        for fld in flds:
            safe = fld.replace(".", "_").replace("[]", "_arr")
            mermaid_lines.append(f"        string {safe} FK")
        if not flds:
            mermaid_lines.append("        string id")
        mermaid_lines.append("    }")
    for link in links.values():
        l, r = link["left"], link["right"]
        if l not in obj_names or r not in obj_names:
            continue
        lbl = link.get("label", "join").replace("↔", "_")
        mermaid_lines.append(f'    {l} ||--o{{ {r} : "{lbl}"')
    mermaid_src = "\n".join(mermaid_lines)

    linked_count = len(links)
    return f"""
        <div class="er-diagram-section">
            <h3>🗺️ Entity Relationship Diagram</h3>
            <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: var(--space-md);">
                Only structural/value-join connections shown ({linked_count} links). Boxes list the fields participating in each connection.
                Solid lines = value-confirmed; dashed = structural candidate (run with <code>--max-distinct 500</code> to confirm).
                Objects with no detected connections have a dimmed border.
            </p>
            {svg}
            <div class="er-legend">
                <span><i style="background: var(--color-success)"></i> ≥ 75% confidence (solid)</span>
                <span><i style="background: var(--color-info)"></i> &lt; 75% confidence (solid)</span>
                <span style="opacity:0.7"><i style="background: var(--color-info);opacity:0.5"></i> structural candidate (dashed)</span>
            </div>
            <details class="mermaid-source">
                <summary>Show Mermaid ER source (copy-paste into mermaid.live)</summary>
                <pre>{html.escape(mermaid_src)}</pre>
            </details>
        </div>
    """


def _render_cross_object(objects: list[dict[str, Any]]) -> str:
    """Render the Cross-Object Analysis tab content."""
    if len(objects) < 2:
        return """
            <div class="empty-state">
                <span class="empty-icon">🔀</span>
                <p>Cross-object analysis requires at least 2 objects.</p>
            </div>
        """

    field_to_objects: dict[str, list[str]] = {}
    for obj in objects:
        obj_name = obj.get("object", "Unknown")
        for field in obj.get("fields", []):
            path = field.get("path", "")
            if path not in field_to_objects:
                field_to_objects[path] = []
            field_to_objects[path].append(obj_name)

    common_fields = [(p, objs) for p, objs in field_to_objects.items() if len(objs) > 1]
    common_fields.sort(key=lambda x: -len(x[1]))

    rows = []
    for path, objs in common_fields[:50]:
        obj_badges = " ".join(f'<span class="object-badge">{html.escape(o)}</span>' for o in objs)
        rows.append(f"""
            <tr>
                <td class="field-path">{html.escape(path)}</td>
                <td class="text-center">{len(objs)}</td>
                <td>{obj_badges}</td>
            </tr>
        """)

    if not rows:
        return """
            <div class="empty-state">
                <span class="empty-icon">🔀</span>
                <p>No common fields found across objects.</p>
            </div>
        """

    return f"""
        <div class="cross-object-info">
            <h3>Common Fields</h3>
            <p>Fields present in multiple objects — potential join keys or shared attributes.</p>
        </div>
        <table class="data-table sortable">
            <thead>
                <tr>
                    <th>Field Path</th>
                    <th class="text-center">Object Count</th>
                    <th>Objects</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    """


# ═══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE WITH PROFESSIONAL STYLING AND DAY/NIGHT MODE
# ═══════════════════════════════════════════════════════════════════════════════

_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        /* ═══════════════════════════════════════════════════════════════════════
           CSS VARIABLES - LIGHT AND DARK THEMES
           ═══════════════════════════════════════════════════════════════════════ */
        :root {{
            /* Typography */
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;

            /* Spacing */
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --space-2xl: 48px;

            /* Border radius */
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;

            /* Transitions */
            --transition-fast: 150ms ease;
            --transition-normal: 250ms ease;
            --transition-slow: 400ms ease;

            /* Semantic colors (shared) */
            --color-success: #22c55e;
            --color-success-light: #86efac;
            --color-info: #3b82f6;
            --color-info-light: #93c5fd;
            --color-warning: #eab308;
            --color-warning-light: #fde047;
            --color-caution: #f97316;
            --color-danger: #ef4444;
            --color-danger-light: #fca5a5;
        }}

        /* ═══ DARK THEME (Night Mode) ═══ */
        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --bg-input: #1e293b;

            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-tertiary: #64748b;
            --text-inverse: #0f172a;

            --border-primary: #334155;
            --border-secondary: #475569;
            --border-focus: #3b82f6;

            --accent-primary: #3b82f6;
            --accent-secondary: #8b5cf6;
            --accent-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);

            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);

            --header-bg: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        }}

        /* ═══ LIGHT THEME (Day Mode) ═══ */
        [data-theme="light"] {{
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f1f5f9;
            --bg-card: #ffffff;
            --bg-hover: #f1f5f9;
            --bg-input: #ffffff;

            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-tertiary: #94a3b8;
            --text-inverse: #f1f5f9;

            --border-primary: #e2e8f0;
            --border-secondary: #cbd5e1;
            --border-focus: #3b82f6;

            --accent-primary: #2563eb;
            --accent-secondary: #7c3aed;
            --accent-gradient: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);

            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.07);
            --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);

            --header-bg: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           BASE STYLES
           ═══════════════════════════════════════════════════════════════════════ */
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        html {{
            font-size: 16px;
            scroll-behavior: smooth;
        }}

        body {{
            font-family: var(--font-sans);
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            transition: background var(--transition-normal), color var(--transition-normal);
            min-height: 100vh;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           HEADER
           ═══════════════════════════════════════════════════════════════════════ */
        header {{
            background: var(--header-bg);
            border-bottom: 1px solid var(--border-primary);
            padding: var(--space-xs) var(--space-xl);
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
            transition: all var(--transition-normal);
        }}

        .header-content {{
            max-width: 1600px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: auto 1fr auto;
            align-items: center;
            gap: var(--space-md);
        }}

        .header-search {{
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-self: center;
            width: 100%;
            max-width: 520px;
        }}
        .header-search .search-input {{
            width: 100%;
            max-width: 520px;
        }}
        /* Out of flow so the input itself is vertically centered in the header row;
           the hit-count floats just beneath the box. */
        .search-status {{
            position: absolute;
            top: calc(100% + 2px);
            left: 0;
            right: 0;
            text-align: center;
            font-size: 0.7rem;
            color: var(--text-tertiary);
            min-height: 14px;
            pointer-events: none;
        }}
        .search-status.has-hits {{
            color: var(--color-info);
        }}
        .search-status.no-hits {{
            color: var(--color-warning);
        }}
        .tab.has-search-hit {{
            box-shadow: inset 0 -2px 0 var(--color-info);
        }}
        .tab.has-search-hit::after {{
            content: attr(data-hits);
            margin-left: 6px;
            padding: 1px 6px;
            border-radius: 8px;
            background: var(--color-info);
            color: white;
            font-size: 0.7rem;
            font-weight: 600;
        }}
        mark.search-hit {{
            background: rgba(250, 204, 21, 0.35);
            color: inherit;
            padding: 0 1px;
            border-radius: 2px;
        }}

        .header-title {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}

        .logo {{
            font-size: 1.25rem;
        }}

        /* Branded lens icon (light/dark variants swapped by theme) */
        .logo-mark {{
            height: 42px;
            width: auto;
            display: block;
        }}
        /* Default to the dark-theme icon (report defaults to dark); swap on light. */
        .logo-mark-light {{ display: none; }}
        .logo-mark-dark {{ display: block; }}
        [data-theme="light"] .logo-mark-light {{ display: block; }}
        [data-theme="light"] .logo-mark-dark {{ display: none; }}

        /* Wordmark rendered as crisp HTML text (scales, theme-aware) */
        .brand {{
            display: flex;
            flex-direction: column;
            line-height: 1.05;
        }}
        .brand-name {{
            font-size: 1.4rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: var(--text-primary);
        }}
        .brand-accent {{ color: #0ea5e9; }}
        .brand-sub {{
            font-size: 0.62rem;
            font-weight: 600;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: var(--text-secondary);
        }}

        .visually-hidden {{
            position: absolute;
            width: 1px; height: 1px;
            padding: 0; margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap; border: 0;
        }}

        header h1 {{
            font-size: 1rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .header-meta {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            flex-wrap: wrap;
        }}

        .meta-item {{
            display: flex;
            align-items: center;
            gap: var(--space-xs);
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .meta-value {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        /* Theme Toggle */
        .theme-toggle {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            background: var(--bg-tertiary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-lg);
            padding: var(--space-xs);
        }}

        .theme-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border: none;
            border-radius: var(--radius-md);
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1rem;
            transition: all var(--transition-fast);
        }}

        .theme-btn:hover {{
            background: var(--bg-hover);
            color: var(--text-primary);
        }}

        .theme-btn.active {{
            background: var(--accent-primary);
            color: var(--text-inverse);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           MAIN CONTAINER
           ═══════════════════════════════════════════════════════════════════════ */
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: var(--space-md) var(--space-lg);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           SEARCH
           ═══════════════════════════════════════════════════════════════════════ */
        .search-container {{
            margin-bottom: var(--space-sm);
        }}

        .search-input {{
            width: 100%;
            max-width: 400px;
            padding: var(--space-xs) var(--space-md);
            font-family: var(--font-sans);
            font-size: 0.875rem;
            background: var(--bg-input);
            border: 2px solid var(--border-primary);
            border-radius: var(--radius-lg);
            color: var(--text-primary);
            transition: all var(--transition-fast);
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--border-focus);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
        }}

        .search-input::placeholder {{
            color: var(--text-tertiary);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           TABS
           ═══════════════════════════════════════════════════════════════════════ */
        .tabs {{
            display: flex;
            gap: var(--space-xs);
            margin-bottom: var(--space-sm);
            flex-wrap: wrap;
            background: var(--bg-secondary);
            padding: 4px;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-primary);
        }}

        .tab {{
            display: flex;
            align-items: center;
            gap: var(--space-xs);
            padding: 4px var(--space-sm);
            font-family: var(--font-sans);
            font-size: 0.8125rem;
            font-weight: 500;
            background: transparent;
            border: none;
            border-radius: var(--radius-md);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all var(--transition-fast);
            white-space: nowrap;
        }}

        .tab:hover {{
            background: var(--bg-hover);
            color: var(--text-primary);
        }}

        .tab.active {{
            background: var(--accent-primary);
            color: var(--text-inverse);
        }}

        .tab-icon {{
            font-size: 1rem;
        }}

        .tab-content {{
            display: none;
            background: var(--bg-card);
            padding: var(--space-md) var(--space-lg);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-primary);
            box-shadow: var(--shadow-md);
            animation: fadeIn var(--transition-normal);
        }}

        .tab-content.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           CARDS
           ═══════════════════════════════════════════════════════════════════════ */
        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-lg);
            overflow: hidden;
            transition: all var(--transition-fast);
        }}

        .card:hover {{
            box-shadow: var(--shadow-md);
        }}

        .card-header {{
            padding: var(--space-xs) var(--space-md);
            border-bottom: 1px solid var(--border-primary);
            background: var(--bg-tertiary);
        }}

        .card-header h3 {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .card-body {{
            padding: var(--space-sm) var(--space-md);
        }}

        /* Overview Grid */
        .overview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: var(--space-sm);
            margin-bottom: var(--space-md);
        }}

        .metric-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
            padding: var(--space-sm) var(--space-md);
            transition: all var(--transition-fast);
        }}

        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}

        .metric-header {{
            display: flex;
            align-items: center;
            gap: var(--space-xs);
            margin-bottom: 4px;
        }}

        .metric-icon {{
            font-size: 0.9rem;
        }}

        .metric-title {{
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .metric-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        /* DQI Card */
        .dqi-card {{
            grid-column: span 2;
        }}

        .dqi-display {{
            display: flex;
            align-items: baseline;
            gap: var(--space-xs);
            margin-bottom: 4px;
        }}

        .dqi-score {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .dqi-grade {{
            font-size: 1rem;
            font-weight: 600;
            padding: 2px var(--space-xs);
            border-radius: var(--radius-sm);
            background: var(--bg-tertiary);
        }}

        .dqi-bar-container {{
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: var(--radius-sm);
            overflow: hidden;
        }}

        .dqi-bar {{
            height: 100%;
            background: var(--accent-gradient);
            border-radius: var(--radius-sm);
            transition: width var(--transition-slow);
        }}

        /* Quality Colors */
        .quality-excellent .dqi-bar {{ background: var(--color-success); }}
        .quality-good .dqi-bar {{ background: var(--color-info); }}
        .quality-fair .dqi-bar {{ background: var(--color-warning); }}
        .quality-poor .dqi-bar {{ background: var(--color-caution); }}
        .quality-critical .dqi-bar {{ background: var(--color-danger); }}

        /* PII Card */
        .pii-card {{
            border-left: 4px solid var(--color-warning);
        }}

        .pii-card.pii-warning {{
            border-left-color: var(--color-danger);
            background: rgba(239, 68, 68, 0.1);
        }}

        .pii-stats {{
            display: flex;
            gap: var(--space-md);
        }}

        .pii-stat {{
            text-align: center;
        }}

        .pii-value {{
            font-size: 1.375rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .pii-value.high-risk {{
            color: var(--color-danger);
        }}

        .pii-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           TABLES
           ═══════════════════════════════════════════════════════════════════════ */
        .table-container {{
            overflow-x: auto;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-primary);
        }}

        .table-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: var(--space-sm);
            margin-bottom: var(--space-sm);
            flex-wrap: wrap;
        }}

        .table-search {{
            flex: 1;
            max-width: 300px;
            padding: var(--space-sm) var(--space-md);
            font-family: var(--font-sans);
            font-size: 0.875rem;
            background: var(--bg-input);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
            color: var(--text-primary);
        }}

        .table-search:focus {{
            outline: none;
            border-color: var(--border-focus);
        }}

        .object-filter-dropdown {{
            position: relative;
            min-width: 220px;
        }}

        .object-filter-toggle {{
            width: 100%;
            padding: var(--space-sm) var(--space-md);
            text-align: left;
            font-family: var(--font-sans);
            font-size: 0.875rem;
            background: var(--bg-input);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
            color: var(--text-primary);
            cursor: pointer;
            transition: all var(--transition-fast);
        }}

        .object-filter-toggle:hover {{
            border-color: var(--border-focus);
        }}

        .object-filter-toggle:focus {{
            outline: none;
            border-color: var(--border-focus);
        }}

        .object-filter-menu {{
            position: absolute;
            top: calc(100% + 6px);
            left: 0;
            z-index: 20;
            width: min(340px, 85vw);
            max-height: 280px;
            overflow-y: auto;
            padding: var(--space-sm);
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.25);
            display: none;
        }}

        .object-filter-menu.open {{
            display: block;
        }}

        .object-filter-option {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            font-size: 0.8125rem;
            color: var(--text-primary);
            padding: 4px 2px;
            cursor: pointer;
        }}

        .object-filter-option input {{
            cursor: pointer;
        }}

        .object-filter-select-all {{
            font-weight: 600;
        }}

        .object-filter-divider {{
            height: 1px;
            background: var(--border-primary);
            margin: 6px 0;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        .data-table th,
        .data-table td {{
            padding: var(--space-sm) var(--space-md);
            text-align: left;
            border-bottom: 1px solid var(--border-primary);
        }}

        .data-table th {{
            background: var(--bg-tertiary);
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.05em;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }}

        .data-table th:hover {{
            color: var(--text-primary);
            background: var(--bg-hover);
        }}

        .data-table tbody tr {{
            transition: background var(--transition-fast);
        }}

        .data-table tbody tr:hover {{
            background: var(--bg-hover);
        }}

        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}

        .field-path {{
            font-family: var(--font-mono);
            font-size: 0.8125rem;
            color: var(--accent-primary);
        }}

        .object-name {{
            font-weight: 500;
            color: var(--text-primary);
        }}

        .example-cell {{
            max-width: 250px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 0.8125rem;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           BADGES
           ═══════════════════════════════════════════════════════════════════════ */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: 500;
            border-radius: var(--radius-sm);
            white-space: nowrap;
        }}

        .badge-info {{
            background: rgba(59, 130, 246, 0.2);
            color: var(--color-info);
        }}

        .badge-success {{
            background: rgba(34, 197, 94, 0.2);
            color: var(--color-success);
        }}

        .badge-warning {{
            background: rgba(234, 179, 8, 0.2);
            color: var(--color-warning);
        }}

        .badge-danger {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--color-danger);
        }}

        /* Cardinality badges — neutral, descriptive scale (NOT severity).
           High cardinality is normal/expected for IDs, so no red/amber. */
        .card-na {{
            background: var(--bg-tertiary);
            color: var(--text-tertiary);
        }}
        .card-low {{
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }}
        .card-med {{
            background: rgba(59, 130, 246, 0.15);
            color: var(--color-info);
        }}
        .card-high {{
            background: rgba(99, 102, 241, 0.18);
            color: var(--accent-secondary);
        }}

        /* Coverage Badges */
        .coverage-badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: var(--radius-sm);
        }}

        .coverage-high {{
            background: var(--color-success);
            color: #000;
        }}

        .coverage-medium {{
            background: var(--color-warning);
            color: #000;
        }}

        .coverage-low {{
            background: var(--color-danger);
            color: #fff;
        }}

        /* Null/Empty Cell Highlighting */
        .null-cell {{
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: var(--radius-sm);
        }}

        .null-none {{
            background: rgba(34, 197, 94, 0.15);
            color: var(--color-success);
        }}

        .null-low {{
            background: rgba(59, 130, 246, 0.15);
            color: var(--color-info);
        }}

        .null-medium {{
            background: rgba(234, 179, 8, 0.2);
            color: var(--color-warning);
        }}

        .null-high {{
            background: rgba(249, 115, 22, 0.25);
            color: var(--color-caution);
        }}

        .null-critical {{
            background: rgba(239, 68, 68, 0.25);
            color: var(--color-danger);
        }}

        /* Type Badges */
        .type-badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 6px;
            font-size: 0.7rem;
            font-weight: 500;
            font-family: var(--font-mono);
            border-radius: var(--radius-sm);
            margin-right: 4px;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }}

        .type-string {{ background: rgba(59, 130, 246, 0.2); color: var(--color-info); }}
        .type-int, .type-float {{ background: rgba(168, 85, 247, 0.2); color: #a855f7; }}
        .type-bool {{ background: rgba(236, 72, 153, 0.2); color: #ec4899; }}
        .type-date {{ background: rgba(34, 197, 94, 0.2); color: var(--color-success); }}
        .type-email {{ background: rgba(249, 115, 22, 0.2); color: var(--color-caution); }}
        .type-url, .type-uri {{ background: rgba(6, 182, 212, 0.2); color: #06b6d4; }}
        .type-object {{ background: rgba(234, 179, 8, 0.2); color: var(--color-warning); }}
        .type-array {{ background: rgba(139, 92, 246, 0.2); color: var(--accent-secondary); }}

        /* PII Badge */
        .pii-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            font-size: 0.7rem;
            font-weight: 600;
            background: rgba(239, 68, 68, 0.2);
            color: var(--color-danger);
            border-radius: var(--radius-sm);
            margin-left: 8px;
        }}

        .pii-type-badge {{
            display: inline-flex;
            padding: 4px 8px;
            font-size: 0.75rem;
            font-weight: 500;
            border-radius: var(--radius-sm);
            margin-right: 4px;
        }}

        .pii-email {{ background: rgba(249, 115, 22, 0.2); color: var(--color-caution); }}
        .pii-phone {{ background: rgba(34, 197, 94, 0.2); color: var(--color-success); }}
        .pii-ssn {{ background: rgba(239, 68, 68, 0.2); color: var(--color-danger); }}
        .pii-credit_card {{ background: rgba(239, 68, 68, 0.3); color: var(--color-danger); }}
        .pii-name {{ background: rgba(59, 130, 246, 0.2); color: var(--color-info); }}
        .pii-address {{ background: rgba(168, 85, 247, 0.2); color: #a855f7; }}
        .pii-ip_address {{ background: rgba(6, 182, 212, 0.2); color: #06b6d4; }}

        /* ═══════════════════════════════════════════════════════════════════════
           HEATMAP
           ═══════════════════════════════════════════════════════════════════════ */
        .heatmap-legend {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            margin-bottom: var(--space-sm);
            padding: var(--space-sm) var(--space-md);
            background: var(--bg-secondary);
            border-radius: var(--radius-md);
            flex-wrap: wrap;
        }}

        .legend-item {{
            padding: 4px 12px;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-weight: 500;
            color: #000;
        }}

        .heatmap-container {{
            overflow-x: auto;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-primary);
        }}

        .heatmap-table {{
            border-collapse: collapse;
            font-size: 0.8125rem;
        }}

        .heatmap-table th,
        .heatmap-table td {{
            padding: var(--space-sm) var(--space-md);
            border: 1px solid var(--border-primary);
            white-space: nowrap;
        }}

        .heatmap-table th {{
            background: var(--bg-tertiary);
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .heatmap-cell {{
            text-align: center;
            font-weight: 600;
            min-width: 70px;
        }}

        .heatmap-empty {{
            background: var(--bg-secondary) !important;
            color: var(--text-tertiary) !important;
        }}

        .sticky-col {{
            position: sticky;
            left: 0;
            background: var(--bg-card);
            z-index: 1;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           DISTRIBUTIONS
           ═══════════════════════════════════════════════════════════════════════ */
        .distributions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: var(--space-sm);
        }}

        .distribution-group-nav {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
            margin-bottom: var(--space-md);
            padding: var(--space-sm);
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
        }}

        .distribution-group-link {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-primary);
            background: var(--bg-tertiary);
            color: var(--text-primary);
            text-decoration: none;
            font-size: 0.75rem;
            font-weight: 500;
            transition: all var(--transition-fast);
        }}

        .distribution-group-link:hover {{
            border-color: var(--accent-primary);
            color: var(--accent-primary);
        }}

        .distribution-group {{
            margin-bottom: var(--space-md);
            scroll-margin-top: 90px;
        }}

        .distribution-group-title {{
            margin-bottom: var(--space-sm);
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-primary);
            font-family: var(--font-mono);
            border-left: 3px solid var(--accent-primary);
            padding-left: var(--space-sm);
        }}

        .distribution-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
            padding: var(--space-sm) var(--space-md);
        }}

        .distribution-header {{
            margin-bottom: var(--space-sm);
        }}

        .distribution-object {{
            display: block;
            font-size: 0.75rem;
            color: var(--text-tertiary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .distribution-field {{
            display: block;
            font-family: var(--font-mono);
            font-size: 0.875rem;
            color: var(--accent-primary);
        }}

        .distribution-chart {{
            display: flex;
            flex-direction: column;
            gap: var(--space-sm);
        }}

        .dist-bar-row {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}

        .dist-label {{
            min-width: 100px;
            max-width: 100px;
            font-size: 0.8125rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-secondary);
        }}

        .dist-bar-container {{
            flex: 1;
            height: 24px;
            background: var(--bg-tertiary);
            border-radius: var(--radius-sm);
            overflow: hidden;
        }}

        .dist-bar {{
            height: 100%;
            background: var(--accent-gradient);
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            padding-left: var(--space-sm);
            min-width: fit-content;
        }}

        .dist-bar-text {{
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-inverse);
            white-space: nowrap;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           QUALITY TAB
           ═══════════════════════════════════════════════════════════════════════ */
        .quality-overview {{
            display: flex;
            justify-content: center;
            margin-bottom: var(--space-md);
        }}

        .overall-dqi-circle {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 110px;
            height: 110px;
            border-radius: 50%;
            background: var(--bg-secondary);
            border: 3px solid var(--border-primary);
        }}

        .overall-dqi-circle.quality-excellent {{ border-color: var(--color-success); }}
        .overall-dqi-circle.quality-good {{ border-color: var(--color-info); }}
        .overall-dqi-circle.quality-fair {{ border-color: var(--color-warning); }}
        .overall-dqi-circle.quality-poor {{ border-color: var(--color-caution); }}
        .overall-dqi-circle.quality-critical {{ border-color: var(--color-danger); }}

        .overall-score {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .overall-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .quality-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: var(--space-sm);
        }}

        .quality-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-md);
            padding: var(--space-sm) var(--space-md);
        }}

        .quality-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-sm);
        }}

        .quality-header h4 {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .quality-score {{
            display: flex;
            align-items: baseline;
            gap: var(--space-xs);
        }}

        .score-value {{
            font-size: 1.125rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .score-grade {{
            font-size: 0.8125rem;
            font-weight: 600;
            padding: 1px 6px;
            border-radius: var(--radius-sm);
            background: var(--bg-tertiary);
        }}

        .quality-dimensions {{
            margin-bottom: var(--space-sm);
        }}

        .dimension-row {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            margin-bottom: 4px;
        }}

        .dimension-name {{
            min-width: 100px;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .dimension-bar-container {{
            flex: 1;
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: var(--radius-sm);
            overflow: hidden;
        }}

        .dimension-bar {{
            height: 100%;
            border-radius: var(--radius-sm);
            transition: width var(--transition-slow);
        }}

        .dimension-score {{
            min-width: 30px;
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-primary);
            text-align: right;
        }}

        .no-issues {{
            padding: var(--space-md);
            background: rgba(34, 197, 94, 0.1);
            border-radius: var(--radius-md);
            color: var(--color-success);
            font-size: 0.875rem;
        }}

        .problem-fields {{
            padding-top: var(--space-md);
            border-top: 1px solid var(--border-primary);
        }}

        .problem-fields h5 {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: var(--space-sm);
            color: var(--color-warning);
        }}

        .problem-field {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-sm) 0;
            font-size: 0.8125rem;
        }}

        .problem-path {{
            font-family: var(--font-mono);
            color: var(--accent-primary);
        }}

        .problem-score {{
            font-weight: 600;
            color: var(--color-danger);
        }}

        .problem-issues {{
            color: var(--text-tertiary);
        }}

        .attention-section {{
            margin-top: var(--space-lg);
        }}
        .attention-section .card-subtitle {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-left: var(--space-sm);
        }}
        .attention-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: var(--space-md);
        }}
        .attention-block {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            padding: var(--space-md);
        }}
        .attention-block-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: var(--space-sm);
        }}
        .attention-block-header h4 {{
            margin: 0;
            font-size: 0.95rem;
            color: var(--text-primary);
        }}
        .attention-block .problem-fields {{
            padding-top: 0;
            border-top: none;
        }}
        .attention-block .problem-field {{
            border-top: 1px dashed var(--border-primary);
        }}
        .attention-block .problem-field:first-child {{
            border-top: none;
        }}
        .attention-block .problem-path {{
            flex: 1;
            word-break: break-all;
        }}
        .attention-block .problem-score {{
            min-width: 28px;
            text-align: right;
        }}
        .attention-block .problem-issues {{
            flex: 1;
            text-align: right;
            font-size: 0.75rem;
        }}

        /* Section header spacing — applies to all h3 inside tab-content sections.
           Adds breathing room between a heading and the table/content beneath it. */
        .tab-content h3 {{
            margin-top: var(--space-xl);
            margin-bottom: var(--space-md);
            padding-bottom: var(--space-sm);
            border-bottom: 1px solid var(--border-primary);
        }}
        .tab-content > h3:first-child,
        .tab-content > div > h3:first-child,
        .tab-content .joins-section h3:first-of-type,
        .tab-content .patterns-section h3:first-of-type,
        .tab-content .insights-section h3:first-of-type {{
            margin-top: 0;
        }}

        /* ── Join Keys sub-tab bar ─────────────────────────────────────────── */
        .jk-subtab-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: var(--space-lg);
            padding-bottom: var(--space-md);
            border-bottom: 1px solid var(--border-primary);
        }}
        .jk-subtab-btn {{
            display: inline-flex;
            align-items: center;
            gap: 7px;
            padding: 6px 16px;
            font-size: 0.84rem;
            font-weight: 500;
            border-radius: var(--radius-sm);
            border: 1.5px solid var(--border-primary);
            background: var(--bg-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            transition: border-color 0.15s, background 0.15s, color 0.15s;
            white-space: nowrap;
        }}
        .jk-subtab-btn:hover {{
            border-color: var(--accent-primary);
            color: var(--text-primary);
        }}
        .jk-subtab-btn.jk-active {{
            border-color: var(--accent-primary);
            background: rgba(99, 102, 241, 0.1);
            color: var(--text-primary);
            font-weight: 600;
        }}
        .jk-count {{
            background: var(--bg-tertiary);
            padding: 1px 7px;
            border-radius: 99px;
            font-size: 0.72rem;
            font-weight: 700;
            color: var(--text-secondary);
        }}
        .jk-subtab-btn.jk-active .jk-count {{
            background: var(--accent-primary);
            color: white;
        }}
        .jk-pane {{
            animation: fadeIn 0.1s ease;
        }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

        /* ER Diagram */
        .er-diagram-section {{
            margin-bottom: var(--space-lg);
            padding: var(--space-md);
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            overflow-x: auto;
        }}
        .er-diagram-section svg {{
            display: block;
            margin: 0 auto;
            max-width: 100%;
            height: auto;
        }}
        .er-legend {{
            display: flex;
            gap: var(--space-md);
            justify-content: center;
            margin-top: var(--space-sm);
            flex-wrap: wrap;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        .er-legend span {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .er-legend i {{
            display: inline-block;
            width: 18px;
            height: 2px;
        }}
        .mermaid-source {{
            margin-top: var(--space-md);
        }}
        .mermaid-source summary {{
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 0.85rem;
            padding: var(--space-xs) 0;
        }}
        .mermaid-source pre {{
            background: var(--bg-tertiary);
            border: 1px solid var(--border-primary);
            border-radius: 6px;
            padding: var(--space-md);
            overflow-x: auto;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            color: var(--text-primary);
        }}

        /* New: Schema dimensions radar + Insights/SWOT/Recommendations + Patterns + Joins + Similar */
        .schema-dimensions {{
            margin-left: var(--space-lg);
            padding: var(--space-md);
            background: var(--bg-secondary);
            border-radius: 8px;
            display: inline-flex;
            flex-direction: column;
            align-items: center;
        }}
        .schema-dimensions h4 {{ margin: 0 0 var(--space-sm) 0; }}

        .insights-section h3 {{ margin-top: var(--space-lg); }}
        .data-story {{
            padding: var(--space-md);
            background: var(--bg-secondary);
            border-radius: 8px;
            font-size: 1rem;
            line-height: 1.6;
        }}
        .swot-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: var(--space-md);
            margin-bottom: var(--space-md);
        }}
        .swot-card {{
            padding: var(--space-md);
            border-radius: 8px;
            background: var(--bg-secondary);
            border-left: 4px solid var(--color-info);
        }}
        .swot-card h4 {{ margin: 0 0 var(--space-sm) 0; }}
        .swot-card ul {{ margin: 0; padding-left: 1.2rem; }}
        .swot-good   {{ border-left-color: var(--color-success); }}
        .swot-warn   {{ border-left-color: var(--color-warning); }}
        .swot-info   {{ border-left-color: var(--color-info); }}
        .swot-danger {{ border-left-color: var(--color-danger); }}

        .severity {{ padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }}
        .sev-high   {{ background: rgba(239, 71, 111, 0.18); color: var(--color-danger); }}
        .sev-medium {{ background: rgba(255, 209, 102, 0.2);  color: var(--color-warning); }}
        .sev-low    {{ background: rgba(126, 217, 87, 0.18);  color: var(--color-success); }}

        .ai-readiness-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-top: var(--space-lg);
        }}
        .ai-readiness-score strong {{ color: var(--accent-primary); }}

        .ai-insights-section {{ max-width: 1200px; }}
        .ai-insights-banner {{
            padding: var(--space-md) var(--space-lg);
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(168, 85, 247, 0.08));
            border: 1px solid rgba(99, 102, 241, 0.25);
            border-radius: 12px;
            margin-bottom: var(--space-lg);
        }}
        .ai-insights-badge {{
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--accent-primary);
            margin-bottom: var(--space-sm);
        }}
        .ai-insights-meta {{ margin: 0 0 var(--space-sm); color: var(--text-secondary); }}
        .ai-insights-disclaimer {{
            margin: 0;
            font-size: 0.875rem;
            color: var(--text-muted);
            font-style: italic;
        }}
        .ai-insight-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: var(--space-md);
        }}
        .ai-insight-card {{
            background: var(--bg-secondary);
            border-radius: 10px;
            border: 1px solid var(--border-color);
            overflow: hidden;
        }}
        .ai-insight-card header {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            padding: var(--space-md);
            border-bottom: 1px solid var(--border-color);
            background: var(--bg-tertiary);
        }}
        .ai-insight-card h4 {{ margin: 0; font-size: 0.95rem; }}
        .ai-insight-icon {{ font-size: 1.25rem; }}
        .ai-insight-body {{
            padding: var(--space-md);
            font-size: 0.9rem;
            line-height: 1.55;
        }}
        .ai-insight-body p {{ margin: 0 0 var(--space-sm); }}
        .ai-insight-list {{ margin: 0; padding-left: 1.2rem; }}
        .ai-recommendations {{ margin-top: var(--space-xl); }}
        .ai-rec-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: var(--space-md);
        }}
        .ai-rec-card {{
            padding: var(--space-md);
            background: var(--bg-secondary);
            border-radius: 8px;
            border-left: 4px solid var(--color-info);
        }}
        .ai-rec-card.sev-high {{ border-left-color: var(--color-danger); }}
        .ai-rec-card.sev-medium {{ border-left-color: var(--color-warning); }}
        .ai-rec-card.sev-low {{ border-left-color: var(--color-success); }}
        .ai-rec-severity {{
            font-size: 0.7rem;
            font-weight: 700;
            margin-right: var(--space-sm);
        }}
        .ai-rec-category {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        .ai-rec-action {{ margin: var(--space-sm) 0 0; }}
        .ai-insights-empty {{ padding: var(--space-lg); color: var(--text-muted); }}

        .content-universe {{ margin: var(--space-md) 0; }}
        .universe-layout {{
            display: flex; gap: var(--space-lg); align-items: center; flex-wrap: wrap;
        }}
        .universe-legend {{ display: flex; flex-direction: column; gap: 4px; }}
        .legend-row {{ display: flex; align-items: center; gap: var(--space-sm); font-size: 0.875rem; }}
        .legend-swatch {{ width: 14px; height: 14px; border-radius: 3px; display: inline-block; }}

        .pattern-pill {{
            display: inline-block;
            padding: 2px 8px;
            margin: 2px;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            background: var(--bg-tertiary, var(--bg-secondary));
            border: 1px solid var(--border-primary);
            border-radius: 10px;
        }}
        .pill-row {{ margin-bottom: var(--space-md); }}

        .badge {{
            padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;
            margin-right: 4px;
        }}
        .badge-good {{ background: rgba(126, 217, 87, 0.2); color: var(--color-success); }}
        .badge-warn {{ background: rgba(255, 209, 102, 0.2); color: var(--color-warning); }}

        .similar-group {{
            margin: var(--space-md) 0;
            padding: var(--space-md);
            background: var(--bg-secondary);
            border-radius: 8px;
        }}
        .similar-group h4 {{ margin: 0 0 var(--space-sm) 0; font-family: var(--font-mono); }}

        /* ═══════════════════════════════════════════════════════════════════════
           STATISTICS TAB
           ═══════════════════════════════════════════════════════════════════════ */
        .stats-summary {{
            display: flex;
            gap: var(--space-md);
            margin-bottom: var(--space-md);
            padding: var(--space-sm) var(--space-md);
            background: var(--bg-secondary);
            border-radius: var(--radius-md);
        }}

        .stats-metric {{
            text-align: center;
        }}

        .stats-metric-value {{
            display: block;
            font-size: 1.375rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .stats-metric-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .stats-object {{
            margin-bottom: var(--space-md);
        }}

        .stats-object h3 {{
            font-size: 0.9375rem;
            font-weight: 600;
            margin-bottom: var(--space-sm);
            padding-bottom: 4px;
            border-bottom: 2px solid var(--accent-primary);
        }}

        .stats-section {{
            margin-bottom: var(--space-md);
        }}

        .stats-section h4 {{
            font-size: 0.8125rem;
            font-weight: 600;
            margin-bottom: var(--space-sm);
            color: var(--text-secondary);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           PII TAB
           ═══════════════════════════════════════════════════════════════════════ */
        .pii-summary {{
            padding: var(--space-sm) var(--space-md);
            background: var(--bg-secondary);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-md);
        }}

        .pii-summary-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-sm);
        }}

        .pii-total {{
            text-align: right;
        }}

        .pii-total-count {{
            display: block;
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--color-warning);
        }}

        .pii-total-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .pii-types {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
        }}

        .high-risk-card {{
            border-left: 4px solid var(--color-danger);
            margin-bottom: var(--space-md);
        }}

        .high-risk-row {{
            background: rgba(239, 68, 68, 0.05);
        }}

        .pii-object-section {{
            margin-bottom: var(--space-md);
        }}

        .pii-object-section h4 {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: var(--space-sm);
            padding-bottom: 4px;
            border-bottom: 2px solid var(--accent-primary);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           RELATIONSHIPS TAB
           ═══════════════════════════════════════════════════════════════════════ */
        .relationships-summary {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-sm) var(--space-md);
            background: var(--bg-secondary);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-md);
        }}

        .rel-total {{
            text-align: center;
        }}

        .rel-total-value {{
            display: block;
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--accent-primary);
        }}

        .rel-total-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .rel-types {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
        }}

        .rel-type-badge {{
            padding: 4px 12px;
            font-size: 0.75rem;
            font-weight: 500;
            border-radius: var(--radius-sm);
        }}

        .rel-foreign_key {{ background: rgba(59, 130, 246, 0.2); color: var(--color-info); }}
        .rel-shared_enum {{ background: rgba(168, 85, 247, 0.2); color: #a855f7; }}
        .rel-hierarchy {{ background: rgba(34, 197, 94, 0.2); color: var(--color-success); }}
        .rel-structural_candidate {{ background: rgba(14, 165, 233, 0.15); color: var(--color-info); }}
        .rel-value_join {{ background: rgba(34, 197, 94, 0.15); color: var(--color-success); }}

        /* Relationship filter bar */
        .rel-filter-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
            margin-top: var(--space-sm);
        }}

        .rel-filter-btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 14px;
            font-size: 0.8rem;
            font-weight: 500;
            border-radius: var(--radius-sm);
            border: 1.5px solid var(--border-primary);
            background: var(--bg-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s;
        }}

        .rel-filter-btn:hover {{
            border-color: var(--accent-primary);
            color: var(--text-primary);
        }}

        .rel-filter-btn.active {{
            border-color: var(--accent-primary);
            background: rgba(var(--accent-primary-rgb, 99, 102, 241), 0.12);
            color: var(--text-primary);
            font-weight: 600;
        }}

        .rel-filter-count {{
            background: var(--bg-tertiary);
            padding: 1px 7px;
            border-radius: 99px;
            font-size: 0.72rem;
            font-weight: 700;
        }}

        .rel-filter-btn.active .rel-filter-count {{
            background: var(--accent-primary);
            color: white;
        }}

        .confidence-badge {{
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: var(--radius-sm);
        }}

        .conf-high {{ background: rgba(34, 197, 94, 0.2); color: var(--color-success); }}
        .conf-medium {{ background: rgba(234, 179, 8, 0.2); color: var(--color-warning); }}
        .conf-low {{ background: rgba(239, 68, 68, 0.2); color: var(--color-danger); }}

        .evidence-cell {{
            font-size: 0.8125rem;
            color: var(--text-secondary);
            max-width: 300px;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           CROSS-OBJECT TAB
           ═══════════════════════════════════════════════════════════════════════ */
        .cross-object-info {{
            margin-bottom: var(--space-sm);
        }}

        .cross-object-info h3 {{
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: var(--space-sm);
        }}

        .cross-object-info p {{
            color: var(--text-secondary);
        }}

        .object-badge {{
            display: inline-flex;
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: 500;
            background: var(--bg-tertiary);
            border-radius: var(--radius-sm);
            margin-right: 4px;
            margin-bottom: 4px;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           EMPTY STATES & WARNINGS
           ═══════════════════════════════════════════════════════════════════════ */
        .empty-state {{
            text-align: center;
            padding: var(--space-2xl);
            color: var(--text-secondary);
        }}

        .empty-state.success {{
            background: rgba(34, 197, 94, 0.1);
            border-radius: var(--radius-lg);
        }}

        .empty-icon {{
            font-size: 3rem;
            display: block;
            margin-bottom: var(--space-md);
        }}

        .warning-summary {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-md) var(--space-lg);
            background: rgba(234, 179, 8, 0.1);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-lg);
            color: var(--color-warning);
            font-weight: 500;
        }}

        .warning-icon {{
            font-size: 1.25rem;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           BUTTONS
           ═══════════════════════════════════════════════════════════════════════ */
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: var(--space-sm);
            padding: var(--space-sm) var(--space-md);
            font-family: var(--font-sans);
            font-size: 0.875rem;
            font-weight: 500;
            border: none;
            border-radius: var(--radius-md);
            cursor: pointer;
            transition: all var(--transition-fast);
        }}

        .btn-primary {{
            background: var(--accent-primary);
            color: var(--text-inverse);
        }}

        .btn-primary:hover {{
            opacity: 0.9;
        }}

        .btn-secondary {{
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-primary);
        }}

        .btn-secondary:hover {{
            background: var(--bg-hover);
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           DISTINCT VALUES MODAL
           ═══════════════════════════════════════════════════════════════════════ */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            backdrop-filter: blur(4px);
        }}

        .modal-overlay.active {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .modal-content {{
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-primary);
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow: hidden;
            box-shadow: var(--shadow-lg);
            animation: modalSlideIn var(--transition-normal);
        }}

        @keyframes modalSlideIn {{
            from {{ opacity: 0; transform: translateY(-20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: var(--space-lg);
            border-bottom: 1px solid var(--border-primary);
            background: var(--bg-tertiary);
        }}

        .modal-header h3 {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0;
        }}

        .modal-close {{
            background: none;
            border: none;
            font-size: 1.5rem;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 0;
            line-height: 1;
        }}

        .modal-close:hover {{
            color: var(--text-primary);
        }}

        .modal-body {{
            padding: var(--space-lg);
            overflow-y: auto;
            max-height: calc(80vh - 80px);
        }}

        .modal-meta {{
            display: flex;
            gap: var(--space-lg);
            margin-bottom: var(--space-lg);
            padding-bottom: var(--space-md);
            border-bottom: 1px solid var(--border-primary);
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .modal-meta span {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        /* Value Distribution Bars */
        .value-bar-list {{
            display: flex;
            flex-direction: column;
            gap: var(--space-sm);
        }}

        .value-bar-item {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
        }}

        .value-bar-label {{
            min-width: 150px;
            max-width: 200px;
            font-family: var(--font-mono);
            font-size: 0.8125rem;
            color: var(--text-primary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .value-bar-track {{
            flex: 1;
            height: 24px;
            background: var(--bg-tertiary);
            border-radius: var(--radius-sm);
            overflow: hidden;
        }}

        .value-bar-fill {{
            height: 100%;
            background: var(--accent-gradient);
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: var(--space-sm);
            min-width: 30px;
            transition: width var(--transition-slow);
        }}

        .value-bar-count {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-inverse);
            white-space: nowrap;
        }}

        .value-bar-pct {{
            min-width: 50px;
            text-align: right;
            font-size: 0.8125rem;
            font-weight: 500;
            color: var(--text-secondary);
        }}

        /* View button in table */
        .distinct-view-btn {{
            display: inline-flex;
            align-items: center;
            gap: var(--space-xs);
            background: var(--bg-tertiary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-sm);
            padding: 2px 8px;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--text-primary);
            cursor: pointer;
            transition: all var(--transition-fast);
        }}

        .distinct-view-btn:hover {{
            background: var(--bg-hover);
            border-color: var(--accent-primary);
            color: var(--accent-primary);
        }}

        .distinct-view-btn .icon {{
            font-size: 0.875rem;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           RESPONSIVE
           ═══════════════════════════════════════════════════════════════════════ */
        @media (max-width: 768px) {{
            html {{
                font-size: 14px;
            }}

            .header-content {{
                flex-direction: column;
                align-items: flex-start;
            }}

            .tabs {{
                flex-wrap: nowrap;
                overflow-x: auto;
                padding-bottom: var(--space-sm);
            }}

            .tab-label {{
                display: none;
            }}

            .overview-grid {{
                grid-template-columns: 1fr;
            }}

            .dqi-card {{
                grid-column: span 1;
            }}

            .distributions-grid,
            .quality-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           PERSONA TOGGLE
           ═══════════════════════════════════════════════════════════════════════ */
        .persona-toggle {{
            display: flex;
            align-items: center;
            gap: 2px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-lg);
            padding: 3px;
        }}
        .persona-btn {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            font-family: var(--font-sans);
            font-size: 0.8rem;
            font-weight: 500;
            border: none;
            border-radius: var(--radius-md);
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all var(--transition-fast);
            white-space: nowrap;
        }}
        .persona-btn:hover {{
            background: var(--bg-hover);
            color: var(--text-primary);
        }}
        .persona-btn.active {{
            background: var(--accent-primary);
            color: var(--text-inverse);
        }}
        .persona-btn .persona-icon {{
            font-size: 1rem;
        }}
        @media (max-width: 900px) {{
            .persona-btn .persona-label {{ display: none; }}
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           CHAPTER NAVIGATION
           ═══════════════════════════════════════════════════════════════════════ */
        .chapter-nav {{
            display: flex;
            gap: 6px;
            margin-bottom: var(--space-sm);
            padding: 6px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-primary);
            border-radius: var(--radius-lg);
            overflow-x: auto;
        }}
        .chapter-btn {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 18px;
            font-family: var(--font-sans);
            font-size: 0.9rem;
            font-weight: 600;
            border: 2px solid transparent;
            border-radius: var(--radius-md);
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all var(--transition-fast);
            white-space: nowrap;
        }}
        .chapter-btn:hover {{
            background: var(--bg-hover);
            color: var(--text-primary);
            border-color: var(--border-secondary);
        }}
        .chapter-btn.active {{
            background: var(--accent-primary);
            color: var(--text-inverse);
            border-color: var(--accent-primary);
        }}
        .chapter-btn .chapter-icon {{
            font-size: 1.1rem;
        }}
        .chapter-tabs {{
            display: none;
            flex-wrap: wrap;
            gap: var(--space-xs);
            padding: 4px;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-sm);
        }}
        .chapter-tabs.active {{
            display: flex;
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           COVER SUMMARY BAND
           ═══════════════════════════════════════════════════════════════════════ */
        .cover-band {{
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: var(--space-xl);
            align-items: center;
            padding: var(--space-lg) var(--space-xl);
            margin-bottom: var(--space-lg);
            background: var(--accent-gradient);
            border-radius: var(--radius-lg);
            color: white;
        }}
        .cover-verdict {{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }}
        .cover-verdict-ring {{
            width: 90px;
            height: 90px;
            border-radius: 50%;
            border: 4px solid rgba(255,255,255,0.3);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: rgba(0,0,0,0.2);
        }}
        .cover-verdict-ring.healthy {{ border-color: #22c55e; }}
        .cover-verdict-ring.attention {{ border-color: #eab308; }}
        .cover-verdict-ring.risk {{ border-color: #ef4444; }}
        .cover-verdict-score {{
            font-size: 1.8rem;
            font-weight: 800;
            line-height: 1;
        }}
        .cover-verdict-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            opacity: 0.9;
        }}
        .cover-info {{
            display: flex;
            flex-direction: column;
            gap: var(--space-sm);
        }}
        .cover-title {{
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .cover-subtitle {{
            font-size: 0.9rem;
            opacity: 0.85;
        }}
        .cover-meta {{
            display: flex;
            gap: var(--space-lg);
            flex-wrap: wrap;
        }}
        .cover-meta-item {{
            display: flex;
            flex-direction: column;
        }}
        .cover-meta-value {{
            font-size: 1.3rem;
            font-weight: 700;
        }}
        .cover-meta-label {{
            font-size: 0.75rem;
            opacity: 0.75;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .cover-kpis {{
            display: flex;
            gap: var(--space-md);
        }}
        .cover-kpi {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: var(--space-sm) var(--space-md);
            background: rgba(255,255,255,0.15);
            border-radius: var(--radius-md);
            min-width: 70px;
        }}
        .cover-kpi-value {{
            font-size: 1.4rem;
            font-weight: 700;
        }}
        .cover-kpi-label {{
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.8;
        }}
        @media (max-width: 900px) {{
            .cover-band {{
                grid-template-columns: 1fr;
                text-align: center;
            }}
            .cover-kpis {{
                justify-content: center;
            }}
            .cover-meta {{
                justify-content: center;
            }}
        }}

        /* ═══════════════════════════════════════════════════════════════════════
           PERSONA-BASED VISIBILITY
           ═══════════════════════════════════════════════════════════════════════ */
        /* Business persona: hide technical details */
        [data-persona="business"] .tech-only,
        [data-persona="business"] [data-persona-hide~="business"] {{
            display: none !important;
        }}
        /* Technical persona: shows everything */
        [data-persona="technical"] [data-persona-hide~="technical"] {{
            display: none !important;
        }}
        /* Simplified language for business */
        [data-persona="business"] .tech-lang {{ display: none; }}
        [data-persona="business"] .biz-lang {{ display: inline; }}
        .biz-lang {{ display: none; }}
        [data-persona="technical"] .biz-lang {{ display: none; }}

        /* ═══════════════════════════════════════════════════════════════════════
           PRINT STYLES
           ═══════════════════════════════════════════════════════════════════════ */
        @media print {{
            body {{
                background: white;
                color: black;
                font-size: 10pt;
            }}
            header {{
                position: static;
                background: white;
                border-bottom: 2px solid #333;
                padding: 10px 0;
            }}
            .theme-toggle, .persona-toggle, .header-search {{
                display: none !important;
            }}
            .chapter-nav, .tabs {{
                display: none !important;
            }}
            .tab-content {{
                display: block !important;
                page-break-inside: avoid;
                border: 1px solid #ccc;
                margin-bottom: 20px;
                box-shadow: none;
            }}
            .tab-content::before {{
                content: attr(data-print-title);
                display: block;
                font-size: 14pt;
                font-weight: bold;
                margin-bottom: 10px;
                padding-bottom: 5px;
                border-bottom: 1px solid #ccc;
            }}
            .cover-band {{
                background: #f0f0f0 !important;
                color: black !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .modal-overlay {{
                display: none !important;
            }}
            .btn, button {{
                display: none;
            }}
            .data-table {{
                font-size: 8pt;
            }}
            .container {{
                max-width: 100%;
                padding: 0;
            }}
        }}
    </style>
</head>
<body data-persona="technical">
    <header>
        <div class="header-content">
            <div class="header-title">
                <img class="logo-mark logo-mark-light" src="{logo_icon_light}" alt="">
                <img class="logo-mark logo-mark-dark" src="{logo_icon_dark}" alt="">
                <span class="brand">
                    <span class="brand-name"><span class="brand-accent">Data</span>lens</span>
                    <span class="brand-sub">Schema Analysis</span>
                </span>
                <h1 class="visually-hidden">Datalens Schema Analysis</h1>
            </div>
            <div class="header-search">
                <input type="text" class="search-input" id="globalSearch" placeholder="🔍 Search fields, objects, values across all tabs…" autocomplete="off">
                <div class="search-status" id="searchStatus"></div>
            </div>
            <div class="header-meta">
                <div class="meta-item">
                    <span>Version:</span>
                    <span class="meta-value">{version_tag}</span>
                </div>
                <div class="meta-item">
                    <span>Objects:</span>
                    <span class="meta-value">{total_objects}</span>
                </div>
                <div class="meta-item">
                    <span>Fields:</span>
                    <span class="meta-value">{total_fields}</span>
                </div>
                <div class="meta-item">
                    <span>Sampled:</span>
                    <span class="meta-value">{total_sampled:,}</span>
                </div>
                <div class="theme-toggle">
                    <button class="theme-btn" id="lightBtn" title="Light Mode" onclick="setTheme('light')">☀️</button>
                    <button class="theme-btn active" id="darkBtn" title="Dark Mode" onclick="setTheme('dark')">🌙</button>
                </div>
                <div class="persona-toggle" title="Switch view perspective">
                    <button class="persona-btn" data-persona="business" onclick="setPersona('business')">
                        <span class="persona-icon">🧑‍💼</span>
                        <span class="persona-label">Business</span>
                    </button>
                    <button class="persona-btn active" data-persona="technical" onclick="setPersona('technical')">
                        <span class="persona-icon">🛠️</span>
                        <span class="persona-label">Technical</span>
                    </button>
                </div>
            </div>
        </div>
    </header>

    <div class="container">
        <!-- Chapter Navigation -->
        <nav class="chapter-nav" aria-label="Report chapters">
            <button class="chapter-btn active" data-chapter="verdict" onclick="switchChapter('verdict')">
                <span class="chapter-icon">📊</span>
                <span>Verdict</span>
            </button>
            <button class="chapter-btn" data-chapter="shape" onclick="switchChapter('shape')">
                <span class="chapter-icon">💡</span>
                <span>Shape</span>
            </button>
            <button class="chapter-btn" data-chapter="health" onclick="switchChapter('health')">
                <span class="chapter-icon">✅</span>
                <span>Health</span>
            </button>
            <button class="chapter-btn" data-chapter="structure" onclick="switchChapter('structure')">
                <span class="chapter-icon">🔗</span>
                <span>Structure</span>
            </button>
            <button class="chapter-btn" data-chapter="fingerprint" onclick="switchChapter('fingerprint')">
                <span class="chapter-icon">🔬</span>
                <span>Fingerprint</span>
            </button>
        </nav>

        <!-- Chapter Sub-tabs -->
        <div class="chapter-tabs active" id="chapter-verdict-tabs">
            {tabs_verdict}
        </div>
        <div class="chapter-tabs" id="chapter-shape-tabs">
            {tabs_shape}
        </div>
        <div class="chapter-tabs" id="chapter-health-tabs">
            {tabs_health}
        </div>
        <div class="chapter-tabs" id="chapter-structure-tabs">
            {tabs_structure}
        </div>
        <div class="chapter-tabs" id="chapter-fingerprint-tabs">
            {tabs_fingerprint}
        </div>

        <div class="tab-content active" id="overview" data-chapter="verdict" data-print-title="Overview &amp; Verdict">
            {overview}
        </div>

        <div class="tab-content" id="trends" data-chapter="fingerprint" data-print-title="Trends &amp; Drift">
            {trends}
        </div>

        <div class="tab-content" id="quality" data-chapter="health" data-print-title="Data Quality">
            {quality}
        </div>

        <div class="tab-content" id="pii" data-chapter="health" data-print-title="PII Detection">
            {pii}
        </div>

        <div class="tab-content" id="field-explorer" data-chapter="structure" data-print-title="Field Explorer">
            {field_explorer}
        </div>

        <div class="tab-content" id="coverage" data-chapter="shape" data-print-title="Coverage Analysis">
            {coverage}
        </div>

        <div class="tab-content" id="distributions" data-chapter="fingerprint" data-print-title="Distributions">
            {distributions}
        </div>

        <div class="tab-content" id="type-warnings" data-chapter="health" data-print-title="Type Warnings">
            {type_warnings}
        </div>

        <div class="tab-content" id="relationships" data-chapter="structure" data-print-title="Relationships">
            {relationships}
        </div>

        <div class="tab-content" id="insights" data-chapter="shape" data-print-title="Insights">
            {insights}
        </div>

        <div class="tab-content" id="ai-insights" data-chapter="shape" data-print-title="AI Insights">
            {ai_insights}
        </div>

        <div class="tab-content" id="patterns" data-chapter="fingerprint" data-print-title="Patterns">
            {patterns}
        </div>

        <div class="tab-content" id="join-keys" data-chapter="structure" data-print-title="Cross-Object Analysis">
            {joins}
        </div>

    </div>

    <!-- Distinct Values Modal -->
    <div class="modal-overlay" id="distinctModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modalTitle">Value Distribution</h3>
                <button class="modal-close" onclick="closeDistinctModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="modal-meta">
                    <div>Total Distinct: <span id="modalDistinctCount">0</span></div>
                    <div>Showing Top: <span id="modalShowingCount">0</span></div>
                </div>
                <div class="value-bar-list" id="valueBarList"></div>
            </div>
        </div>
    </div>

    <!-- Datalens Footer -->
    <footer style="text-align: center; padding: 20px; border-top: 1px solid var(--border-color); color: var(--text-secondary); font-size: 12px; margin-top: 40px;">
        <div style="margin-bottom: 8px;">Generated with <strong>Datalens</strong> — Advanced Schema Analysis & Data Profiling</div>
        <div style="opacity: 0.7;">Open-source & lightweight • Works offline • Zero dependencies</div>
    </footer>

    <script>
        // Field value distributions data (embedded from analysis)
        const fieldValueDistributions = {field_distributions_json};
        const maxDistinctConfigured = {max_distinct_configured};
        // ═══════════════════════════════════════════════════════════════════════
        // THEME SWITCHING
        // ═══════════════════════════════════════════════════════════════════════
        function setTheme(theme) {{
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('datalens-theme', theme);

            document.getElementById('lightBtn').classList.toggle('active', theme === 'light');
            document.getElementById('darkBtn').classList.toggle('active', theme === 'dark');
        }}

        // Load saved theme or default to dark
        const savedTheme = localStorage.getItem('datalens-theme') || 'dark';
        setTheme(savedTheme);

        // ═══════════════════════════════════════════════════════════════════════
        // PERSONA SWITCHING
        // ═══════════════════════════════════════════════════════════════════════
        function setPersona(persona) {{
            document.body.setAttribute('data-persona', persona);
            localStorage.setItem('datalens-persona', persona);

            document.querySelectorAll('.persona-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.persona === persona);
            }});
        }}

        // Load saved persona or default to technical.
        // Migrate legacy values ('analyst'/'engineer') to the merged 'technical' view.
        let savedPersona = localStorage.getItem('datalens-persona') || 'technical';
        if (savedPersona === 'analyst' || savedPersona === 'engineer') {{
            savedPersona = 'technical';
        }}
        setPersona(savedPersona);

        // ═══════════════════════════════════════════════════════════════════════
        // CHAPTER NAVIGATION
        // ═══════════════════════════════════════════════════════════════════════
        let currentChapter = 'verdict';

        function switchChapter(chapter) {{
            currentChapter = chapter;

            // Update chapter buttons
            document.querySelectorAll('.chapter-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.chapter === chapter);
            }});

            // Show/hide chapter tab bars
            document.querySelectorAll('.chapter-tabs').forEach(tabs => {{
                tabs.classList.remove('active');
            }});
            const chapterTabs = document.getElementById(`chapter-${{chapter}}-tabs`);
            if (chapterTabs) {{
                chapterTabs.classList.add('active');
            }}

            // Activate the first tab in this chapter
            const firstTab = chapterTabs?.querySelector('.tab');
            if (firstTab) {{
                // Deactivate all tabs and contents
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                // Activate first tab in chapter
                firstTab.classList.add('active');
                const targetId = firstTab.dataset.tab;
                const targetContent = document.getElementById(targetId);
                if (targetContent) {{
                    targetContent.classList.add('active');
                }}
            }}
        }}

        // ═══════════════════════════════════════════════════════════════════════
        // TAB SWITCHING (with chapter awareness)
        // ═══════════════════════════════════════════════════════════════════════
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                const targetId = tab.dataset.tab;
                const targetContent = document.getElementById(targetId);
                if (targetContent) {{
                    targetContent.classList.add('active');

                    // Update chapter nav to match the tab's chapter
                    const tabChapter = targetContent.dataset.chapter;
                    if (tabChapter && tabChapter !== currentChapter) {{
                        currentChapter = tabChapter;
                        document.querySelectorAll('.chapter-btn').forEach(btn => {{
                            btn.classList.toggle('active', btn.dataset.chapter === tabChapter);
                        }});
                        document.querySelectorAll('.chapter-tabs').forEach(tabs => {{
                            tabs.classList.remove('active');
                        }});
                        const chapterTabs = document.getElementById(`chapter-${{tabChapter}}-tabs`);
                        if (chapterTabs) chapterTabs.classList.add('active');
                    }}
                }}
            }});
        }});

        // ═══════════════════════════════════════════════════════════════════════
        // GLOBAL SEARCH (works across every tab)
        // ═══════════════════════════════════════════════════════════════════════
        const searchInput = document.getElementById('globalSearch');
        const searchStatus = document.getElementById('searchStatus');
        // Selectors that represent "row-level" units we hide/show per match.
        const ROW_SELECTORS = [
            '.data-table tbody tr',
            '.distribution-card',
            '.quality-card',
            '.attention-block',
            '.pii-object-section',
            '.problem-field',
            '.similar-group',
            '.pattern-pill',
            '.swot-card',
            '.universe-row'
        ].join(',');

        function clearHighlights(root) {{
            root.querySelectorAll('mark.search-hit').forEach(m => {{
                const parent = m.parentNode;
                parent.replaceChild(document.createTextNode(m.textContent), m);
                parent.normalize();
            }});
        }}

        function highlightText(root, query) {{
            if (!query) return;
            const re = new RegExp('(' + query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'ig');
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {{
                acceptNode: (n) => {{
                    if (!n.nodeValue || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
                    if (n.parentNode.closest('script,style,mark')) return NodeFilter.FILTER_REJECT;
                    return re.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                }}
            }});
            const nodes = [];
            let cur;
            while ((cur = walker.nextNode())) nodes.push(cur);
            nodes.forEach(node => {{
                const span = document.createElement('span');
                span.innerHTML = node.nodeValue.replace(re, '<mark class="search-hit">$1</mark>');
                node.parentNode.replaceChild(span, node);
            }});
        }}

        function runGlobalSearch(query) {{
            const tabs = document.querySelectorAll('.tab');
            const contents = document.querySelectorAll('.tab-content');
            // Always clear prior state
            tabs.forEach(t => {{
                t.classList.remove('has-search-hit');
                t.removeAttribute('data-hits');
            }});
            contents.forEach(c => {{
                clearHighlights(c);
                c.querySelectorAll(ROW_SELECTORS).forEach(r => {{ r.style.display = ''; }});
            }});

            if (!query) {{
                searchStatus.textContent = '';
                searchStatus.className = 'search-status';
                return;
            }}

            const q = query.toLowerCase();
            let totalHits = 0;
            let firstHitTabId = null;

            contents.forEach(content => {{
                const rows = content.querySelectorAll(ROW_SELECTORS);
                let tabHits = 0;
                if (rows.length === 0) {{
                    // Tabs without row units: count by raw text presence
                    if (content.textContent.toLowerCase().includes(q)) {{
                        tabHits = 1;
                    }}
                }} else {{
                    rows.forEach(r => {{
                        if (r.textContent.toLowerCase().includes(q)) {{
                            r.style.display = '';
                            tabHits += 1;
                        }} else {{
                            r.style.display = 'none';
                        }}
                    }});
                }}
                if (tabHits > 0) {{
                    highlightText(content, query);
                    const tab = document.querySelector('.tab[data-tab="' + content.id + '"]');
                    if (tab) {{
                        tab.classList.add('has-search-hit');
                        tab.setAttribute('data-hits', tabHits);
                    }}
                    totalHits += tabHits;
                    if (!firstHitTabId) firstHitTabId = content.id;
                }}
            }});

            if (totalHits > 0) {{
                searchStatus.textContent = totalHits + ' match' + (totalHits === 1 ? '' : 'es') + ' across tabs';
                searchStatus.className = 'search-status has-hits';
                // Auto-switch to first matching tab if current active tab has none
                const activeTab = document.querySelector('.tab.active');
                if (activeTab && !activeTab.classList.contains('has-search-hit') && firstHitTabId) {{
                    const target = document.querySelector('.tab[data-tab="' + firstHitTabId + '"]');
                    if (target) target.click();
                }}
            }} else {{
                searchStatus.textContent = 'No matches';
                searchStatus.className = 'search-status no-hits';
            }}
        }}

        let searchTimer;
        searchInput.addEventListener('input', (e) => {{
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => runGlobalSearch(e.target.value.trim()), 150);
        }});

        // ═══════════════════════════════════════════════════════════════════════
        // TABLE SORTING
        // ═══════════════════════════════════════════════════════════════════════
        document.querySelectorAll('.sortable th').forEach(th => {{
            th.addEventListener('click', () => {{
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                if (!tbody) return;

                const rows = Array.from(tbody.querySelectorAll('tr'));
                const idx = Array.from(th.parentNode.children).indexOf(th);
                const asc = th.dataset.sort !== 'asc';

                // Reset all sort indicators
                th.parentNode.querySelectorAll('th').forEach(h => h.dataset.sort = '');
                th.dataset.sort = asc ? 'asc' : 'desc';

                rows.sort((a, b) => {{
                    const aCell = a.children[idx];
                    const bCell = b.children[idx];
                    if (!aCell || !bCell) return 0;

                    const aVal = aCell.textContent.trim();
                    const bVal = bCell.textContent.trim();
                    const aNum = parseFloat(aVal.replace(/[^0-9.-]/g, ''));
                    const bNum = parseFloat(bVal.replace(/[^0-9.-]/g, ''));

                    if (!isNaN(aNum) && !isNaN(bNum)) {{
                        return asc ? aNum - bNum : bNum - aNum;
                    }}
                    return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                }});

                rows.forEach(row => tbody.appendChild(row));
            }});
        }});

        // ═══════════════════════════════════════════════════════════════════════
        // OBJECT FILTERS (MULTI-SELECT)
        // ═══════════════════════════════════════════════════════════════════════
        function initObjectMultiSelectFilter(config) {{
            const dropdown = document.getElementById(config.dropdownId);
            const toggle = document.getElementById(config.toggleId);
            const menu = document.getElementById(config.menuId);
            const optionsContainer = document.getElementById(config.optionsId);
            const selectAll = document.getElementById(config.selectAllId);
            const items = config.getItems();

            if (!dropdown || !toggle || !menu || !optionsContainer || !selectAll || !items.length) return;

            const objectNames = [...new Set(
                items
                    .map(item => config.getObjectName(item))
                    .filter(Boolean)
            )].sort((a, b) => a.localeCompare(b));

            objectNames.forEach((name, idx) => {{
                const option = document.createElement('label');
                option.className = 'object-filter-option';
                option.innerHTML = `
                    <input type="checkbox" value="${{name}}" id="${{config.idPrefix}}-${{idx}}" checked>
                    <span>${{name}}</span>
                `;
                optionsContainer.appendChild(option);
            }});

            function getOptionCheckboxes() {{
                return Array.from(optionsContainer.querySelectorAll('input[type="checkbox"]'));
            }}

            function updateToggleLabel() {{
                const optionCheckboxes = getOptionCheckboxes();
                const selectedCount = optionCheckboxes.filter(cb => cb.checked).length;

                if (selectedCount === optionCheckboxes.length) {{
                    toggle.textContent = 'Objects: All';
                }} else if (selectedCount === 0) {{
                    toggle.textContent = 'Objects: None';
                }} else {{
                    toggle.textContent = `Objects: ${{selectedCount}} selected`;
                }}

                toggle.setAttribute('aria-expanded', menu.classList.contains('open') ? 'true' : 'false');
            }}

            function syncSelectAllState() {{
                const optionCheckboxes = getOptionCheckboxes();
                const selectedCount = optionCheckboxes.filter(cb => cb.checked).length;

                if (selectedCount === 0) {{
                    selectAll.checked = false;
                    selectAll.indeterminate = false;
                }} else if (selectedCount === optionCheckboxes.length) {{
                    selectAll.checked = true;
                    selectAll.indeterminate = false;
                }} else {{
                    selectAll.checked = false;
                    selectAll.indeterminate = true;
                }}
            }}

            function applyFilter() {{
                const selected = new Set(
                    getOptionCheckboxes()
                        .filter(cb => cb.checked)
                        .map(cb => cb.value)
                );

                items.forEach(item => {{
                    const objectName = config.getObjectName(item);
                    config.setVisible(item, selected.has(objectName));
                }});
            }}

            toggle.addEventListener('click', () => {{
                menu.classList.toggle('open');
                updateToggleLabel();
            }});

            selectAll.addEventListener('change', () => {{
                getOptionCheckboxes().forEach(cb => {{
                    cb.checked = selectAll.checked;
                }});
                selectAll.indeterminate = false;
                updateToggleLabel();
                applyFilter();
            }});

            optionsContainer.addEventListener('change', (e) => {{
                if (!(e.target instanceof HTMLInputElement)) return;
                syncSelectAllState();
                updateToggleLabel();
                applyFilter();
            }});

            document.addEventListener('click', (e) => {{
                if (!dropdown.contains(e.target)) {{
                    menu.classList.remove('open');
                    updateToggleLabel();
                }}
            }});

            syncSelectAllState();
            updateToggleLabel();
            applyFilter();
        }}

        initObjectMultiSelectFilter({{
            dropdownId: 'objectFilterDropdown',
            toggleId: 'objectFilterToggle',
            menuId: 'objectFilterMenu',
            optionsId: 'objectFilterOptions',
            selectAllId: 'objectSelectAll',
            idPrefix: 'object-filter',
            getItems: () => Array.from((document.getElementById('field-explorer-table') || document.createElement('table')).querySelectorAll('tbody tr')),
            getObjectName: (row) => row.children[0] ? row.children[0].textContent.trim() : '',
            setVisible: (row, visible) => {{ row.style.display = visible ? '' : 'none'; }},
        }});

        initObjectMultiSelectFilter({{
            dropdownId: 'distObjectFilterDropdown',
            toggleId: 'distObjectFilterToggle',
            menuId: 'distObjectFilterMenu',
            optionsId: 'distObjectFilterOptions',
            selectAllId: 'distObjectSelectAll',
            idPrefix: 'dist-object-filter',
            getItems: () => Array.from(document.querySelectorAll('#distributions-grid .distribution-card')),
            getObjectName: (card) => card.getAttribute('data-object') || '',
            setVisible: (card, visible) => {{ card.style.display = visible ? '' : 'none'; }},
        }});

        // Trends & Drift: one object filter across every drift table.
        initObjectMultiSelectFilter({{
            dropdownId: 'trendsObjectFilterDropdown',
            toggleId: 'trendsObjectFilterToggle',
            menuId: 'trendsObjectFilterMenu',
            optionsId: 'trendsObjectFilterOptions',
            selectAllId: 'trendsObjectSelectAll',
            idPrefix: 'trends-object-filter',
            getItems: () => Array.from(document.querySelectorAll('#trends .drift-table tbody tr')),
            getObjectName: (row) => row.children[0] ? row.children[0].textContent.trim() : '',
            setVisible: (row, visible) => {{ row.style.display = visible ? '' : 'none'; }},
        }});

        // Export every drift change (across all drift tables, respecting the object
        // filter) as a single CSV to share with a content producer.
        function exportDriftChanges() {{
            const cards = Array.from(document.querySelectorAll('#trends .card'))
                .filter(card => card.querySelector('table.drift-table'));
            const out = [['Change Type', 'Object', 'Field', 'Details']];
            cards.forEach(card => {{
                const heading = card.querySelector('.card-header h3');
                const changeType = heading
                    ? heading.childNodes[0].textContent.trim()
                    : 'Change';
                const headerCells = Array.from(card.querySelectorAll('thead th'))
                    .map(th => th.textContent.trim());
                card.querySelectorAll('table.drift-table tbody tr').forEach(tr => {{
                    if (tr.style.display === 'none') return;  // respect the object filter
                    const cells = Array.from(tr.children).map(td =>
                        td.textContent.replace(/\\s+/g, ' ').trim());
                    const obj = cells[0] || '';
                    const field = cells[1] || '';
                    // Remaining columns become "Header=value; ..." detail.
                    const details = cells.slice(2)
                        .map((v, i) => `${{headerCells[i + 2] || 'col'}}: ${{v}}`)
                        .filter(s => s && !s.endsWith(': '))
                        .join('; ');
                    out.push([changeType, obj, field, details]);
                }});
            }});
            if (out.length === 1) {{ alert('No drift changes to export.'); return; }}
            const csv = out.map(row => row.map(cell => {{
                let t = String(cell).replace(/"/g, '""');
                return (t.includes(',') || t.includes('"') || t.includes('\\n')) ? `"${{t}}"` : t;
            }}).join(',')).join('\\n');
            const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'schema-drift-changes.csv';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}

        // ═══════════════════════════════════════════════════════════════════════
        // EXPORT TABLE TO CSV
        // ═══════════════════════════════════════════════════════════════════════
        function exportTable(tableId) {{
            const table = document.getElementById(tableId);
            if (!table) return;

            const rows = [];
            table.querySelectorAll('tr').forEach(tr => {{
                const cells = [];
                tr.querySelectorAll('th, td').forEach(cell => {{
                    let text = cell.textContent.trim().replace(/"/g, '""');
                    if (text.includes(',') || text.includes('"') || text.includes('\\n')) {{
                        text = `"${{text}}"`;
                    }}
                    cells.push(text);
                }});
                rows.push(cells.join(','));
            }});

            const csv = rows.join('\\n');
            const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', `${{tableId}}.csv`);
            link.click();
            URL.revokeObjectURL(url);
        }}

        // ═══════════════════════════════════════════════════════════════════════
        // DISTINCT VALUES MODAL
        // ═══════════════════════════════════════════════════════════════════════
        function showDistinctValues(objName, fieldPath) {{
            const key = `${{objName}}.${{fieldPath}}`;
            const data = fieldValueDistributions[key];

            if (!data || !data.values) {{
                console.warn('No distribution data for:', key);
                return;
            }}

            // Update modal title
            document.getElementById('modalTitle').textContent = `${{fieldPath}}`;
            const rawCount = data.distinct_count || Object.keys(data.values).length;
            const isCapped = maxDistinctConfigured > 0 && rawCount >= maxDistinctConfigured;
            document.getElementById('modalDistinctCount').textContent = isCapped ? `${{rawCount}}+` : rawCount;
            document.getElementById('modalShowingCount').textContent = Object.keys(data.values).length;

            // Calculate total for percentages
            const total = Object.values(data.values).reduce((a, b) => a + b, 0);

            // Build bar chart
            const container = document.getElementById('valueBarList');
            container.innerHTML = '';

            // Sort by count descending
            const sortedEntries = Object.entries(data.values).sort((a, b) => b[1] - a[1]);
            const maxCount = sortedEntries.length > 0 ? sortedEntries[0][1] : 1;

            sortedEntries.forEach(([value, count]) => {{
                const pct = (count / total * 100).toFixed(1);
                const barWidth = (count / maxCount * 100).toFixed(1);

                const item = document.createElement('div');
                item.className = 'value-bar-item';
                item.innerHTML = `
                    <div class="value-bar-label" title="${{value}}">${{value}}</div>
                    <div class="value-bar-track">
                        <div class="value-bar-fill" style="width: ${{barWidth}}%">
                            <span class="value-bar-count">${{count}}</span>
                        </div>
                    </div>
                    <div class="value-bar-pct">${{pct}}%</div>
                `;
                container.appendChild(item);
            }});

            // Show modal
            document.getElementById('distinctModal').classList.add('active');
        }}

        function closeDistinctModal() {{
            document.getElementById('distinctModal').classList.remove('active');
        }}

        // Close modal on overlay click
        document.getElementById('distinctModal').addEventListener('click', (e) => {{
            if (e.target.id === 'distinctModal') {{
                closeDistinctModal();
            }}
        }});

        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                closeDistinctModal();
            }}
        }});
    </script>
</body>
</html>
'''
