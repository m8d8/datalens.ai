"""
BYOS — Bring Your Own Schema.

Drop in the JSON Schema you *expect* (draft 2020-12 / 07 keywords) and Datalens
checks every run against it, next to what it learns on its own:

    datalens analyze --path data/ --schema expected.json
    datalens analyze --path data/ --schema orders=orders.schema.json --schema users=users.schema.json
    datalens schema infer --path data/ -o expected.json      # bootstrap one from real data

Supported keywords: ``type`` (incl. ["string","null"]), ``required``,
``properties`` (nested), ``items`` (arrays), ``enum``, ``const``, ``minimum`` /
``maximum``, ``exclusiveMinimum`` / ``exclusiveMaximum``, ``pattern``,
``format`` (date, date-time, email, uri, uuid), ``additionalProperties: false``.

Thresholds live in ``x-datalens`` blocks and become drift rules for that object:

    {"x-datalens": {"defaults": {"coverage": {"change_pct": 20}}},     # generic
     "properties": {
        "id":    {"type": "string", "x-datalens": {"coverage": {"drop_pct": 5}}},
        "title": {"type": "string", "x-datalens": {"coverage": {"drop_pct": 10}}}}}

``x-datalens.min_coverage`` (default 99) is the coverage a *required* field must
reach in this run for the "required" check to pass.

One file can describe several objects with a top-level ``objects`` (or
``$defs``) map keyed by object name; a plain schema applies to every object
unless its ``title`` / ``x-datalens.object`` names one.
"""

from datalens.contract.infer import infer_schema
from datalens.contract.loader import ExpectedField, ExpectedObject, load_expected_schemas
from datalens.contract.validate import validate_contract

__all__ = ["ExpectedField", "ExpectedObject", "infer_schema", "load_expected_schemas", "validate_contract"]
