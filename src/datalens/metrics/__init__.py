"""
Stats & Metrics Export Sinks for Datalens.

Export schema analysis metrics to various backends for monitoring and alerting.
Supports Prometheus, StatsD, CloudWatch, Datadog, and custom HTTP endpoints.
"""

from __future__ import annotations

import json
import logging
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


@dataclass
class Metric:
    """Represents a single metric."""
    name: str
    value: float
    metric_type: str = "gauge"  # gauge, counter, histogram
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utcnow)
    unit: str | None = None
    
    def with_prefix(self, prefix: str) -> "Metric":
        """Return a copy with prefixed name."""
        return Metric(
            name=f"{prefix}.{self.name}",
            value=self.value,
            metric_type=self.metric_type,
            tags=self.tags.copy(),
            timestamp=self.timestamp,
            unit=self.unit,
        )


class MetricsSink(ABC):
    """Abstract base class for metrics sinks."""
    
    @abstractmethod
    def push(self, metric: Metric) -> bool:
        """
        Push a single metric.
        
        Args:
            metric: The metric to push
        
        Returns:
            True if successfully pushed
        """
        pass
    
    @abstractmethod
    def push_batch(self, metrics: list[Metric]) -> int:
        """
        Push multiple metrics.
        
        Args:
            metrics: List of metrics to push
        
        Returns:
            Number of successfully pushed metrics
        """
        pass
    
    def close(self) -> None:
        """Close any connections."""
        pass


class StatsDSink(MetricsSink):
    """Push metrics to StatsD."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "datalens",
    ):
        self.host = host
        self.port = port
        self.prefix = prefix
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def _format_metric(self, metric: Metric) -> str:
        """Format metric for StatsD."""
        name = f"{self.prefix}.{metric.name}" if self.prefix else metric.name
        
        # Add tags in DogStatsD format
        if metric.tags:
            tags = ",".join(f"{k}:{v}" for k, v in sorted(metric.tags.items()))
            name = f"{name}|#{tags}"
        
        type_map = {"gauge": "g", "counter": "c", "histogram": "h", "timing": "ms"}
        stat_type = type_map.get(metric.metric_type, "g")
        
        return f"{name}:{metric.value}|{stat_type}"
    
    def push(self, metric: Metric) -> bool:
        """Push metric to StatsD."""
        try:
            data = self._format_metric(metric)
            self._socket.sendto(data.encode(), (self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"Failed to push metric to StatsD: {e}")
            return False
    
    def push_batch(self, metrics: list[Metric]) -> int:
        """Push multiple metrics to StatsD."""
        success = 0
        for metric in metrics:
            if self.push(metric):
                success += 1
        return success
    
    def close(self) -> None:
        """Close UDP socket."""
        self._socket.close()


class PrometheusSink(MetricsSink):
    """
    Push metrics to Prometheus Pushgateway.
    
    Requires a Prometheus Pushgateway running to receive metrics.
    """
    
    def __init__(
        self,
        pushgateway_url: str,
        job: str = "datalens",
        instance: str | None = None,
        timeout: float = 10.0,
    ):
        self.pushgateway_url = pushgateway_url.rstrip("/")
        self.job = job
        self.instance = instance
        self.timeout = timeout
        self._metrics_buffer: list[str] = []
    
    def _format_metric(self, metric: Metric) -> str:
        """Format metric in Prometheus text format."""
        name = metric.name.replace(".", "_").replace("-", "_")
        
        # Build labels
        labels = dict(metric.tags)
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            full_name = f"{name}{{{label_str}}}"
        else:
            full_name = name
        
        return f"{full_name} {metric.value}"
    
    def push(self, metric: Metric) -> bool:
        """Push metric to Prometheus Pushgateway."""
        return self.push_batch([metric]) == 1
    
    def push_batch(self, metrics: list[Metric]) -> int:
        """Push metrics to Prometheus Pushgateway."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for Prometheus sink")
            return 0
        
        if not metrics:
            return 0
        
        # Build Prometheus text format
        lines = []
        for metric in metrics:
            lines.append(self._format_metric(metric))
        
        body = "\n".join(lines) + "\n"
        
        # Build URL
        url = f"{self.pushgateway_url}/metrics/job/{self.job}"
        if self.instance:
            url += f"/instance/{self.instance}"
        
        try:
            response = httpx.post(
                url,
                content=body,
                headers={"Content-Type": "text/plain"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.debug(f"Pushed {len(metrics)} metrics to Prometheus")
            return len(metrics)
        except Exception as e:
            logger.error(f"Failed to push metrics to Prometheus: {e}")
            return 0


class CloudWatchSink(MetricsSink):
    """Push metrics to AWS CloudWatch."""
    
    def __init__(
        self,
        namespace: str = "Datalens",
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for CloudWatch sink")
        
        self.namespace = namespace
        
        client_kwargs: dict[str, Any] = {}
        if region:
            client_kwargs["region_name"] = region
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
        
        self._client = boto3.client("cloudwatch", **client_kwargs)
    
    def push(self, metric: Metric) -> bool:
        """Push metric to CloudWatch."""
        return self.push_batch([metric]) == 1
    
    def push_batch(self, metrics: list[Metric]) -> int:
        """Push metrics to CloudWatch."""
        if not metrics:
            return 0
        
        # CloudWatch limits: 1000 metrics per request
        batch_size = 1000
        total_pushed = 0
        
        for i in range(0, len(metrics), batch_size):
            batch = metrics[i : i + batch_size]
            metric_data = []
            
            for metric in batch:
                data: dict[str, Any] = {
                    "MetricName": metric.name,
                    "Value": metric.value,
                    "Timestamp": metric.timestamp,
                }
                
                if metric.tags:
                    data["Dimensions"] = [
                        {"Name": k, "Value": v}
                        for k, v in metric.tags.items()
                    ]
                
                if metric.unit:
                    data["Unit"] = metric.unit
                
                metric_data.append(data)
            
            try:
                self._client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metric_data,
                )
                total_pushed += len(batch)
            except Exception as e:
                logger.error(f"Failed to push metrics to CloudWatch: {e}")
        
        return total_pushed


class DatadogSink(MetricsSink):
    """Push metrics to Datadog."""
    
    def __init__(
        self,
        api_key: str,
        app_key: str | None = None,
        site: str = "datadoghq.com",
        prefix: str = "datalens",
    ):
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        self.prefix = prefix
        self._base_url = f"https://api.{site}"
    
    def push(self, metric: Metric) -> bool:
        """Push metric to Datadog."""
        return self.push_batch([metric]) == 1
    
    def push_batch(self, metrics: list[Metric]) -> int:
        """Push metrics to Datadog."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for Datadog sink")
            return 0
        
        if not metrics:
            return 0
        
        series = []
        for metric in metrics:
            name = f"{self.prefix}.{metric.name}" if self.prefix else metric.name
            
            point = {
                "metric": name,
                "type": "gauge" if metric.metric_type == "gauge" else "count",
                "points": [[int(metric.timestamp.timestamp()), metric.value]],
            }
            
            if metric.tags:
                point["tags"] = [f"{k}:{v}" for k, v in metric.tags.items()]
            
            series.append(point)
        
        headers = {
            "Content-Type": "application/json",
            "DD-API-KEY": self.api_key,
        }
        if self.app_key:
            headers["DD-APPLICATION-KEY"] = self.app_key
        
        try:
            response = httpx.post(
                f"{self._base_url}/api/v1/series",
                json={"series": series},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            logger.debug(f"Pushed {len(metrics)} metrics to Datadog")
            return len(metrics)
        except Exception as e:
            logger.error(f"Failed to push metrics to Datadog: {e}")
            return 0


class JSONFileSink(MetricsSink):
    """Write metrics to a JSON file (for debugging/local use)."""
    
    def __init__(self, filepath: str, append: bool = True):
        self.filepath = filepath
        self.append = append
        self._metrics: list[dict] = []
        
        # Load existing if appending
        if append:
            try:
                with open(filepath) as f:
                    self._metrics = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
    
    def push(self, metric: Metric) -> bool:
        """Add metric to buffer."""
        self._metrics.append({
            "name": metric.name,
            "value": metric.value,
            "type": metric.metric_type,
            "tags": metric.tags,
            "timestamp": metric.timestamp.isoformat(),
            "unit": metric.unit,
        })
        return True
    
    def push_batch(self, metrics: list[Metric]) -> int:
        """Add multiple metrics to buffer."""
        for metric in metrics:
            self.push(metric)
        return len(metrics)
    
    def flush(self) -> None:
        """Write buffered metrics to file."""
        with open(self.filepath, "w") as f:
            json.dump(self._metrics, f, indent=2)
        logger.info(f"Flushed {len(self._metrics)} metrics to {self.filepath}")
    
    def close(self) -> None:
        """Flush and close."""
        self.flush()


class HTTPSink(MetricsSink):
    """Push metrics to a custom HTTP endpoint."""
    
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        batch_size: int = 100,
        timeout: float = 10.0,
    ):
        self.url = url
        self.headers = headers or {}
        self.batch_size = batch_size
        self.timeout = timeout
    
    def push(self, metric: Metric) -> bool:
        """Push metric to HTTP endpoint."""
        return self.push_batch([metric]) == 1
    
    def push_batch(self, metrics: list[Metric]) -> int:
        """Push metrics to HTTP endpoint."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for HTTP sink")
            return 0
        
        if not metrics:
            return 0
        
        total_pushed = 0
        headers = {"Content-Type": "application/json", **self.headers}
        
        for i in range(0, len(metrics), self.batch_size):
            batch = metrics[i : i + self.batch_size]
            payload = [
                {
                    "name": m.name,
                    "value": m.value,
                    "type": m.metric_type,
                    "tags": m.tags,
                    "timestamp": m.timestamp.isoformat(),
                    "unit": m.unit,
                }
                for m in batch
            ]
            
            try:
                response = httpx.post(
                    self.url,
                    json={"metrics": payload},
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                total_pushed += len(batch)
            except Exception as e:
                logger.error(f"Failed to push metrics to HTTP endpoint: {e}")
        
        return total_pushed


class MetricsExporter:
    """
    Orchestrates metrics extraction and export from analysis results.
    
    Usage:
        exporter = MetricsExporter()
        exporter.add_sink(StatsDSink(host="localhost"))
        exporter.add_sink(JSONFileSink("metrics.json"))
        
        metrics = exporter.extract_metrics(analysis_result)
        exporter.export(metrics)
    """
    
    def __init__(self, prefix: str = "datalens"):
        self._sinks: list[MetricsSink] = []
        self.prefix = prefix
    
    def add_sink(self, sink: MetricsSink) -> None:
        """Add a metrics sink."""
        self._sinks.append(sink)
        logger.info(f"Added metrics sink: {type(sink).__name__}")
    
    def extract_metrics(
        self,
        analysis_result: dict[str, Any],
        source: str = "unknown",
    ) -> list[Metric]:
        """
        Extract metrics from analysis results.
        
        Args:
            analysis_result: Schema analysis result dict
            source: Source identifier for tagging
        
        Returns:
            List of extracted metrics
        """
        metrics: list[Metric] = []
        base_tags = {"source": source}
        
        # Overview metrics
        metrics.append(Metric(
            name="objects.count",
            value=len(analysis_result.get("objects", [])),
            tags=base_tags,
        ))
        
        # Per-object metrics
        for obj in analysis_result.get("objects", []):
            obj_name = obj.get("object", "unknown")
            obj_tags = {**base_tags, "object": obj_name}
            
            metrics.append(Metric(
                name="object.fields.count",
                value=len(obj.get("fields", [])),
                tags=obj_tags,
            ))
            
            metrics.append(Metric(
                name="object.records.sampled",
                value=obj.get("sampled", 0),
                tags=obj_tags,
            ))
            
            # Field coverage
            sampled = obj.get("sampled", 1) or 1
            for field in obj.get("fields", []):
                field_path = field.get("path", "unknown")
                presence = field.get("presence_count", 0)
                coverage = (presence / sampled * 100) if sampled > 0 else 0
                
                metrics.append(Metric(
                    name="field.coverage",
                    value=coverage,
                    tags={**obj_tags, "field": field_path},
                    unit="Percent",
                ))
        
        # Quality metrics
        quality = analysis_result.get("quality", {})
        if quality:
            schema_quality = quality.get("schema_quality", {})
            
            metrics.append(Metric(
                name="quality.overall_score",
                value=schema_quality.get("overall_score", 0),
                tags=base_tags,
                unit="Percent",
            ))
            
            for dim in schema_quality.get("dimensions", []):
                metrics.append(Metric(
                    name=f"quality.dimension.{dim['name']}",
                    value=dim.get("score", 0),
                    tags=base_tags,
                    unit="Percent",
                ))
        
        # PII metrics
        pii_summary = analysis_result.get("pii_summary", {})
        if pii_summary:
            metrics.append(Metric(
                name="pii.fields.count",
                value=pii_summary.get("total_fields", 0),
                tags=base_tags,
            ))
            
            for pii_type, count in pii_summary.get("by_type", {}).items():
                metrics.append(Metric(
                    name="pii.by_type.count",
                    value=count,
                    tags={**base_tags, "pii_type": pii_type},
                ))
        
        # Add prefix to all metrics
        return [m.with_prefix(self.prefix) for m in metrics]
    
    def export(self, metrics: list[Metric]) -> dict[str, int]:
        """
        Export metrics to all sinks.
        
        Args:
            metrics: List of metrics to export
        
        Returns:
            Dict of sink names to successful push counts
        """
        if not metrics:
            logger.info("No metrics to export")
            return {}
        
        results: dict[str, int] = {}
        
        for sink in self._sinks:
            sink_name = type(sink).__name__
            success = sink.push_batch(metrics)
            results[sink_name] = success
            logger.info(f"{sink_name}: pushed {success}/{len(metrics)} metrics")
        
        return results
    
    def extract_and_export(
        self,
        analysis_result: dict[str, Any],
        source: str = "unknown",
    ) -> tuple[list[Metric], dict[str, int]]:
        """
        Extract metrics from analysis and export to all sinks.
        
        Args:
            analysis_result: Schema analysis result dict
            source: Source identifier
        
        Returns:
            Tuple of (extracted metrics, export results by sink)
        """
        metrics = self.extract_metrics(analysis_result, source)
        results = self.export(metrics)
        return metrics, results
    
    def close(self) -> None:
        """Close all sinks."""
        for sink in self._sinks:
            sink.close()
