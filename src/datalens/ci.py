"""
CI/CD support — a machine-readable run summary, quality gates, exit codes and
notifications, shared by ``datalens analyze``, ``datalens drift`` and
``datalens scores``.

Exit codes (stable, for pipelines):

    0  OK — no gate failed (warnings are allowed unless --fail-on warn)
    1  WARN — drift warnings and --fail-on warn
    2  FAIL — a drift breach with --fail-on fail|warn, or a score gate failed
    3  ERROR — the run itself failed (bad config, unreadable source, …)

Gates:

    --fail-on never|warn|fail          react to the drift report and expected-schema status
    --min-score health=70,dqi=80,completeness=90
                                       absolute floors (health, dqi or any DQI
                                       dimension: completeness, consistency,
                                       uniqueness, validity, timeliness,
                                       granularity, accuracy)
    --max-drop dqi=5,health=10         max allowed drop in points vs the
                                       drift reference run

Notifications (``--notify``, repeatable):

    slack:https://hooks.slack.com/services/…   Slack incoming webhook
    webhook:https://example.com/hook           JSON POST of the run summary
    file:path/to/alerts.jsonl                  append one JSON line (local/testing)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXIT_OK, EXIT_WARN, EXIT_FAIL, EXIT_ERROR = 0, 1, 2, 3

SCORE_NAMES = ("health", "dqi", "completeness", "consistency", "uniqueness",
               "validity", "timeliness", "granularity", "accuracy")


def build_run_summary(result: Any, *, run_date: str | None = None) -> dict[str, Any]:
    """Compact, stable JSON view of a run: scores, volumes, drift and top actions."""
    decision = result.decision or {}
    verdict = decision.get("health_verdict", {})
    quality = result.quality or {}
    drift = result.drift_report
    compliance = decision.get("compliance_scorecard", {})
    scores: dict[str, float | None] = {
        "health": verdict.get("score"),
        "dqi": quality.get("overall_dqi"),
        **{k: v for k, v in (quality.get("schema_dimensions") or {}).items()},
    }
    return {
        "version_tag": result.version_tag,
        "run_date": run_date,
        "status": verdict.get("status"),
        "scores": scores,
        "health": {
            "status": verdict.get("status"),
            "score": verdict.get("score"),
            "base_dqi": verdict.get("base_dqi"),
            "penalties": verdict.get("penalties", {}),
            "drivers": verdict.get("drivers", []),
        },
        "objects": {
            obj.get("object"): {
                "rows": obj.get("total_rows", obj.get("sampled")),
                "sampled": obj.get("sampled"),
                "fields": len(obj.get("fields", [])),
                "dqi": next((o.get("dqi") for o in quality.get("objects", []) if o.get("object") == obj.get("object")), None),
                "fitness": [b.get("label") for b in decision.get("fitness_for_use", {}).get(obj.get("object"), [])],
            }
            for obj in result.schema_json.get("objects", [])
        },
        "pii": {
            "risk": compliance.get("risk"),
            "risk_reason": compliance.get("risk_reason"),
            "high_risk_fields": [f"{f.get('object')}.{f.get('field')}" for f in compliance.get("must_mask", [])],
            "masked_in_outputs": bool((result.pii_summary or {}).get("masking_enabled")),
        },
        "drift": None if drift is None else {
            "mode": drift.get("mode"),
            "reference": (drift.get("reference") or {}).get("tag"),
            "status": drift.get("status"),
            "summary": drift.get("summary"),
            "highlights": drift.get("highlights", []),
        },
        "contract": None if not getattr(result, "contract", None) else {
            "status": result.contract.get("status"),
            "conformance_pct": result.contract.get("conformance_pct"),
            "summary": result.contract.get("summary"),
            "failures": [
                c["message"] for o in result.contract.get("objects", []) for c in o["checks"] if c["status"] == "fail"
            ][:20],
        },
        "top_actions": [
            {"severity": a.get("severity"), "category": a.get("category"), "action": a.get("action")}
            for a in decision.get("top_actions", [])
        ],
    }


def parse_gate_spec(spec: str | None, *, option: str) -> dict[str, float]:
    """Parse "health=70,dqi=80" into {"health": 70.0, "dqi": 80.0}."""
    gates: dict[str, float] = {}
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        name, sep, value = part.partition("=")
        name = name.strip().lower()
        if not sep or name not in SCORE_NAMES:
            raise ValueError(
                f"Invalid {option} entry '{part}'. Use NAME=NUMBER with NAME in: {', '.join(SCORE_NAMES)}"
            )
        gates[name] = float(value)
    return gates


def evaluate_gates(
    summary: dict[str, Any],
    *,
    fail_on: str = "never",
    min_scores: dict[str, float] | None = None,
    max_drops: dict[str, float] | None = None,
    reference_scores: dict[str, float] | None = None,
) -> tuple[int, list[str]]:
    """Return (exit code, human-readable reasons) for the configured gates."""
    reasons: list[str] = []
    code = EXIT_OK
    scores = summary.get("scores") or {}

    drift = summary.get("drift") or {}
    status = drift.get("status")
    counts = drift.get("summary") or {}
    if fail_on in ("fail", "warn") and status == "fail":
        code = EXIT_FAIL
        reasons.append(f"Drift breach: {counts.get('fail', 0)} finding(s) at 'fail' severity.")
    elif fail_on == "warn" and status == "warn":
        code = max(code, EXIT_WARN)
        reasons.append(f"Drift warning: {counts.get('warn', 0)} finding(s) at 'warn' severity.")

    contract = summary.get("contract") or {}
    if fail_on in ("fail", "warn") and contract.get("status") == "fail":
        code = EXIT_FAIL
        reasons.append(f"Expected schema: {(contract.get('summary') or {}).get('fail', 0)} check(s) failed "
                       f"(conformance {contract.get('conformance_pct')}%).")
    elif fail_on == "warn" and contract.get("status") == "warn":
        code = max(code, EXIT_WARN)
        reasons.append("Expected schema: warnings.")

    for name, floor in (min_scores or {}).items():
        value = scores.get(name)
        if value is None:
            reasons.append(f"Score gate {name}≥{floor:g}: score not available in this run.")
            code = EXIT_FAIL
        elif value < floor:
            reasons.append(f"Score gate failed: {name} {value:.1f} < {floor:g}.")
            code = EXIT_FAIL

    for name, allowed in (max_drops or {}).items():
        before = (reference_scores or {}).get(name)
        value = scores.get(name)
        if before is None or value is None:
            continue
        drop = before - value
        if drop > allowed:
            reasons.append(f"Drop gate failed: {name} fell {drop:.1f} pts ({before:.1f} → {value:.1f}), max {allowed:g}.")
            code = EXIT_FAIL

    return code, reasons


def reference_scores_from_metrics(metrics: dict[str, float] | None) -> dict[str, float]:
    """Pull health/dqi/dimension scores out of a stored run's metric dict."""
    out: dict[str, float] = {}
    for key, value in (metrics or {}).items():
        metric, obj, path = (key.split("|", 2) + ["", ""])[:3]
        if obj:
            continue
        if metric == "health" and not path:
            out["health"] = value
        elif metric == "dqi" and not path:
            out["dqi"] = value
        elif metric == "dqi" and path in SCORE_NAMES:
            out[path] = value
    return out


def notify(targets: list[str], summary: dict[str, Any], exit_code: int, reasons: list[str]) -> list[str]:
    """Send the run outcome to each target. Returns one status line per target."""
    if not targets:
        return []
    payload = {**summary, "exit_code": exit_code, "gate_reasons": reasons}
    title = _title(summary, exit_code)
    lines: list[str] = []
    for target in targets:
        kind, _, dest = target.partition(":")
        try:
            if kind == "file":
                path = Path(dest)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, default=str) + "\n")
                ok = True
            elif kind in ("slack", "webhook"):
                ok = _post(kind, dest, title, payload, reasons)
            else:
                lines.append(f"✗ {target}: unknown target type (use slack:, webhook: or file:)")
                continue
            lines.append(f"{'✓' if ok else '✗'} notified {kind}")
        except Exception as e:  # notifications are best-effort
            lines.append(f"✗ {kind}: {e}")
    return lines


def _title(summary: dict[str, Any], exit_code: int) -> str:
    label = {EXIT_OK: "OK", EXIT_WARN: "WARN", EXIT_FAIL: "FAIL"}.get(exit_code, "ERROR")
    health = (summary.get("scores") or {}).get("health")
    return f"Datalens {label}: run {summary.get('version_tag')} — health {health}"


def _post(kind: str, url: str, title: str, payload: dict[str, Any], reasons: list[str]) -> bool:
    from datalens.alerts import Alert, AlertSeverity, AlertType, SlackChannel, WebhookChannel

    highlights = ((payload.get("drift") or {}).get("highlights") or []) + \
        ((payload.get("contract") or {}).get("failures") or [])
    message = "\n".join([*reasons, *[f"• {h}" for h in highlights[:8]]]) or "No gate failures."
    severity = AlertSeverity.ERROR if payload["exit_code"] >= EXIT_FAIL else (
        AlertSeverity.WARNING if payload["exit_code"] == EXIT_WARN else AlertSeverity.INFO)
    alert = Alert(AlertType.SCHEMA_DRIFT, severity, title, message,
                  source=str(payload.get("version_tag")), metadata={"summary": payload})
    channel = SlackChannel(url) if kind == "slack" else WebhookChannel(url)
    return channel.send(alert)
