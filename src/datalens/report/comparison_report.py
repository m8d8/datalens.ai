"""
Comparison Report Generator — Professional interactive schema comparison HTML report.

Features:
- Side-by-side schema metrics
- Filterable field comparison table
- Divergence analysis (type, coverage, cardinality, values)
- Dark/light mode toggle
- Interactive search and export
- Responsive design
"""

from __future__ import annotations

import base64
import html
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datalens.compare.deep_diff import DeepSchemaDiff

from datalens.report._logo import LOGO_ICON_DARK_SVG, LOGO_ICON_LIGHT_SVG


def _svg_data_uri(svg: str) -> str:
    """Base64 data URI for an SVG."""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def generate_comparison_html(diff: DeepSchemaDiff | None = None, record_diff: Any = None) -> str:
    """
    Generate a professional interactive schema comparison report.

    Args:
        diff: Optional DeepSchemaDiff result from compare_deep_schemas (None if raw data comparison).
        record_diff: Optional RecordDiff result from compare_records.

    Returns:
        Complete HTML document as a string.
    """
    # Prepare data for JavaScript (only if schema comparison available)
    if diff:
        paths_data = json.dumps([
            {
                "path": pc.path,
                "in_s1": pc.in_schema1,
                "in_s2": pc.in_schema2,
                "type_s1": sorted(pc.type_s1),
                "type_s2": sorted(pc.type_s2),
                "coverage_s1": round(pc.coverage_s1, 1),
                "coverage_s2": round(pc.coverage_s2, 1),
                "coverage_delta": round(pc.coverage_delta, 1),
                "null_pct_s1": round(pc.null_pct_s1, 1),
                "null_pct_s2": round(pc.null_pct_s2, 1),
                "distinct_s1": pc.distinct_s1,
                "distinct_s2": pc.distinct_s2,
                "cardinality_ratio": pc.cardinality_ratio,
                "samples_s1": pc.sample_distinct_s1[:10],
                "samples_s2": pc.sample_distinct_s2[:10],
                "value_overlap_pct": round(pc.value_overlap_pct, 1) if pc.value_overlap_pct else None,
                "is_high_card_s1": pc.is_high_cardinality_s1,
                "is_high_card_s2": pc.is_high_cardinality_s2,
                "divergence_score": round(pc.divergence_score, 1),
            }
            for pc in diff.path_comparisons
        ])

        divergences_data = json.dumps({
            "type": diff.type_divergences,
            "coverage": diff.coverage_gaps,
            "cardinality": diff.cardinality_explosions,
            "value_drift": diff.value_drifts,
        })
    else:
        paths_data = "[]"
        divergences_data = "{}"

    # Prepare record comparison data if available
    records_data = {}
    if record_diff:
        records_data = {
            "matched": record_diff.matched_records,
            "with_changes": record_diff.records_with_changes,
            "only_s1": record_diff.only_in_s1,
            "only_s2": record_diff.only_in_s2,
            "total_changes": record_diff.total_changes,
            "is_sampled": record_diff.is_sampled,
            "sample_size": record_diff.sample_size,
            "total_s1": record_diff.total_records_s1,
            "total_s2": record_diff.total_records_s2,
            "fields": {
                field: {
                    "changes": summary.total_changes,
                    "change_types": summary.change_types,
                    "samples": [
                        {
                            "id": change.record_id,
                            "val_s1": str(change.value_s1),
                            "val_s2": str(change.value_s2),
                            "type": change.change_type,
                        }
                        for change in summary.sample_changes
                    ],
                }
                for field, summary in record_diff.field_summaries.items()
            },
            "orphans_s1": record_diff.orphans_s1,
            "orphans_s2": record_diff.orphans_s2,
        }
    records_data_json = json.dumps(records_data)

    # Determine if we have schema data
    has_schema = diff is not None

    if has_schema:
        mode_badge = "Deep Comparison" if diff.deep_compare_enabled else "Metadata Comparison"
        display_name1 = html.escape(diff.schema1_name)
        display_name2 = html.escape(diff.schema2_name)
    else:
        mode_badge = "Record Comparison"
        display_name1 = html.escape(record_diff.schema1_name) if record_diff else "Schema 1"
        display_name2 = html.escape(record_diff.schema2_name) if record_diff else "Schema 2"

    if record_diff and has_schema:
        mode_badge += " + Records"

    total_divergences = (
        (len(diff.type_divergences)
         + len(diff.coverage_gaps)
         + len(diff.cardinality_explosions)
         + len(diff.value_drifts))
        if has_schema
        else 0
    )

    # Prepare logo URIs
    logo_light = _svg_data_uri(LOGO_ICON_LIGHT_SVG)
    logo_dark = _svg_data_uri(LOGO_ICON_DARK_SVG)

    # Escape for JavaScript
    logo_light_js = logo_light.replace("'", "\\'")
    logo_dark_js = logo_dark.replace("'", "\\'")

    # Build HTML content using string concatenation (avoids f-string brace issues)
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>Datalens Schema Comparison: {display_name1} vs {display_name2}</title>',
        _get_css(),
        '</head>',
        '<body>',
        '    <div class="container">',
        f'        <header>',
        f'            <div class="header-title">',
        f'                <div style="display: flex; align-items: center; gap: 10px;">',
        f'                    <img id="logoIcon" class="logo-icon" src="{logo_light}" alt="Datalens Logo" style="width: 28px; height: 28px;" data-light="{logo_light}" data-dark="{logo_dark}">',
        f'                    <div>',
        f'                        <div style="font-size: 13px; color: #666; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Datalens</div>',
        f'                        <div style="font-size: 13px; color: #999;">Schema Comparison</div>',
        f'                    </div>',
        f'                </div>',
        f'            </div>',
        f'            <div style="flex: 1; margin: 0 20px; text-align: center; font-size: 14px; color: #666;">',
        f'                <strong>{display_name1}</strong> ↔ <strong>{display_name2}</strong>',
        f'            </div>',
        f'            <div class="header-controls">',
        f'                <span class="mode-badge">{mode_badge}</span>',
        f'                <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark mode">🌙</button>',
        f'            </div>',
        f'        </header>',
        (_get_summary_grid(diff, total_divergences) if has_schema else ""),
        _get_tabs_html(has_schema=has_schema, has_records=bool(record_diff)),
        _get_tab_content(diff, display_name1, display_name2, record_diff, has_schema=has_schema),
        '        <footer>',
        f'            <p>Datalens Schema Comparison Report | Generated: {(diff.compared_at if has_schema else (record_diff.compared_at if record_diff else "N/A"))}</p>',
        '        </footer>',
        '    </div>',
        '',
        _get_javascript(paths_data, divergences_data, records_data_json),
        '</body>',
        '</html>',
    ]

    return '\n'.join(html_parts)


def _get_css() -> str:
    """Return the CSS styles."""
    return '''    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --color-primary: #2563eb;
            --color-success: #10b981;
            --color-warning: #f59e0b;
            --color-danger: #ef4444;
            --color-info: #0ea5e9;

            --bg-light: #ffffff;
            --bg-light-secondary: #f9fafb;
            --text-light: #1f2937;
            --border-light: #e5e7eb;

            --bg-dark: #1f2937;
            --bg-dark-secondary: #111827;
            --text-dark: #f3f4f6;
            --border-dark: #374151;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            background-color: var(--bg-light);
            color: var(--text-light);
            line-height: 1.6;
            transition: background-color 0.3s, color 0.3s;
        }

        body.dark-mode {
            background-color: var(--bg-dark);
            color: var(--text-dark);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--border-light);
            padding-bottom: 20px;
        }

        body.dark-mode header {
            border-color: var(--border-dark);
        }

        .logo-icon {
            display: none;
        }

        body.dark-mode .logo-icon {
            display: none;
        }

        body:not(.dark-mode) .logo-icon {
            display: block;
        }

        .header-title {
            flex: 1;
        }

        .header-title h1 {
            font-size: 28px;
            margin-bottom: 5px;
        }

        .schema-names {
            font-size: 14px;
            color: #666;
        }

        body.dark-mode .schema-names {
            color: #aaa;
        }

        .header-controls {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .mode-badge {
            background-color: var(--color-info);
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .theme-toggle {
            cursor: pointer;
            font-size: 20px;
            background: none;
            border: none;
            color: var(--text-light);
            padding: 5px;
        }

        body.dark-mode .theme-toggle {
            color: var(--text-dark);
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }

        .summary-card {
            background-color: var(--bg-light-secondary);
            border-radius: 8px;
            padding: 15px;
            border-left: 4px solid var(--color-primary);
        }

        body.dark-mode .summary-card {
            background-color: var(--bg-dark-secondary);
        }

        .summary-card.success {
            border-left-color: var(--color-success);
        }

        .summary-card.warning {
            border-left-color: var(--color-warning);
        }

        .summary-card.danger {
            border-left-color: var(--color-danger);
        }

        .summary-label {
            font-size: 12px;
            font-weight: 600;
            color: #999;
            text-transform: uppercase;
            margin-bottom: 5px;
        }

        body.dark-mode .summary-label {
            color: #bbb;
        }

        .summary-value {
            font-size: 24px;
            font-weight: bold;
            color: var(--color-primary);
        }

        .summary-card.danger .summary-value {
            color: var(--color-danger);
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background-color: var(--border-light);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }

        body.dark-mode .progress-bar {
            background-color: var(--border-dark);
        }

        .progress-fill {
            height: 100%;
            background-color: var(--color-primary);
            transition: width 0.3s;
        }

        .tabs {
            display: flex;
            gap: 0;
            border-bottom: 2px solid var(--border-light);
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        body.dark-mode .tabs {
            border-color: var(--border-dark);
        }

        .tab-button {
            padding: 12px 20px;
            border: none;
            background: none;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: #999;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.3s;
        }

        body.dark-mode .tab-button {
            color: #999;
        }

        .tab-button.active {
            color: var(--color-primary);
            border-bottom-color: var(--color-primary);
        }

        .tab-button:hover:not(.active) {
            color: var(--text-light);
        }

        body.dark-mode .tab-button:hover:not(.active) {
            color: var(--text-dark);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .table-wrapper {
            overflow-x: auto;
            border: 1px solid var(--border-light);
            border-radius: 8px;
        }

        body.dark-mode .table-wrapper {
            border-color: var(--border-dark);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        th {
            background-color: var(--bg-light-secondary);
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid var(--border-light);
            position: sticky;
            top: 0;
            z-index: 10;
        }

        body.dark-mode th {
            background-color: var(--bg-dark-secondary);
            border-bottom-color: var(--border-dark);
        }

        td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-light);
        }

        body.dark-mode td {
            border-bottom-color: var(--border-dark);
        }

        tr:hover td {
            background-color: var(--bg-light-secondary);
        }

        body.dark-mode tr:hover td {
            background-color: var(--bg-dark-secondary);
        }

        .path-name {
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            color: var(--color-primary);
        }

        body.dark-mode .path-name {
            color: #60a5fa;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-right: 4px;
            margin-bottom: 2px;
        }

        .badge-success {
            background-color: #d1fae5;
            color: #065f46;
        }

        body.dark-mode .badge-success {
            background-color: #064e3b;
            color: #d1fae5;
        }

        .badge-warning {
            background-color: #fef3c7;
            color: #92400e;
        }

        body.dark-mode .badge-warning {
            background-color: #78350f;
            color: #fef3c7;
        }

        .badge-danger {
            background-color: #fee2e2;
            color: #7f1d1d;
        }

        body.dark-mode .badge-danger {
            background-color: #7f1d1d;
            color: #fee2e2;
        }

        .badge-info {
            background-color: #dbeafe;
            color: #0c4a6e;
        }

        body.dark-mode .badge-info {
            background-color: #0c4a6e;
            color: #dbeafe;
        }

        .filters {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 6px 12px;
            border: 1px solid var(--border-light);
            background-color: var(--bg-light-secondary);
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s;
        }

        body.dark-mode .filter-btn {
            border-color: var(--border-dark);
            background-color: var(--bg-dark-secondary);
        }

        .filter-btn.active {
            background-color: var(--color-primary);
            color: white;
            border-color: var(--color-primary);
        }

        .search-box {
            margin-bottom: 20px;
        }

        .search-input {
            width: 100%;
            max-width: 400px;
            padding: 8px 12px;
            border: 1px solid var(--border-light);
            border-radius: 4px;
            font-size: 14px;
        }

        body.dark-mode .search-input {
            background-color: var(--bg-dark-secondary);
            border-color: var(--border-dark);
            color: var(--text-dark);
        }

        .divergence-section {
            margin-bottom: 30px;
        }

        .divergence-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .divergence-item {
            background-color: var(--bg-light-secondary);
            border-left: 4px solid var(--color-warning);
            padding: 12px;
            border-radius: 4px;
        }

        body.dark-mode .divergence-item {
            background-color: var(--bg-dark-secondary);
        }

        .divergence-item.danger {
            border-left-color: var(--color-danger);
        }

        .divergence-path {
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 12px;
            color: var(--color-primary);
            font-weight: 600;
            margin-bottom: 6px;
        }

        body.dark-mode .divergence-path {
            color: #60a5fa;
        }

        .divergence-details {
            font-size: 12px;
            line-height: 1.5;
        }

        footer {
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 12px;
            border-top: 1px solid var(--border-light);
            margin-top: 40px;
        }

        body.dark-mode footer {
            border-color: var(--border-dark);
            color: #aaa;
        }

        .no-results {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        body.dark-mode .no-results {
            color: #aaa;
        }
    </style>'''


def _get_summary_grid(diff: Any, total_divergences: int) -> str:
    """Generate the summary grid."""
    return f'''        <div class="summary-grid">
            <div class="summary-card success">
                <div class="summary-label">Similarity Score</div>
                <div class="summary-value">{diff.schema_similarity_score:.1f}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {diff.schema_similarity_score}%"></div>
                </div>
            </div>
            <div class="summary-card success">
                <div class="summary-label">Structural Alignment</div>
                <div class="summary-value">{diff.structural_alignment:.1f}%</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {diff.structural_alignment}%"></div>
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Common Objects</div>
                <div class="summary-value">{len(diff.common_objects)}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Added Objects</div>
                <div class="summary-value" style="color: var(--color-success)">{len(diff.added_objects)}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Removed Objects</div>
                <div class="summary-value" style="color: var(--color-danger)">{len(diff.removed_objects)}</div>
            </div>
            <div class="summary-card danger">
                <div class="summary-label">Total Divergences</div>
                <div class="summary-value">{total_divergences}</div>
            </div>
        </div>'''


def _get_tabs_html(has_schema: bool = True, has_records: bool = False) -> str:
    """Generate the tabs HTML."""
    tabs = ["        <div class=\"tabs\">"]

    if has_schema:
        # Show schema tabs if schema comparison is available
        tabs.extend([
            "            <button class=\"tab-button active\" onclick=\"showTab('summary')\">Summary</button>",
            "            <button class=\"tab-button\" onclick=\"showTab('fields')\">Fields</button>",
            "            <button class=\"tab-button\" onclick=\"showTab('divergences')\">Divergences</button>",
            "            <button class=\"tab-button\" onclick=\"showTab('objects')\">Objects</button>",
        ])
        if has_records:
            tabs.append("            <button class=\"tab-button\" onclick=\"showTab('records')\">Records</button>")
    else:
        # Raw data comparison: show Overview (active) and Records tabs
        if has_records:
            tabs.extend([
                "            <button class=\"tab-button active\" onclick=\"showTab('overview')\">Overview</button>",
                "            <button class=\"tab-button\" onclick=\"showTab('records')\">Records</button>",
            ])

    tabs.append("        </div>")
    return "\n".join(tabs)


def _get_tab_content(diff: Any, schema1_name: str, schema2_name: str, record_diff: Any = None, has_schema: bool = True) -> str:
    """Generate the tab content."""
    if not has_schema:
        # For raw data comparison, show Overview (active) and Records tabs
        if record_diff:
            overview_tab = f'''        <div id="overview" class="tab-content active">
            <h2 style="margin-bottom: 20px">Comparison Overview</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-label">Matched Records</div>
                    <div class="summary-value">{record_diff.matched_records}</div>
                </div>
                <div class="summary-card warning">
                    <div class="summary-label">With Changes</div>
                    <div class="summary-value" style="color: var(--color-warning)">{record_diff.records_with_changes}</div>
                </div>
                <div class="summary-card danger">
                    <div class="summary-label">Only in Schema 1</div>
                    <div class="summary-value" style="color: var(--color-danger)">{record_diff.only_in_s1}</div>
                </div>
                <div class="summary-card success">
                    <div class="summary-label">Only in Schema 2</div>
                    <div class="summary-value" style="color: var(--color-success)">{record_diff.only_in_s2}</div>
                </div>
            </div>
            {f'<div style="font-size: 12px; color: #666; margin-top: 15px;"><em>Sampled {record_diff.sample_size} of {record_diff.total_records_s1} records from Schema 1 and {record_diff.total_records_s2} from Schema 2</em></div>' if record_diff.is_sampled else ''}
        </div>

        <div id="records" class="tab-content">
            <h2 style="margin-bottom: 20px">Field-Level Changes</h2>
            <div style="margin-top: 10px;">
                <div id="recordsFieldsList">
                </div>
            </div>
        </div>'''
            return overview_tab
        return ""

    # Has schema: generate all schema tabs
    common_objs_html = _render_object_list(diff.common_objects, "common")
    added_objs_html = _render_object_list(diff.added_objects, "added")
    removed_objs_html = _render_object_list(diff.removed_objects, "removed")

    common_s1 = len(diff.common_objects) + len(diff.removed_objects)
    common_s2 = len(diff.common_objects) + len(diff.added_objects)
    paths_s1 = sum(1 for p in diff.path_comparisons if p.in_schema1)
    paths_s2 = sum(1 for p in diff.path_comparisons if p.in_schema2)

    schema_tabs = f'''        <div id="summary" class="tab-content active">
        <h2 style="margin-bottom: 20px">Comparison Summary</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">Schema 1</div>
                <div style="font-size: 18px; margin: 10px 0;">{schema1_name}</div>
                <div style="font-size: 12px; color: #666;">
                    Objects: {common_s1}<br>
                    Paths: {paths_s1}
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Schema 2</div>
                <div style="font-size: 18px; margin: 10px 0;">{schema2_name}</div>
                <div style="font-size: 12px; color: #666;">
                    Objects: {common_s2}<br>
                    Paths: {paths_s2}
                </div>
            </div>
        </div>
    </div>

    <div id="fields" class="tab-content">
        <h2 style="margin-bottom: 20px">Field Comparison</h2>
        <div class="search-box">
            <input type="text" class="search-input" id="fieldSearch" placeholder="Search fields..." onkeyup="filterTable()">
        </div>
        <div class="filters">
            <button class="filter-btn active" onclick="filterByStatus('all')">All Fields</button>
            <button class="filter-btn" onclick="filterByStatus('common')">Common</button>
            <button class="filter-btn" onclick="filterByStatus('added')">Added in S2</button>
            <button class="filter-btn" onclick="filterByStatus('removed')">Removed in S2</button>
            <button class="filter-btn" onclick="filterByStatus('divergent')">Divergences</button>
        </div>
        <div class="table-wrapper">
            <table id="fieldsTable">
                <thead>
                    <tr>
                        <th>Path</th>
                        <th>Type S1</th>
                        <th>Type S2</th>
                        <th>Coverage S1</th>
                        <th>Coverage S2</th>
                        <th>Cardinality S1</th>
                        <th>Cardinality S2</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="fieldsTableBody">
                </tbody>
            </table>
        </div>
    </div>

    <div id="divergences" class="tab-content">
        <h2 style="margin-bottom: 20px">Divergence Analysis</h2>
        <div id="divergencesContent">
        </div>
    </div>

    <div id="objects" class="tab-content">
        <h2 style="margin-bottom: 20px">Objects</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">Common Objects</div>
                <div class="summary-value">{len(diff.common_objects)}</div>
            </div>
            <div class="summary-card success">
                <div class="summary-label">Added (in Schema 2)</div>
                <div class="summary-value" style="color: var(--color-success)">{len(diff.added_objects)}</div>
            </div>
            <div class="summary-card danger">
                <div class="summary-label">Removed (from Schema 1)</div>
                <div class="summary-value" style="color: var(--color-danger)">{len(diff.removed_objects)}</div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
            <div>
                <h3 style="margin-bottom: 10px;">Common Objects</h3>
                <div style="max-height: 300px; overflow-y: auto;">
                    {common_objs_html}
                </div>
            </div>
            <div>
                <h3 style="margin-bottom: 10px;">Added in Schema 2</h3>
                <div style="max-height: 300px; overflow-y: auto;">
                    {added_objs_html}
                </div>
            </div>
        </div>
        {'<div style="margin-top: 20px;"><h3 style="margin-bottom: 10px;">Removed from Schema 1</h3><div>' + removed_objs_html + '</div></div>' if diff.removed_objects else ''}
    </div>'''

    # Add records tab if available
    if record_diff:
        schema_tabs += f'''
    <div id="records" class="tab-content">
        <h2 style="margin-bottom: 20px">Record Comparison</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">Matched Records</div>
                <div class="summary-value">{record_diff.matched_records}</div>
            </div>
            <div class="summary-card warning">
                <div class="summary-label">With Changes</div>
                <div class="summary-value" style="color: var(--color-warning)">{record_diff.records_with_changes}</div>
            </div>
            <div class="summary-card danger">
                <div class="summary-label">Only in Schema 1</div>
                <div class="summary-value" style="color: var(--color-danger)">{record_diff.only_in_s1}</div>
            </div>
            <div class="summary-card success">
                <div class="summary-label">Only in Schema 2</div>
                <div class="summary-value" style="color: var(--color-success)">{record_diff.only_in_s2}</div>
            </div>
        </div>
        {f'<div style="font-size: 12px; color: #666; margin-top: 10px;"><em>Sampled {record_diff.sample_size} of {record_diff.total_records_s1} records from Schema 1 and {record_diff.total_records_s2} from Schema 2</em></div>' if record_diff.is_sampled else ''}
        <div style="margin-top: 20px;">
            <h3>Fields with Changes</h3>
            <div id="recordsFieldsList" style="margin-top: 10px;">
            </div>
        </div>
    </div>'''

    return schema_tabs


def _get_javascript(paths_data: str, divergences_data: str, records_data_json: str = "{}") -> str:
    """Generate the JavaScript code. Uses JSON injection to avoid f-string brace issues."""
    return f'''    <script>
        const PATHS_DATA = {paths_data};
        const DIVERGENCES_DATA = {divergences_data};
        const RECORDS_DATA = {records_data_json};
        let currentFilter = 'all';

        function toggleTheme() {{
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');

            // Swap logo
            const logoIcon = document.getElementById('logoIcon');
            if (logoIcon) {{
                const temp = logoIcon.src;
                logoIcon.src = isDark ? logoIcon.dataset.dark : logoIcon.dataset.light;
            }}
        }}

        function showTab(tabName) {{
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');

            if (tabName === 'fields') {{
                populateFieldsTable();
            }} else if (tabName === 'divergences') {{
                populateDivergencesTab();
            }} else if (tabName === 'records') {{
                populateRecordsTab();
            }}
        }}

        function populateRecordsTab() {{
            const container = document.getElementById('recordsFieldsList');
            if (container.children.length > 0) return;  // Already populated

            if (!RECORDS_DATA || !RECORDS_DATA.fields || Object.keys(RECORDS_DATA.fields).length === 0) {{
                container.innerHTML = '<div class="no-results">No record comparison data available.</div>';
                return;
            }}

            const fields = Object.entries(RECORDS_DATA.fields).sort((a, b) => b[1].changes - a[1].changes);

            fields.forEach(([field, data]) => {{
                const section = document.createElement('div');
                section.style.marginBottom = '20px';
                section.style.padding = '15px';
                section.style.backgroundColor = 'var(--bg-light-secondary)';
                section.style.borderRadius = '4px';

                let html = '<h4 style="margin: 0 0 10px 0;">' + field + '</h4>';
                html += '<div style="font-size: 12px; margin-bottom: 10px; color: #666;">';
                html += '<strong>Changes:</strong> ' + data.changes + ' records | ';
                const changeTypes = Object.entries(data.change_types).map(([k, v]) => k.replace(/_/g, ' ') + ': ' + v).join(', ');
                html += '<strong>Types:</strong> ' + changeTypes;
                html += '</div>';

                if (data.samples && data.samples.length > 0) {{
                    html += '<div class="table-wrapper" style="margin-top: 10px; border: 1px solid var(--border-light); border-radius: 4px; overflow: hidden;">';
                    html += '<table style="width: 100%; font-size: 12px; border-collapse: collapse;">';
                    html += '<thead style="background-color: var(--border-light);"><tr><th style="padding: 10px; text-align: left;">Record ID</th><th style="padding: 10px; text-align: left;">Change Type</th><th style="padding: 10px; text-align: left;">Schema 1 Value</th><th style="padding: 10px; text-align: left;">Schema 2 Value</th></tr></thead>';
                    html += '<tbody>';
                    data.samples.forEach((sample, idx) => {{
                        const bgColor = idx % 2 === 0 ? 'transparent' : 'var(--bg-light-secondary)';
                        const badgeClass = sample.type === 'modified' ? 'badge-warning' : (sample.type === 'null_to_value' ? 'badge-success' : 'badge-danger');
                        html += '<tr style="background-color: ' + bgColor + '; border-bottom: 1px solid var(--border-light);">';
                        html += '<td style="padding: 8px 10px;"><code style="font-size: 11px; color: var(--color-primary);">' + sample.id + '</code></td>';
                        html += '<td style="padding: 8px 10px;"><span class="badge ' + badgeClass + '">' + sample.type.replace(/_/g, ' ') + '</span></td>';
                        html += '<td style="padding: 8px 10px; font-family: monospace; font-size: 11px; max-width: 200px; word-break: break-word;">' + (sample.val_s1 || '(empty)') + '</td>';
                        html += '<td style="padding: 8px 10px; font-family: monospace; font-size: 11px; max-width: 200px; word-break: break-word;">' + (sample.val_s2 || '(empty)') + '</td>';
                        html += '</tr>';
                    }});
                    html += '</tbody></table></div>';
                }} else {{
                    html += '<div style="font-size: 12px; color: #999; font-style: italic;">No sample data available</div>';
                }}
                section.innerHTML = html;
                container.appendChild(section);
            }});
        }}

        function populateFieldsTable() {{
            const tbody = document.getElementById('fieldsTableBody');
            tbody.innerHTML = '';

            PATHS_DATA.forEach(path => {{
                if (!shouldShowPath(path)) return;

                const row = tbody.insertRow();
                row.className = `path-row status-${{getPathStatus(path)}}`;

                const typeS1 = path.type_s1.join(', ') || 'N/A';
                const typeS2 = path.type_s2.join(', ') || 'N/A';
                const status = getPathStatus(path);
                const statusBadge = {{
                    'common': '<span class="badge badge-success">Common</span>',
                    'added': '<span class="badge badge-success">Added</span>',
                    'removed': '<span class="badge badge-danger">Removed</span>',
                    'divergent': '<span class="badge badge-warning">Divergent</span>'
                }}[status] || '';

                row.innerHTML = `
                    <td><span class="path-name">${{path.path}}</span></td>
                    <td>${{typeS1}}</td>
                    <td>${{typeS2}}</td>
                    <td>${{path.coverage_s1.toFixed(1)}}%</td>
                    <td>${{path.coverage_s2.toFixed(1)}}%</td>
                    <td>${{path.distinct_s1}}</td>
                    <td>${{path.distinct_s2}}</td>
                    <td>${{statusBadge}}</td>
                `;
            }});
        }}

        function getPathStatus(path) {{
            if (!path.in_s1) return 'added';
            if (!path.in_s2) return 'removed';

            // Compare types properly (they're arrays)
            const typesMatch = JSON.stringify(path.type_s1) === JSON.stringify(path.type_s2);
            const typesChanged = !typesMatch;
            const coverageChanged = Math.abs(path.coverage_delta) > 10;
            const cardinalityChanged = path.cardinality_ratio && (path.cardinality_ratio > 2 || path.cardinality_ratio < 0.5);

            if (typesChanged || coverageChanged || cardinalityChanged) {{
                return 'divergent';
            }}
            return 'common';
        }}

        function shouldShowPath(path) {{
            if (currentFilter === 'all') return true;
            return getPathStatus(path) === currentFilter;
        }}

        function filterByStatus(status) {{
            currentFilter = status;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            populateFieldsTable();
        }}

        function filterTable() {{
            const input = document.getElementById('fieldSearch').value.toLowerCase();
            document.querySelectorAll('#fieldsTableBody tr').forEach(row => {{
                const path = row.querySelector('.path-name').textContent.toLowerCase();
                row.style.display = path.includes(input) ? '' : 'none';
            }});
        }}

        function populateDivergencesTab() {{
            const container = document.getElementById('divergencesContent');
            if (container.innerHTML) return;

            let html = '';

            if (DIVERGENCES_DATA.type.length > 0) {{
                html += '<div class="divergence-section"><h3>Type Divergences</h3><div class="divergence-list">';
                DIVERGENCES_DATA.type.forEach(div => {{
                    html += '<div class="divergence-item danger">';
                    html += '<div class="divergence-path">' + div.object + '.' + div.path + '</div>';
                    html += '<div class="divergence-details">';
                    html += '<strong>Schema 1:</strong> ' + div.type_s1.join(', ') + ' | ';
                    html += '<strong>Schema 2:</strong> ' + div.type_s2.join(', ');
                    html += '</div></div>';
                }});
                html += '</div></div>';
            }}

            if (DIVERGENCES_DATA.coverage.length > 0) {{
                html += '<div class="divergence-section"><h3>Coverage Gaps</h3><div class="divergence-list">';
                DIVERGENCES_DATA.coverage.forEach(gap => {{
                    const deltaStr = gap.delta > 0 ? '+' + gap.delta.toFixed(1) : gap.delta.toFixed(1);
                    html += '<div class="divergence-item">';
                    html += '<div class="divergence-path">' + gap.object + '.' + gap.path + '</div>';
                    html += '<div class="divergence-details">';
                    html += 'Schema 1: ' + gap.coverage_s1.toFixed(1) + '% → ';
                    html += 'Schema 2: ' + gap.coverage_s2.toFixed(1) + '% (Δ ' + deltaStr + '%)';
                    html += '</div></div>';
                }});
                html += '</div></div>';
            }}

            if (DIVERGENCES_DATA.cardinality.length > 0) {{
                html += '<div class="divergence-section"><h3>Cardinality Changes</h3><div class="divergence-list">';
                DIVERGENCES_DATA.cardinality.forEach(exp => {{
                    html += '<div class="divergence-item">';
                    html += '<div class="divergence-path">' + exp.object + '.' + exp.path + '</div>';
                    html += '<div class="divergence-details">';
                    html += exp.cardinality_s1 + ' → ' + exp.cardinality_s2 + ' distinct values (' + exp.ratio.toFixed(1) + 'x)';
                    html += '</div></div>';
                }});
                html += '</div></div>';
            }}

            if (DIVERGENCES_DATA.value_drift.length > 0) {{
                html += '<div class="divergence-section"><h3>Value Drifts</h3><div class="divergence-list">';
                DIVERGENCES_DATA.value_drift.forEach(drift => {{
                    html += '<div class="divergence-item warning">';
                    html += '<div class="divergence-path">' + drift.object + '.' + drift.path + '</div>';
                    html += '<div class="divergence-details">' + drift.message + '</div></div>';
                }});
                html += '</div></div>';
            }}

            if (!html) {{
                html = '<div class="no-results">No divergences found. Schemas are well-aligned.</div>';
            }}

            container.innerHTML = html;
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            const isDark = localStorage.getItem('theme') === 'dark';
            if (isDark) {{
                document.body.classList.add('dark-mode');
                const logoIcon = document.getElementById('logoIcon');
                if (logoIcon) {{
                    logoIcon.src = logoIcon.dataset.dark;
                }}
            }}
        }});
    </script>'''


def _render_object_list(objects: list[str], css_class: str) -> str:
    """Render a list of objects with styling."""
    if not objects:
        return '<div class="no-results">None</div>'
    return "".join([
        f'<div style="padding: 8px; margin: 4px 0; border-left: 2px solid var(--border-light); font-size: 13px;">'
        f'{html.escape(obj)}</div>'
        for obj in objects
    ])
