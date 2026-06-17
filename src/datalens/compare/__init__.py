"""
Deep schema comparison — compare two independent schemas side-by-side.

Supports both metadata mode (fast, structure/coverage/cardinality) and
deep mode (slower, with value sampling and overlap analysis).

Record-level comparison — detect data-level changes for matching records.
"""

from datalens.compare.deep_diff import (
    PathComparison,
    DeepSchemaDiff,
    compare_deep_schemas,
)
from datalens.compare.record_comparison import (
    RecordChange,
    RecordDiff,
    RecordDiffSummary,
    compare_records,
    load_records_from_source,
)

__all__ = [
    "PathComparison",
    "DeepSchemaDiff",
    "compare_deep_schemas",
    "RecordChange",
    "RecordDiff",
    "RecordDiffSummary",
    "compare_records",
    "load_records_from_source",
]
