"""
Alerts & Notifications for Datalens.

Configurable alerting system that triggers based on schema analysis results.
Supports multiple notification channels: Slack, Email, Webhooks, PagerDuty.
"""

from __future__ import annotations

import json
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts that can be triggered."""
    LOW_QUALITY_SCORE = "low_quality_score"
    PII_DETECTED = "pii_detected"
    SCHEMA_DRIFT = "schema_drift"
    LOW_COVERAGE = "low_coverage"
    HIGH_NULL_RATE = "high_null_rate"
    TYPE_INCONSISTENCY = "type_inconsistency"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    CUSTOM = "custom"


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


@dataclass
class Alert:
    """Represents a single alert."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    source: str  # Database/collection/object name
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AlertRule:
    """Rule for triggering alerts."""
    name: str
    alert_type: AlertType
    severity: AlertSeverity
    condition: str  # Python expression evaluated against analysis results
    message_template: str
    enabled: bool = True
    
    def evaluate(self, context: dict[str, Any]) -> bool:
        """
        Evaluate the rule condition.

        The condition is parsed and evaluated by a restricted AST evaluator
        (see ``alerts.safe_eval``) — never Python ``eval``. Only literals,
        names bound to ``context``, boolean/comparison/arithmetic operators,
        and membership tests are permitted; function calls, attribute access,
        and imports cannot execute.

        Args:
            context: Dict containing analysis results to evaluate against

        Returns:
            True if condition is met (alert should trigger). Returns False on
            any unsafe/malformed expression.
        """
        from datalens.alerts.safe_eval import UnsafeExpressionError, safe_eval

        try:
            return bool(safe_eval(self.condition, context))
        except UnsafeExpressionError as e:
            logger.warning(f"Rejected unsafe condition in rule '{self.name}': {e}")
            return False
        except Exception as e:
            logger.warning(f"Error evaluating rule '{self.name}': {e}")
            return False
    
    def format_message(self, context: dict[str, Any]) -> str:
        """Format the alert message with context values."""
        try:
            return self.message_template.format(**context)
        except KeyError as e:
            return f"{self.message_template} (missing key: {e})"


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""
    
    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """
        Send an alert through this channel.
        
        Args:
            alert: The alert to send
        
        Returns:
            True if successfully sent
        """
        pass
    
    @abstractmethod
    def send_batch(self, alerts: list[Alert]) -> int:
        """
        Send multiple alerts.
        
        Args:
            alerts: List of alerts to send
        
        Returns:
            Number of successfully sent alerts
        """
        pass


class SlackChannel(NotificationChannel):
    """Send alerts to Slack via webhook."""
    
    def __init__(
        self,
        webhook_url: str,
        channel: str | None = None,
        username: str = "Datalens",
        icon_emoji: str = ":chart_with_upwards_trend:",
    ):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji
    
    def _severity_to_color(self, severity: AlertSeverity) -> str:
        """Map severity to Slack attachment color."""
        return {
            AlertSeverity.INFO: "#3498db",
            AlertSeverity.WARNING: "#f39c12",
            AlertSeverity.ERROR: "#e74c3c",
            AlertSeverity.CRITICAL: "#9b59b6",
        }.get(severity, "#95a5a6")
    
    def _build_payload(self, alert: Alert) -> dict[str, Any]:
        """Build Slack message payload."""
        payload: dict[str, Any] = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": self._severity_to_color(alert.severity),
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Type", "value": alert.alert_type.value, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True},
                    ],
                    "footer": "Datalens Schema Analysis",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ],
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        return payload
    
    def send(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for Slack notifications")
            return False
        
        try:
            payload = self._build_payload(alert)
            response = httpx.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Sent Slack alert: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    def send_batch(self, alerts: list[Alert]) -> int:
        """Send multiple alerts to Slack."""
        success = 0
        for alert in alerts:
            if self.send(alert):
                success += 1
        return success


class EmailChannel(NotificationChannel):
    """Send alerts via email."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        from_email: str,
        to_emails: list[str],
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.to_emails = to_emails
        self.username = username
        self.password = password
        self.use_tls = use_tls
    
    def _build_email(self, alert: Alert) -> MIMEMultipart:
        """Build email message."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)
        
        # Plain text version
        text = f"""
Datalens Alert
==============

Title: {alert.title}
Severity: {alert.severity.value.upper()}
Type: {alert.alert_type.value}
Source: {alert.source}
Time: {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}

Message:
{alert.message}

---
This alert was generated by Datalens Schema Analysis
        """
        
        # HTML version
        severity_colors = {
            AlertSeverity.INFO: "#3498db",
            AlertSeverity.WARNING: "#f39c12",
            AlertSeverity.ERROR: "#e74c3c",
            AlertSeverity.CRITICAL: "#9b59b6",
        }
        color = severity_colors.get(alert.severity, "#95a5a6")
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0;">
                <h2 style="margin: 0;">{alert.title}</h2>
            </div>
            <div style="border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px;">
                <table style="width: 100%; margin-bottom: 15px;">
                    <tr>
                        <td><strong>Severity:</strong> {alert.severity.value.upper()}</td>
                        <td><strong>Type:</strong> {alert.alert_type.value}</td>
                    </tr>
                    <tr>
                        <td><strong>Source:</strong> {alert.source}</td>
                        <td><strong>Time:</strong> {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}</td>
                    </tr>
                </table>
                <p style="background: #f8f9fa; padding: 15px; border-radius: 5px;">{alert.message}</p>
                <hr style="border: none; border-top: 1px solid #eee;">
                <p style="color: #888; font-size: 12px;">Generated by Datalens Schema Analysis</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        
        return msg
    
    def send(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            msg = self._build_email(alert)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_email, self.to_emails, msg.as_string())
            
            logger.info(f"Sent email alert: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def send_batch(self, alerts: list[Alert]) -> int:
        """Send multiple alerts via email."""
        success = 0
        for alert in alerts:
            if self.send(alert):
                success += 1
        return success


class WebhookChannel(NotificationChannel):
    """Send alerts to a custom webhook endpoint."""
    
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        method: str = "POST",
        timeout: float = 10.0,
    ):
        self.url = url
        self.headers = headers or {}
        self.method = method.upper()
        self.timeout = timeout
    
    def send(self, alert: Alert) -> bool:
        """Send alert to webhook."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for webhook notifications")
            return False
        
        try:
            headers = {"Content-Type": "application/json", **self.headers}
            payload = alert.to_dict()
            
            response = httpx.request(
                self.method,
                self.url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(f"Sent webhook alert: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    def send_batch(self, alerts: list[Alert]) -> int:
        """Send multiple alerts to webhook."""
        success = 0
        for alert in alerts:
            if self.send(alert):
                success += 1
        return success


class PagerDutyChannel(NotificationChannel):
    """Send alerts to PagerDuty."""
    
    def __init__(self, routing_key: str, service_name: str = "Datalens"):
        self.routing_key = routing_key
        self.service_name = service_name
        self.events_url = "https://events.pagerduty.com/v2/enqueue"
    
    def _severity_to_pagerduty(self, severity: AlertSeverity) -> str:
        """Map severity to PagerDuty severity."""
        return {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical",
        }.get(severity, "info")
    
    def send(self, alert: Alert) -> bool:
        """Send alert to PagerDuty."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for PagerDuty notifications")
            return False
        
        try:
            payload = {
                "routing_key": self.routing_key,
                "event_action": "trigger",
                "dedup_key": f"{alert.source}-{alert.alert_type.value}-{alert.timestamp.isoformat()}",
                "payload": {
                    "summary": alert.title,
                    "severity": self._severity_to_pagerduty(alert.severity),
                    "source": self.service_name,
                    "custom_details": {
                        "message": alert.message,
                        "alert_type": alert.alert_type.value,
                        "source": alert.source,
                        **alert.metadata,
                    },
                },
            }
            
            response = httpx.post(self.events_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Sent PagerDuty alert: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")
            return False
    
    def send_batch(self, alerts: list[Alert]) -> int:
        """Send multiple alerts to PagerDuty."""
        success = 0
        for alert in alerts:
            if self.send(alert):
                success += 1
        return success


class AlertManager:
    """
    Manages alert rules and notification channels.
    
    Usage:
        manager = AlertManager()
        manager.add_channel(SlackChannel(webhook_url="..."))
        manager.add_rule(AlertRule(
            name="low_quality",
            alert_type=AlertType.LOW_QUALITY_SCORE,
            severity=AlertSeverity.WARNING,
            condition="quality_score < 70",
            message_template="Quality score {quality_score}% is below threshold",
        ))
        
        alerts = manager.evaluate(analysis_results)
        manager.send_alerts(alerts)
    """
    
    def __init__(self):
        self._channels: list[NotificationChannel] = []
        self._rules: list[AlertRule] = []
        self._default_rules_added = False
    
    def add_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel."""
        self._channels.append(channel)
        logger.info(f"Added notification channel: {type(channel).__name__}")
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self._rules.append(rule)
        logger.debug(f"Added alert rule: {rule.name}")
    
    def add_default_rules(
        self,
        quality_threshold: float = 70,
        coverage_threshold: float = 50,
        null_rate_threshold: float = 50,
    ) -> None:
        """Add default alerting rules."""
        if self._default_rules_added:
            return
        
        default_rules = [
            AlertRule(
                name="low_quality_score",
                alert_type=AlertType.LOW_QUALITY_SCORE,
                severity=AlertSeverity.WARNING,
                condition=f"quality_score < {quality_threshold}",
                message_template="Overall quality score {quality_score:.1f}% is below threshold ({threshold}%)",
            ),
            AlertRule(
                name="pii_detected",
                alert_type=AlertType.PII_DETECTED,
                severity=AlertSeverity.ERROR,
                condition="pii_count > 0",
                message_template="Detected {pii_count} potential PII field(s): {pii_types}",
            ),
            AlertRule(
                name="low_coverage",
                alert_type=AlertType.LOW_COVERAGE,
                severity=AlertSeverity.WARNING,
                condition=f"avg_coverage < {coverage_threshold}",
                message_template="Average field coverage {avg_coverage:.1f}% is below threshold ({threshold}%)",
            ),
            AlertRule(
                name="high_null_rate",
                alert_type=AlertType.HIGH_NULL_RATE,
                severity=AlertSeverity.WARNING,
                condition=f"max_null_rate > {null_rate_threshold}",
                message_template="Field '{high_null_field}' has {max_null_rate:.1f}% null values",
            ),
            AlertRule(
                name="type_inconsistency",
                alert_type=AlertType.TYPE_INCONSISTENCY,
                severity=AlertSeverity.ERROR,
                condition="multi_type_fields > 0",
                message_template="{multi_type_fields} field(s) have inconsistent types",
            ),
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
        
        self._default_rules_added = True
        logger.info(f"Added {len(default_rules)} default alert rules")
    
    def evaluate(
        self,
        analysis_result: dict[str, Any],
        source: str = "unknown",
    ) -> list[Alert]:
        """
        Evaluate all rules against analysis results.
        
        Args:
            analysis_result: Schema analysis result dict
            source: Source identifier (database/collection name)
        
        Returns:
            List of triggered alerts
        """
        alerts: list[Alert] = []
        
        # Build evaluation context from analysis results
        context = self._build_context(analysis_result)
        context["source"] = source
        
        for rule in self._rules:
            if not rule.enabled:
                continue
            
            try:
                if rule.evaluate(context):
                    alert = Alert(
                        alert_type=rule.alert_type,
                        severity=rule.severity,
                        title=f"{rule.name.replace('_', ' ').title()}",
                        message=rule.format_message(context),
                        source=source,
                        metadata={"rule": rule.name, **context},
                    )
                    alerts.append(alert)
                    logger.info(f"Alert triggered: {rule.name}")
            except Exception as e:
                logger.warning(f"Error evaluating rule '{rule.name}': {e}")
        
        return alerts
    
    def _build_context(self, analysis_result: dict[str, Any]) -> dict[str, Any]:
        """Build evaluation context from analysis results."""
        context: dict[str, Any] = {
            "quality_score": 0,
            "pii_count": 0,
            "pii_types": "",
            "avg_coverage": 100,
            "max_null_rate": 0,
            "high_null_field": "",
            "multi_type_fields": 0,
            "threshold": 70,
        }
        
        # Quality score
        quality = analysis_result.get("quality", {})
        if quality:
            schema_quality = quality.get("schema_quality", {})
            context["quality_score"] = schema_quality.get("overall_score", 0)
        
        # PII detection
        pii_summary = analysis_result.get("pii_summary", {})
        if pii_summary:
            context["pii_count"] = pii_summary.get("total_fields", 0)
            by_type = pii_summary.get("by_type", {})
            context["pii_types"] = ", ".join(by_type.keys()) if by_type else "none"
        
        # Coverage analysis
        objects = analysis_result.get("objects", [])
        if objects:
            coverages = []
            null_rates = []
            multi_type_count = 0
            high_null_field = ""
            max_null = 0
            
            for obj in objects:
                sampled = obj.get("sampled", 1) or 1
                for field in obj.get("fields", []):
                    presence = field.get("presence_count", 0)
                    coverage = (presence / sampled * 100) if sampled > 0 else 0
                    coverages.append(coverage)
                    
                    null_rate = 100 - coverage
                    if null_rate > max_null:
                        max_null = null_rate
                        high_null_field = field.get("path", "unknown")
                    null_rates.append(null_rate)
                    
                    if len(field.get("types", [])) > 1:
                        multi_type_count += 1
            
            context["avg_coverage"] = sum(coverages) / len(coverages) if coverages else 100
            context["max_null_rate"] = max_null
            context["high_null_field"] = high_null_field
            context["multi_type_fields"] = multi_type_count
        
        return context
    
    def send_alerts(self, alerts: list[Alert]) -> dict[str, int]:
        """
        Send alerts through all channels.
        
        Args:
            alerts: List of alerts to send
        
        Returns:
            Dict of channel names to successful send counts
        """
        if not alerts:
            logger.info("No alerts to send")
            return {}
        
        results: dict[str, int] = {}
        
        for channel in self._channels:
            channel_name = type(channel).__name__
            success = channel.send_batch(alerts)
            results[channel_name] = success
            logger.info(f"{channel_name}: sent {success}/{len(alerts)} alerts")
        
        return results
    
    def evaluate_and_send(
        self,
        analysis_result: dict[str, Any],
        source: str = "unknown",
    ) -> tuple[list[Alert], dict[str, int]]:
        """
        Evaluate rules and send any triggered alerts.
        
        Args:
            analysis_result: Schema analysis result dict
            source: Source identifier
        
        Returns:
            Tuple of (triggered alerts, send results by channel)
        """
        alerts = self.evaluate(analysis_result, source)
        results = self.send_alerts(alerts)
        return alerts, results
