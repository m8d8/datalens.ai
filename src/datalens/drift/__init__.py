"""
Drift detection: configurable rules, a learned rolling baseline, and one report.

- ``rules``    — threshold rules per dataset / object / field (drop vs increase)
- ``metrics``  — flat per-run metrics and PSI distribution math
- ``baseline`` — robust rolling band (median ± k·1.4826·MAD)
- ``engine``   — builds the drift report with an explanation for every finding
"""

from datalens.drift.engine import build_drift_report
from datalens.drift.metrics import extract_metrics
from datalens.drift.rules import BUILTIN_DEFAULTS, DriftRules

__all__ = ["BUILTIN_DEFAULTS", "DriftRules", "build_drift_report", "extract_metrics"]
