"""
Profiling — source-agnostic schema analysis and data profiling.

This layer consumes records from any Connector and produces the
standardized field-statistics JSON contract.

Modules:
- sampler: Core profiling engine
- types: Type inference
- pii: PII detection and masking
- quality: Data Quality Index (DQI)
- statistics: Numeric and temporal statistics
- relationships: Field relationship detection
"""

from datalens.profiling.sampler import profile_source
from datalens.profiling.types import infer_type, is_empty_value
from datalens.profiling.pii import detect_pii_in_schema, get_pii_summary, PIIType
from datalens.profiling.quality import compute_schema_quality, get_quality_grade
from datalens.profiling.statistics import compute_statistics_summary
from datalens.profiling.relationships import analyze_relationships

__all__ = [
    # Core profiling
    "profile_source",
    "infer_type",
    "is_empty_value",
    # PII
    "detect_pii_in_schema",
    "get_pii_summary",
    "PIIType",
    # Quality
    "compute_schema_quality",
    "get_quality_grade",
    # Statistics
    "compute_statistics_summary",
    # Relationships
    "analyze_relationships",
]
