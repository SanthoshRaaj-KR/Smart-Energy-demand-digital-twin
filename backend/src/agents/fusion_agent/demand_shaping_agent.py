"""
demand_shaping_agent.py
=======================
Specialized demand-side shaping to avoid overstressing the grid in fallback mode.
"""

from __future__ import annotations


class DemandShapingAgent:
    """Transforms raw intelligence multipliers into operational demand factors."""

    _RISK_CAP = {
        "LOW": 1.10,
        "MEDIUM": 1.14,
        "HIGH": 1.18,
        "CRITICAL": 1.22,
    }

    def __init__(self, blend: float = 0.60) -> None:
        self._blend = blend

    def effective_edm(self, raw_edm: float, demand_risk: str) -> float:
        blended = 1.0 + (raw_edm - 1.0) * self._blend
        cap = self._RISK_CAP.get((demand_risk or "LOW").upper(), 1.14)
        return max(0.85, min(blended, cap))

    @staticmethod
    def thermal_factor(anomaly_c: float) -> float:
        # Conservative hourly sensitivity: +0.6% demand per +1C anomaly.
        return 1.0 + max(anomaly_c, 0.0) * 0.006
