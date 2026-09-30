"""
Drift rules — which change counts as drift, how severe it is, and what to say.

Rules live in the ``drift:`` section of the app config (``-c``) or the
connection config (``--cc``). The rule for a (metric, object, field) is resolved
most-specific first:

    drift.objects.<object>.fields.<field pattern>.<metric>
    drift.objects.<object>.<metric>
    drift.defaults.<metric>
    BUILTIN_DEFAULTS[<metric>]

Object names and field paths accept fnmatch wildcards ("orders*", "address.*").

Threshold keys, per metric (any subset):

    drop_pct / increase_pct / change_pct   relative change, % of the old value
    drop_pts / increase_pts / change_pts   absolute change, in the metric's unit
                                           (percentage points for coverage)

Each value is either a number (breach = "fail") or {warn: x, fail: y}.
``min_delta`` ignores changes smaller than that absolute amount (e.g. a
category count going 1 → 2 is +100% but rarely matters).
``change_*`` applies in both directions. Messages can be customised with
``drop_message`` / ``increase_message`` (or ``message``) using the variables
{object} {field} {metric} {old} {new} {delta} {delta_pct} {threshold} {baseline}.

Schema events use severities directly:

    schema: {field_removed: fail, field_added: info, type_changed: fail,
             object_removed: fail, object_added: info, field_renamed: warn}
    categories: {new: warn, vanished: warn}
    distribution: {psi_warn: 0.10, psi_fail: 0.25}
"""

from __future__ import annotations

import copy
import fnmatch
from dataclasses import dataclass
from typing import Any

SEVERITY_ORDER = {"ok": 0, "info": 1, "warn": 2, "fail": 3}

# Out-of-the-box rules: conservative enough to be quiet on normal day-to-day
# variation, loud on real breakage. Every value is overridable in config.
BUILTIN_DEFAULTS: dict[str, Any] = {
    "row_count": {"drop_pct": {"warn": 10, "fail": 25}, "increase_pct": {"warn": 50, "fail": 200}},
    "coverage": {"drop_pts": {"warn": 5, "fail": 15}, "increase_pts": {"warn": 15}},
    "distinct": {"change_pct": {"warn": 25}, "min_delta": 3},
    "orphan_pct": {"increase_pts": {"warn": 0.5, "fail": 2}},
    "dqi": {"drop_pts": {"warn": 3, "fail": 8}},
    "health": {"drop_pts": {"warn": 5, "fail": 15}},
    "distribution": {"psi_warn": 0.10, "psi_fail": 0.25},
    "categories": {"new": "warn", "vanished": "warn"},
    "schema": {
        "field_removed": "fail",
        "field_added": "info",
        "field_renamed": "warn",
        "type_changed": "fail",
        "object_removed": "fail",
        "object_added": "info",
    },
}

_DEFAULT_MESSAGES = {
    "drop": "{object}{dot}{field}: {metric} dropped from {old} to {new} ({delta_pct}); threshold {threshold}",
    "increase": "{object}{dot}{field}: {metric} rose from {old} to {new} ({delta_pct}); threshold {threshold}",
}


@dataclass
class Evaluation:
    """Outcome of checking one metric change against its rule."""

    severity: str            # "ok" | "info" | "warn" | "fail"
    direction: str           # "drop" | "increase" | "unchanged"
    threshold: str           # human-readable threshold that fired, e.g. "drop_pct ≥ 25"
    scope: str               # "field" | "object" | "dataset" | "builtin" | "contract" | "rolling"
    message_template: str | None = None


class DriftRules:
    """Resolved drift rule set (built-ins ← config defaults ← object ← field)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = copy.deepcopy(config or {})
        self.compare_to: str = str(cfg.get("compare_to", "previous"))
        # Objects/fields with fewer rows than this aren't judged on coverage,
        # category or distribution changes (1–2 rows flip those at random).
        self.min_rows: int = int(cfg.get("min_rows", 20))
        self.rolling: dict[str, Any] = {
            "window": 14, "min_history": 3, "k": 3.0,
            "abs_floor": 0.0, "rel_floor": 0.05, "exclude_breaches": True,
            **(cfg.get("rolling") or {}),
        }
        self.defaults = _merge(BUILTIN_DEFAULTS, cfg.get("defaults") or {})
        self._user_defaults = cfg.get("defaults") or {}
        self.objects: dict[str, Any] = cfg.get("objects") or {}

    # ── resolution ───────────────────────────────────────────────────────
    def resolve(self, metric: str, obj: str | None = None, path: str | None = None) -> tuple[dict[str, Any], str]:
        """Return (rule dict, scope) for a metric at the most specific level configured."""
        obj_rule = _match(self.objects, obj) if obj else None
        if obj_rule is not None and path:
            field_rule = _match(obj_rule.get("fields") or {}, path)
            if field_rule is not None and metric in field_rule:
                return _as_rule(field_rule[metric]), "field"
        if obj_rule is not None and metric in obj_rule:
            return _as_rule(obj_rule[metric]), "object"
        if metric in self._user_defaults:
            return _as_rule(self.defaults.get(metric)), "dataset"
        return _as_rule(self.defaults.get(metric)), "builtin"

    def schema_severity(self, event: str, obj: str | None = None, path: str | None = None) -> tuple[str, str]:
        rule, scope = self.resolve("schema", obj, path)
        return str(rule.get(event, BUILTIN_DEFAULTS["schema"].get(event, "warn"))), scope

    def category_severity(self, event: str, obj: str | None = None, path: str | None = None) -> tuple[str, str]:
        rule, scope = self.resolve("categories", obj, path)
        return str(rule.get(event, "warn")), scope

    def psi_thresholds(self, obj: str | None = None, path: str | None = None) -> tuple[float, float, str]:
        rule, scope = self.resolve("distribution", obj, path)
        return float(rule.get("psi_warn", 0.10)), float(rule.get("psi_fail", 0.25)), scope

    # ── evaluation ───────────────────────────────────────────────────────
    def evaluate(
        self, metric: str, old: float, new: float, obj: str | None = None, path: str | None = None,
    ) -> Evaluation:
        """Severity of a change old → new for a threshold metric."""
        rule, scope = self.resolve(metric, obj, path)
        return evaluate_change(rule, old, new, scope)


def evaluate_change(rule: dict[str, Any], old: float, new: float, scope: str) -> Evaluation:
    delta = new - old
    direction = "drop" if delta < 0 else "increase" if delta > 0 else "unchanged"
    if direction == "unchanged" or abs(delta) < float(rule.get("min_delta", 0) or 0):
        return Evaluation("ok", direction, "", scope)
    magnitude_pts = abs(delta)
    magnitude_pct = (abs(delta) / abs(old) * 100) if old else (100.0 if delta else 0.0)

    best = Evaluation("ok", direction, "", scope)
    for key in (f"{direction}_pct", f"{direction}_pts", "change_pct", "change_pts"):
        if key not in rule:
            continue
        magnitude = magnitude_pct if key.endswith("_pct") else magnitude_pts
        for severity, limit in _levels(rule[key]):
            if magnitude >= limit and SEVERITY_ORDER[severity] > SEVERITY_ORDER[best.severity]:
                unit = "%" if key.endswith("_pct") else " pts"
                best = Evaluation(severity, direction, f"{key} ≥ {limit:g}{unit}", scope)
    template = rule.get(f"{direction}_message") or rule.get("message")
    best.message_template = template
    return best


def render_message(template: str | None, direction: str, **values: Any) -> str:
    """Fill a message template (user-defined or default) with change details."""
    values.setdefault("field", "")
    values["dot"] = "." if values.get("field") else ""
    template = template or _DEFAULT_MESSAGES.get(direction, "{object}{dot}{field}: {metric} changed")
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def _levels(value: Any) -> list[tuple[str, float]]:
    if isinstance(value, dict):
        return [(sev, float(value[sev])) for sev in ("info", "warn", "fail") if value.get(sev) is not None]
    try:
        return [("fail", float(value))]
    except (TypeError, ValueError):
        return []


def _as_rule(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _match(mapping: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    """Exact key first, then the first fnmatch pattern that matches."""
    if not name or not mapping:
        return None
    if name in mapping:
        return mapping[name]
    for pattern, value in mapping.items():
        if fnmatch.fnmatchcase(name, pattern):
            return value
    return None


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out
