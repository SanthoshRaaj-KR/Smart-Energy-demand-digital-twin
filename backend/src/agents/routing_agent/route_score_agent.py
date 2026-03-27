"""
route_score_agent.py
====================
Specialized agent for route scoring at a given hour.
"""

from __future__ import annotations

from typing import Any


class RouteScoreAgent:
    """
    Lower score is better.
    """

    def score(
        self,
        path: Any,
        path_temp_c: float,
        carbon_tax: float,
    ) -> float:
        path_cost = float(path.total_cost())
        thermal_penalty = max(path_temp_c - 25.0, 0.0) * 0.05
        congestion_penalty = max(0.0, 1.0 - (float(path.bottleneck_capacity) / 4000.0))
        return path_cost + carbon_tax + thermal_penalty + congestion_penalty
