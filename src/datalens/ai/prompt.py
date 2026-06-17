"""
Prompt templates for AI schema insight generation.
"""

from __future__ import annotations

from typing import Any

from datalens.ai.context import summarize_analytics_for_prompt, summarize_schema_for_prompt


INSIGHT_SECTION_KEYS = (
    "unique_id_patterns",
    "key_domain_fields",
    "structural_value_patterns",
    "cross_object_patterns",
    "domain_field_assessments",
    "hidden_value_relationships",
    "data_story",
    "quality_assessment",
    "recommendations",
)


def build_insights_prompt(ctx: dict[str, Any]) -> str:
    """
    Build the user prompt asking for structured JSON insights.
    """
    schema = ctx.get("schema") or {}
    objects = schema.get("objects", [])
    schema_summary = summarize_schema_for_prompt(objects)
    analytics_summary = summarize_analytics_for_prompt(ctx)

    return f"""You are an expert data analyst reviewing a schema profiling report.
Analyze the schema and deterministic findings below. Infer domain meaning from field
names and value patterns only — do not invent external facts.

## Schema
{schema_summary}

## Deterministic analytics
{analytics_summary}

Respond with a single JSON object (no markdown fences) containing exactly these keys:
- unique_id_patterns: per-object unique ID / key patterns (string, markdown bullets OK)
- key_domain_fields: important business/domain fields and their structural patterns
- structural_value_patterns: value shape patterns (enums, formats, nesting, null rates)
- cross_object_patterns: relationships and join patterns across objects
- domain_field_assessments: assessments for likely domain-critical fields
- hidden_value_relationships: non-obvious value correlations or lineage hints
- data_story: 2-4 sentence narrative of what this dataset represents
- quality_assessment: concise data quality observations
- recommendations: array of objects with keys category, severity (low|medium|high), action

Be specific, reference actual field paths, and prioritize actionable insights."""


def build_cli_prompt(ctx: dict[str, Any]) -> str:
    """Prompt for license-based CLI providers (cursor-agent, gh copilot, etc.)."""
    return build_insights_prompt(ctx)
