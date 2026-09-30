"""
Datalens CLI — single entrypoint for all schema analysis operations.

Usage:
    datalens analyze <SOURCE-SPEC> [options]

Examples:
    # Analyze a local CSV file
    datalens analyze --source file --path data.csv

    # Analyze a JSON file with specific root
    datalens analyze --source file --path data.json --root items

    # Analyze every supported file in a directory (one object per file)
    datalens analyze --source file --path ./exports --pattern "*.jsonl.gz"

    # Analyze MongoDB collections
    datalens analyze --source mongodb --db mydb --collections users,orders

    # Analyze MongoDB with query and tag
    datalens analyze --source mongodb --db mydb --object "products|{\"active\": true} -> ActiveProducts"

    # Analyze all collections in a MongoDB database
    datalens analyze --source mongodb --db mydb
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from datalens import __version__, analyze
from datalens.config import Config, ConnectionLoader, load_config

console = Console()


def _get_artifact_prefix(
    source_spec: dict[str, Any],
    source_type: str | None = None,
    connection_config_name: str | None = None,
) -> str:
    """
    Extract the identifier prefix for output artifacts.

    Returns just the identifier part (e.g., 'sales_test', 'mydb', 'api_example_com')
    without timestamp or file extension.

    Examples:
      - sales_test (from file)
      - mydb (from MongoDB)
      - api_example_com (from HTTP URI)
      - my_api (from connection config)
    """
    # Priority 1: Use connection config name if provided
    if connection_config_name:
        return connection_config_name.lower()[:20]

    # Determine identifier from source spec
    source = source_spec.get("source") or source_type or "data"
    source_lower = source.lower()

    if source_lower == "http":
        uri = source_spec.get("uri", "")
        if uri:
            parsed = uri.split("//")[-1].split("/")[0].replace(".", "_").replace("-", "_")
            return parsed[:20]
    elif source_lower == "mongodb":
        db = source_spec.get("db")
        if db:
            return db.lower()[:20]
    elif source_lower == "file":
        path = source_spec.get("path")
        if path:
            import os
            name = os.path.basename(path)
            # Strip compression suffix so e.g. "data.jsonl.gz" -> "data"
            if name.lower().endswith((".gz", ".zip")):
                name = os.path.splitext(name)[0]
            return os.path.splitext(name)[0].lower()[:20]
    elif source_lower == "s3":
        uri = source_spec.get("uri", "")
        if uri:
            parts = uri.replace("s3://", "").split("/")
            return (parts[0] + "_" + parts[1] if len(parts) > 1 else parts[0]).lower()[:20]

    return source_lower[:20]


def _get_output_subdir_name(
    source_spec: dict[str, Any],
    source_type: str | None = None,
    version_tag: str | None = None,
    connection_config_name: str | None = None,
) -> str:
    """
    Generate a descriptive output subdirectory name based on source.

    Format: {source_identifier}_{short_timestamp}

    Examples:
      - my_api_0611_0320 (from connection config)
      - prod_db_0611_0320 (from MongoDB db name)
      - data_csv_0611_0320 (from file name)
      - s3_datalake_0611_0320 (from S3 path)
    """
    base_name = _get_artifact_prefix(source_spec, source_type, connection_config_name)

    # Add timestamp suffix (MMDD_HHMMSS)
    if version_tag:
        # Extract HHMMSS from version_tag (format: YYYYmmdd_HHMMSS)
        parts = version_tag.split("_")
        if len(parts) >= 2:
            hhmmss = parts[-1]
            mmdd = parts[0][4:]  # Get MMDD from YYYYmmdd
            timestamp_short = f"{mmdd}_{hhmmss}"
        else:
            timestamp_short = version_tag[-8:]  # Fallback to last 8 chars
    else:
        from datetime import datetime
        timestamp_short = datetime.now().strftime("%m%d_%H%M%S")

    return f"{base_name}_{timestamp_short}"


@click.group()
@click.version_option(version=__version__, prog_name="datalens")
def cli() -> None:
    """
    Datalens — Advanced Schema Analysis & Data Profiling

    Analyze schemas, profile data quality, discover patterns and relationships,
    and generate rich interactive reports.
    """
    pass


@cli.command()
@click.option(
    "--source",
    "-s",
    type=click.Choice(["file", "mongodb", "s3", "http"], case_sensitive=False),
    required=False,
    help="Data source type (optional if using --cc)",
)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    help="Path to file (for file source)",
)
@click.option(
    "--root",
    help="Root element/path for JSON/XML files",
)
@click.option(
    "--sheets",
    help="Comma-separated sheet names for Excel files (default: all)",
)
@click.option(
    "--pattern",
    help='Glob pattern to select files when --path is a directory (e.g. "*.jsonl.gz")',
)
@click.option(
    "--recursive/--no-recursive",
    default=None,
    help="Scan subdirectories too when --path is a directory (default: top-level only)",
)
@click.option(
    "--db",
    help="Database name (for mongodb source)",
)
@click.option(
    "--collections",
    help='Comma-separated collection names (e.g., "users,orders")',
)
@click.option(
    "--object",
    "objects",
    multiple=True,
    help='Object spec: "coll|{query} -> tag" (can be repeated)',
)
@click.option(
    "--uri",
    help="Connection URI (mongodb://, s3://, http://)",
)
@click.option(
    "--sample-size",
    type=int,
    default=None,
    help="Number of records to sample per object (default: 10000, or the connection config's "
    "'profiling.sample_size' if set; 0 = full scan)",
)
@click.option(
    "--full-scan",
    is_flag=True,
    default=False,
    help="Process all records without sampling (equivalent to --sample-size 0)",
)
@click.option(
    "--max-depth",
    type=int,
    default=None,
    help="Maximum nesting depth to traverse (default: 10, or the connection config's "
    "'profiling.max_depth' if set)",
)
@click.option(
    "--max-distinct",
    type=int,
    default=None,
    help="Maximum distinct values to track per field (default: 100, or the connection config's "
    "'profiling.max_distinct_values' if set)",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    help="Path to application config file (YAML)",
)
@click.option(
    "--env",
    "-e",
    default=None,
    help="Env swimlane (dev/staging/prod, ...) for config-{env}.yaml overlay "
    "(default: $DATALENS_ENV). See .datalens/config.yaml / config-{env}.yaml.",
)
@click.option(
    "--cc",
    "--connection-config",
    "connection_config",
    type=click.Path(),
    help="Connection config name or file path (YAML) for predefined credentials",
)
@click.option(
    "--secrets",
    type=click.Path(exists=True),
    help="Path to secrets file (YAML)",
)
@click.option(
    "--out-dir",
    "-o",
    type=click.Path(),
    default="output",
    help="Output directory (default: output)",
)
@click.option(
    "--version-tag",
    help="Version tag for this run (default: timestamp)",
)
@click.option(
    "--compare-to",
    help="Compare against a specific saved run (version tag) to show drift in the report.",
)
@click.option(
    "--detect-drift",
    is_flag=True,
    default=False,
    help="Compare against the most recent saved run to show schema drift.",
)
@click.option(
    "--history-dir",
    type=click.Path(),
    default=None,
    help="Where versioned runs are stored for drift (default: <out-dir>/.history).",
)
@click.option(
    "--history-retention-days",
    type=int,
    default=None,
    help="Delete saved history runs older than N days (default: 0 = keep forever). "
    "Tags in --history-protected-tag (default: 'baseline') are never deleted.",
)
@click.option(
    "--history-protected-tag",
    "history_protected_tags",
    multiple=True,
    help="Version tag to always keep regardless of age (can be repeated; default: 'baseline').",
)
@click.option(
    "--coverage-threshold",
    type=float,
    default=None,
    help="Dataset-level coverage-change breach threshold in %-points (applies to all objects/fields).",
)
@click.option(
    "--object-coverage-threshold",
    "object_coverage_thresholds",
    multiple=True,
    help='Object-level breach threshold: "OBJECT=PCT" (can be repeated).',
)
@click.option(
    "--field-coverage-threshold",
    "field_coverage_thresholds",
    multiple=True,
    help='Field-level breach threshold: "OBJECT.FIELD_PATH=PCT" (can be repeated).',
)
@click.option(
    "--report-coverage-reduction/--no-report-coverage-reduction",
    default=None,
    help="Flag fields whose coverage dropped beyond their threshold (default: enabled).",
)
@click.option(
    "--report-coverage-increase/--no-report-coverage-increase",
    default=None,
    help="Flag fields whose coverage rose beyond their threshold (default: enabled).",
)
@click.option(
    "--ai",
    type=click.Choice(
        ["off", "anthropic", "openai", "cursor", "copilot", "claude", "auto"],
        case_sensitive=False,
    ),
    default="off",
    help="AI provider for insights (default: off)",
)
@click.option(
    "--mask-pii/--no-mask-pii",
    default=True,
    help="Mask detected PII in reports (default: enabled)",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable debug mode",
)
def analyze_cmd(
    source: str,
    path: str | None,
    root: str | None,
    sheets: str | None,
    pattern: str | None,
    recursive: bool | None,
    db: str | None,
    collections: str | None,
    objects: tuple[str, ...],
    uri: str | None,
    sample_size: int | None,
    full_scan: bool,
    max_depth: int | None,
    max_distinct: int | None,
    config_file: str | None,
    env: str | None,
    connection_config: str | None,
    secrets: str | None,
    out_dir: str,
    version_tag: str | None,
    compare_to: str | None,
    detect_drift: bool,
    history_dir: str | None,
    history_retention_days: int | None,
    history_protected_tags: tuple[str, ...],
    coverage_threshold: float | None,
    object_coverage_thresholds: tuple[str, ...],
    field_coverage_thresholds: tuple[str, ...],
    report_coverage_reduction: bool | None,
    report_coverage_increase: bool | None,
    ai: str,
    mask_pii: bool,
    debug: bool,
) -> None:
    """
    Analyze a data source and generate schema reports.

    Supports local files (CSV, JSON, XML, XLSX) and MongoDB databases.
    Generates a self-contained interactive HTML report.
    """
    try:
        # Validate that either --source or --cc is provided
        if not source and not connection_config:
            raise click.UsageError(
                "Either --source/-s or --cc/--connection-config must be provided"
            )

        # Handle full scan flag (overrides sample_size)
        if full_scan:
            sample_size = 0

        # Build source spec (may be empty if using --cc)
        source_spec = _build_source_spec(
            source=source or "unknown",
            path=path,
            root=root,
            sheets=sheets,
            pattern=pattern,
            recursive=recursive,
            db=db,
            collections=collections,
            objects=objects,
            uri=uri,
        )

        # Merge connection config if provided
        conn_profiling: dict[str, Any] = {}
        conn_drift: dict[str, Any] = {}
        conn_history: dict[str, Any] = {}
        if connection_config:
            source_spec = _merge_connection_config(source_spec, connection_config, debug)
            # Display connection metadata if available
            try:
                loader = ConnectionLoader()
                conn_cfg = loader.load_connection(connection_config)
                conn_profiling = conn_cfg.profiling or {}
                conn_drift = conn_cfg.drift or {}
                conn_history = conn_cfg.history or {}
                if conn_cfg.metadata:
                    metadata_info = []
                    if conn_cfg.metadata.get("description"):
                        metadata_info.append(f"[dim]Description:[/dim] {conn_cfg.metadata.get('description')}")
                    if conn_cfg.metadata.get("owner"):
                        metadata_info.append(f"[dim]Owner:[/dim] {conn_cfg.metadata.get('owner')}")
                    if conn_cfg.metadata.get("tags"):
                        tags = ", ".join(conn_cfg.metadata.get("tags", []))
                        metadata_info.append(f"[dim]Tags:[/dim] {tags}")
                    if metadata_info:
                        console.print(Panel("\n".join(metadata_info), title="Connection Info"))
            except Exception:
                pass  # Silently skip if metadata can't be loaded

        # Resolve sampling knobs: explicit CLI flag > connection config's
        # 'profiling' section > global/env-swimlane config file > built-in
        # default. --full-scan already forced sample_size=0 above, so it
        # always wins. Leaving a value as None here lets load_config's own
        # layering (auto-discovered config -> dataclass default) apply it.
        if sample_size is None:
            sample_size = conn_profiling.get("sample_size")
        if max_depth is None:
            max_depth = conn_profiling.get("max_depth")
        if max_distinct is None:
            max_distinct = conn_profiling.get("max_distinct_values")

        # Resolve coverage-drift breach thresholds: explicit CLI flags (as a whole)
        # override the connection config's 'drift' section entirely; otherwise fall
        # back to it, then to the global/env-swimlane config file (None = unset).
        cli_coverage_thresholds = _build_coverage_thresholds(
            coverage_threshold, object_coverage_thresholds, field_coverage_thresholds
        )
        coverage_thresholds = cli_coverage_thresholds or conn_drift.get("coverage_thresholds") or None
        if report_coverage_reduction is None:
            report_coverage_reduction = conn_drift.get("report_reduction_threshold_exceeds")
        if report_coverage_increase is None:
            report_coverage_increase = conn_drift.get("report_increase_threshold_exceeds")

        # Resolve history retention: explicit CLI flag > connection config's
        # 'history' section > global/env-swimlane config file > default (0 = keep forever).
        if history_retention_days is None:
            history_retention_days = conn_history.get("retention_days")
        protected_tags: list[str] | None = (
            list(history_protected_tags) if history_protected_tags else conn_history.get("protected_tags")
        )

        # Generate version tag first (needed for output dir naming)
        if not version_tag:
            from datetime import datetime
            version_tag = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Extract connection config name (if provided)
        # connection_config can be: "my_api" or "/path/to/config.yaml"
        connection_config_name = None
        if connection_config:
            if "/" in connection_config or "\\" in connection_config:
                # It's a file path - extract filename without extension
                connection_config_name = Path(connection_config).stem
            else:
                # It's just a name
                connection_config_name = connection_config

        # Create structured output subdirectory
        subdir_name = _get_output_subdir_name(
            source_spec, source, version_tag, connection_config_name
        )
        structured_out_dir = str(Path(out_dir) / subdir_name)

        # Load config with structured output directory
        config = load_config(
            config_file=config_file,
            env=env,
            secrets_file=secrets,
            sample_size=sample_size,
            max_depth=max_depth,
            max_distinct_values=max_distinct,
            coverage_thresholds=coverage_thresholds,
            report_coverage_reduction_exceeds=report_coverage_reduction,
            report_coverage_increase_exceeds=report_coverage_increase,
            history_retention_days=history_retention_days,
            history_protected_tags=protected_tags,
            out_dir=structured_out_dir,
            version_tag=version_tag,
            ai_provider=ai if ai != "auto" else "",
            mask_pii=mask_pii,
            debug=debug,
        )

        # Show header (use source_spec source if available, otherwise source flag)
        display_source = source_spec.get("source") or source or "unknown"
        console.print(Panel.fit(
            f"[bold cyan]◆[/bold cyan] [bold]Datalens[/bold] v{__version__}\n"
            f"[dim]Advanced Schema Analysis & Data Profiling[/dim]\n\n"
            f"Source: [cyan]{display_source}[/cyan]\n"
            f"Output: [green]{config.out_dir}[/green]\n"
            f"Version: [yellow]{config.version_tag}[/yellow]",
            title="Schema Analysis",
        ))

        # Set up versioned history store for drift detection.
        from datalens.history.store import HistoryStore

        store_dir = Path(history_dir) if history_dir else Path(out_dir) / ".history"
        history_store = HistoryStore(store_dir)

        # Load a previous run to compare against (drift), if requested.
        previous_schema = None
        if compare_to:
            previous_schema = history_store.load(compare_to)
            if previous_schema is None:
                console.print(
                    f"[yellow]⚠ No saved run found for --compare-to '{compare_to}'; "
                    f"proceeding without drift.[/yellow]"
                )
        elif detect_drift:
            previous_schema = history_store.get_latest()
            if previous_schema is None:
                console.print(
                    "[yellow]⚠ No prior run in history yet; this run becomes the baseline.[/yellow]"
                )

        # Run analysis with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing schema...", total=None)

            result = analyze(source_spec, config, previous_schema=previous_schema)

            progress.update(task, description="[green]Analysis complete!")

        # Persist this run so future runs can detect drift against it.
        try:
            history_store.save(config.version_tag, result.schema_json)
        except Exception as e:  # history is best-effort; never fail the run
            if debug:
                console.print(f"[yellow]Could not save run to history: {e}[/yellow]")

        # Prune old runs beyond the configured retention window (protected tags kept forever).
        if config.history_retention_days > 0:
            try:
                pruned = history_store.purge_expired(
                    config.history_retention_days,
                    protected_tags=config.history_protected_tags,
                )
                if pruned:
                    console.print(
                        f"🧹 Pruned {len(pruned)} history run(s) older than "
                        f"{config.history_retention_days}d: {', '.join(pruned)}"
                    )
            except Exception as e:  # history is best-effort; never fail the run
                if debug:
                    console.print(f"[yellow]Could not prune history: {e}[/yellow]")

        # Save outputs to structured directory (from config)
        out_path = Path(config.out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Build artifact prefix from source identifier (file, db, connection name, etc.)
        artifact_prefix = _get_artifact_prefix(source_spec, source, connection_config_name)

        # Save HTML report
        html_file = out_path / f"{artifact_prefix}-datalens-report.html"
        html_file.write_text(result.html_report, encoding="utf-8")
        console.print(f"📊 HTML Report: [link=file://{html_file.absolute()}]{html_file}[/link]")

        # Save schema JSON
        json_file = out_path / f"{artifact_prefix}-datalens-schema.json"
        json_file.write_text(
            json.dumps(result.schema_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(f"📋 Schema JSON: [link=file://{json_file.absolute()}]{json_file}[/link]")

        # Save markdown summary
        md_file = out_path / f"{artifact_prefix}-datalens-summary.md"
        md_file.write_text(result.summary_md, encoding="utf-8")
        console.print(f"📝 Summary: [link=file://{md_file.absolute()}]{md_file}[/link]")

        # Machine-readable drift artifacts (only produced when a previous run was compared).
        if result.schema_drift_json is not None:
            schema_drift_file = out_path / f"{artifact_prefix}-datalens-schema-drift.json"
            schema_drift_file.write_text(
                json.dumps(result.schema_drift_json, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            console.print(
                f"🧬 Schema Drift JSON: [link=file://{schema_drift_file.absolute()}]{schema_drift_file}[/link]"
            )

        if result.coverage_drift_json is not None:
            coverage_drift_file = out_path / f"{artifact_prefix}-datalens-coverage-drift.json"
            coverage_drift_file.write_text(
                json.dumps(result.coverage_drift_json, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            console.print(
                f"📈 Coverage Drift JSON: [link=file://{coverage_drift_file.absolute()}]{coverage_drift_file}[/link]"
            )

        # Save AI insights markdown when generated
        if result.ai_insights_md:
            ai_md_file = out_path / f"{artifact_prefix}-datalens-ai-insights.md"
            ai_md_file.write_text(result.ai_insights_md, encoding="utf-8")
            provider = (result.ai_insights or {}).get("provider", "ai")
            console.print(
                f"✨ AI Insights ({provider}): "
                f"[link=file://{ai_md_file.absolute()}]{ai_md_file}[/link]"
            )

        # Print summary stats
        console.print()
        console.print(Panel(
            f"Objects: [cyan]{len(result.objects_analyzed)}[/cyan]\n"
            f"Fields: [cyan]{result.total_fields}[/cyan]\n"
            f"Records Sampled: [cyan]{result.total_sampled:,}[/cyan]",
            title="[bold cyan]◆ Datalens Results[/bold cyan]",
        ))

        # Print closing message with branding
        console.print("\n[bold cyan]✓[/bold cyan] [bold]Analysis complete![/bold]")
        console.print("[dim]Open the HTML report to explore your data with Datalens.[/dim]\n")

        if result.warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  ⚠️  {warning}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


def _parse_coverage_threshold_spec(spec: str) -> tuple[str, float]:
    """Parse a 'KEY=PCT' coverage-threshold spec into (key, percentage)."""
    if "=" not in spec:
        raise click.UsageError(
            f"Invalid threshold spec '{spec}'; expected KEY=PCT (e.g. \"orders_sample=40\")"
        )
    key, _, pct_str = spec.partition("=")
    key = key.strip()
    if not key:
        raise click.UsageError(f"Invalid threshold spec '{spec}': missing key before '='")
    try:
        pct = float(pct_str.strip())
    except ValueError:
        raise click.UsageError(f"Invalid percentage in threshold spec '{spec}': '{pct_str}'")
    return key, pct


def _build_coverage_thresholds(
    dataset: float | None,
    object_specs: tuple[str, ...],
    field_specs: tuple[str, ...],
) -> dict[str, Any]:
    """Build the coverage_thresholds dict consumed by history.diff from CLI flags."""
    thresholds: dict[str, Any] = {}

    if dataset is not None:
        thresholds["dataset"] = dataset

    if object_specs:
        object_thresholds: dict[str, float] = {}
        for spec in object_specs:
            name, pct = _parse_coverage_threshold_spec(spec)
            object_thresholds[name] = pct
        thresholds["objects"] = object_thresholds

    if field_specs:
        field_thresholds: dict[str, dict[str, float]] = {}
        for spec in field_specs:
            key, pct = _parse_coverage_threshold_spec(spec)
            obj_name, _, field_path = key.partition(".")
            if not field_path:
                raise click.UsageError(
                    f"Invalid field threshold spec '{spec}'; expected OBJECT.FIELD_PATH=PCT"
                )
            field_thresholds.setdefault(obj_name, {})[field_path] = pct
        thresholds["fields"] = field_thresholds

    return thresholds


def _build_source_spec(
    source: str,
    path: str | None,
    root: str | None,
    sheets: str | None,
    db: str | None,
    collections: str | None,
    objects: tuple[str, ...],
    uri: str | None,
    pattern: str | None = None,
    recursive: bool | None = None,
) -> dict[str, Any]:
    """Build source specification dict from CLI options.

    Returns empty spec if source is unknown (will be filled by connection config).
    """
    source_lower = source.lower()

    # Return empty spec if no source provided (will use connection config)
    if source_lower == "unknown":
        return {}

    spec: dict[str, Any] = {"source": source_lower}

    if source_lower == "file":
        if not path:
            raise click.UsageError("--path is required for file source")
        spec["path"] = path
        if root:
            spec["root"] = root
        if sheets:
            spec["sheets"] = sheets
        if pattern:
            spec["pattern"] = pattern
        if recursive:
            spec["recursive"] = True

    elif source.lower() == "mongodb":
        if not db:
            raise click.UsageError("--db is required for mongodb source")
        spec["db"] = db
        if uri:
            spec["uri"] = uri
        if collections:
            spec["collections"] = collections
        if objects:
            spec["objects"] = list(objects)

    elif source.lower() in ("s3", "http"):
        if not uri:
            raise click.UsageError(f"--uri is required for {source} source")
        spec["uri"] = uri
        if root:
            spec["root"] = root

    return spec


def _merge_connection_config(
    source_spec: dict[str, Any],
    connection_config_name: str,
    debug: bool = False,
) -> dict[str, Any]:
    """
    Load connection config and merge with source spec.

    Connection config provides base values; source_spec CLI flags override them.
    """
    loader = ConnectionLoader()
    try:
        conn_config = loader.load_connection(connection_config_name)
    except Exception as e:
        raise click.UsageError(f"Failed to load connection config: {e}")

    # Build source spec from connection config
    conn_spec = {"source": conn_config.source_type}
    conn_spec.update(conn_config.params)

    # Merge: connection config is base, CLI overrides take precedence
    # Only override with source_spec values if they were explicitly provided (not defaults)
    merged_spec = conn_spec.copy()
    for key, value in source_spec.items():
        if key == "source":
            # Source type from --source flag takes precedence
            if source_spec["source"] != conn_config.source_type:
                merged_spec["source"] = source_spec["source"]
        elif key in ("path", "root", "sheets", "pattern", "recursive", "db", "collections", "objects", "uri"):
            # Only add if provided in CLI (not None)
            if value is not None:
                merged_spec[key] = value

    if debug:
        console.print(f"[dim]Merged source spec: {merged_spec}[/dim]")

    return merged_spec


@cli.command()
def version() -> None:
    """Show version information."""
    console.print(f"Datalens v{__version__}")


@cli.command()
def info() -> None:
    """Show information about available connectors and AI providers."""
    from datalens.connectors.registry import list_available_sources

    console.print(Panel.fit(
        f"[bold]Datalens[/bold] v{__version__}\n\n"
        f"[cyan]Available Sources:[/cyan]\n"
        f"  {', '.join(list_available_sources())}\n\n"
        f"[cyan]AI Providers:[/cyan]\n"
        f"  anthropic, openai (API key) · cursor, copilot, claude (license/login)\n\n"
        f"[cyan]Documentation:[/cyan]\n"
        f"  https://github.com/datalens-ai/datalens",
        title="System Info",
    ))


@cli.command("connection-list")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information (description, metadata, tags)",
)
def connection_list_cmd(verbose: bool) -> None:
    """List available connection configurations."""
    loader = ConnectionLoader()
    connections = loader.list_connections()

    if not connections:
        console.print(
            "[yellow]No connection configs found.[/yellow]\n"
            "Create one at: [cyan].datalens/connections/{name}.yaml[/cyan]\n"
            "Or: [cyan]~/.datalens/connections/{name}.yaml[/cyan] (global)"
        )
        return

    if verbose:
        # Show detailed information
        output_lines = []
        for name, source_type in connections:
            try:
                config = loader.load_connection(name)
                output_lines.append(f"\n[bold cyan]{name}[/bold cyan] [dim]({source_type})[/dim]")
                if config.metadata:
                    if config.metadata.get("description"):
                        output_lines.append(f"  Description: {config.metadata.get('description')}")
                    if config.metadata.get("created"):
                        output_lines.append(f"  Created: {config.metadata.get('created')}")
                    if config.metadata.get("tags"):
                        tags_str = ", ".join(config.metadata.get("tags", []))
                        output_lines.append(f"  Tags: {tags_str}")
                    if config.metadata.get("owner"):
                        output_lines.append(f"  Owner: {config.metadata.get('owner')}")
            except Exception as e:
                output_lines.append(f"\n[bold cyan]{name}[/bold cyan] [dim]({source_type})[/dim]")
                output_lines.append(f"  [red]Error loading config: {e}[/red]")

        console.print(Panel("\n".join(output_lines), title="Available Connections"))
    else:
        # Show simple list
        table_lines = []
        for name, source_type in connections:
            table_lines.append(f"  [cyan]{name:25}[/cyan] [dim]{source_type}[/dim]")

        console.print(Panel(
            "\n".join(table_lines),
            title="Available Connections",
        ))
        console.print("\n[dim]Tip: Use [cyan]datalens connection-list --verbose[/cyan] for more details[/dim]")

    console.print("\nUsage: [cyan]datalens analyze --cc {connection_name}[/cyan]")


@cli.command()
@click.option(
    "--schema1",
    type=click.Path(exists=True),
    required=False,
    help="Path to first schema JSON file",
)
@click.option(
    "--schema2",
    type=click.Path(exists=True),
    required=False,
    help="Path to second schema JSON file",
)
@click.option(
    "--run1",
    type=click.Path(exists=True),
    required=False,
    help="Output directory from first analyze run (auto-finds schema JSON)",
)
@click.option(
    "--run2",
    type=click.Path(exists=True),
    required=False,
    help="Output directory from second analyze run (auto-finds schema JSON)",
)
@click.option(
    "--name1",
    type=str,
    default=None,
    help="Display name for first schema (default: inferred from file/dir)",
)
@click.option(
    "--name2",
    type=str,
    default=None,
    help="Display name for second schema (default: inferred from file/dir)",
)
@click.option(
    "-o",
    "--out-dir",
    type=click.Path(),
    default="output/comparisons",
    help="Output directory for comparison report (default: output/comparisons)",
)
@click.option(
    "--deep-compare",
    is_flag=True,
    default=False,
    help="Enable deep value sampling and overlap analysis (slower)",
)
@click.option(
    "--max-value-samples",
    type=int,
    default=100,
    help="Max distinct value samples per field in deep mode (default: 100)",
)
@click.option(
    "--cardinality-threshold",
    type=int,
    default=10000,
    help="High-cardinality threshold; fields above show samples only (default: 10000)",
)
@click.option(
    "--format",
    type=click.Choice(["html", "json", "markdown"], case_sensitive=False),
    default="html",
    help="Output format (default: html)",
)
@click.option(
    "--compare-records",
    is_flag=True,
    default=False,
    help="Enable record-level comparison (detects data value changes for matching records)",
)
@click.option(
    "--match-by",
    type=str,
    default="id",
    help="Primary key field(s) for record matching (e.g., 'id' or 'provider_id,country_code')",
)
@click.option(
    "--sample-records",
    type=int,
    default=10000,
    help="Max records to sample for comparison (default: 10000, 0 = full scan)",
)
def compare_cmd(
    schema1: str | None,
    schema2: str | None,
    run1: str | None,
    run2: str | None,
    name1: str | None,
    name2: str | None,
    out_dir: str,
    deep_compare: bool,
    max_value_samples: int,
    cardinality_threshold: int,
    format: str,
    compare_records: bool,
    match_by: str,
    sample_records: int,
) -> None:
    """
    Compare two datasets — schemas and/or records.

    Schema mode: Compare structure, types, coverage, cardinality (fast).
    Deep mode: + value samples, overlap %, distribution (optional).
    Record mode: Detect value changes for matching records (requires raw data).

    Examples:
        # Schema comparison (metadata mode)
        datalens compare --schema1 s1.json --schema2 s2.json

        # Schema + deep value analysis
        datalens compare --schema1 s1.json --schema2 s2.json --deep-compare

        # Record-level comparison (from raw JSON files)
        datalens compare \\
          --source1 file --path1 staging.json \\
          --source2 file --path2 prod.json \\
          --compare-records --match-by id

        # Composite key matching
        datalens compare --path1 s1.json --path2 s2.json \\
          --compare-records --match-by provider_id,country_code
    """
    try:
        from datalens.compare import compare_deep_schemas

        # Determine which paths to load
        if run1 and run2:
            # Auto-locate schema JSONs in run directories
            run1_path = Path(run1)
            run2_path = Path(run2)

            schema1_file = None
            schema2_file = None

            for f in run1_path.glob("*-datalens-schema.json"):
                schema1_file = f
                break
            for f in run2_path.glob("*-datalens-schema.json"):
                schema2_file = f
                break

            if not schema1_file or not schema2_file:
                raise click.UsageError(
                    "Could not find *-datalens-schema.json in run directories"
                )

            schema1 = str(schema1_file)
            schema2 = str(schema2_file)

            # Infer display names from directory names
            if not name1:
                name1 = run1_path.name
            if not name2:
                name2 = run2_path.name

        elif schema1 and schema2:
            # Use provided schema paths
            if not name1:
                name1 = Path(schema1).stem
            if not name2:
                name2 = Path(schema2).stem

        else:
            raise click.UsageError(
                "Either --schema1 & --schema2 or --run1 & --run2 must be provided"
            )

        # Load schemas
        console.print(f"[dim]Loading {schema1}...[/dim]")
        with open(schema1) as f:
            schema1_data = json.load(f)

        console.print(f"[dim]Loading {schema2}...[/dim]")
        with open(schema2) as f:
            schema2_data = json.load(f)

        # Show header
        mode = "Deep" if deep_compare else "Metadata"
        console.print(Panel.fit(
            f"[bold cyan]◆[/bold cyan] [bold]Datalens Schema Compare[/bold]\n"
            f"[dim]Comparing schemas ({mode} mode)[/dim]\n\n"
            f"Schema 1: [cyan]{name1}[/cyan]\n"
            f"Schema 2: [cyan]{name2}[/cyan]",
            title="Schema Comparison",
        ))

        # Run schema comparison
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Comparing schemas...", total=None)
            diff = compare_deep_schemas(
                schema1_data,
                schema2_data,
                name1=name1,
                name2=name2,
                deep_compare=deep_compare,
                max_value_samples=max_value_samples,
                cardinality_threshold=cardinality_threshold,
            )
            progress.update(task, completed=True)

        # Run record comparison if requested
        record_diff = None
        if compare_records:
            from datalens.compare import load_records_from_source, compare_records as compare_records_fn

            # Parse composite key
            key_fields = [f.strip() for f in match_by.split(",")]

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Loading records from sources...", total=None)

                # Determine if we should sample
                actual_sample = sample_records if sample_records > 0 else None
                is_sampled = actual_sample is not None

                try:
                    # Load records from schema1 (if it's a data file, not a schema JSON)
                    console.print(f"[dim]  Loading records from {schema1}...[/dim]")
                    records_s1, total_s1, is_raw_s1 = load_records_from_source(
                        schema1, key_fields, sample_size=actual_sample
                    )

                    console.print(f"[dim]  Loading records from {schema2}...[/dim]")
                    records_s2, total_s2, is_raw_s2 = load_records_from_source(
                        schema2, key_fields, sample_size=actual_sample
                    )

                    # If comparing raw data files, skip schema comparison
                    if is_raw_s1 or is_raw_s2:
                        console.print("[dim]Raw data detected — skipping schema comparison[/dim]")
                        diff = None

                    progress.update(task, description="[cyan]Comparing records...")

                    record_diff = compare_records_fn(
                        records_s1,
                        records_s2,
                        primary_key=key_fields if len(key_fields) > 1 else key_fields[0],
                        schema1_name=name1,
                        schema2_name=name2,
                        total_records_s1=total_s1,
                        total_records_s2=total_s2,
                        is_sampled=is_sampled,
                        sample_size=actual_sample or 0,
                    )
                    progress.update(task, completed=True)

                except Exception as e:
                    console.print(
                        f"[yellow]⚠ Record comparison failed:[/yellow] {e}\n"
                        "[dim]Make sure --schema1/2 point to raw data files, not schema JSONs.[/dim]"
                    )
                    record_diff = None

        # Create output directory
        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)

        # Determine output subdir name
        from datetime import datetime
        timestamp = datetime.now().strftime("%m%d_%H%M%S")
        subdir_name = f"{name1}_vs_{name2}_{timestamp}"
        output_subdir = out_dir_path / subdir_name
        output_subdir.mkdir(parents=True, exist_ok=True)

        # Generate outputs based on format
        if format.lower() in ("html", "all"):
            from datalens.report.comparison_report import generate_comparison_html
            html_path = output_subdir / "comparison-report.html"
            html_content = generate_comparison_html(diff, record_diff=record_diff)
            with open(html_path, "w") as f:
                f.write(html_content)
            console.print(f"[green]✓[/green] HTML report: [cyan]{html_path}[/cyan]")

        if diff:
            if format.lower() in ("json", "all"):
                json_path = output_subdir / "comparison-schema.json"
                # Convert diff to JSON-serializable format
                diff_json = {
                    "metadata": {
                        "schema1_name": diff.schema1_name,
                        "schema2_name": diff.schema2_name,
                        "compared_at": diff.compared_at,
                        "deep_compare_enabled": diff.deep_compare_enabled,
                    },
                    "similarity_score": diff.schema_similarity_score,
                    "structural_alignment": diff.structural_alignment,
                    "objects": {
                        "added": diff.added_objects,
                        "removed": diff.removed_objects,
                        "common": diff.common_objects,
                    },
                    "divergences": {
                        "type": diff.type_divergences,
                        "coverage": diff.coverage_gaps,
                        "cardinality": diff.cardinality_explosions,
                        "value_drift": diff.value_drifts,
                    },
                    "summary": {
                        "total_paths": len(diff.path_comparisons),
                        "type_divergences": len(diff.type_divergences),
                        "coverage_gaps": len(diff.coverage_gaps),
                        "cardinality_explosions": len(diff.cardinality_explosions),
                        "value_drifts": len(diff.value_drifts),
                    },
                }
                with open(json_path, "w") as f:
                    json.dump(diff_json, f, indent=2)
                console.print(f"[green]✓[/green] JSON summary: [cyan]{json_path}[/cyan]")

            if format.lower() in ("markdown", "all"):
                md_path = output_subdir / "comparison-summary.md"
                md_content = _generate_comparison_markdown(diff)
                with open(md_path, "w") as f:
                    f.write(md_content)
                console.print(f"[green]✓[/green] Markdown summary: [cyan]{md_path}[/cyan]")

            # Print summary
            summary_parts = [
                f"Similarity Score: [bold]{diff.schema_similarity_score:.1f}%[/bold]\n"
                f"Structural Alignment: [bold]{diff.structural_alignment:.1f}%[/bold]\n\n"
                f"Objects: [cyan]{len(diff.common_objects)}[/cyan] common, "
                f"[yellow]+{len(diff.added_objects)}[/yellow], "
                f"[red]-{len(diff.removed_objects)}[/red]\n\n"
                f"Divergences:\n"
                f"  Type mismatches: {len(diff.type_divergences)}\n"
                f"  Coverage gaps: {len(diff.coverage_gaps)}\n"
                f"  Cardinality changes: {len(diff.cardinality_explosions)}\n"
                f"  Value drifts: {len(diff.value_drifts)}"
            ]
        else:
            summary_parts = [
                f"Record Comparison Only:\n"
            ]

        if record_diff:
            summary_parts.append(
                f"\n\nRecord Comparison:\n"
                f"  Matched records: [cyan]{record_diff.matched_records}[/cyan]\n"
                f"  Records with changes: [yellow]{record_diff.records_with_changes}[/yellow]\n"
                f"  Only in schema 1: [red]{record_diff.only_in_s1}[/red]\n"
                f"  Only in schema 2: [green]{record_diff.only_in_s2}[/green]\n"
                f"  Total value changes: {record_diff.total_changes}"
            )
            if record_diff.is_sampled:
                summary_parts.append(f"\n  (Sampled {record_diff.sample_size} of {record_diff.total_records_s1} records)")

        console.print(Panel(
            "".join(summary_parts),
            title="Comparison Summary",
        ))

        console.print(f"\n[dim]Output: {output_subdir}[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


def _generate_comparison_markdown(diff: Any) -> str:
    """Generate markdown summary of comparison."""
    lines = [
        "# Schema Comparison Report",
        f"\n**Schema 1:** {diff.schema1_name}  \n**Schema 2:** {diff.schema2_name}",
        f"\n**Compared at:** {diff.compared_at}",
        f"\n**Mode:** {'Deep (with value sampling)' if diff.deep_compare_enabled else 'Metadata'}",
        "\n---\n",
        "## Summary\n",
        f"- **Similarity Score:** {diff.schema_similarity_score:.1f}%",
        f"- **Structural Alignment:** {diff.structural_alignment:.1f}%",
        f"- **Common Objects:** {len(diff.common_objects)}",
        f"- **Added Objects:** {len(diff.added_objects)}",
        f"- **Removed Objects:** {len(diff.removed_objects)}",
        "\n---\n",
    ]

    if diff.added_objects:
        lines.append("## Added Objects (in Schema 2)\n")
        for obj in diff.added_objects:
            lines.append(f"- {obj}")
        lines.append("")

    if diff.removed_objects:
        lines.append("## Removed Objects (from Schema 1)\n")
        for obj in diff.removed_objects:
            lines.append(f"- {obj}")
        lines.append("")

    if diff.type_divergences:
        lines.append("## Type Divergences\n")
        for div in diff.type_divergences[:20]:
            types1 = ", ".join(div["type_s1"])
            types2 = ", ".join(div["type_s2"])
            lines.append(f"- **{div['object']}.{div['path']}**: {types1} → {types2}")
        if len(diff.type_divergences) > 20:
            lines.append(f"\n... and {len(diff.type_divergences) - 20} more")
        lines.append("")

    if diff.coverage_gaps:
        lines.append("## Coverage Gaps\n")
        for gap in sorted(diff.coverage_gaps, key=lambda x: abs(x["delta"]), reverse=True)[:10]:
            lines.append(
                f"- **{gap['object']}.{gap['path']}**: "
                f"{gap['coverage_s1']:.1f}% → {gap['coverage_s2']:.1f}% "
                f"(Δ {gap['delta']:+.1f}%)"
            )
        if len(diff.coverage_gaps) > 10:
            lines.append(f"\n... and {len(diff.coverage_gaps) - 10} more")
        lines.append("")

    if diff.cardinality_explosions:
        lines.append("## Cardinality Changes\n")
        for exp in sorted(diff.cardinality_explosions, key=lambda x: x["ratio"], reverse=True)[:10]:
            lines.append(
                f"- **{exp['object']}.{exp['path']}**: "
                f"{exp['cardinality_s1']} → {exp['cardinality_s2']} "
                f"({exp['ratio']:.1f}x)"
            )
        if len(diff.cardinality_explosions) > 10:
            lines.append(f"\n... and {len(diff.cardinality_explosions) - 10} more")
        lines.append("")

    if diff.value_drifts:
        lines.append("## Value Drifts\n")
        for drift in diff.value_drifts[:10]:
            lines.append(
                f"- **{drift['object']}.{drift['path']}**: {drift['message']}"
            )
        if len(diff.value_drifts) > 10:
            lines.append(f"\n... and {len(diff.value_drifts) - 10} more")
        lines.append("")

    if not (diff.type_divergences or diff.coverage_gaps or diff.cardinality_explosions or diff.value_drifts):
        lines.append("## No Divergences Found\n")
        lines.append("The schemas are structurally and semantically aligned.")

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
