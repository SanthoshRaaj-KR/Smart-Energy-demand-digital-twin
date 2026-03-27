"""
src/agents/state_agent/intermittency_agent.py
=============================================
Simulates Supply-Side Chaos by mapping real-time cloud cover and weather
descriptions from the live LLM context cache to sudden base-generation
slashes (simulating the drop-off of solar/wind).
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Heuristic mapping of OpenWeatherMap condition strings to % capacity loss
WEATHER_IMPACT_MAP = {
    "clear sky": 0.0,
    "few clouds": 0.05,
    "scattered clouds": 0.10,
    "broken clouds": 0.20,
    "overcast clouds": 0.35,
    "drizzle": 0.40,
    "rain": 0.50,
    "heavy intensity rain": 0.60,
    "thunderstorm": 0.70,
    "haze": 0.15,
    "dust": 0.25,
    "fog": 0.30,
}


def apply_renewable_chaos(city_id: str, base_generation_mw: float, weather_context: Dict[str, Any]) -> float:
    """
    Looks at the current weather condition and slashes the generation_mw 
    representing abrupt renewable drop-offs.
    
    Returns the new effective generation capacity (MW).
    """
    condition = weather_context.get("current_condition", "clear sky").lower()
    
    # Simple substring matching in case of complex strings like 'light rain'
    penalty_pct = 0.0
    for key, penalty in WEATHER_IMPACT_MAP.items():
        if key in condition:
            penalty_pct = max(penalty_pct, penalty)
            
    if penalty_pct > 0:
        new_gen = base_generation_mw * (1.0 - penalty_pct)
        logger.info(
            "[\u2601\ufe0f CHAOS] %s weather '%s' caused a %.0f%% renewable drop-off! "
            "Capacity slashed: %.0f MW \u2192 %.0f MW",
            city_id, condition, penalty_pct * 100, base_generation_mw, new_gen
        )
        return new_gen
        
    return base_generation_mw
