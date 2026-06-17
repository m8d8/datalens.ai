"""
Core analysis engine — the library-first entry point.

analyze(source_spec, config) -> AnalysisResult

This module is CLI-agnostic: no print(), no sys.exit(), no implicit filesystem assumptions.
The CLI and future web service are thin callers of this engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from datalens.config import Config
from datalens.connectors.registry import get_connector
from datalens.profiling.sampler import profile_source
from datalens.profiling.pii import detect_pii_in_schema, get_pii_summary
from datalens.profiling.quality import compute_schema_quality
from datalens.profiling.statistics import compute_statistics_summary
from datalens.profiling.relationships import analyze_relationships
from datalens.profiling.patterns import analyze_patterns
from datalens.profiling.joins import analyze_joins
from datalens.profiling.insights import build_insights
from datalens.profiling.decision import build_decision_layer
from datalens.history.diff import detect_drift
from datalens.ai.service import run_ai_insights
from datalens.report.html_report import generate_html_report
from datalens.report.summary import generate_summary


@dataclass
class AnalysisResult:
    """Result of a schema analysis run."""

    # Core artifacts
    schema_json: dict[str, Any]
    """Per-object field statistics in the §3 JSON contract."""

    summary_md: str
    """Markdown schema summary."""

    html_report: str
    """Self-contained interactive HTML report."""

    # Metadata
    version_tag: str
    """Run version/tag (timestamp or user-provided)."""

    objects_analyzed: list[str]
    """Names of objects (collections/tables/files) analyzed."""

    total_fields: int
    """Total fields discovered across all objects."""

    total_sampled: int
    """Total records sampled across all objects."""

    # Phase 3: Advanced analytics
    quality: dict[str, Any] | None = None
    """Data Quality Index (DQI) per object and overall."""

    pii_summary: dict[str, Any] | None = None
    """PII detection summary with high-risk fields."""

    statistics: dict[str, Any] | None = None
    """Numeric and temporal field statistics."""

    relationships: dict[str, Any] | None = None
    """Detected field relationships and potential foreign keys."""

    patterns: dict[str, Any] | None = None
    """Per-field value-shape / identifier pattern detections."""

    joins: dict[str, Any] | None = None
    """Primary keys, cross-object FK candidates, value-overlap joins, nested relationships."""

    insights: dict[str, Any] | None = None
    """Deterministic data story, SWOT, content universe, recommendations, AI readiness."""

    decision: dict[str, Any] | None = None
    """v2 decision layer: health verdict, compliance scorecard, fitness, action plan."""

    diff: dict[str, Any] | None = None
    """Schema drift vs. a previous run (summary form), if a previous run was supplied."""

    # Optional
    ai_insights: dict[str, Any] | None = None
    """AI-generated insights (only if AI provider configured)."""

    ai_insights_md: str | None = None
    """AI insights as markdown (companion to ai_insights)."""

    warnings: list[str] = field(default_factory=list)
    """Any warnings encountered during analysis."""


def analyze(
    source_spec: dict[str, Any],
    config: Config | None = None,
    *,
    previous_schema: dict[str, Any] | None = None,
) -> AnalysisResult:
    """
    Run schema analysis on a data source.

    Args:
        source_spec: Source specification dict with keys:
            - source: "file" | "mongodb" | "s3" | "http" | ...
            - For file: path, root (optional), sheets (optional)
            - For mongodb: db, collections or objects (list of "coll|query -> tag")
            - ... (see CLI grammar for full spec)
        config: Optional Config object. If None, uses defaults.
        previous_schema: Optional schema JSON from a prior run. When provided,
            schema drift is computed and a decision layer is derived from it.

    Returns:
        AnalysisResult with schema JSON, summary, HTML report, and metadata.

    Raises:
        ValueError: If source_spec is invalid or missing required fields.
        ConnectionError: If unable to connect to the data source.
    """
    config = config or Config()

    # Get the appropriate connector
    connector = get_connector(source_spec, config)

    try:
        connector.connect()

        # Profile the source
        schema_json = profile_source(connector, config)

        # Phase 3+: Advanced analytics
        patterns_data = analyze_patterns(schema_json)
        quality_data = compute_schema_quality(schema_json, patterns_data=patterns_data)
        pii_data = detect_pii_in_schema(schema_json)
        pii_summary = get_pii_summary(pii_data) if pii_data else None
        statistics_data = compute_statistics_summary(schema_json)
        relationships_data = analyze_relationships(schema_json)
        joins_data = analyze_joins(schema_json)
        insights_data = build_insights(
            schema_json, quality_data, joins_data, patterns_data, pii_summary,
        )

        # Generate summary
        summary_md = generate_summary(schema_json, config)

        # Compute metadata
        objects_analyzed = [obj["object"] for obj in schema_json.get("objects", [])]
        total_fields = sum(len(obj.get("fields", [])) for obj in schema_json.get("objects", []))
        total_sampled = sum(obj.get("sampled", 0) for obj in schema_json.get("objects", []))

        # Schema drift vs. a previous run (if supplied)
        schema_diff = detect_drift(schema_json, previous_schema)
        diff_summary = (
            {"summary": schema_diff.summary(), "has_drift": schema_diff.has_drift}
            if schema_diff is not None else None
        )

        # Build the result first (analytics computed exactly once above), then
        # derive the v2 decision layer from it.
        result = AnalysisResult(
            schema_json=schema_json,
            summary_md=summary_md,
            html_report="",  # filled in below
            version_tag=config.version_tag,
            objects_analyzed=objects_analyzed,
            total_fields=total_fields,
            total_sampled=total_sampled,
            quality=quality_data.to_dict() if quality_data else None,
            pii_summary=pii_summary,
            statistics=statistics_data,
            relationships=relationships_data,
            patterns=patterns_data,
            joins=joins_data,
            insights=insights_data,
            diff=diff_summary,
            warnings=[],
        )
        result.decision = build_decision_layer(result, schema_diff)

        # Optional AI insights (network / CLI — only when configured).
        ai_insights, ai_insights_md = run_ai_insights(result, config)
        if ai_insights is not None:
            result.ai_insights = ai_insights
            result.ai_insights_md = ai_insights_md
            if not ai_insights.get("enabled"):
                result.warnings.append(
                    f"AI provider did not produce insights: {ai_insights.get('error', 'unknown')}"
                )

        # Generate HTML report from the ALREADY-computed analytics (no recompute).
        result.html_report = generate_html_report(
            schema_json,
            config,
            patterns_data=patterns_data,
            quality_data=quality_data,
            pii_data=pii_data,
            pii_summary=pii_summary,
            relationships_data=relationships_data,
            statistics_data=statistics_data,
            joins_data=joins_data,
            insights_data=insights_data,
            diff=schema_diff,
            previous_schema=previous_schema,
            decision=result.decision,
            ai_insights=result.ai_insights,
            include_pii=True,
            include_quality=True,
            include_relationships=True,
            include_statistics=True,
        )

        return result

    finally:
        connector.close()
