"""
path_climate_agent.py
=====================
Specialized agent for climate estimation on a transmission path.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


class PathClimateAgent:
    """
    Computes path-level thermal view from per-city hourly context.
    """

    DEFAULT_BASE_TEMP_C = 30.0

    def city_temp_c(self, city_ctx: Dict[str, Any], hour_index: int) -> float:
        hourly_temp = city_ctx.get("hourly_temperature_c", {})
        if isinstance(hourly_temp, dict):
            v = hourly_temp.get(hour_index, hourly_temp.get(str(hour_index)))
            if v is not None:
                return float(v)

        anomaly = city_ctx.get("hourly_temperature_anomaly", {})
        if isinstance(anomaly, dict):
            a = anomaly.get(hour_index, anomaly.get(str(hour_index)))
            if a is not None:
                return self.DEFAULT_BASE_TEMP_C + float(a)

        return self.DEFAULT_BASE_TEMP_C + float(city_ctx.get("temperature_anomaly", 0.0))

    def path_temp_c(self, path: Any, hour_index: int, city_contexts: Dict[str, Dict[str, Any]]) -> float:
        hop_ids = self._extract_hops(path)
        if not hop_ids:
            return self.DEFAULT_BASE_TEMP_C

        temps = [self.city_temp_c(city_contexts.get(h, {}), hour_index) for h in hop_ids]
        return max(temps) if temps else self.DEFAULT_BASE_TEMP_C

    @staticmethod
    def _extract_hops(path: Any) -> List[str]:
        if hasattr(path, "raw_path") and hasattr(path.raw_path, "hops"):
            return list(path.raw_path.hops)
        hops: List[str] = []
        if hasattr(path, "source"):
            hops.append(path.source)
        if hasattr(path, "destination"):
            hops.append(path.destination)
        return hops
