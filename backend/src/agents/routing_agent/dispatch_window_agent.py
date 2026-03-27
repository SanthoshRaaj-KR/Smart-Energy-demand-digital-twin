"""
dispatch_window_agent.py
========================
Specialized agent that decides whether current hour is good for dispatch.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .path_climate_agent import PathClimateAgent


class DispatchWindowAgent:
    """
    Prefers cooler hours for routing to reduce thermal losses / stress.
    """

    def __init__(self, climate_agent: PathClimateAgent, preferred_hours_per_day: int = 8):
        self._climate = climate_agent
        self._preferred_hours_per_day = preferred_hours_per_day

    def should_dispatch_now(
        self,
        candidate_paths: List[Any],
        hour_index: int,
        city_contexts: Dict[str, Dict[str, Any]],
        buyer_risk: str,
    ) -> bool:
        risk = (buyer_risk or "").upper()
        if risk in {"HIGH", "CRITICAL"}:
            return True

        if not candidate_paths:
            return False

        day_start = (hour_index // 24) * 24
        hour_of_day = hour_index % 24

        avg_temp_by_hour: List[tuple[int, float]] = []
        for h in range(day_start, day_start + 24):
            path_temps = [
                self._climate.path_temp_c(path, h, city_contexts)
                for path in candidate_paths
            ]
            avg_temp = sum(path_temps) / max(len(path_temps), 1)
            avg_temp_by_hour.append((h % 24, avg_temp))

        ranked = sorted(avg_temp_by_hour, key=lambda x: x[1])
        preferred = {h for h, _ in ranked[: self._preferred_hours_per_day]}
        return hour_of_day in preferred

    def best_dispatch_hour(
        self,
        candidate_paths: List[Any],
        day_index: int,
        city_contexts: Dict[str, Dict[str, Any]],
        buyer_risk: str,
    ) -> int:
        """
        Choose best hour for dispatch for a given day.
        High/critical risk selects earliest safe hour; otherwise coolest hour.
        """
        if not candidate_paths:
            return day_index * 24

        day_start = day_index * 24
        hourly_scores: List[tuple[int, float]] = []
        for h in range(day_start, day_start + 24):
            path_temps = [self._climate.path_temp_c(path, h, city_contexts) for path in candidate_paths]
            avg_temp = sum(path_temps) / max(len(path_temps), 1)
            hourly_scores.append((h, avg_temp))

        risk = (buyer_risk or "").upper()
        if risk in {"HIGH", "CRITICAL"}:
            ranked = sorted(hourly_scores, key=lambda x: x[1])
            shortlist = sorted(ranked[: max(self._preferred_hours_per_day, 1)], key=lambda x: x[0])
            return shortlist[0][0]

        return min(hourly_scores, key=lambda x: x[1])[0]
