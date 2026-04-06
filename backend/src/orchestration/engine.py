"""
Two-tier orchestration engine (Stage 1..4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class DayOrchestrationSummary:
    day_index: int
    llm_agents_enabled: bool
    anomaly_detected: bool
    max_state_imbalance_mw: float
    estimated_baseline_cost: float
    estimated_llm_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_index": self.day_index,
            "llm_agents_enabled": self.llm_agents_enabled,
            "anomaly_detected": self.anomaly_detected,
            "max_state_imbalance_mw": self.max_state_imbalance_mw,
            "estimated_baseline_cost": self.estimated_baseline_cost,
            "estimated_llm_cost": self.estimated_llm_cost,
        }


class OrchestrationEngine:
    """
    Lightweight helper that converts baseline/intelligence signals into
    standardized day-level orchestration decisions.
    """

    def evaluate_day(
        self,
        *,
        day_index: int,
        baseline_day: Dict[str, Any] | None,
        delta_event: Dict[str, Any] | None,
        baseline_unit_cost: float = 1.0,
        llm_unit_cost: float = 10.0,
    ) -> DayOrchestrationSummary:
        llm_from_baseline = bool((baseline_day or {}).get("llm_agents_enabled", False))
        anomaly_detected = bool(delta_event)
        llm_agents_enabled = llm_from_baseline or anomaly_detected
        imbalance = float((baseline_day or {}).get("max_state_imbalance_mw", 0.0) or 0.0)

        estimated_baseline_cost = baseline_unit_cost
        estimated_llm_cost = baseline_unit_cost + (llm_unit_cost if llm_agents_enabled else 0.0)

        return DayOrchestrationSummary(
            day_index=day_index,
            llm_agents_enabled=llm_agents_enabled,
            anomaly_detected=anomaly_detected,
            max_state_imbalance_mw=imbalance,
            estimated_baseline_cost=estimated_baseline_cost,
            estimated_llm_cost=estimated_llm_cost,
        )

