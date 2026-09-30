"""
Next steps — turn every finding of a run into a specific, prioritised action.

Each action says *what* is wrong (named objects/fields and the evidence numbers),
*why it matters*, *how to fix it* (a copy-ready snippet), and where it came
from (drift, expected schema, PII, integrity, quality, freshness or AI), so a
reader can act without re-deriving anything.

Priority = severity (high 3 · medium 2 · low 1) × 10 + breadth (0–10, share of
rows/fields affected). Effort is a labelled estimate: config/consumer changes
are low, upstream data fixes medium, data-model changes high.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from datalens.drift.metrics import field_coverage
from datalens.profiling.naming import leaf_name

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
_FROM_DRIFT = {"fail": "high", "warn": "medium", "info": "low"}


def _action(**kw: Any) -> dict[str, Any]:
    breadth = max(0.0, min(10.0, float(kw.pop("breadth", 0.0))))
    kw["priority"] = round(SEVERITY_RANK[kw["severity"]] * 10 + breadth, 1)
    kw.setdefault("fields", [])
    kw.setdefault("persona", "engineer")
    return kw


def build_next_steps(result: Any, decision: dict[str, Any]) -> list[dict[str, Any]]:
    """All actions for a run, highest priority first (ids are stable per run)."""
    drift = getattr(result, "drift_report", None)
    schema = getattr(result, "schema_json", None) or {}
    quality = getattr(result, "quality", None)
    actions: list[dict[str, Any]] = []
    actions += _pii_actions(decision, drift)
    actions += _drift_actions(drift)
    actions += _contract_actions(getattr(result, "contract", None))
    actions += _integrity_actions(getattr(result, "joins", None), drift)
    type_changed = {f"{f.get('object')}.{f.get('field')}" for f in (drift or {}).get("findings", [])
                    if f.get("kind") == "type_changed"}
    actions += _type_actions(schema, skip=type_changed)
    actions += _completeness_actions(schema)
    actions += _uniqueness_actions(quality)
    actions += _freshness_actions(quality)
    actions += _ai_actions(getattr(result, "ai_insights", None), actions)

    actions.sort(key=lambda a: (-a["priority"], a["title"]))
    actions = _merge_duplicates(actions)
    for i, a in enumerate(actions, start=1):
        a["id"] = f"A{i:02d}"
    return actions


_FAMILY = {
    ("drift", "row_count"): "volume", ("drift", "coverage"): "coverage", ("drift", "type_changed"): "type",
    ("drift", "field_removed"): "presence", ("drift", "object_removed"): "presence",
    ("drift", "categories_new"): "categories", ("contract", "type"): "type", ("contract", "enum"): "categories",
    ("contract", "object"): "presence", ("contract", "format"): "type",
}


def _merge_duplicates(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    One problem, one action: drift and expected-schema checks often describe the
    same thing (a field vanished → drift "removed" + schema "required missing").
    Actions on the same field and problem family are merged into the
    higher-priority one, keeping every source and piece of evidence.
    """
    kept: list[dict[str, Any]] = []
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for a in actions:  # already highest priority first
        family = a.pop("family", None)
        key = (a["fields"][0], family) if family and a["fields"] else None
        if key and key in index:
            main = index[key]
            if a.pop("explains", False):
                # The lower-priority finding explains the problem (e.g. a rename behind
                # "required field missing"): lead with it, keep the higher severity.
                main["also"] = main.get("also", []) + [f"[{main['source']}] {main['why']}"]
                for k in ("title", "fix", "impact"):
                    main[k] = a[k]
                main["why"] = a["why"]
                main["fields"] = list(dict.fromkeys(a["fields"] + main["fields"]))
            else:
                main.setdefault("also", []).append(f"[{a['source']}] {a['why']}")
            if a["source"] not in main.setdefault("sources", [main["source"]]):
                main["sources"].append(a["source"])
            continue
        if key:
            index[key] = a
        a.pop("explains", None)
        kept.append(a)
    for a in kept:
        if a.get("also"):
            a["why"] = a["why"] + " Also: " + " ".join(a.pop("also"))
    return kept


# ── PII ─────────────────────────────────────────────────────────────────────

def _pii_actions(decision: dict[str, Any], drift: dict[str, Any] | None) -> list[dict[str, Any]]:
    card = decision.get("compliance_scorecard") or {}
    new_fields = {
        (f.get("object"), f.get("field")) for f in (drift or {}).get("findings", [])
        if f.get("kind") == "field_added"
    }
    out = []
    for f in card.get("must_mask", []):
        obj, path, kind = f.get("object"), f.get("field"), f.get("type")
        is_new = (obj, path) in new_fields
        out.append(_action(
            title=f"Mask or remove `{obj}.{path}` ({kind}) before the data is shared",
            severity="high" if kind in ("ssn", "credit_card", "passport", "driver_license", "date_of_birth")
            or is_new else "medium",
            category="Privacy", source="pii", persona="governance", effort="low",
            fields=[f"{obj}.{path}"], breadth=5 if is_new else 3,
            why=(f"Values look like {kind} (confidence {f.get('confidence', 0):.0%}, detected by "
                 f"{f.get('method', 'name')}). Masked in this report, but present in the source"
                 + (" — and it is new since the reference run." if is_new else ".")),
            impact="Personal data in analytics extracts is a compliance and breach risk.",
            fix=(f"-- keep a joinable token instead of the raw value\n"
                 f"UPDATE {obj} SET {leaf_name(path)} = sha2(concat('<salt>', {leaf_name(path)}), 256);\n"
                 f"-- or drop it from the analytics copy / add it to pii_force for masking"),
        ))
    return out


# ── drift ───────────────────────────────────────────────────────────────────

def _drift_actions(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not report:
        return []
    ref = (report.get("reference") or {}).get("tag") or report.get("mode")
    out = []
    for f in report.get("findings", []):
        sev = _FROM_DRIFT.get(f["severity"])
        if sev is None or f["severity"] == "info":
            continue
        obj, path, kind = f.get("object") or "", f.get("field") or "", f["kind"]
        target = f"{obj}.{path}" if path else obj or "dataset"
        base = dict(severity=sev, category="Drift", source="drift", fields=[target] if obj else [],
                    family=_FAMILY.get(("drift", kind)),
                    why=f["message"] + f" (rule: {f['rule'].get('threshold')}, scope {f['rule'].get('scope')})",
                    evidence={k: f.get(k) for k in ("old", "new", "delta_pct", "z", "band") if f.get(k) is not None})
        pct = abs(f.get("delta_pct") or 0)
        if kind == "row_count":
            out.append(_action(**base, title=f"Check the `{obj}` load — volume moved {f.get('delta_pct', 0):+.0f}% vs {ref}",
                               effort="medium", breadth=min(10, pct / 10),
                               impact="Missing or duplicated rows silently skew every downstream count and KPI.",
                               fix=f"-- compare with the source system for the same period\nSELECT COUNT(*) FROM {obj};\n"
                                   f"-- then re-run the load; gate the job with: datalens analyze ... --fail-on fail"))
        elif kind == "coverage":
            out.append(_action(**base, title=f"Find why `{target}` coverage changed ({_fmt_pct(f)}) since {ref}",
                               effort="medium", breadth=min(10, abs(f.get("delta") or 0) / 5),
                               impact="Consumers relying on the field get more empty values than before.",
                               fix=f"SELECT COUNT(*) FILTER (WHERE {leaf_name(path)} IS NULL) * 100.0 / COUNT(*) FROM {obj};\n"
                                   f"-- fix upstream, or declare it optional in the expected schema"))
        elif kind == "type_changed":
            out.append(_action(**base, title=f"Restore one type for `{target}` ({f.get('old')} → {f.get('new')})",
                               effort="medium", breadth=6,
                               impact="Mixed types break casts, joins and aggregations downstream.",
                               fix=f"-- cast at the source, e.g.\nSELECT CAST({leaf_name(path)} AS INTEGER) FROM {obj};\n"
                                   f"-- and pin the type in your expected schema (--schema)"))
        elif kind in ("field_removed", "object_removed"):
            out.append(_action(**base, title=f"`{target}` disappeared since {ref} — restore it or update consumers",
                               effort="medium", breadth=7,
                               impact="Reports and jobs reading this field will fail or show blanks.",
                               fix="-- search consumers for the field before accepting the change\n"
                                   f"grep -rn \"{leaf_name(path) or obj}\" <your dbt/sql/bi repo>"))
        elif kind == "field_renamed":
            base["fields"] = [f"{obj}.{f.get('old')}", f"{obj}.{f.get('new')}"]
            base["family"] = "presence"
            base["explains"] = True
            out.append(_action(**base, title=f"Update consumers for the rename `{f.get('old')}` → `{f.get('new')}` in `{obj}`",
                               effort="low", breadth=5,
                               impact="Anything reading the old name now gets nothing.",
                               fix=f"-- temporary alias while consumers migrate\nSELECT {leaf_name(str(f.get('new')))} AS "
                                   f"{leaf_name(str(f.get('old')))} FROM {obj};"))
        elif kind == "distribution":
            out.append(_action(**base, title=f"Confirm the value shift in `{target}` is real (PSI {f.get('new')})",
                               effort="low", breadth=min(10, (f.get("new") or 0) * 10), persona="analyst",
                               impact="A mapping, unit or source change can look like a business trend.",
                               fix=f"SELECT {leaf_name(path)}, COUNT(*) FROM {obj} GROUP BY 1 ORDER BY 2 DESC;\n"
                                   f"-- compare with the reference run's mix in the Trends & Drift tab"))
        elif kind == "categories_new":
            vals = ", ".join(f"'{v}'" for v in (f.get("new") or [])[:5])
            out.append(_action(**base, title=f"Map new value(s) {vals} in `{target}`",
                               effort="low", breadth=3, persona="analyst",
                               impact="Lookups, enums and dashboards filters may drop or mislabel the new values.",
                               fix="-- add them to downstream lookups / CASE mappings / the expected schema enum"))
        elif kind == "categories_vanished":
            out.append(_action(**base, title=f"Values stopped appearing in `{target}`",
                               effort="low", breadth=3, persona="analyst",
                               impact="A filter or upstream mapping may be dropping a category.",
                               fix=f"SELECT {leaf_name(path)}, COUNT(*) FROM {obj} GROUP BY 1;"))
        # dqi / health / distinct / orphan_pct: summary signals or covered by the
        # integrity actions below — not separate to-dos.
    return out


def _fmt_pct(f: dict[str, Any]) -> str:
    if f.get("delta_pct") is not None:
        return f"{f['delta_pct']:+.1f}%"
    if f.get("delta") is not None:
        return f"{f['delta']:+.1f} pts"
    return "changed"


# ── expected schema ─────────────────────────────────────────────────────────

_CONTRACT_FIX = {
    "required": "-- populate it upstream, or remove it from `required` if it is legitimately optional",
    "type": "-- cast at the source, or widen `type` in the expected schema if both types are valid",
    "enum": "-- map the new values downstream, or add them to `enum` if they are valid",
    "range": "-- fix the out-of-range values upstream, or adjust minimum/maximum",
    "pattern": "-- fix the offending values, or relax `pattern`",
    "format": "-- normalise the values (e.g. ISO-8601 dates) at the source",
    "object": "-- check the source/path configuration — the whole object is missing",
    "nullable": "-- add \"null\" to the field's type, or stop writing nulls",
    "unexpected_fields": "-- declare the new fields in the expected schema, or stop emitting them",
}


def _contract_title(c: dict[str, Any], target: str) -> str:
    check = c["check"]
    if check == "required" and c.get("observed") == "missing":
        return f"Required field `{target}` is missing"
    if check == "required":
        return f"Required field `{target}` is only {c.get('observed')} populated"
    if check == "object":
        return f"Expected object `{target}` is missing"
    return f"`{target}` fails the {check} check ({c.get('observed')})"


def _contract_actions(contract: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not contract:
        return []
    out = []
    for obj in contract.get("objects", []):
        for c in obj["checks"]:
            if c["status"] not in ("fail", "warn"):
                continue
            target = f"{obj['object']}.{c['field']}" if c["field"] else obj["object"]
            family = _FAMILY.get(("contract", c["check"]))
            if c["check"] == "required":
                family = "presence" if c["observed"] == "missing" else "coverage"
            out.append(_action(
                family=family,
                title=_contract_title(c, target),
                severity="high" if c["status"] == "fail" else "medium",
                category="Expected schema", source="contract", effort="medium", fields=[target],
                breadth=6 if c["check"] in ("required", "type", "object") else 4,
                why=f"{c['message']} (expected {c['expected']}, observed {c['observed']})",
                impact="The data no longer matches what its consumers were promised.",
                fix=_CONTRACT_FIX.get(c["check"], ""),
            ))
    return out


# ── integrity ───────────────────────────────────────────────────────────────

def _integrity_actions(joins: dict[str, Any] | None, report: dict[str, Any] | None) -> list[dict[str, Any]]:
    drifted = {f"{f.get('object')}.{f.get('field')}": f for f in (report or {}).get("findings", [])
               if f.get("kind") == "orphan_pct"}
    out = []
    for link in (joins or {}).get("referential_integrity", []):
        if not link["orphan_occurrences"]:
            continue
        change = drifted.get(link["child"])
        pct = link["orphan_pct"]
        c_obj, _, c_path = link["child"].partition(".")
        p_obj, _, p_path = link["parent"].partition(".")
        out.append(_action(
            title=f"{pct}% of `{link['child']}` values have no match in `{link['parent']}`",
            severity="high" if pct >= 1 or (change and change["severity"] == "fail") else "medium" if pct >= 0.1 else "low",
            category="Integrity", source="drift" if change else "integrity", effort="medium",
            fields=[link["child"], link["parent"]],
            breadth=min(10, pct * 2),
            why=(f"{link['orphan_occurrences']:,} of {link['child_occurrences']:,} references "
                 f"({link['orphan_distinct']:,} distinct values) point to rows that don't exist."
                 + (f" New since the reference run: {change['message']}" if change else "")),
            impact="Joins silently drop these rows (inner join) or show blanks (left join).",
            fix=(f"SELECT c.{leaf_name(c_path)}, COUNT(*) FROM {c_obj} c\n"
                 f"LEFT JOIN {p_obj} p ON c.{leaf_name(c_path)} = p.{p_path}\n"
                 f"WHERE p.{p_path} IS NULL GROUP BY 1 ORDER BY 2 DESC;"),
        ))
    return out


# ── quality ─────────────────────────────────────────────────────────────────

def _type_actions(schema_json: dict[str, Any], skip: set[str] | None = None) -> list[dict[str, Any]]:
    """Mixed-type fields, grouped by root cause (same field name + same type pair across objects)."""
    groups: dict[tuple[str, tuple[str, ...]], list[tuple[str, str, float]]] = defaultdict(list)
    for obj in schema_json.get("objects", []):
        for f in obj.get("fields", []):
            if f"{obj['object']}.{f['path']}" in (skip or set()):
                continue  # already an action from drift
            non_null = {t: c for t, c in (f.get("types") or {}).items() if t != "null"}
            if len(non_null) < 2:
                continue
            total = sum(non_null.values())
            minority = (total - max(non_null.values())) / total * 100
            stem = leaf_name(f["path"]).replace("first_", "").replace("last_", "")
            groups[(stem, tuple(sorted(non_null)))].append((obj["object"], f["path"], minority))
    out = []
    for (stem, types), members in groups.items():
        fields = [f"{o}.{p}" for o, p, _ in members]
        worst = max(m for _, _, m in members)
        names = ", ".join(f"`{x}`" for x in fields[:6])
        out.append(_action(
            title=(f"Normalise the type of {names}" if len(fields) > 1 else f"Normalise the type of {names}")
                  + f" ({' vs '.join(types)})",
            severity="medium" if worst >= 1 else "low",
            category="Consistency", source="quality", effort="medium", fields=fields,
            breadth=min(10, len(fields) * 2 + worst / 10),
            why=(f"{len(fields)} field(s) hold both {' and '.join(types)} values; up to {worst:.1f}% of values "
                 f"use the minority type." + (" Same name and type mix → one root cause, one fix." if len(fields) > 1 else "")),
            impact="Every consumer has to special-case the field; sorting, joins and casts break.",
            fix=f"-- pick one representation at the source, e.g. for text:\nCAST({stem} AS VARCHAR)\n"
                "-- then pin it in the expected schema (type)",
        ))
    return out


def _completeness_actions(schema_json: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Low coverage that is actually a problem: top-level fields < 50%, or nested fields
    that are often missing *even when their parent is present*. Nested fields of a
    rarely-present parent (e.g. extras.* on 5% of rows) are sparse by design.
    """
    out = []
    for obj in schema_json.get("objects", []):
        sampled = obj.get("sampled", 0) or 0
        if sampled < 20:
            continue
        fields = {f["path"]: f for f in obj.get("fields", [])}
        low = []
        for path, f in fields.items():
            cov = field_coverage(f, sampled)
            if cov >= 50:
                continue
            parent = path.rsplit(".", 1)[0] if "." in path else None
            if parent and parent in fields:
                parent_present = fields[parent].get("presence_count", 0) - fields[parent].get("null_empty_count", 0)
                own = f.get("presence_count", 0) - f.get("null_empty_count", 0)
                if parent_present and own / parent_present >= 0.5:
                    continue  # conditionally complete
                if parent_present and field_coverage(fields[parent], sampled) < 50:
                    continue  # sparse parent: absence is structural
            if "[]" in path:
                continue
            low.append((path, cov))
        if not low:
            continue
        low.sort(key=lambda x: x[1])
        names = ", ".join(f"`{p}` ({c:.0f}%)" for p, c in low[:6])
        out.append(_action(
            title=f"Fill or document the sparse fields in `{obj['object']}`",
            severity="low", category="Completeness", source="quality", effort="low",
            persona="analyst", fields=[f"{obj['object']}.{p}" for p, _ in low], breadth=min(10, len(low)),
            why=f"{len(low)} field(s) are populated in under half the rows: {names}.",
            impact="Filters and aggregates on these fields cover only part of the data.",
            fix="-- if optional by design, mark them optional in the expected schema;\n"
                "-- otherwise fix collection upstream",
        ))
    return out


def _uniqueness_actions(quality: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for obj in (quality or {}).get("objects", []):
        u = (obj.get("dimensions") or {}).get("uniqueness") or {}
        details = u.get("details") or {}
        key, ratio = details.get("key_field"), details.get("key_distinct_ratio")
        if key and ratio is not None and ratio < 0.99:
            out.append(_action(
                title=f"`{obj['object']}.{key}` has duplicate values ({ratio:.1%} distinct)",
                severity="high" if ratio < 0.95 else "medium", category="Uniqueness", source="quality",
                effort="medium", fields=[f"{obj['object']}.{key}"], breadth=(1 - ratio) * 100,
                why="The most identifier-like field isn't unique, so rows may be duplicated.",
                impact="Duplicates double-count in every aggregate and break joins.",
                fix=f"SELECT {key}, COUNT(*) FROM {obj['object']} GROUP BY 1 HAVING COUNT(*) > 1;",
            ))
    return out


def _freshness_actions(quality: dict[str, Any] | None) -> list[dict[str, Any]]:
    stale = []
    for obj in (quality or {}).get("objects", []):
        t = (obj.get("dimensions") or {}).get("timeliness") or {}
        d = t.get("details") or {}
        age = d.get("median_age_days")
        if d.get("age_basis") == "newest record" and age is not None and age > 7:
            stale.append((obj["object"], d.get("newest_field"), age))
    if not stale:
        return []
    youngest = min(a for _, _, a in stale)
    names = ", ".join(f"`{o}.{f}`" for o, f, _ in stale)
    return [_action(
        title=f"Newest record is {youngest} days old ({', '.join(o for o, _, _ in stale)}) — is the feed still running?",
        severity="medium" if youngest > 30 else "low", category="Timeliness", source="quality",
        effort="low", persona="analyst", fields=[f"{o}.{f}" for o, f, _ in stale],
        breadth=min(10, youngest / 30),
        why=f"Latest dates: {names} — {youngest} days or more before today.",
        impact="Decisions may be made on stale data.",
        fix="-- if this is an archive, ignore; otherwise check the ingestion schedule",
    )]


def _ai_actions(ai: dict[str, Any] | None, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ai or not ai.get("enabled"):
        return []
    known = {f for a in existing for f in a["fields"]}
    out = []
    for rec in ai.get("recommendations", []) or []:
        text = str(rec.get("action", "")).strip()
        if not text:
            continue
        mentioned = [f for f in known if f.split(".")[-1] in text]
        out.append(_action(
            title=text.split(". ")[0][:160],
            severity=str(rec.get("severity", "low")).lower() if str(rec.get("severity", "")).lower() in SEVERITY_RANK else "low",
            category=str(rec.get("category", "AI")).title(), source="ai", effort="medium", persona="analyst",
            fields=mentioned, breadth=1,
            why=text, impact="Suggested by the AI reviewer — verify before acting.",
            fix="", related=[a["title"] for a in existing if set(a["fields"]) & set(mentioned)][:3],
        ))
    return out
