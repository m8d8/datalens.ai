"""Check a profiled run against expected schemas (BYOS)."""

from __future__ import annotations

import re
from typing import Any

from datalens.contract.loader import FORMAT_MAP, ExpectedField, ExpectedObject

STATUS_ORDER = {"pass": 0, "info": 1, "warn": 2, "fail": 3}


def _coverage(f: dict[str, Any], sampled: int) -> float:
    return max(0, f.get("presence_count", 0) - f.get("null_empty_count", 0)) / sampled * 100 if sampled else 0.0


def _presence(f: dict[str, Any], sampled: int) -> float:
    return f.get("presence_count", 0) / sampled * 100 if sampled else 0.0


def _match_objects(expected: list[ExpectedObject], objects: dict[str, dict[str, Any]]) -> list[tuple[ExpectedObject, str | None, str]]:
    """Pair each expected schema with the data object(s) it describes."""
    pairs: list[tuple[ExpectedObject, str | None, str]] = []
    for exp in expected:
        if exp.object:
            pairs.append((exp, exp.object if exp.object in objects else None, "named"))
            continue
        if len(objects) == 1:
            pairs.append((exp, next(iter(objects)), "only object"))
            continue
        matched = False
        for name, obj in objects.items():
            paths = {f["path"] for f in obj.get("fields", [])}
            overlap = len(paths & set(exp.fields)) / max(1, len(exp.fields))
            if overlap >= 0.5:
                pairs.append((exp, name, f"{overlap:.0%} of expected fields present"))
                matched = True
        if not matched:
            pairs.append((exp, None, "no object with ≥50% of the expected fields"))
    return pairs


def validate_contract(schema_json: dict[str, Any], expected: list[ExpectedObject]) -> dict[str, Any] | None:
    """Return the contract report, or None when no expected schema was given."""
    if not expected:
        return None
    objects = {o["object"]: o for o in schema_json.get("objects", [])}
    reports = []
    for exp, name, how in _match_objects(expected, objects):
        if name is None:
            label = exp.object or exp.source
            reports.append({
                "object": label, "schema": exp.source, "matched_by": how, "status": "fail",
                "conformance_pct": 0.0,
                "checks": [_check("", "object", "fail", f"object `{label}`", "not found",
                                  f"No object matching expected schema `{label}` in this run ({how}).")],
            })
            continue
        reports.append(_validate_object(objects[name], exp, how))

    worst = max((STATUS_ORDER[r["status"]] for r in reports), default=0)
    total = sum(len(r["checks"]) for r in reports)
    passed = sum(1 for r in reports for c in r["checks"] if c["status"] in ("pass", "info"))
    return {
        "status": next(k for k, v in STATUS_ORDER.items() if v == worst),
        "conformance_pct": round(passed / total * 100, 1) if total else 100.0,
        "objects": reports,
        "summary": {s: sum(1 for r in reports for c in r["checks"] if c["status"] == s)
                    for s in ("fail", "warn", "info", "pass")},
    }


def _check(field: str, check: str, status: str, expected: Any, observed: Any, message: str) -> dict[str, Any]:
    return {"field": field, "check": check, "status": status, "expected": expected,
            "observed": observed, "message": message}


def _validate_object(obj: dict[str, Any], exp: ExpectedObject, how: str) -> dict[str, Any]:
    name = obj["object"]
    sampled = obj.get("sampled", 0) or 0
    fields = {f["path"]: f for f in obj.get("fields", [])}
    checks: list[dict[str, Any]] = []

    for path, ef in exp.fields.items():
        f = fields.get(path)
        if f is None:
            if ef.required:
                checks.append(_check(path, "required", "fail", "present", "missing",
                                     f"Required field `{name}.{path}` is missing."))
            else:
                checks.append(_check(path, "present", "info", "optional", "absent",
                                     f"Optional field `{name}.{path}` not present in this run."))
            continue
        checks.extend(_field_checks(name, sampled, f, ef))

    declared = set(exp.fields)
    unexpected = [p for p in fields if p not in declared and not _under_open_parent(p, exp)]
    top_unexpected = [p for p in unexpected if "." not in p and "[]" not in p]
    if top_unexpected:
        status = "warn" if exp.closed else "info"
        checks.append(_check(
            ", ".join(top_unexpected[:10]), "unexpected_fields", status,
            "only declared fields" if exp.closed else "declared fields (others allowed)",
            f"{len(top_unexpected)} undeclared",
            f"`{name}` has {len(top_unexpected)} field(s) not in the expected schema: "
            + ", ".join(f"`{p}`" for p in top_unexpected[:10])
            + (" (additionalProperties is false)." if exp.closed else "."),
        ))

    worst = max((STATUS_ORDER[c["status"]] for c in checks), default=0)
    judged = [c for c in checks if c["status"] != "info"]
    passed = sum(1 for c in judged if c["status"] == "pass")
    return {
        "object": name,
        "schema": exp.source,
        "matched_by": how,
        "status": next(k for k, v in STATUS_ORDER.items() if v == worst),
        "conformance_pct": round(passed / len(judged) * 100, 1) if judged else 100.0,
        "checks": checks,
    }


def _under_open_parent(path: str, exp: ExpectedObject) -> bool:
    """Children of a declared object/array without declared properties are allowed."""
    parts = path.replace("[]", "").split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        for candidate in (parent, parent + "[]"):
            ef = exp.fields.get(candidate)
            if ef is not None and not any(p.startswith(candidate + ".") or p.startswith(candidate + "[]")
                                          for p in exp.fields if p != candidate):
                return True
    return False


def _field_checks(obj: str, sampled: int, f: dict[str, Any], ef: ExpectedField) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    where = f"`{obj}.{ef.path}`"
    types = {t: c for t, c in (f.get("types") or {}).items()}
    non_null = {t: c for t, c in types.items() if t != "null"}
    total = sum(non_null.values())

    # required → coverage floor
    if ef.required:
        cov = _presence(f, sampled) if ef.nullable else _coverage(f, sampled)
        what = "present" if ef.nullable else "present and non-empty"
        status = "pass" if cov >= ef.min_coverage else "fail"
        out.append(_check(ef.path, "required", status, f"≥{ef.min_coverage:g}% {what}", f"{cov:.1f}%",
                          f"{where} is required: {cov:.1f}% of rows {what} (needs ≥{ef.min_coverage:g}%)."
                          if status == "fail" else f"{where} required: {cov:.1f}% {what}."))
    elif not ef.nullable and ef.types and types.get("null"):
        out.append(_check(ef.path, "nullable", "warn", "no nulls", f"{types['null']:,} null",
                          f"{where} is not declared nullable but has {types['null']:,} null value(s)."))

    # type
    allowed = ef.allowed_shapes()
    if allowed and total:
        wrong = {t: c for t, c in non_null.items() if t not in allowed}
        if wrong:
            share = sum(wrong.values()) / total * 100
            status = "fail" if share >= 1 else "warn"
            out.append(_check(ef.path, "type", status, "/".join(ef.types), sorted(non_null),
                              f"{where} expected {'/'.join(ef.types)}; {share:.1f}% of values are "
                              + ", ".join(f"{t} ({c:,})" for t, c in wrong.items()) + "."))
        else:
            out.append(_check(ef.path, "type", "pass", "/".join(ef.types), sorted(non_null),
                              f"{where} type matches ({'/'.join(sorted(non_null))})."))

    # format
    if ef.format in FORMAT_MAP and total:
        shape = FORMAT_MAP[ef.format]
        share = non_null.get(shape, 0) / total * 100
        status = "pass" if share >= 99 else "fail" if share < 90 else "warn"
        out.append(_check(ef.path, "format", status, ef.format, f"{share:.1f}% match",
                          f"{where} format {ef.format}: {share:.1f}% of values match."))

    masked = f.get("masked")
    values = f.get("value_counts") or {}
    complete = bool(f.get("low_cardinality"))
    scope = "all values" if complete else "the most frequent values"

    # enum
    if ef.enum is not None and values and not masked:
        allowed_values = {str(v) for v in ef.enum}
        bad = {v: c for v, c in values.items() if v not in allowed_values}
        if bad:
            vc_total = sum(values.values()) or 1
            share = sum(bad.values()) / vc_total * 100
            shown = ", ".join(f"'{v}' ({c:,})" for v, c in sorted(bad.items(), key=lambda kv: -kv[1])[:5])
            out.append(_check(ef.path, "enum", "fail", ef.enum, sorted(bad)[:10],
                              f"{where} has values outside the allowed set ({share:.1f}% of {scope}): {shown}."))
        else:
            out.append(_check(ef.path, "enum", "pass", ef.enum, "all allowed",
                              f"{where}: every observed value is allowed (checked {scope})."))

    # range
    numeric = f.get("numeric")
    if numeric and any(v is not None for v in (ef.minimum, ef.maximum, ef.exclusive_minimum, ef.exclusive_maximum)):
        lo, hi = numeric["min"], numeric["max"]
        problems = []
        if ef.minimum is not None and lo < ef.minimum:
            problems.append(f"min {lo:g} < {ef.minimum:g}")
        if ef.exclusive_minimum is not None and lo <= ef.exclusive_minimum:
            problems.append(f"min {lo:g} ≤ {ef.exclusive_minimum:g}")
        if ef.maximum is not None and hi > ef.maximum:
            problems.append(f"max {hi:g} > {ef.maximum:g}")
        if ef.exclusive_maximum is not None and hi >= ef.exclusive_maximum:
            problems.append(f"max {hi:g} ≥ {ef.exclusive_maximum:g}")
        bounds = f"[{ef.minimum if ef.minimum is not None else ef.exclusive_minimum}, " \
                 f"{ef.maximum if ef.maximum is not None else ef.exclusive_maximum}]"
        out.append(_check(ef.path, "range", "fail" if problems else "pass", bounds, f"[{lo:g}, {hi:g}]",
                          f"{where} out of range: " + "; ".join(problems) + "." if problems
                          else f"{where} within {bounds} (observed {lo:g}–{hi:g})."))

    # pattern
    if ef.pattern and not masked:
        try:
            rx = re.compile(ef.pattern)
        except re.error as e:
            out.append(_check(ef.path, "pattern", "warn", ef.pattern, "invalid regex", f"{where}: bad pattern ({e})."))
        else:
            sample = [str(v) for v in values] or [str(v) for v in f.get("examples") or []]
            bad = [v for v in sample if not rx.search(v)]
            if sample:
                out.append(_check(ef.path, "pattern", "fail" if bad else "pass", ef.pattern,
                                  f"{len(bad)} of {len(sample)} checked values don't match",
                                  f"{where} values not matching /{ef.pattern}/: "
                                  + ", ".join(f"'{v}'" for v in bad[:5]) + f" (checked {scope})."
                                  if bad else f"{where} matches /{ef.pattern}/ (checked {scope})."))
    return out
