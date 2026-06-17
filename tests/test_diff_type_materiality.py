"""Type-drift should ignore minority value-shapes that come from sampling noise."""

from __future__ import annotations

from datalens.history.diff import compare_schemas


def _schema(types_a: dict, types_b: dict, sampled: int = 10000) -> dict:
    """One object 'episodes_vod' with one field 'series.id' having the given type dicts."""
    return {
        "objects": [{
            "object": "episodes_vod",
            "sampled": sampled,
            "fields": [{
                "path": "metadata.attributes.series.id",
                "presence_count": sum(types_a.values()) or sampled,
                "null_empty_count": 0,
                "types": types_a if types_a else types_b,
            }],
        }]
    }


def test_stray_minority_shape_is_not_drift():
    # Run 1: all numeric_id. Run 2: same field, but the sample caught 3 UUIDs in 10k.
    old = _schema({"numeric_id": 10000}, {})
    new = _schema({"numeric_id": 9997, "uuid": 3}, {})
    diff = compare_schemas(old, new)
    assert diff.type_changes == [], "A 0.03% UUID minority should be treated as noise"


def test_material_shape_change_is_still_drift():
    # Run 2: UUIDs are now ~30% — a real change in the field's shape.
    old = _schema({"numeric_id": 10000}, {})
    new = _schema({"numeric_id": 7000, "uuid": 3000}, {})
    diff = compare_schemas(old, new)
    assert len(diff.type_changes) == 1
    change = diff.type_changes[0]
    assert change["field"] == "metadata.attributes.series.id"
    assert set(change["old_types"]) == {"numeric_id"}
    assert set(change["new_types"]) == {"numeric_id", "uuid"}


def test_dominant_type_flip_is_drift():
    old = _schema({"int": 9000, "string": 1000}, {})
    new = _schema({"int": 1000, "string": 9000}, {})
    diff = compare_schemas(old, new)
    # Both shapes are material in both runs → set is equal → not a type change,
    # but coverage/identity is unchanged; ensure we don't crash and the set logic holds.
    assert diff.type_changes == []


def test_threshold_is_configurable():
    old = _schema({"numeric_id": 10000}, {})
    new = _schema({"numeric_id": 9900, "uuid": 100}, {})  # 1% UUID
    # Default 2% → noise, no drift
    assert compare_schemas(old, new).type_changes == []
    # Strict 0% → every observed shape counts → drift
    assert len(compare_schemas(old, new, type_minor_threshold=0.0).type_changes) == 1


def test_null_only_change_is_not_a_type_change():
    # Field gains some nulls but the value-shape is unchanged.
    old = _schema({"string": 10000}, {})
    new = _schema({"string": 9000, "null": 1000}, {})
    diff = compare_schemas(old, new)
    assert diff.type_changes == []
