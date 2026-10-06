from datalens.profiling.insights import build_content_universe
from datalens.report.html_report import _render_content_universe


def _field(path, counts, sampled=1000, ftype="string", nulls=0, exact=True):
    return {
        "path": path, "sampled_docs": sampled, "types": {ftype: sum(counts.values()), **({"null": nulls} if nulls else {})},
        "value_counts": counts, "distinct_count_in_sample": len(counts), "distinct_is_exact": exact,
    }


def _schema(*fields, sampled=1000):
    return {"objects": [{"object": "o", "sampled": sampled, "fields": list(fields)}]}


def test_few_values_high_coverage_is_a_pie():
    u = build_content_universe(_schema(_field("Provider", {"A": 600, "B": 300, "C": 100})))
    (dim,) = u["dimensions"]
    assert dim["kind"] == "pie" and dim["distinct"] == 3 and dim["coverage_pct"] == 100.0
    assert "<path" in _render_content_universe(u)


def test_10_to_50_values_is_a_vertical_bar_chart():
    counts = {f"v{i}": 100 - i for i in range(20)}
    u = build_content_universe(_schema(_field("Genre", counts, sampled=sum(counts.values()))))
    (dim,) = u["dimensions"]
    assert dim["kind"] == "bar" and dim["segments"][0]["label"] == "v0"
    out = _render_content_universe(u)
    assert "<rect" in out and "universe-bars" in out


def test_nothing_qualifies_means_no_chart():
    low_cov = _field("Genre", {"a": 100, "b": 50}, sampled=1000)                     # 15% filled
    high_card = _field("Name", {f"n{i}": 10 for i in range(60)}, sampled=600)         # > 50 values
    near_unique = _field("Label", {f"n{i}": 1 for i in range(40)}, sampled=40)        # ~unique
    ident = _field("customer_id", {"a": 500, "b": 500})
    numeric = _field("Score", {"1": 500, "2": 500}, ftype="int")
    single = _field("Platform", {"x": 1000})
    u = build_content_universe(_schema(low_cov, high_card, near_unique, ident, numeric, single))
    assert u["dimensions"] == [] and u["segments"] == []
    assert _render_content_universe(u) == ""


def test_at_most_three_fields_and_tiny_objects_ignored():
    fields = [_field(f"f{i}", {"a": 600, "b": 400}) for i in range(5)]
    assert len(build_content_universe(_schema(*fields))["dimensions"]) == 3
    assert build_content_universe(_schema(_field("region", {"US": 15, "CA": 11}, sampled=26), sampled=26))["dimensions"] == []


def test_same_field_is_shown_for_every_object_that_has_it():
    schema = {"objects": [
        {"object": "A", "sampled": 100, "fields": [_field("Provider", {"x": 60, "y": 40}, sampled=100)]},
        {"object": "B", "sampled": 80, "fields": [_field("Provider", {"x": 80}, sampled=80)]},   # single value rides along
        {"object": "C", "sampled": 90, "fields": [_field("Provider", {"x": 20}, sampled=90)]},   # 22% filled: not shown
    ]}
    dims = build_content_universe(schema)["dimensions"]
    # combined chart first, then one per object
    assert [(d["object"], d["distinct"]) for d in dims] == [("All 2 objects combined", 2), ("A", 2), ("B", 1)]
    assert dims[0]["aggregate"] and {s["label"]: s["count"] for s in dims[0]["segments"]} == {"x": 140, "y": 40}
    out = _render_content_universe({"dimensions": dims})
    assert len(__import__("re").findall(r"universe-card( universe-agg)?\"", out)) == 3 and out.count("<h4>Provider</h4>") == 1


def test_field_present_in_every_object_outranks_a_better_looking_partial_one():
    shared = lambda: _field("Provider", {"x": 60, "y": 40}, sampled=100)   # noqa: E731
    schema = {"objects": [
        {"object": "A", "sampled": 100, "fields": [shared(), _field("Category", {"p": 50, "q": 50}, sampled=100)]},
        {"object": "B", "sampled": 100, "fields": [shared()]},
        {"object": "C", "sampled": 100, "fields": [shared()]},
    ]}
    u = build_content_universe(schema)
    assert u["dimensions"][0]["field"] == "Provider" and u["dimensions"][0]["aggregate"]
    assert u["field"] == "Provider"


def test_single_value_field_alone_is_not_shown():
    assert build_content_universe(_schema(_field("Platform", {"x": 1000})))["dimensions"] == []


def test_lists_of_ids_are_not_content():
    ids = _field("umpire_ids[]", {"a1": 600, "b2": 400})
    assert build_content_universe(_schema(ids, _field("team_ids", {"a": 500, "b": 500})))["dimensions"] == []
