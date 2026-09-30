"""
Drift engine — compares this run with a reference and explains every change.

Reference modes (``drift.compare_to`` / ``--compare-to``):

    previous         the most recent earlier run (day-over-day)
    baseline:<tag>   a fixed run, e.g. the original load
    rolling          a band learned from the last N runs (see baseline.py);
                     falls back to `previous` + static rules during cold start

What is compared (each finding says which rule fired and at what scope):

    schema        objects/fields added or removed, likely renames, type changes
    volume        row_count per object
    coverage      % of rows with a non-empty value, per field
    categories    new / vanished values of low-cardinality fields
    distribution  PSI of categorical (top values) or numeric (percentiles) fields
    distinct      number of categories of low-cardinality fields
    integrity     orphan % of detected foreign keys
    scores        DQI (overall and per object) and health
"""

from __future__ import annotations

from typing import Any

from datalens.drift.baseline import history_values, learn_band, score_against_band
from datalens.drift.metrics import (
    categorical_psi,
    field_coverage,
    metric_key,
    numeric_psi,
    proportion_se_pts,
    psi_noise,
    split_key,
)
from datalens.drift.rules import SEVERITY_ORDER, DriftRules, render_message
from datalens.history.diff import _material_types
from datalens.profiling.naming import is_identifier_name

THRESHOLD_METRICS = ("row_count", "coverage", "distinct", "orphan_pct", "dqi", "health")

NOISE_SIGMAS = 3.0
"""Changes within this many standard errors of sampling noise are not reported."""

METRIC_LABELS = {
    "row_count": "row count",
    "coverage": "coverage",
    "distinct": "category count",
    "orphan_pct": "orphan rate",
    "dqi": "DQI",
    "health": "health score",
}

HOW = {
    "row_count": "Rows in the object: true count when the whole file/collection was read, else sampled rows.",
    "coverage": "Share of rows where the field exists and is not null/empty, in %.",
    "distinct": "Number of distinct values of a low-cardinality (category-like) field.",
    "orphan_pct": "Share of foreign-key occurrences whose value has no matching parent key.",
    "dqi": "Data Quality Index (0–100), weighted mean of the quality dimensions.",
    "health": "Health score: DQI minus penalties for PII, drift and mixed types.",
    "distribution": "Population Stability Index: Σ (new% − old%) · ln(new% / old%) over value bins.",
    "categories": "Values of a category-like field present in one run but not the other.",
    "schema": "Structural comparison of object and field paths and their material value types.",
}


def _fmt(metric: str, value: float | None) -> str:
    if value is None:
        return "—"
    if metric in ("coverage", "orphan_pct"):
        return f"{value:.1f}%"
    if metric in ("row_count", "distinct"):
        return f"{value:,.0f}"
    return f"{value:.1f}"


def _pct(old: float | None, new: float | None) -> float | None:
    if old in (None, 0) or new is None:
        return None
    return round((new - old) / abs(old) * 100, 2)


class _Collector:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []

    def add(self, **finding: Any) -> None:
        if finding.get("severity", "ok") == "ok":
            return
        self.findings.append(finding)


def build_drift_report(
    current_schema: dict[str, Any],
    current_metrics: dict[str, float],
    *,
    rules: DriftRules,
    mode: str = "previous",
    reference_tag: str | None = None,
    reference_schema: dict[str, Any] | None = None,
    reference_metrics: dict[str, float] | None = None,
    history: list[dict[str, Any]] | None = None,
    reference_fields: set[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    """
    Build the drift report, or None when there is nothing to compare against.

    ``history`` is the list of earlier runs, newest first, each
    ``{"tag", "timestamp", "metrics", "breached"}`` — used by rolling mode.
    ``reference_fields`` are (object, path) foreign keys: their value mix follows
    whichever entities appear in a load, so it isn't judged as distribution drift.
    """
    history = history or []
    if reference_schema is None and not history:
        return None

    base_mode = mode.split(":", 1)[0]
    out = _Collector()
    rolling_cfg = rules.rolling
    rolling_used: list[str] = []
    cold_start: list[str] = []

    cur_objects = {o["object"]: o for o in current_schema.get("objects", [])}
    ref_objects = {o["object"]: o for o in (reference_schema or {}).get("objects", [])}
    changed_fields: set[tuple[str, str]] = set()
    skipped_small: set[str] = set()
    min_rows = rules.min_rows
    ref_keys = reference_fields or set()

    # How often each field appeared in the recent window (rolling mode learns
    # which fields are intermittent, e.g. only present on some days).
    window_runs = history[: int(rolling_cfg["window"])] if base_mode == "rolling" else []

    def seen_in_window(obj: str, path: str) -> int:
        key = metric_key("coverage", obj, path)
        return sum(1 for r in window_runs if key in (r.get("metrics") or {}))

    # ── schema ──────────────────────────────────────────────────────────
    if reference_schema is not None:
        for name in sorted(set(cur_objects) - set(ref_objects)):
            sev, scope = rules.schema_severity("object_added", name)
            out.add(kind="object_added", metric="schema", object=name, field="", severity=sev,
                    rule={"scope": scope, "threshold": "object_added", "source": "rule"},
                    message=f"New object `{name}` appeared.", how=HOW["schema"])
        for name in sorted(set(ref_objects) - set(cur_objects)):
            sev, scope = rules.schema_severity("object_removed", name)
            out.add(kind="object_removed", metric="schema", object=name, field="", severity=sev,
                    rule={"scope": scope, "threshold": "object_removed", "source": "rule"},
                    message=f"Object `{name}` is missing from this run.", how=HOW["schema"])

        for name in sorted(set(cur_objects) & set(ref_objects)):
            cur_obj, ref_obj = cur_objects[name], ref_objects[name]
            cur_fields = {f["path"]: f for f in cur_obj.get("fields", [])}
            ref_fields = {f["path"]: f for f in ref_obj.get("fields", [])}
            added = sorted(set(cur_fields) - set(ref_fields))
            removed = sorted(set(ref_fields) - set(cur_fields))
            renames = _pair_renames(ref_obj, cur_obj, removed, added)
            for old_path, new_path, evidence in renames:
                sev, scope = rules.schema_severity("field_renamed", name, new_path)
                out.add(kind="field_renamed", metric="schema", object=name, field=new_path,
                        old=old_path, new=new_path, severity=sev,
                        rule={"scope": scope, "threshold": "field_renamed", "source": "rule"},
                        message=f"`{name}.{old_path}` looks renamed to `{new_path}` ({evidence}).",
                        how="A removed and an added field in the same object with the same type, "
                            "coverage and values are paired as a likely rename.")
                changed_fields.update({(name, old_path), (name, new_path)})
            renamed_old = {r[0] for r in renames}
            renamed_new = {r[1] for r in renames}
            for path in removed:
                changed_fields.add((name, path))
                if path in renamed_old:
                    continue
                sev, scope = rules.schema_severity("field_removed", name, path)
                cov = field_coverage(ref_fields[path], ref_obj.get("sampled", 0))
                expected = ref_fields[path].get("presence_count", 0) / max(1, ref_obj.get("sampled", 0)) \
                    * cur_obj.get("sampled", 0)
                seen = seen_in_window(name, path)
                why = ""
                if expected < 5:
                    sev, why = "info", (f" Only ~{expected:.1f} row(s) would be expected in this run, "
                                        f"so it may be absent by chance.")
                elif window_runs and seen < len(window_runs):
                    sev, why = "info", (f" It appeared in only {seen} of the last {len(window_runs)} runs "
                                        f"(intermittent).")
                out.add(kind="field_removed", metric="schema", object=name, field=path, severity=sev,
                        old=round(cov, 1), rule={"scope": scope, "threshold": "field_removed", "source": "rule"},
                        message=f"Field `{name}.{path}` disappeared (was {cov:.0f}% populated).{why}",
                        how=HOW["schema"])
            for path in added:
                changed_fields.add((name, path))
                if path in renamed_new:
                    continue
                sev, scope = rules.schema_severity("field_added", name, path)
                cov = field_coverage(cur_fields[path], cur_obj.get("sampled", 0))
                pii = cur_fields[path].get("masked")
                if pii and SEVERITY_ORDER[sev] < SEVERITY_ORDER["warn"]:
                    sev = "warn"
                seen = seen_in_window(name, path)
                if seen and not pii:
                    sev = "info"
                out.add(kind="field_added", metric="schema", object=name, field=path, severity=sev,
                        new=round(cov, 1), pii=pii,
                        rule={"scope": scope, "threshold": "field_added" + (" (contains PII)" if pii else ""),
                              "source": "rule"},
                        message=(f"{'Field' if seen else 'New field'} `{name}.{path}` ({cov:.0f}% populated)"
                                 + (f" — contains {pii} PII; check it is meant to be here." if pii
                                    else f" reappeared (seen in {seen} of the last {len(window_runs)} runs)."
                                    if seen else ".")),
                        how=HOW["schema"])

            for path in sorted(set(cur_fields) & set(ref_fields)):
                old_t = _material_types(ref_fields[path], 0.02)
                new_t = _material_types(cur_fields[path], 0.02)
                # All-null on one side is a coverage change, not a type change.
                if old_t != new_t and old_t and new_t:
                    sev, scope = rules.schema_severity("type_changed", name, path)
                    share = _new_type_share(cur_fields[path], new_t - old_t)
                    out.add(kind="type_changed", metric="schema", object=name, field=path,
                            old=sorted(old_t), new=sorted(new_t), severity=sev,
                            rule={"scope": scope, "threshold": "type_changed", "source": "rule"},
                            message=(f"`{name}.{path}` type changed {sorted(old_t)} → {sorted(new_t)}"
                                     + (f"; {share:.1f}% of values now have the new type." if share else ".")),
                            how="Types making up ≥2% of a field's non-null values are compared; "
                                "rarer shapes are treated as sampling noise.")
                if min(ref_obj.get("sampled", 0), cur_obj.get("sampled", 0)) < min_rows:
                    skipped_small.add(name)
                    continue
                if (name, path) in ref_keys or is_identifier_name(path) or "date" in new_t:
                    continue
                known = set()
                for run in window_runs:
                    known.update((run.get("categories") or {}).get(metric_key("categories", name, path), []))
                _compare_values(out, rules, name, path, ref_fields[path], cur_fields[path],
                                ref_obj, cur_obj, min_rows, known, len(window_runs))

    # ── threshold metrics ───────────────────────────────────────────────
    ref_metrics = reference_metrics or {}
    keys = sorted(set(current_metrics) | set(ref_metrics))
    for key in keys:
        metric, obj, path = split_key(key)
        if metric not in THRESHOLD_METRICS or (obj, path) in changed_fields:
            continue
        if obj and obj not in cur_objects:
            continue
        if metric in ("coverage", "distinct"):
            small = cur_objects[obj].get("sampled", 0) < min_rows or (
                obj in ref_objects and ref_objects[obj].get("sampled", 0) < min_rows)
            if small:
                skipped_small.add(obj)
                continue
        new = current_metrics.get(key)
        if new is None:
            continue
        label = METRIC_LABELS[metric]
        where = f"{obj}.{path}" if path else (obj or "dataset")
        if metric == "dqi" and path and not obj:
            label, where = f"{path} score", "dataset"

        if base_mode == "rolling":
            values = history_values(history, key, window=int(rolling_cfg["window"]),
                                    exclude_breaches=bool(rolling_cfg["exclude_breaches"]))
            if len(values) >= int(rolling_cfg["min_history"]):
                abs_floor = float(rolling_cfg["abs_floor"])
                if metric in ("distinct", "row_count"):
                    abs_floor = max(abs_floor, 1.0)  # counts move in whole units
                if metric == "coverage":
                    # A percentage measured on n rows carries sampling noise; the band
                    # is never narrower than that noise.
                    n = current_metrics.get(metric_key("sampled", obj), 0)
                    abs_floor = max(abs_floor, proportion_se_pts(sorted(values)[len(values) // 2], n))
                band = learn_band(values, k=float(rolling_cfg["k"]),
                                  abs_floor=abs_floor,
                                  rel_floor=float(rolling_cfg["rel_floor"]))
                if metric in ("coverage", "orphan_pct", "dqi", "health"):
                    band.lower, band.upper = max(0.0, band.lower), min(100.0, band.upper)
                elif metric in ("row_count", "distinct"):
                    band.lower = max(0.0, band.lower)
                severity, z = score_against_band(new, band, float(rolling_cfg["k"]))
                rolling_used.append(key)
                direction = "drop" if new < band.median else "increase"
                out.add(kind=metric, metric=metric, object=obj, field=path, old=round(band.median, 4),
                        new=new, delta=round(new - band.median, 4), delta_pct=_pct(band.median, new),
                        direction=direction, severity=severity, z=round(z, 2), band=band.to_dict(),
                        rule={"scope": "rolling", "source": "rolling",
                              "threshold": f"outside median ± {rolling_cfg['k']}σ̂ "
                                           f"and the range seen in the window "
                                           f"[{_fmt(metric, band.lower)} … {_fmt(metric, band.upper)}]"},
                        message=(f"{where}: {label} {_fmt(metric, new)} is outside its learned normal range "
                                 f"{_fmt(metric, band.lower)}–{_fmt(metric, band.upper)} "
                                 f"(median {_fmt(metric, band.median)} over {band.n} runs, z={z:+.1f})."),
                        how=HOW[metric] + " Band = median ± k·1.4826·MAD of recent runs, widened to "
                            "cover every non-breached value seen in the window.")
                # Explicit user rules still apply on top of the learned band.
                rule, scope = rules.resolve(metric, obj, path)
                if scope in ("field", "object", "dataset") and key in ref_metrics:
                    _static(out, rules, metric, obj, path, ref_metrics[key], new, label, where)
                continue
            cold_start.append(key)

        if key in ref_metrics:
            if metric == "coverage" and _within_noise(ref_metrics[key], new, obj, ref_metrics, current_metrics):
                continue
            _static(out, rules, metric, obj, path, ref_metrics[key], new, label, where)

    findings = out.findings
    # Causes before symptoms: structural and volume changes first, derived scores last.
    kind_rank = {"object_removed": 0, "row_count": 1, "field_removed": 2, "type_changed": 3, "coverage": 4,
                 "orphan_pct": 5, "field_renamed": 6, "categories_new": 7, "categories_vanished": 8,
                 "distribution": 9, "distinct": 10, "field_added": 11, "object_added": 12, "dqi": 13, "health": 14}
    findings.sort(key=lambda f: (-SEVERITY_ORDER[f["severity"]], kind_rank.get(f["kind"], 20),
                                 f.get("object", ""), f.get("field", "")))
    counts = {sev: sum(1 for f in findings if f["severity"] == sev) for sev in ("fail", "warn", "info")}
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "ok"
    return {
        "mode": mode,
        "reference": {
            "tag": reference_tag,
            "runs_in_history": len(history),
            "rolling": {
                **{k: rolling_cfg[k] for k in ("window", "min_history", "k", "rel_floor", "exclude_breaches")},
                "metrics_scored": len(rolling_used),
                "metrics_cold_start": len(cold_start),
            } if base_mode == "rolling" else None,
        },
        "status": status,
        "summary": {**counts, "total": len(findings)},
        "notes": [
            f"Object `{o}` has fewer than {min_rows} rows in this or the reference run: coverage, "
            f"category and distribution changes were not judged (too few rows to be meaningful)."
            for o in sorted(skipped_small)
        ],
        "findings": findings,
        "highlights": [f["message"] for f in findings if f["severity"] in ("fail", "warn")][:10],
        "breached_metrics": sorted({
            metric_key(f["metric"], f.get("object", ""), f.get("field", ""))
            for f in findings if f["severity"] == "fail" and f["metric"] in THRESHOLD_METRICS
        }),
    }


def _within_noise(old: float, new: float, obj: str, ref_metrics: dict, cur_metrics: dict) -> bool:
    """True when a coverage change is within NOISE_SIGMAS standard errors of sampling noise."""
    n_old = ref_metrics.get(metric_key("sampled", obj), 0)
    n_new = cur_metrics.get(metric_key("sampled", obj), 0)
    if not n_old or not n_new:
        return False
    p = (old + new) / 2
    se = (proportion_se_pts(p, n_old) ** 2 + proportion_se_pts(p, n_new) ** 2) ** 0.5
    return abs(new - old) <= NOISE_SIGMAS * se


def _static(out, rules, metric, obj, path, old, new, label, where) -> None:
    ev = rules.evaluate(metric, old, new, obj or None, path or None)
    if ev.severity == "ok":
        return
    delta_pct = _pct(old, new)
    values = {
        "object": obj or "dataset", "field": path, "metric": label,
        "old": _fmt(metric, old), "new": _fmt(metric, new),
        "delta": f"{new - old:+.2f}",
        "delta_pct": f"{delta_pct:+.1f}%" if delta_pct is not None else f"{new - old:+.2f} pts",
        "threshold": ev.threshold, "baseline": _fmt(metric, old),
    }
    out.add(kind=metric, metric=metric, object=obj, field=path, old=old, new=new,
            delta=round(new - old, 4), delta_pct=delta_pct, direction=ev.direction, severity=ev.severity,
            rule={"scope": ev.scope, "threshold": ev.threshold, "source": "rule"},
            message=render_message(ev.message_template, ev.direction, **values),
            how=HOW[metric])


def _compare_values(out, rules, name, path, ref_f, cur_f, ref_obj, cur_obj, min_rows=20,
                    known_values: set[str] | None = None, window: int = 0) -> None:
    """Category and distribution drift for a field present in both runs."""
    if ref_f.get("masked") or cur_f.get("masked"):
        return
    filled = lambda f: f.get("presence_count", 0) - f.get("null_empty_count", 0)  # noqa: E731
    if min(filled(ref_f), filled(cur_f)) < min_rows:
        return
    if field_coverage(cur_f, cur_obj.get("sampled", 0)) < 1:
        return
    # Identifier-like fields (a distinct value on most rows: keys, per-row counters)
    # get new values with every new row — that's growth, not drift.
    present = max(1, cur_f.get("presence_count", 0) - cur_f.get("null_empty_count", 0))
    if cur_f.get("distinct_count_in_sample", 0) / present >= 0.5:
        return
    full_scan = cur_obj.get("total_rows") == cur_obj.get("sampled")
    ref_vc, cur_vc = ref_f.get("value_counts") or {}, cur_f.get("value_counts") or {}
    categorical = ref_f.get("low_cardinality") and cur_f.get("low_cardinality") and ref_vc and cur_vc

    if categorical:
        score, new_cats, vanished = categorical_psi(ref_vc, cur_vc)
        if known_values:
            # Rolling mode: a value seen anywhere in the recent window isn't new.
            new_cats = [c for c in new_cats if c not in known_values]
        cur_total = sum(cur_vc.values()) or 1
        ref_total = sum(ref_vc.values()) or 1
        if new_cats:
            sev, scope = rules.category_severity("new", name, path)
            # A value seen once or twice at <1% share is what small samples produce
            # by chance — worth knowing, not worth an alert.
            rare = [c for c in new_cats if cur_vc[c] <= 2 and cur_vc[c] / cur_total < 0.01]
            if rare and len(rare) == len(new_cats) and (not full_scan or cur_total < 1000):
                sev = "info"
            shown = ", ".join(f"'{c}' ({cur_vc[c]:,})" for c in new_cats[:5])
            seen_in = f" (never seen in the last {window} runs)" if known_values else ""
            out.add(kind="categories_new", metric="categories", object=name, field=path, new=new_cats,
                    severity=sev, rule={"scope": scope, "threshold": "new", "source": "rule"},
                    message=f"`{name}.{path}` has new value(s){seen_in}: {shown}.", how=HOW["categories"])
        # Vanished only counts when ≥5 rows would be expected today (P(0 | λ≥5) < 1%).
        significant = [c for c in vanished
                       if ref_vc[c] / ref_total >= 0.005 and ref_vc[c] / ref_total * cur_total >= 5]
        if significant:
            sev, scope = rules.category_severity("vanished", name, path)
            shown = ", ".join(f"'{c}' (was {ref_vc[c] / ref_total:.1%})" for c in significant[:5])
            out.add(kind="categories_vanished", metric="categories", object=name, field=path,
                    old=significant, severity=sev,
                    rule={"scope": scope, "threshold": "vanished (≥0.5% share and ≥5 rows expected)",
                          "source": "rule"},
                    message=f"`{name}.{path}` lost value(s): {shown}.", how=HOW["categories"])
        top_shift = _top_share_shift(ref_vc, cur_vc, ref_total, cur_total)
        noise = psi_noise(len(set(ref_vc) | set(cur_vc)), ref_total, cur_total)
    elif ref_f.get("numeric") and cur_f.get("numeric"):
        score = numeric_psi(ref_f["numeric"]["quantiles"], cur_f["numeric"]["quantiles"])
        o, n = ref_f["numeric"], cur_f["numeric"]
        top_shift = (f"mean {o['mean']:.4g} → {n['mean']:.4g}, median {o['quantiles']['p50']:.4g} → "
                     f"{n['quantiles']['p50']:.4g}, p95 {o['quantiles']['p95']:.4g} → {n['quantiles']['p95']:.4g}")
        noise = psi_noise(12, min(o.get("count", 0), 20000), min(n.get("count", 0), 20000))
    else:
        return

    warn, fail, scope = rules.psi_thresholds(name, path)
    floor = NOISE_SIGMAS * noise
    if score <= floor:
        return  # indistinguishable from two samples of the same distribution
    sev = "fail" if score >= fail else "warn" if score >= warn else "ok"
    out.add(kind="distribution", metric="distribution", object=name, field=path, new=score,
            severity=sev, noise_floor=round(floor, 4),
            rule={"scope": scope, "threshold": f"PSI ≥ {warn} warn / ≥ {fail} fail "
                                               f"(and above the sampling-noise floor {floor:.3f})", "source": "rule"},
            message=f"`{name}.{path}` distribution shifted (PSI {score:.2f}): {top_shift}.",
            how=HOW["distribution"] + " <0.10 stable, 0.10–0.25 moderate, >0.25 major.")


def _top_share_shift(ref_vc, cur_vc, ref_total, cur_total) -> str:
    moves = []
    for cat in set(ref_vc) | set(cur_vc):
        before, after = ref_vc.get(cat, 0) / ref_total, cur_vc.get(cat, 0) / cur_total
        moves.append((abs(after - before), cat, before, after))
    moves.sort(reverse=True)
    return "; ".join(f"'{c}' {b:.1%} → {a:.1%}" for _, c, b, a in moves[:3])


def _new_type_share(field: dict[str, Any], new_types: set[str]) -> float:
    types = field.get("types", {})
    total = sum(c for t, c in types.items() if t != "null")
    if not total or not new_types:
        return 0.0
    return sum(types.get(t, 0) for t in new_types) / total * 100


def _pair_renames(ref_obj, cur_obj, removed, added) -> list[tuple[str, str, str]]:
    """Pair removed/added fields that look like the same data under a new name."""
    ref_fields = {f["path"]: f for f in ref_obj.get("fields", [])}
    cur_fields = {f["path"]: f for f in cur_obj.get("fields", [])}
    pairs: list[tuple[float, str, str, str]] = []
    for old in removed:
        of = ref_fields[old]
        for new in added:
            nf = cur_fields[new]
            if old.rsplit(".", 1)[0] != new.rsplit(".", 1)[0] and ("." in old or "." in new):
                continue  # different parent object
            if _material_types(of, 0.02) != _material_types(nf, 0.02):
                continue
            cov_gap = abs(field_coverage(of, ref_obj.get("sampled", 0)) - field_coverage(nf, cur_obj.get("sampled", 0)))
            if cov_gap > 10:
                continue
            ov, nv = set((of.get("value_counts") or {})), set((nf.get("value_counts") or {}))
            overlap = len(ov & nv) / len(ov | nv) if ov | nv else 0.0
            if overlap < 0.5:
                continue
            pairs.append((overlap - cov_gap / 100, old, new,
                          f"same type, coverage within {cov_gap:.0f} pts, {overlap:.0%} value overlap"))
    pairs.sort(reverse=True)
    used_old, used_new, out = set(), set(), []
    for _, old, new, evidence in pairs:
        if old in used_old or new in used_new:
            continue
        used_old.add(old)
        used_new.add(new)
        out.append((old, new, evidence))
    return out
