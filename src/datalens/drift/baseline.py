"""
Rolling baseline — each metric learns its own normal range from recent runs.

For a metric x observed in the last N runs (x₁ … x_N, oldest runs drop out as
new ones arrive — the baseline is *auto-incremental*):

    M      = median(x₁ … x_N)                      typical value
    MAD    = median(|xᵢ − M|)                      typical deviation
    σ̂      = 1.4826 · MAD                          robust standard deviation
                                                   (equals σ for normal data, but
                                                   one outlier run can't inflate it)
    floor  = max(abs_floor, rel_floor · |M|)       minimum band half-width, so a
                                                   metric that never moved doesn't
                                                   alert on the tiniest change
    band   = [ min(M − k·σ̂ₑ, min(x)·(1 − rel_floor)),
               max(M + k·σ̂ₑ, max(x)·(1 + rel_floor)) ]
                                                   σ̂ₑ = max(σ̂, floor), k = 3 by default;
                                                   the band always covers every value
                                                   seen in the window (that didn't
                                                   breach), so recurring patterns —
                                                   e.g. a double-header every few
                                                   days — are learned as normal
    z      = (x_today − M) / σ̂ₑ                    how far from typical, in robust sigmas

Today's value alerts only when it falls outside the band: "fail" when it is
also more than k robust sigmas from typical; otherwise "warn" (outside the
range seen so far, but not extreme).

Learning safeguards:
- Cold start: with fewer than ``min_history`` past values the band isn't
  trusted and static threshold rules are used instead (the report says so).
- ``exclude_breaches``: a value that breached in its own run is left out of
  future baselines, so a bad day can't teach the baseline that bad is normal.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

MAD_TO_SIGMA = 1.4826


@dataclass
class Band:
    median: float
    sigma: float          # robust sigma actually used (after floor)
    lower: float
    upper: float
    n: int                # history values the band was learned from
    values: list[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "median": round(self.median, 4),
            "sigma": round(self.sigma, 4),
            "lower": round(self.lower, 4),
            "upper": round(self.upper, 4),
            "n": self.n,
        }


def learn_band(
    values: list[float],
    *,
    k: float = 3.0,
    abs_floor: float = 0.0,
    rel_floor: float = 0.02,
) -> Band | None:
    """Robust band from past values (None when there are no values)."""
    if not values:
        return None
    m = median(values)
    mad = median(abs(v - m) for v in values)
    sigma = max(MAD_TO_SIGMA * mad, abs_floor, rel_floor * abs(m))
    if sigma == 0:
        sigma = 1e-9
    lo_seen, hi_seen = min(values), max(values)
    lower = min(m - k * sigma, lo_seen - rel_floor * abs(lo_seen))
    upper = max(m + k * sigma, hi_seen + rel_floor * abs(hi_seen))
    return Band(m, sigma, lower, upper, len(values), list(values))


def score_against_band(value: float, band: Band, k: float = 3.0) -> tuple[str, float]:
    """(severity, robust z) of today's value against a learned band."""
    z = (value - band.median) / band.sigma
    if band.lower <= value <= band.upper:
        return "ok", z
    return ("fail" if abs(z) > k else "warn"), z


def history_values(
    history: list[dict[str, Any]],
    key: str,
    *,
    window: int,
    exclude_breaches: bool = True,
) -> list[float]:
    """Values of one metric across the most recent `window` runs (newest first input)."""
    values: list[float] = []
    for run in history:
        if len(values) >= window:
            break
        metrics = run.get("metrics") or {}
        if key not in metrics:
            continue
        if exclude_breaches and key in set(run.get("breached") or []):
            continue
        values.append(float(metrics[key]))
    return values
