"""
Relationships — detect field relationships and potential foreign keys.

STRATEGY (value-first, name-last):
  All join candidates MUST be confirmed by actual value overlap (Jaccard similarity
  of sampled distinct value sets). Field-name similarity alone is never sufficient.

  Excluded unconditionally:
  - Audit / temporal fields (created*, updated*, modified*, timestamp, …)
  - Username / person-name fields (email, login, author, …)
  - Low-information status/flag/type fields

  Scan order (top-level scalars first, then one level deep):
  1. High-cardinality value-overlap joins between different objects.
  2. Low-cardinality shared-enum fields (same small value set, e.g. status codes).
  3. Self-referential hierarchy fields (parent_id style within one object).

  Note: naming-convention-only detection ("user_id looks like it references users")
  has been intentionally removed — it generates too many false positives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from datalens.profiling.joins import (
    _coverage,
    _distinct_set,
    _is_audit_field,
    _is_join_useless,
    _identifier_bias,
    _depth,
)


@dataclass
class RelationshipCandidate:
    """A potential relationship between two fields."""

    source_object: str
    source_field: str
    target_object: str
    target_field: str
    relationship_type: str  # "value_join", "shared_enum", "hierarchy"
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": f"{self.source_object}.{self.source_field}",
            "target": f"{self.target_object}.{self.target_field}",
            "type": self.relationship_type,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class ObjectRelationships:
    object_name: str
    outgoing: list[RelationshipCandidate] = field(default_factory=list)
    incoming: list[RelationshipCandidate] = field(default_factory=list)


def _scalar_fields(
    obj: dict[str, Any],
    *,
    max_depth: int | None = None,
    min_cov: float = 0.0,
) -> list[tuple[str, dict[str, Any]]]:
    """Return (path, field) for scalar leaf fields, optionally filtered by depth."""
    sampled = obj.get("sampled", 0)
    result = []
    for f in obj.get("fields", []):
        path = f.get("path", "")
        types = set(f.get("types", {}).keys()) - {"null"}
        if not types or {"object", "array"} & types:
            continue
        if max_depth is not None and _depth(path) != max_depth:
            continue
        if min_cov > 0 and sampled > 0:
            if _coverage(f, sampled) < min_cov:
                continue
        result.append((path, f))
    return result


def detect_value_joins(
    schema_json: dict[str, Any],
    min_jaccard: float = 0.15,
    max_depth_scan: int = 1,
) -> list[RelationshipCandidate]:
    """
    Detect cross-object joins using value Jaccard (where possible) with structural
    fallback for high-cardinality capped fields.  Delegates to joins.py logic.
    """
    # Import here to avoid circular at module load time.
    from datalens.profiling.joins import find_value_confirmed_joins, JoinCandidate

    raw: list[JoinCandidate] = find_value_confirmed_joins(schema_json, min_jaccard)
    results = []
    for jc in raw:
        src_obj, src_fld = jc.left.split(".", 1)
        tgt_obj, tgt_fld = jc.right.split(".", 1)
        rel_type = "value_join" if "value_confirmed" in jc.kind else "structural_candidate"
        results.append(
            RelationshipCandidate(
                source_object=src_obj,
                source_field=src_fld,
                target_object=tgt_obj,
                target_field=tgt_fld,
                relationship_type=rel_type,
                confidence=jc.confidence,
                evidence=jc.evidence,
            )
        )
    return results


def detect_shared_enums(
    schema_json: dict[str, Any],
    min_jaccard: float = 0.6,
) -> list[RelationshipCandidate]:
    """
    Detect shared low-cardinality enum/reference fields (e.g. country codes, genres).

    Only looks at fields with <= 50 distinct values.
    Excludes audit, temporal, and identity fields.
    """
    objs = schema_json.get("objects", [])
    enum_fields: list[tuple[str, str, set]] = []

    for obj in objs:
        name = obj.get("object", "Unknown")
        sampled = obj.get("sampled", 0)
        for path, f in _scalar_fields(obj, min_cov=0.5):
            types = set(f.get("types", {}).keys()) - {"null"}
            if _is_join_useless(path, types):
                continue
            # Skip high-identity fields — they're join keys, not enums.
            if _identifier_bias(path) > 1.0:
                continue
            distinct = f.get("distinct_count_in_sample", 0)
            if distinct < 2 or distinct > 50:
                continue
            vals = _distinct_set(f)
            if len(vals) >= 2:
                enum_fields.append((name, path, vals))

    results: list[RelationshipCandidate] = []
    seen: set[frozenset] = set()
    for i, (obj1, path1, vals1) in enumerate(enum_fields):
        for obj2, path2, vals2 in enum_fields[i + 1:]:
            if obj1 == obj2:
                continue
            key = frozenset({f"{obj1}.{path1}", f"{obj2}.{path2}"})
            if key in seen:
                continue
            inter = vals1 & vals2
            union = vals1 | vals2
            if not union:
                continue
            jaccard = len(inter) / len(union)
            if jaccard < min_jaccard:
                continue
            seen.add(key)
            shared = sorted(str(v) for v in list(inter)[:8])
            results.append(
                RelationshipCandidate(
                    source_object=obj1,
                    source_field=path1,
                    target_object=obj2,
                    target_field=path2,
                    relationship_type="shared_enum",
                    confidence=round(jaccard, 2),
                    evidence=[
                        f"Shared enum values Jaccard {jaccard:.0%}",
                        f"Shared: {shared}",
                    ],
                )
            )
    return results


def detect_hierarchy(
    schema_json: dict[str, Any],
) -> list[RelationshipCandidate]:
    """Detect self-referential parent/child fields within a single object."""
    results: list[RelationshipCandidate] = []
    for obj in schema_json.get("objects", []):
        obj_name = obj.get("object", "Unknown")
        for path, f in _scalar_fields(obj):
            leaf = path.split(".")[-1].lower()
            if "parent" in leaf and ("id" in leaf or "key" in leaf or leaf == "parent"):
                results.append(
                    RelationshipCandidate(
                        source_object=obj_name,
                        source_field=path,
                        target_object=obj_name,
                        target_field="_id",
                        relationship_type="hierarchy",
                        confidence=0.80,
                        evidence=["Self-referential parent field detected"],
                    )
                )
    return results


def detect_relationships_by_naming(
    schema_json: dict[str, Any],
) -> list[RelationshipCandidate]:
    """
    Infer foreign-key relationships by name convention (domain-agnostic).

    A scalar field whose leaf name looks like ``<entity>_id`` / ``<entity>Id``
    is treated as a foreign key into an object named ``<entity>`` (singular or
    plural). This is a name-similarity heuristic — no value confirmation and no
    baked-in vocabulary — complementary to the value-based join detection.

    Returns ``RelationshipCandidate``s with ``relationship_type == "foreign_key"``.
    """
    objects = schema_json.get("objects", [])
    # Map normalized object name → (object_name, preferred target id field).
    name_index: dict[str, tuple[str, str]] = {}
    for obj in objects:
        obj_name = obj.get("object", "Unknown")
        id_field = "_id"
        for f in obj.get("fields", []):
            leaf = f.get("path", "").split(".")[-1].lower()
            if leaf in ("_id", "id"):
                id_field = f.get("path", "_id")
                break
        for key in {obj_name.lower(), obj_name.lower().rstrip("s")}:
            name_index.setdefault(key, (obj_name, id_field))

    results: list[RelationshipCandidate] = []
    for obj in objects:
        obj_name = obj.get("object", "Unknown")
        for path, _f in _scalar_fields(obj):
            leaf = path.split(".")[-1].lower()
            # Strip an id suffix to recover the referenced entity stem.
            if leaf in ("_id", "id"):
                continue  # this is a primary key, not a foreign key
            if leaf.endswith("_id"):
                stem = leaf[:-3]
            elif leaf.endswith("id") and len(leaf) > 2:
                stem = leaf[:-2]
            else:
                continue
            stem = stem.strip("_")
            if not stem:
                continue

            target = name_index.get(stem) or name_index.get(stem + "s")
            if not target:
                continue
            target_object, target_field = target
            if target_object == obj_name:
                continue  # self-reference is handled by hierarchy detection

            results.append(
                RelationshipCandidate(
                    source_object=obj_name,
                    source_field=path,
                    target_object=target_object,
                    target_field=target_field,
                    relationship_type="foreign_key",
                    confidence=0.7,
                    evidence=[f"Field name `{leaf}` references object `{target_object}` by convention"],
                )
            )
    return results


def analyze_relationships(schema_json: dict[str, Any]) -> dict[str, Any]:
    """
    Perform value-confirmed relationship analysis.

    Returns a dict compatible with the HTML report renderer.
    """
    value_joins = detect_value_joins(schema_json)
    enum_rels = detect_shared_enums(schema_json)
    hierarchy_rels = detect_hierarchy(schema_json)

    all_rels = value_joins + enum_rels + hierarchy_rels
    all_rels.sort(key=lambda r: -r.confidence)

    by_object: dict[str, ObjectRelationships] = {
        obj.get("object", "Unknown"): ObjectRelationships(object_name=obj.get("object", "Unknown"))
        for obj in schema_json.get("objects", [])
    }
    for rel in all_rels:
        if rel.source_object in by_object:
            by_object[rel.source_object].outgoing.append(rel)
        if rel.target_object in by_object:
            by_object[rel.target_object].incoming.append(rel)

    return {
        "total_relationships": len(all_rels),
        "by_type": {
            "value_join": len([r for r in all_rels if r.relationship_type == "value_join"]),
            "structural_candidate": len([r for r in all_rels if r.relationship_type == "structural_candidate"]),
            "shared_enum": len(enum_rels),
            "hierarchy": len(hierarchy_rels),
        },
        "relationships": [r.to_dict() for r in all_rels],
        "by_object": {
            name: {
                "outgoing": [r.to_dict() for r in obj_rels.outgoing],
                "incoming": [r.to_dict() for r in obj_rels.incoming],
            }
            for name, obj_rels in by_object.items()
        },
    }


def generate_relationship_graph(relationships: list[RelationshipCandidate]) -> str:
    """Generate a Mermaid diagram of relationships."""
    lines = ["graph LR"]
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()


def generate_relationship_graph(relationships: list[RelationshipCandidate]) -> str:
    """
    Generate a Mermaid diagram of relationships.

    Returns:
        Mermaid markdown syntax for the relationship graph.
    """
    lines = ["graph LR"]
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()

    for rel in relationships:
        src = rel.source_object.replace(" ", "_")
        tgt = rel.target_object.replace(" ", "_")

        if src not in seen_nodes:
            lines.append(f"    {src}[{rel.source_object}]")
            seen_nodes.add(src)

        if tgt not in seen_nodes:
            lines.append(f"    {tgt}[{rel.target_object}]")
            seen_nodes.add(tgt)

        edge_key = f"{src}->{tgt}"
        if edge_key not in seen_edges:
            if rel.relationship_type == "foreign_key":
                lines.append(f"    {src} -->|FK| {tgt}")
            elif rel.relationship_type == "hierarchy":
                lines.append(f"    {src} -.->|parent| {tgt}")
            else:
                lines.append(f"    {src} -.-> {tgt}")
            seen_edges.add(edge_key)

    return "\n".join(lines)
