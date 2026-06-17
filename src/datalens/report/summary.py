"""
Markdown Summary Generator — generates a readable schema summary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datalens.config import Config


def generate_summary(schema_json: dict[str, Any], config: "Config") -> str:
    """
    Generate a markdown schema summary.

    Args:
        schema_json: Schema analysis JSON from profiling.
        config: Configuration object.

    Returns:
        Markdown summary string.
    """
    objects = schema_json.get("objects", [])

    lines = [
        "# Schema Analysis Summary",
        "",
        f"**Version:** {config.version_tag}",
        f"**Source Type:** {schema_json.get('source_type', 'Unknown')}",
        "",
        "## Overview",
        "",
    ]

    # Summary stats
    total_objects = len(objects)
    total_fields = sum(len(obj.get("fields", [])) for obj in objects)
    total_sampled = sum(obj.get("sampled", 0) for obj in objects)

    lines.extend([
        f"- **Objects Analyzed:** {total_objects}",
        f"- **Total Fields:** {total_fields}",
        f"- **Total Records Sampled:** {total_sampled:,}",
        "",
    ])

    # Per-object summaries
    for obj in objects:
        obj_name = obj.get("object", "Unknown")
        obj_label = obj.get("label")
        sampled = obj.get("sampled", 0)
        fields = obj.get("fields", [])

        header = f"## {obj_name}"
        if obj_label:
            header += f" ({obj_label})"
        lines.append(header)
        lines.append("")

        lines.append(f"**Sampled Records:** {sampled:,}")
        lines.append(f"**Total Fields:** {len(fields)}")
        lines.append("")

        # Key statistics
        high_coverage = [f for f in fields if f.get("presence_count", 0) / max(sampled, 1) >= 0.9]
        low_coverage = [f for f in fields if f.get("presence_count", 0) / max(sampled, 1) < 0.5]
        multi_type = [f for f in fields if len([t for t in f.get("types", {}) if t != "null"]) > 1]
        low_card = [f for f in fields if f.get("low_cardinality")]

        lines.extend([
            f"- High coverage fields (≥90%): {len(high_coverage)}",
            f"- Low coverage fields (<50%): {len(low_coverage)}",
            f"- Multi-type fields: {len(multi_type)}",
            f"- Low cardinality fields: {len(low_card)}",
            "",
        ])

        # Sample fields
        if fields:
            lines.append("### Sample Fields")
            lines.append("")
            lines.append("| Field | Coverage | Types | Distinct |")
            lines.append("|-------|----------|-------|----------|")

            for field in fields[:10]:  # First 10 fields
                path = field.get("path", "")
                presence = field.get("presence_count", 0)
                coverage_pct = (presence / max(sampled, 1)) * 100
                types = ", ".join(field.get("types", {}).keys())
                distinct = field.get("distinct_count_in_sample", 0)

                lines.append(f"| `{path}` | {coverage_pct:.1f}% | {types} | {distinct} |")

            if len(fields) > 10:
                lines.append(f"| ... and {len(fields) - 10} more fields | | | |")

            lines.append("")

        # Type warnings
        if multi_type:
            lines.append("### Type Warnings")
            lines.append("")
            for field in multi_type[:5]:
                path = field.get("path", "")
                types = field.get("types", {})
                type_str = ", ".join(f"{t}: {c}" for t, c in types.items())
                lines.append(f"- `{path}`: {type_str}")
            if len(multi_type) > 5:
                lines.append(f"- ... and {len(multi_type) - 5} more")
            lines.append("")

    # Cross-object analysis
    if len(objects) > 1:
        lines.append("## Cross-Object Analysis")
        lines.append("")

        # Find common fields
        field_to_objects: dict[str, list[str]] = {}
        for obj in objects:
            obj_name = obj.get("object", "Unknown")
            for field in obj.get("fields", []):
                path = field.get("path", "")
                if path not in field_to_objects:
                    field_to_objects[path] = []
                field_to_objects[path].append(obj_name)

        common = [(p, objs) for p, objs in field_to_objects.items() if len(objs) > 1]
        common.sort(key=lambda x: -len(x[1]))

        if common:
            lines.append("### Common Fields")
            lines.append("")
            for path, objs in common[:10]:
                lines.append(f"- `{path}` (in {len(objs)} objects)")
            if len(common) > 10:
                lines.append(f"- ... and {len(common) - 10} more common fields")
            lines.append("")

    return "\n".join(lines)
