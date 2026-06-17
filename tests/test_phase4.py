"""Tests for Phase 4: Cloud Connectors, Alerts, and Metrics."""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

# Check for optional dependencies
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


# ============================================================================
# S3 Connector Tests
# ============================================================================

class TestS3Connector:
    """Tests for S3 connector."""
    
    def test_s3_connector_import(self):
        """Test S3Connector can be imported."""
        from datalens.connectors.s3 import S3Connector, s3_available
        assert S3Connector is not None
        assert callable(s3_available)
    
    def test_s3_available_check(self):
        """Test s3_available function."""
        from datalens.connectors.s3 import s3_available
        assert s3_available() == HAS_BOTO3
    
    @pytest.mark.skipif(not HAS_BOTO3, reason="boto3 not installed")
    def test_s3_connector_list_keys(self):
        """Test listing keys from S3."""
        from datalens.connectors.s3 import S3Connector
        
        with patch("boto3.Session") as mock_session:
            mock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_client
            
            # Mock paginator
            mock_paginator = MagicMock()
            mock_client.get_paginator.return_value = mock_paginator
            mock_paginator.paginate.return_value = [
                {"Contents": [{"Key": "data/file1.json"}, {"Key": "data/file2.json"}]}
            ]
            
            connector = S3Connector(bucket="test-bucket")
            keys = connector.list_keys(prefix="data/", suffix=".json")
            
            assert len(keys) == 2
            assert "data/file1.json" in keys


# ============================================================================
# HTTP Connector Tests
# ============================================================================

class TestHTTPConnector:
    """Tests for HTTP connector."""
    
    def test_http_connector_import(self):
        """Test HTTPConnector can be imported."""
        from datalens.connectors.http import HTTPConnector, httpx_available
        assert HTTPConnector is not None
        assert callable(httpx_available)
    
    def test_httpx_available_check(self):
        """Test httpx_available function."""
        from datalens.connectors.http import httpx_available
        assert httpx_available() == HAS_HTTPX
    
    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_http_connector_get(self):
        """Test HTTP GET request."""
        from datalens.connectors.http import HTTPConnector
        
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"id": 1}]}
            mock_response.raise_for_status = MagicMock()
            mock_client.request.return_value = mock_response
            
            connector = HTTPConnector(base_url="https://api.example.com")
            result = connector.get("/items")
            
            assert result == {"data": [{"id": 1}]}
    
    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_http_connector_pagination(self):
        """Test HTTP pagination."""
        from datalens.connectors.http import HTTPConnector
        
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            # First page
            response1 = MagicMock()
            response1.json.return_value = {"data": [{"id": 1}, {"id": 2}]}
            response1.raise_for_status = MagicMock()
            
            # Second page (partial)
            response2 = MagicMock()
            response2.json.return_value = {"data": [{"id": 3}]}
            response2.raise_for_status = MagicMock()
            
            mock_client.request.side_effect = [response1, response2]
            
            connector = HTTPConnector(base_url="https://api.example.com")
            records = connector.fetch_paginated(
                "/items",
                data_key="data",
                page_size=2,
            )
            
            assert len(records) == 3


# ============================================================================
# FTP Connector Tests
# ============================================================================

class TestFTPConnector:
    """Tests for FTP connector."""
    
    def test_ftp_connector_import(self):
        """Test FTPConnector can be imported."""
        from datalens.connectors.ftp import FTPConnector, SFTPConnector, paramiko_available
        assert FTPConnector is not None
        assert SFTPConnector is not None
        assert callable(paramiko_available)
    
    def test_paramiko_available_check(self):
        """Test paramiko_available function."""
        from datalens.connectors.ftp import paramiko_available
        assert paramiko_available() == HAS_PARAMIKO
    
    @patch("ftplib.FTP")
    def test_ftp_connector_read_json(self, mock_ftp_class):
        """Test FTP JSON read."""
        from datalens.connectors.ftp import FTPConnector
        
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        # Mock file read
        test_data = json.dumps([{"id": 1}, {"id": 2}]).encode()
        
        def mock_retrbinary(cmd, callback):
            callback(test_data)
        
        mock_ftp.retrbinary = mock_retrbinary
        
        connector = FTPConnector(host="ftp.example.com", username="user", password="pass")
        data = connector.read_json("/data/test.json")
        
        assert len(data) == 2
        assert data[0]["id"] == 1


# ============================================================================
# Alerts Tests
# ============================================================================

class TestAlerts:
    """Tests for alerts system."""
    
    def test_alert_creation(self):
        """Test Alert dataclass."""
        from datalens.alerts import Alert, AlertType, AlertSeverity
        
        alert = Alert(
            alert_type=AlertType.LOW_QUALITY_SCORE,
            severity=AlertSeverity.WARNING,
            title="Low Quality",
            message="Quality score is 65%",
            source="test_db",
        )
        
        assert alert.alert_type == AlertType.LOW_QUALITY_SCORE
        assert alert.severity == AlertSeverity.WARNING
        assert "Low Quality" in alert.title
    
    def test_alert_to_dict(self):
        """Test Alert serialization."""
        from datalens.alerts import Alert, AlertType, AlertSeverity
        
        alert = Alert(
            alert_type=AlertType.PII_DETECTED,
            severity=AlertSeverity.ERROR,
            title="PII Found",
            message="Found email addresses",
            source="users_collection",
        )
        
        data = alert.to_dict()
        
        assert data["alert_type"] == "pii_detected"
        assert data["severity"] == "error"
        assert "timestamp" in data
    
    def test_alert_rule_evaluation(self):
        """Test AlertRule condition evaluation."""
        from datalens.alerts import AlertRule, AlertType, AlertSeverity
        
        rule = AlertRule(
            name="low_quality",
            alert_type=AlertType.LOW_QUALITY_SCORE,
            severity=AlertSeverity.WARNING,
            condition="quality_score < 70",
            message_template="Quality is {quality_score}%",
        )
        
        # Should trigger
        assert rule.evaluate({"quality_score": 50}) is True
        
        # Should not trigger
        assert rule.evaluate({"quality_score": 80}) is False
    
    def test_alert_rule_message_format(self):
        """Test AlertRule message formatting."""
        from datalens.alerts import AlertRule, AlertType, AlertSeverity
        
        rule = AlertRule(
            name="pii_detected",
            alert_type=AlertType.PII_DETECTED,
            severity=AlertSeverity.ERROR,
            condition="pii_count > 0",
            message_template="Found {pii_count} PII fields: {pii_types}",
        )
        
        message = rule.format_message({
            "pii_count": 3,
            "pii_types": "email, phone, ssn",
        })
        
        assert "3" in message
        assert "email" in message
    
    def test_alert_manager_evaluate(self):
        """Test AlertManager evaluation."""
        from datalens.alerts import AlertManager, AlertRule, AlertType, AlertSeverity
        
        manager = AlertManager()
        manager.add_rule(AlertRule(
            name="test_rule",
            alert_type=AlertType.LOW_QUALITY_SCORE,
            severity=AlertSeverity.WARNING,
            condition="quality_score < 70",
            message_template="Quality is low",
        ))
        
        # Create mock analysis result
        analysis_result = {
            "quality": {
                "schema_quality": {"overall_score": 50}
            },
            "objects": [],
        }
        
        alerts = manager.evaluate(analysis_result, source="test")
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.LOW_QUALITY_SCORE
    
    def test_slack_channel_payload(self):
        """Test Slack channel payload building."""
        from datalens.alerts import SlackChannel, Alert, AlertType, AlertSeverity
        
        channel = SlackChannel(
            webhook_url="https://hooks.slack.com/test",
            username="TestBot",
        )
        
        alert = Alert(
            alert_type=AlertType.PII_DETECTED,
            severity=AlertSeverity.ERROR,
            title="PII Alert",
            message="Found sensitive data",
            source="test_collection",
        )
        
        payload = channel._build_payload(alert)
        
        assert payload["username"] == "TestBot"
        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["title"] == "PII Alert"
    
    def test_webhook_channel(self):
        """Test WebhookChannel."""
        from datalens.alerts import WebhookChannel, Alert, AlertType, AlertSeverity
        
        channel = WebhookChannel(
            url="https://example.com/webhook",
            headers={"X-Custom": "value"},
        )
        
        assert channel.url == "https://example.com/webhook"
        assert channel.headers["X-Custom"] == "value"


# ============================================================================
# Metrics Tests
# ============================================================================

class TestMetrics:
    """Tests for metrics export system."""
    
    def test_metric_creation(self):
        """Test Metric dataclass."""
        from datalens.metrics import Metric
        
        metric = Metric(
            name="quality.score",
            value=85.5,
            metric_type="gauge",
            tags={"source": "test"},
        )
        
        assert metric.name == "quality.score"
        assert metric.value == 85.5
        assert metric.tags["source"] == "test"
    
    def test_metric_with_prefix(self):
        """Test Metric prefix addition."""
        from datalens.metrics import Metric
        
        metric = Metric(name="score", value=100)
        prefixed = metric.with_prefix("datalens")
        
        assert prefixed.name == "datalens.score"
        assert metric.name == "score"  # Original unchanged
    
    def test_statsd_format(self):
        """Test StatsD metric formatting."""
        from datalens.metrics import StatsDSink, Metric
        
        sink = StatsDSink(host="localhost", port=8125, prefix="test")
        
        metric = Metric(
            name="quality.score",
            value=85.5,
            metric_type="gauge",
            tags={"env": "dev"},
        )
        
        formatted = sink._format_metric(metric)
        
        assert "test.quality.score" in formatted
        assert ":85.5|g" in formatted
    
    def test_json_file_sink(self):
        """Test JSON file sink."""
        from datalens.metrics import JSONFileSink, Metric
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        
        try:
            sink = JSONFileSink(filepath=filepath, append=False)
            
            metrics = [
                Metric(name="metric1", value=10),
                Metric(name="metric2", value=20),
            ]
            
            count = sink.push_batch(metrics)
            sink.flush()
            
            assert count == 2
            
            with open(filepath) as f:
                data = json.load(f)
            
            assert len(data) == 2
            assert data[0]["name"] == "metric1"
        finally:
            os.unlink(filepath)
    
    def test_metrics_exporter_extract(self):
        """Test MetricsExporter extraction."""
        from datalens.metrics import MetricsExporter
        
        exporter = MetricsExporter(prefix="datalens")
        
        analysis_result = {
            "objects": [
                {
                    "object": "test_collection",
                    "sampled": 100,
                    "fields": [
                        {"path": "id", "presence_count": 100},
                        {"path": "name", "presence_count": 80},
                    ],
                }
            ],
            "quality": {
                "schema_quality": {
                    "overall_score": 85,
                    "dimensions": [
                        {"name": "completeness", "score": 90},
                    ],
                }
            },
            "pii_summary": {
                "total_fields": 2,
                "by_type": {"email": 1, "phone": 1},
            },
        }
        
        metrics = exporter.extract_metrics(analysis_result, source="test")
        
        assert len(metrics) > 0
        
        # Check some expected metrics exist
        metric_names = [m.name for m in metrics]
        assert any("objects.count" in n for n in metric_names)
        assert any("quality.overall_score" in n for n in metric_names)
        assert any("pii.fields.count" in n for n in metric_names)
    
    def test_prometheus_format(self):
        """Test Prometheus metric formatting."""
        from datalens.metrics import PrometheusSink, Metric
        
        sink = PrometheusSink(
            pushgateway_url="http://localhost:9091",
            job="test",
        )
        
        metric = Metric(
            name="quality.score",
            value=85.5,
            tags={"env": "dev", "source": "test"},
        )
        
        formatted = sink._format_metric(metric)
        
        assert "quality_score" in formatted
        assert '85.5' in formatted


# ============================================================================
# Connector Exports Tests
# ============================================================================

class TestConnectorExports:
    """Test connector module exports."""
    
    def test_get_s3_connector(self):
        """Test S3 connector getter."""
        from datalens.connectors import get_s3_connector
        
        S3Connector, s3_available = get_s3_connector()
        assert S3Connector is not None
        assert callable(s3_available)
    
    def test_get_http_connector(self):
        """Test HTTP connector getter."""
        from datalens.connectors import get_http_connector
        
        HTTPConnector, httpx_available = get_http_connector()
        assert HTTPConnector is not None
        assert callable(httpx_available)
    
    def test_get_ftp_connectors(self):
        """Test FTP connectors getter."""
        from datalens.connectors import get_ftp_connectors
        
        FTPConnector, SFTPConnector, paramiko_available = get_ftp_connectors()
        assert FTPConnector is not None
        assert SFTPConnector is not None
        assert callable(paramiko_available)


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase4Integration:
    """Integration tests for Phase 4 features."""
    
    def test_full_analysis_with_alerts(self):
        """Test full analysis flow with alert evaluation."""
        from datalens.core import analyze
        from datalens.config import Config
        from datalens import get_alert_manager
        import tempfile
        import os
        
        # Create test data
        test_data = [
            {
                "id": "1",
                "email": "test@example.com",
                "name": "Test User",
                "score": 85,
            },
            {
                "id": "2",
                "email": "user@test.com",
                "name": None,  # Missing value
                "score": 92,
            },
        ]
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(test_data, f)
            filepath = f.name
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                source_spec = {"source": "file", "path": filepath}
                config = Config(out_dir=tmpdir, sample_size=10)
                
                result = analyze(source_spec, config)
                
                # Create alert manager and evaluate
                AlertManager = get_alert_manager()
                manager = AlertManager()
                manager.add_default_rules()
                
                # Convert result to dict for alert evaluation
                result_dict = {
                    "objects": result.schema_json.get("objects", []),
                    "quality": result.quality,
                    "pii_summary": result.pii_summary,
                }
                
                alerts = manager.evaluate(result_dict, source="test")
                
                # Test passes if alert manager can evaluate (may or may not trigger alerts)
                assert isinstance(alerts, list)
        finally:
            os.unlink(filepath)
    
    def test_full_analysis_with_metrics(self):
        """Test full analysis flow with metrics extraction."""
        from datalens.core import analyze
        from datalens.config import Config
        from datalens import get_metrics_exporter
        from datalens.metrics import JSONFileSink
        import tempfile
        import os
        
        test_data = [{"id": i, "value": i * 10} for i in range(10)]
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(test_data, f)
            filepath = f.name
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                source_spec = {"source": "file", "path": filepath}
                config = Config(out_dir=tmpdir, sample_size=10)
                
                result = analyze(source_spec, config)
                
                # Create metrics exporter
                MetricsExporter = get_metrics_exporter()
                exporter = MetricsExporter(prefix="test")
                
                metrics_file = os.path.join(tmpdir, "metrics.json")
                exporter.add_sink(JSONFileSink(metrics_file))
                
                # Convert result to dict for metrics extraction
                result_dict = {
                    "objects": result.schema_json.get("objects", []),
                    "quality": result.quality,
                    "pii_summary": result.pii_summary,
                }
                
                metrics, results = exporter.extract_and_export(result_dict, source="test")
                
                assert len(metrics) > 0
                assert "JSONFileSink" in results
                assert results["JSONFileSink"] == len(metrics)
        finally:
            os.unlink(filepath)
