"""Tests for the safe alert-condition evaluator (no eval)."""

from __future__ import annotations

import pytest

from datalens.alerts.safe_eval import UnsafeExpressionError, safe_eval, safe_eval_bool
from datalens.alerts import AlertRule, AlertType, AlertSeverity


# ─── Valid expressions evaluate correctly ────────────────────────────────────

def test_simple_comparison():
    assert safe_eval("quality_score < 70", {"quality_score": 50}) is True
    assert safe_eval("quality_score < 70", {"quality_score": 90}) is False


def test_boolean_and_or_not():
    ctx = {"pii_count": 3, "quality_score": 65}
    assert safe_eval("pii_count > 0 and quality_score < 70", ctx) is True
    assert safe_eval("pii_count > 5 or quality_score < 70", ctx) is True
    assert safe_eval("not (pii_count > 0)", ctx) is False


def test_arithmetic_and_chained_compare():
    assert safe_eval("0 < avg_coverage <= 100", {"avg_coverage": 55}) is True
    assert safe_eval("max_null_rate * 2 > 100", {"max_null_rate": 60}) is True


def test_membership():
    assert safe_eval("'ssn' in types", {"types": ["email", "ssn"]}) is True
    assert safe_eval("'ssn' not in types", {"types": ["email"]}) is True


# ─── Unsafe expressions are rejected and never execute ───────────────────────

def test_import_is_blocked():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("__import__('os').system('echo pwned')", {})


def test_function_call_is_blocked():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("open('/etc/passwd')", {})


def test_attribute_access_is_blocked():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("x.__class__", {"x": 1})


def test_unknown_name_is_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_eval("mystery_var > 1", {})


def test_safe_eval_bool_fails_closed():
    # Malicious / malformed → False, no execution.
    assert safe_eval_bool("__import__('os')", {}) is False
    assert safe_eval_bool("1 +", {}) is False


# ─── AlertRule.evaluate uses the safe path ───────────────────────────────────

def test_alert_rule_evaluate_safe_true():
    rule = AlertRule(
        name="low_quality",
        alert_type=AlertType.LOW_QUALITY_SCORE,
        severity=AlertSeverity.WARNING,
        condition="quality_score < 70",
        message_template="low",
    )
    assert rule.evaluate({"quality_score": 50}) is True
    assert rule.evaluate({"quality_score": 80}) is False


def test_alert_rule_evaluate_rejects_malicious_condition():
    rule = AlertRule(
        name="evil",
        alert_type=AlertType.CUSTOM,
        severity=AlertSeverity.CRITICAL,
        condition="__import__('os').system('echo pwned')",
        message_template="x",
    )
    # Must not execute; must return False.
    assert rule.evaluate({}) is False
