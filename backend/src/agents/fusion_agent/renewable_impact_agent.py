"""
renewable_impact_agent.py
=========================
Applies weather intermittency only to renewable share of generation.
"""

from __future__ import annotations

from typing import Dict

from src.agents.state_agent.intermittency_agent import apply_renewable_chaos


class RenewableImpactAgent:
    """
    Limits weather-chaos to renewable slice instead of full generation fleet.
    """

    DEFAULT_RENEWABLE_SHARE = 0.30
    CITY_RENEWABLE_SHARE: Dict[str, float] = {
        "KAR": 0.55,
        "UP": 0.15,
        "WB": 0.10,
        "BHR": 0.12,
    }

    def apply(self, city_id: str, scaled_generation_mw: float, condition: str) -> float:
        share = self.CITY_RENEWABLE_SHARE.get(city_id, self.DEFAULT_RENEWABLE_SHARE)
        renewable_block = scaled_generation_mw * share
        firm_block = scaled_generation_mw - renewable_block
        weather_context = {"current_condition": condition}
        renewable_after = apply_renewable_chaos(city_id, renewable_block, weather_context)
        return firm_block + renewable_after
