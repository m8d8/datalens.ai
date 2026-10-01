"""
Join analysis — unique/composite keys and cross-object join candidates.

Pure data-driven inference. Three layers:

1. Per-object primary key inference: find a single field with near-unique values
   covering all records. If none, find smallest composite key by combining
   high-coverage high-cardinality fields heuristically (proxy: highest
   distinct counts × coverage).

2. Cross-object FK candidates: same field path present in 2+ objects with high
   cardinality and high coverage on both sides.

3. Cross-object value-overlap candidates: different paths whose distinct values
   overlap strongly; scored by Jaccard similarity of distinct values weighted
   by cardinality compatibility and type match.

4. Within-object nested relationships: nested arrays/objects under the same
   parent path form 1:N/1:1 relationships; surface them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datalens.profiling.sampler import ProfileScratch


@dataclass
class PrimaryKeyCandidate:
    object_name: str
    fields: list[str]  # single field or composite
    coverage: float    # 0-1
    distinct_ratio: float  # distinct / sampled
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object_name,
            "fields": self.fields,
            "is_composite": len(self.fields) > 1,
            "coverage": round(self.coverage, 3),
            "distinct_ratio": round(self.distinct_ratio, 3),
            "rationale": self.rationale,
        }


@dataclass
class JoinCandidate:
    left: str   # "object.path"
    right: str
    kind: str   # "same_path_fk" | "value_overlap" | "name_similarity"
    confidence: float  # 0-1
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "right": self.right,
            "kind": self.kind,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
        }


@dataclass
class DuplicateFieldCandidate:
    object_name: str
    field_a: str
    field_b: str
    jaccard: float          # 0 for structural duplicates
    confidence: float
    coverage_a: float
    coverage_b: float
    recommend: str          # "a" | "b" | "either"
    evidence: list[str]
    kind: str               # "value_duplicate" | "structural_duplicate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "object": self.object_name,
            "field_a": self.field_a,
            "field_b": self.field_b,
            "jaccard": round(self.jaccard, 3),
            "confidence": round(self.confidence, 3),
            "coverage_a": round(self.coverage_a, 3),
            "coverage_b": round(self.coverage_b, 3),
            "recommend": self.recommend,
            "evidence": self.evidence,
            "kind": self.kind,
        }


def _coverage(field_data: dict[str, Any], sampled: int) -> float:
    presence = field_data.get("presence_count", 0)
    nulls = field_data.get("null_empty_count", 0)
    eff = max(0, presence - nulls)
    return (eff / sampled) if sampled else 0.0


def _scratch_hashes(
    scratch: "ProfileScratch | None", obj_name: str, path: str
) -> Counter | None:
    """Exact value-hash counts for a field, or None when unavailable / over the tracking limit."""
    if scratch is None or path in scratch.overflow.get(obj_name, ()):
        return None
    hashes = scratch.field_hashes(obj_name, path)
    return hashes if hashes else None


def _containment(child: Counter | set, shared: set) -> float:
    """Share of the child's occurrences (row-weighted when counts are known) found in `shared`."""
    if isinstance(child, Counter):
        total = sum(child.values())
        return (sum(child[h] for h in shared) / total) if total else 0.0
    return (len(shared) / len(child)) if child else 0.0


def _shared_examples(a_field: dict[str, Any], b_field: dict[str, Any], limit: int = 5) -> list[str]:
    """Readable shared values (from the displayed top values on both sides)."""
    a_keys = set((a_field.get("value_counts") or {}).keys()) | {str(v) for v in a_field.get("examples") or []}
    b_keys = set((b_field.get("value_counts") or {}).keys()) | {str(v) for v in b_field.get("examples") or []}
    return sorted(a_keys & b_keys)[:limit]


def _get_path(record: Any, path: str) -> Any:
    """Value at a dotted scalar path in a raw record (None if absent)."""
    cur = record
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _distinct_set(field_data: dict[str, Any]) -> set[Any]:
    """Best-effort distinct value set from a field, using value_counts or distinct_values."""
    vc = field_data.get("value_counts") or {}
    if isinstance(vc, dict) and vc:
        return set(vc.keys())
    if isinstance(vc, list) and vc:
        return {entry[0] for entry in vc if isinstance(entry, (list, tuple)) and entry}
    dv = field_data.get("distinct_values") or []
    if dv:
        return set(dv)
    return set(field_data.get("examples") or [])


# Audit/timestamp-like field names — excluded from composite key candidates by default.
# These typically describe *when* a record was created or changed and are not stable
# entity identifiers.
_AUDIT_NAME_HINTS = (
    "create", "update", "modify", "delete", "expire", "publish",
    "lastmod", "lastupdate", "lastchange",
    "timestamp", "_ts", "_at", "ingested", "imported", "loaded",
    "received", "fetched", "synced", "etl",
    "createtime", "modifytime", "deletetime", "updatetime",
    "createdate", "modifydate", "updatedate",
)

# Identifier-like field name hints — these get a bias when picking composite keys.
_IDENTIFIER_NAME_HINTS = (
    "id", "uuid", "guid", "key", "code", "slug", "sku",
    "isbn", "ean", "upc", "ref", "no", "number", "hash",
    "token", "fingerprint",
)


def _is_audit_field(path: str, types: set[str]) -> bool:
    """Heuristic: treat date/datetime-typed fields and audit-named fields as audit."""
    if {"date", "datetime", "timestamp"} & types:
        return True
    leaf = path.split(".")[-1].lower()
    return any(hint in leaf for hint in _AUDIT_NAME_HINTS)


def _identifier_bias(path: str) -> float:
    """Return a multiplier (1.0–2.0) that favors identifier-shaped field names."""
    leaf = path.split(".")[-1].lower()
    # Word-boundary-ish check so 'video' doesn't get credit for 'id'.
    tokens = leaf.replace("_", " ").replace("-", " ").split()
    for hint in _IDENTIFIER_NAME_HINTS:
        if leaf == hint or leaf.endswith(hint) or hint in tokens:
            return 2.0
    return 1.0


def _composite_product(chosen: list[tuple[str, float, float]], sampled: int) -> float:
    """Approximate combined-distinct of a composite candidate."""
    product = 1.0
    for _, _, ratio in chosen:
        product *= max(1.0, ratio * sampled)
    return product


def infer_primary_keys(schema_json: dict[str, Any]) -> list[PrimaryKeyCandidate]:
    """Return a primary-key candidate per object: single field if possible, else composite.

    Audit/timestamp fields (createdAt, updatedAt, modifiedAt, …) are excluded
    from composite key candidates — they describe when a record changed, not
    which entity it represents. They are only considered as a last-resort
    tiebreaker when no other combination reaches uniqueness, and the rationale
    flags that the suggestion is weak and should be reviewed.
    """
    candidates: list[PrimaryKeyCandidate] = []
    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "Unknown")
        sampled = obj.get("sampled", 0)
        if sampled <= 0:
            continue
        fields = obj.get("fields", [])

        scored = []
        for f in fields:
            path = f.get("path", "")
            if "[]" in path or "." in path:
                continue  # prefer top-level scalar fields for PK
            types = {t for t in f.get("types", {}).keys() if t != "null"}
            if not types or "object" in types or "array" in types:
                continue
            cov = _coverage(f, sampled)
            distinct = f.get("distinct_count_in_sample", 0)
            ratio = distinct / sampled if sampled else 0.0
            is_audit = _is_audit_field(path, types)
            scored.append((f, path, cov, ratio, is_audit))

        if not scored:
            continue

        # Single-field PK: coverage >= 0.95 and distinct_ratio >= 0.95, never an audit field.
        # Prefer identifier-shaped names when multiple qualify.
        single = sorted(
            [s for s in scored if s[2] >= 0.95 and s[3] >= 0.95 and not s[4]],
            key=lambda s: (-_identifier_bias(s[1]), -s[3], -s[2]),
        )
        if single:
            _, path, cov, ratio, _ = single[0]
            candidates.append(
                PrimaryKeyCandidate(
                    object_name=obj_name,
                    fields=[path],
                    coverage=cov,
                    distinct_ratio=ratio,
                    rationale=(
                        f"Field has {ratio:.0%} distinct ratio and "
                        f"{cov:.0%} effective coverage — strong unique key candidate."
                    ),
                )
            )
            continue

        # Composite PK: prefer identifier-shaped, non-audit fields.
        # Audit/timestamp fields are only allowed as a last resort, flagged.
        non_audit = [s for s in scored if not s[4]]

        def _rank_score(s: tuple) -> float:
            _, path, cov, ratio, _ = s
            return cov * ratio * _identifier_bias(path)

        ranked = sorted(non_audit, key=lambda s: -_rank_score(s))

        def _greedy(pool: list[tuple]) -> list[tuple[str, float, float]]:
            picked: list[tuple[str, float, float]] = []
            product = 1.0
            for _, p, cov, ratio, _ in pool[:8]:
                if cov < 0.5 or ratio <= 0:
                    continue
                picked.append((p, cov, ratio))
                product *= max(1.0, ratio * sampled)
                if product >= sampled and len(picked) >= 2:
                    return picked
            return picked

        chosen = _greedy(ranked)
        identifier_present = any(_identifier_bias(p) > 1.0 for p, _, _ in chosen)
        fallback_used = False

        # Fall back to audit fields only if no non-audit composite reaches uniqueness.
        if len(chosen) < 2 or _composite_product(chosen, sampled) < sampled:
            audit_pool = sorted(scored, key=lambda s: -_rank_score(s))
            audit_chosen = _greedy(audit_pool)
            if _composite_product(audit_chosen, sampled) > _composite_product(chosen, sampled):
                chosen = audit_chosen
                fallback_used = any(
                    _is_audit_field(p, set()) for p, _, _ in chosen
                )

        if len(chosen) >= 2:
            paths = [c[0] for c in chosen]
            min_cov = min(c[1] for c in chosen)
            avg_ratio = sum(c[2] for c in chosen) / len(chosen)
            rationale_bits = [
                "No single field is unique; combining "
                + " + ".join(f"`{p}`" for p in paths)
                + " approximates a unique tuple based on high cardinality "
                "and coverage of each component."
            ]
            if identifier_present and not fallback_used:
                rationale_bits.append(
                    "Preferred identifier-shaped fields over audit timestamps."
                )
            if fallback_used:
                rationale_bits.append(
                    "⚠ Includes an audit/timestamp field as a last resort — "
                    "consider designating a stable business key (e.g. `id`, `uuid`, "
                    "external code) instead."
                )
            candidates.append(
                PrimaryKeyCandidate(
                    object_name=obj_name,
                    fields=paths,
                    coverage=min_cov,
                    distinct_ratio=avg_ratio,
                    rationale=" ".join(rationale_bits),
                )
            )

    return candidates


def _path_signature(path: str) -> str:
    return path.replace("[]", "").lower()


def _depth(path: str) -> int:
    """Dot-depth of a path (0 = top-level, 1 = one nested level, etc.)."""
    clean = path.replace("[]", "")
    return clean.count(".")


# Username/person-like hints — irrelevant for entity-joins.
_USERNAME_HINTS = (
    "username", "user_name", "login", "email", "fullname", "firstname",
    "lastname", "displayname", "nickname", "handle", "author", "owner",
    "creator", "editor", "actor",
)

# Low-information field names — high prevalence but zero join signal.
_NOISE_HINTS = (
    "status", "state", "type", "flag", "active", "enabled",
    "sort", "order", "rank", "weight", "priority",
    "version", "revision", "count", "total", "index",
)


def _is_join_useless(path: str, types: set[str]) -> bool:
    """Return True if this field should never be used as a join field."""
    if _is_audit_field(path, types):
        return True
    leaf = path.split(".")[-1].lower()
    if any(h in leaf for h in _USERNAME_HINTS):
        return True
    if any(h == leaf or leaf == h + "s" for h in _NOISE_HINTS):
        return True
    return False


def _eligible_join_fields(
    obj: dict[str, Any],
    *,
    min_cov: float = 0.7,
    min_distinct_ratio: float = 0.05,
    min_distinct_count: int = 10,
    max_depth: int | None = None,
) -> list[tuple[str, dict[str, Any], float, float, set[str]]]:
    """
    Return eligible join fields for an object: (path, field, coverage, distinct_ratio, types).

    Rules (applied in order):
    - No audit / temporal / username / noise fields.
    - Only scalar leaf fields (no object/array types).
    - coverage >= min_cov, distinct_count >= min_distinct_count, distinct_ratio >= min_distinct_ratio.
    - If max_depth is set, only fields at that depth level are returned.
    """
    sampled = obj.get("sampled", 0)
    if sampled <= 0:
        return []
    result = []
    for f in obj.get("fields", []):
        path = f.get("path", "")
        # Only leaf fields — no intermediate object/array paths.
        types = set(f.get("types", {}).keys()) - {"null"}
        if not types or {"object", "array"} & types:
            continue
        if _is_join_useless(path, types):
            continue
        if max_depth is not None and _depth(path) != max_depth:
            continue
        cov = _coverage(f, sampled)
        distinct = f.get("distinct_count_in_sample", 0)
        ratio = distinct / sampled if sampled else 0.0
        if cov < min_cov or distinct < min_distinct_count or ratio < min_distinct_ratio:
            continue
        result.append((path, f, cov, ratio, types))
    return result


def find_value_confirmed_joins(
    schema_json: dict[str, Any],
    min_jaccard: float = 0.15,
    scratch: "ProfileScratch | None" = None,
    min_containment: float = 0.8,
) -> list[JoinCandidate]:
    """
    Cross-object join candidates using TWO tracks, top-level-first.

    Track A — Value Jaccard (medium/low-cardinality fields):
      Used when distinct_count_in_sample < max_distinct cap AND values genuinely repeat.
      Jaccard of stored distinct-value sets must meet min_jaccard.
      This is a hard value-confirmed signal.

    Track B — Structural compatibility (high-cardinality identifier fields):
      Used when the stored distinct count HIT the cap (i.e., real cardinality is unknown
      but ≥ cap). Values can't be meaningfully compared with a 50-value sample.
      Signal: same semantic type, similar cardinality profile, identifier-shaped name,
      high coverage.  Labelled "structural candidate" — not "value confirmed".
      Explicitly notes that users should re-run with higher --max-distinct to confirm.

    When a ProfileScratch is supplied, every field has an exact value-hash set, so
    Track A applies to high-cardinality fields too, and a pair also qualifies when
    one side's values are (row-weighted) contained in the other's — the normal
    shape of a foreign key into a larger dimension (Jaccard alone would be low).

    Scan order: top-level (depth 0) first; one level deep (depth 1) only if no
    cross-object pair is linked at depth 0.
    """
    objs = schema_json.get("objects", [])
    if len(objs) < 2:
        return []

    max_distinct = schema_json.get("config", {}).get("max_distinct_values", 50)

    def _is_capped(f: dict[str, Any], sampled: int) -> bool:
        """True if the stored distinct count likely hit the --max-distinct cap."""
        d = f.get("distinct_count_in_sample", 0)
        # If stored distinct == cap AND presence >> cap → almost certainly capped.
        return d >= max_distinct and (f.get("presence_count", 0) or sampled) > max_distinct * 2

    def _enrich_fields(obj: dict[str, Any], depth: int) -> list[dict]:
        """Build an enriched field descriptor for join analysis at a given depth."""
        sampled = obj.get("sampled", 0)
        name = obj.get("object", "Unknown")
        result = []
        for f in obj.get("fields", []):
            path = f.get("path", "")
            if _depth(path) != depth:
                continue
            types = set(f.get("types", {}).keys()) - {"null"}
            if not types or {"object", "array"} & types:
                continue
            if _is_join_useless(path, types):
                continue
            cov = _coverage(f, sampled)
            if cov < 0.6:
                continue
            distinct = f.get("distinct_count_in_sample", 0)
            ratio = distinct / sampled if sampled else 0.0
            hashed = _scratch_hashes(scratch, name, path)
            if hashed is not None:
                capped, vals = False, hashed
            else:
                capped = _is_capped(f, sampled)
                vals = None if capped else _distinct_set(f)
            result.append({
                "field": f,
                "obj": name,
                "path": path,
                "cov": cov,
                "ratio": ratio,
                "distinct": distinct,
                "types": types,
                "type_sig": _struct_type_sig(types),
                "id_bias": _identifier_bias(path),
                "capped": capped,
                "vals": vals,
                "sampled": sampled,
            })
        return result

    def _try_pairs(
        depth: int,
        already_linked: set[frozenset],
    ) -> list[JoinCandidate]:
        per_obj: dict[str, list[dict]] = {}
        for obj in objs:
            name = obj.get("object", "Unknown")
            fields = _enrich_fields(obj, depth)
            if fields:
                per_obj[name] = fields

        out: list[JoinCandidate] = []
        obj_names = list(per_obj.keys())

        for i, a_name in enumerate(obj_names):
            for b_name in obj_names[i + 1:]:
                pair_key = frozenset({a_name, b_name})
                if pair_key in already_linked:
                    continue
                best: JoinCandidate | None = None

                for af in per_obj[a_name]:
                    for bf in per_obj[b_name]:
                        if af["type_sig"] != bf["type_sig"]:
                            continue  # incompatible types

                        same_path = _path_signature(af["path"]) == _path_signature(bf["path"])
                        id_bias = max(af["id_bias"], bf["id_bias"])
                        # Small integer measures (counts, positions) overlap by accident;
                        # numeric joins need identifier-shaped names on both sides.
                        if (af["type_sig"] in ("int", "float") and not same_path
                                and min(af["id_bias"], bf["id_bias"]) <= 1.0):
                            continue

                        # Track A: value Jaccard — both uncapped, values available
                        if not af["capped"] and not bf["capped"]:
                            a_vals = af["vals"] or set()
                            b_vals = bf["vals"] or set()
                            if len(a_vals) < 5 or len(b_vals) < 5:
                                continue
                            a_keys, b_keys = set(a_vals), set(b_vals)
                            inter = a_keys & b_keys
                            if not inter:
                                continue
                            union = a_keys | b_keys
                            jaccard = len(inter) / len(union)
                            contained = max(_containment(a_vals, inter), _containment(b_vals, inter))
                            fk_shaped = contained >= min_containment and (id_bias > 1.0 or same_path)
                            if jaccard < min_jaccard and not fk_shaped:
                                continue
                            strength = max(jaccard, contained if fk_shaped else 0.0)
                            conf = min(1.0, strength * 0.7 + min(af["cov"], bf["cov"]) * 0.3)
                            if id_bias > 1.0:
                                conf = min(1.0, conf + 0.12)
                            if same_path:
                                conf = min(1.0, conf + 0.05)
                            shared = (
                                _shared_examples(af["field"], bf["field"])
                                if isinstance(a_vals, Counter)
                                else sorted(str(v) for v in list(inter)[:5])
                            )
                            ev = [
                                f"Value overlap Jaccard {jaccard:.0%} "
                                f"({len(inter)} shared / {len(union)} distinct values)",
                                f"Containment {contained:.0%} (share of the smaller side's "
                                f"occurrences found on the other side)",
                                f"Shared sample: {shared}",
                                f"Coverage {af['cov']:.0%} / {bf['cov']:.0%}",
                            ]
                            if same_path:
                                ev.append("Same field path on both sides")
                            kind = "value_confirmed_same_path" if same_path else "value_confirmed_overlap"
                            c = JoinCandidate(
                                left=f"{a_name}.{af['path']}",
                                right=f"{b_name}.{bf['path']}",
                                kind=kind,
                                confidence=conf,
                                evidence=ev,
                            )
                            if best is None or c.confidence > best.confidence:
                                best = c

                        # Track B: structural compatibility — at least one side is capped
                        elif id_bias > 1.0:
                            # Only worth reporting for identifier-shaped fields.
                            ratio_sim = 1.0 - abs(af["ratio"] - bf["ratio"])
                            conf = min(1.0,
                                       (af["cov"] + bf["cov"]) / 2 * 0.5
                                       + ratio_sim * 0.3
                                       + (0.1 if same_path else 0.0)
                                      )
                            ev = [
                                f"Structural: both fields are {af['type_sig']} "
                                f"identifiers with similar cardinality profiles",
                                f"Coverage {af['cov']:.0%} / {bf['cov']:.0%}; "
                                f"cardinality ratio {af['ratio']:.0%} / {bf['ratio']:.0%}",
                                f"⚠ Stored values capped at {max_distinct} — run with "
                                f"--max-distinct 500+ to confirm actual value overlap",
                            ]
                            if same_path:
                                ev.append("Same field path on both sides (name corroborates)")
                            kind = "structural_same_path" if same_path else "structural_overlap"
                            c = JoinCandidate(
                                left=f"{a_name}.{af['path']}",
                                right=f"{b_name}.{bf['path']}",
                                kind=kind,
                                confidence=conf,
                                evidence=ev,
                            )
                            if best is None or c.confidence > best.confidence:
                                best = c

                if best:
                    out.append(best)
                    already_linked.add(pair_key)
        return out

    already_linked: set[frozenset] = set()
    result = _try_pairs(0, already_linked)
    result += _try_pairs(1, already_linked)
    result.sort(key=lambda c: -c.confidence)
    return result[:30]


def find_nested_relationships(schema_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Within-object: collect array-parent paths with their nested children counts."""
    nested: list[dict[str, Any]] = []
    for obj in schema_json.get("objects", []):
        name = obj.get("object", "Unknown")
        sampled = obj.get("sampled", 0)
        groups: dict[str, list[dict[str, Any]]] = {}
        for f in obj.get("fields", []):
            path = f.get("path", "")
            if "[]" not in path:
                continue
            segments = path.split(".")
            parent_idx = max(i for i, s in enumerate(segments) if "[]" in s)
            parent = ".".join(segments[: parent_idx + 1])
            if parent == path:
                continue
            groups.setdefault(parent, []).append(f)
        for parent, children in groups.items():
            if not children:
                continue
            avg_cov = sum(_coverage(c, sampled) for c in children) / len(children)
            nested.append(
                {
                    "object": name,
                    "parent_path": parent,
                    "child_count": len(children),
                    "avg_coverage": round(avg_cov, 3),
                    "kind": "array_of_objects (1:N)",
                    "children": [c.get("path", "") for c in children[:8]],
                }
            )
    nested.sort(key=lambda n: (-n["child_count"], n["object"]))
    return nested


def find_intra_object_duplicates(
    schema_json: dict[str, Any],
    min_jaccard: float = 0.6,
    min_coverage: float = 0.5,
    scratch: "ProfileScratch | None" = None,
    shared_domains: list[dict[str, Any]] | None = None,
    min_row_equality: float = 0.9,
) -> list[DuplicateFieldCandidate]:
    """
    Find fields within the same object whose VALUES look nearly identical — likely duplicates.

    Track A — Value confirmed (uncapped fields): Jaccard of stored distinct values >= min_jaccard.
    Track B — Structural (both capped, same type, same identifier category): similar cardinality
              profiles with both fields being identifier-shaped.

    Audit, temporal, and noise fields are excluded.
    Only returns pairs where coverage on both sides is >= min_coverage.

    With a ProfileScratch, value-overlapping pairs are also checked row by row on
    the in-memory row sample: two fields are only duplicates when they hold the
    *same value in the same row* (>= min_row_equality). Fields that share a value
    set but differ per row (e.g. batter_id vs non_striker_id — two roles pointing
    at the same entity) are appended to `shared_domains` instead.
    """
    max_distinct = schema_json.get("config", {}).get("max_distinct_values", 50)
    results: list[DuplicateFieldCandidate] = []

    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "Unknown")
        sampled = obj.get("sampled", 0)
        if sampled <= 0:
            continue

        # Build eligible field list: scalar, non-audit, sufficient coverage
        eligible = []
        for f in obj.get("fields", []):
            path = f.get("path", "")
            types = set(f.get("types", {}).keys()) - {"null"}
            if not types or {"object", "array"} & types:
                continue
            if _is_audit_field(path, types):
                continue
            cov = _coverage(f, sampled)
            if cov < min_coverage:
                continue
            distinct = f.get("distinct_count_in_sample", 0)
            hashed = _scratch_hashes(scratch, obj_name, path)
            if hashed is not None:
                capped, vals = False, set(hashed)
            else:
                capped = (distinct >= max_distinct and
                          (f.get("presence_count", 0) or sampled) > max_distinct * 2)
                vals = None if capped else _distinct_set(f)
            eligible.append({
                "field": f,
                "path": path,
                "types": types,
                "type_sig": _struct_type_sig(types),
                "cov": cov,
                "distinct": distinct,
                "ratio": distinct / sampled if sampled else 0.0,
                "capped": capped,
                "vals": vals,
            })

        for i, af in enumerate(eligible):
            for bf in eligible[i + 1:]:
                # Skip structurally identical paths (array traversal variants)
                if af["path"].replace("[]", "") == bf["path"].replace("[]", ""):
                    continue
                # Must share at least one type
                if af["type_sig"] != bf["type_sig"]:
                    continue

                # Track A: value Jaccard (both uncapped)
                if not af["capped"] and not bf["capped"]:
                    a_v = af["vals"] or set()
                    b_v = bf["vals"] or set()
                    if len(a_v) < 3 or len(b_v) < 3:
                        continue
                    inter = a_v & b_v
                    if not inter:
                        continue
                    union = a_v | b_v
                    jaccard = len(inter) / len(union)
                    if jaccard < min_jaccard:
                        continue
                    conf = min(1.0, jaccard * 0.8 + min(af["cov"], bf["cov"]) * 0.2)
                    shared_sample = (
                        _shared_examples(af["field"], bf["field"])
                        if scratch is not None
                        else sorted(str(v) for v in list(inter)[:5])
                    )
                    ev = [
                        f"Value Jaccard {jaccard:.0%} ({len(inter)} shared / {len(union)} union)",
                        f"Shared sample: {shared_sample}",
                        f"Coverage: {af['cov']:.0%} (a) vs {bf['cov']:.0%} (b)",
                    ]
                    rows = scratch.rows.get(obj_name) if scratch is not None else None
                    if rows and "[]" not in af["path"] + bf["path"]:
                        both = equal = 0
                        for rec in rows:
                            va, vb = _get_path(rec, af["path"]), _get_path(rec, bf["path"])
                            if va is None or vb is None:
                                continue
                            both += 1
                            equal += va == vb
                        if both:
                            row_eq = equal / both
                            if row_eq < min_row_equality:
                                numeric = af["type_sig"] in ("int", "float")
                                id_like = min(_identifier_bias(af["path"]), _identifier_bias(bf["path"])) > 1.0
                                if shared_domains is not None and (id_like or not numeric):
                                    shared_domains.append({
                                        "object": obj_name,
                                        "field_a": af["path"],
                                        "field_b": bf["path"],
                                        "jaccard": round(jaccard, 3),
                                        "row_equality": round(row_eq, 3),
                                        "note": (
                                            "Same set of values but different per row — likely two "
                                            "roles referencing the same entity, not a duplicate."
                                        ),
                                    })
                                continue
                            ev.append(f"Same value in the same row for {row_eq:.0%} of {both} rows checked")
                            conf = min(1.0, conf * 0.5 + row_eq * 0.5)
                    kind = "value_duplicate"
                    jaccard_val = jaccard

                # Track B: structural duplicate (both capped, identifier-shaped)
                elif af["capped"] and bf["capped"]:
                    ia = _identifier_bias(af["path"])
                    ib = _identifier_bias(bf["path"])
                    if ia <= 1.0 or ib <= 1.0:
                        continue  # both must be identifier-shaped to flag as structural duplicate
                    ratio_sim = 1.0 - abs(af["ratio"] - bf["ratio"])
                    conf = min(1.0,
                               (af["cov"] + bf["cov"]) / 2 * 0.6
                               + ratio_sim * 0.3
                               + max(ia, ib) * 0.05)
                    if conf < 0.5:
                        continue
                    ev = [
                        f"Structural: both are high-cardinality {af['type_sig']} identifier fields",
                        f"Cardinality profiles {af['ratio']:.0%} / {bf['ratio']:.0%} "
                        f"(ratio similarity {ratio_sim:.0%})",
                        f"⚠ Run with --max-distinct 500+ to value-confirm overlap",
                    ]
                    kind = "structural_duplicate"
                    jaccard_val = 0.0
                else:
                    continue

                # Recommend field with better effective coverage
                if af["cov"] >= bf["cov"] + 0.05:
                    rec = "a"
                elif bf["cov"] >= af["cov"] + 0.05:
                    rec = "b"
                else:
                    rec = "either"

                results.append(DuplicateFieldCandidate(
                    object_name=obj_name,
                    field_a=af["path"],
                    field_b=bf["path"],
                    jaccard=jaccard_val,
                    confidence=conf,
                    coverage_a=af["cov"],
                    coverage_b=bf["cov"],
                    recommend=rec,
                    evidence=ev,
                    kind=kind,
                ))

    results.sort(key=lambda d: -d.confidence)
    return results


def _struct_type_sig(types: set[str]) -> str:
    """Coarse semantic type bucket for structural comparison."""
    for t in ("uuid", "numeric_id", "email", "url", "date"):
        if t in types:
            return t
    if "int" in types:
        return "int"
    if "float" in types:
        return "float"
    if "string" in types:
        return "string"
    return str(sorted(types))


def find_referential_integrity(
    schema_json: dict[str, Any],
    primary_keys: list[PrimaryKeyCandidate],
    scratch: "ProfileScratch | None",
    min_containment: float = 0.5,
) -> list[dict[str, Any]]:
    """
    Foreign-key → primary-key links with their orphan rate.

    For every single-field primary key (the parent) and every scalar field in
    another object with a compatible type (the child), measure how many of the
    child's occurrences resolve to a parent key. A child qualifies as a foreign
    key when at least `min_containment` of its occurrences resolve; everything
    that doesn't resolve is an orphan (a reference to a row that doesn't exist).

    Needs exact value hashes (ProfileScratch); returns [] without them.
    Numeric children must also have an identifier-shaped name, so a small
    integer measure (e.g. quantity 1..10) isn't mistaken for a reference into
    an integer id range.
    """
    if scratch is None:
        return []
    objs = {o.get("object", ""): o for o in schema_json.get("objects", [])}

    # Parents: every top-level field that is unique per row (not only the chosen
    # primary key) — an object can carry several unique keys (internal id,
    # external code), and the one other objects reference is the one that matters.
    parents = []
    for obj_name, obj in objs.items():
        sampled = obj.get("sampled", 0)
        for f in obj.get("fields", []):
            path = f.get("path", "")
            if "." in path or "[]" in path or not sampled:
                continue
            ptypes = set(f.get("types", {})) - {"null"}
            if not ptypes or {"object", "array"} & ptypes:
                continue
            if _coverage(f, sampled) < 0.95 or f.get("distinct_count_in_sample", 0) / sampled < 0.95:
                continue
            keys = _scratch_hashes(scratch, obj_name, path)
            if keys:
                parents.append((obj_name, path, set(keys), _struct_type_sig(ptypes)))

    links: list[dict[str, Any]] = []
    for obj_name, obj in objs.items():
        for f in obj.get("fields", []):
            path = f.get("path", "")
            types = set(f.get("types", {}).keys()) - {"null"}
            if not types or {"object", "array"} & types or _is_audit_field(path, types):
                continue
            child = _scratch_hashes(scratch, obj_name, path)
            if not child or len(child) < 3:
                continue
            sig = _struct_type_sig(types)
            if sig in ("int", "float") and _identifier_bias(path) <= 1.0:
                continue
            best = None
            for p_obj, p_path, p_keys, p_sig in parents:
                if p_obj == obj_name or p_sig != sig:
                    continue
                shared = set(child) & p_keys
                if len(shared) < min(10, max(2, len(p_keys) // 2)):
                    continue
                contained = _containment(child, shared)
                if contained < min_containment:
                    continue
                if best is None or contained > best[0]:
                    best = (contained, p_obj, p_path, shared)
            if best is None:
                continue
            contained, p_obj, p_path, shared = best
            total = sum(child.values())
            links.append({
                "child": f"{obj_name}.{path}",
                "parent": f"{p_obj}.{p_path}",
                "child_occurrences": total,
                "orphan_occurrences": total - sum(child[h] for h in shared),
                "orphan_distinct": len(child) - len(shared),
                "orphan_pct": round((1 - contained) * 100, 2),
                "resolved_pct": round(contained * 100, 2),
            })
    links.sort(key=lambda x: (-x["orphan_pct"], x["child"]))
    return links


def _prefer_referenced_keys(
    pks: list[PrimaryKeyCandidate], integrity: list[dict[str, Any]]
) -> list[PrimaryKeyCandidate]:
    """When several fields are unique, prefer the one other objects actually reference."""
    refs: dict[tuple[str, str], int] = {}
    for link in integrity:
        obj, _, path = link["parent"].partition(".")
        refs[(obj, path)] = refs.get((obj, path), 0) + 1
    out = []
    for pk in pks:
        best = max(
            ((path, n) for (obj, path), n in refs.items() if obj == pk.object_name),
            key=lambda item: item[1],
            default=None,
        )
        current = refs.get((pk.object_name, pk.fields[0]), 0) if len(pk.fields) == 1 else 0
        if best and best[0] not in pk.fields and best[1] > current:
            pk = PrimaryKeyCandidate(
                object_name=pk.object_name,
                fields=[best[0]],
                coverage=1.0,
                distinct_ratio=1.0,
                rationale=(
                    f"`{best[0]}` is unique per row and is referenced by {best[1]} field(s) in "
                    f"other objects — the key the rest of the data joins on."
                ),
            )
        out.append(pk)
    return out


def analyze_joins(
    schema_json: dict[str, Any],
    scratch: "ProfileScratch | None" = None,
) -> dict[str, Any]:
    """Top-level orchestration of all join/key inference."""
    pks = infer_primary_keys(schema_json)
    value_joins = find_value_confirmed_joins(schema_json, scratch=scratch)
    nested = find_nested_relationships(schema_json)
    shared_domains: list[dict[str, Any]] = []
    duplicates = find_intra_object_duplicates(
        schema_json, scratch=scratch, shared_domains=shared_domains,
    )
    integrity = find_referential_integrity(schema_json, pks, scratch)
    pks = _prefer_referenced_keys(pks, integrity)
    # Split by kind for backward-compat keys consumed by the HTML renderer.
    same_path = [c for c in value_joins if c.kind == "value_confirmed_same_path"]
    overlap = [c for c in value_joins if c.kind == "value_confirmed_overlap"]
    return {
        "primary_keys": [p.to_dict() for p in pks],
        "same_path_fk": [c.to_dict() for c in same_path],
        "value_overlap": [c.to_dict() for c in overlap],
        "all_value_joins": [c.to_dict() for c in value_joins],
        "intra_duplicates": [d.to_dict() for d in duplicates],
        "shared_domains": shared_domains,
        "referential_integrity": integrity,
        "nested_relationships": nested,
        "totals": {
            "primary_keys": len(pks),
            "value_confirmed_joins": len(value_joins),
            "intra_duplicates": len(duplicates),
            "nested_relationships": len(nested),
            "foreign_keys": len(integrity),
            "orphaned_links": sum(1 for link in integrity if link["orphan_occurrences"]),
        },
    }
