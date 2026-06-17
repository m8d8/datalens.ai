"""
Datalens.ai — Advanced Schema Analysis & Data Profiling

A domain-agnostic tool for analyzing schemas, profiling data quality,
discovering patterns and relationships, and generating rich interactive reports.

Works with local files (CSV, JSON, XML, XLSX) and databases (MongoDB, more coming).
Cloud connectors support S3, HTTP/REST APIs, and FTP/SFTP servers.
Includes alerting via Slack/Email/Webhooks and metrics export to StatsD/Prometheus/Datadog.

CLI-first design; AI insights are optional and only activate when configured.
"""

__version__ = "0.2.0"
__author__ = "Datalens Contributors"

from datalens.core import analyze

# Lazy imports for optional components
def get_alert_manager():
    """Get AlertManager for configuring alerts and notifications."""
    from datalens.alerts import AlertManager
    return AlertManager

def get_metrics_exporter():
    """Get MetricsExporter for pushing metrics to monitoring backends."""
    from datalens.metrics import MetricsExporter
    return MetricsExporter

__all__ = [
    "analyze",
    "__version__",
    "get_alert_manager",
    "get_metrics_exporter",
]
