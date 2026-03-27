"""
hourly_fusion_agent.py
======================
Combines baseline demand predictions with live intelligence + hourly climate.

The user can inject a predictor model later via `predictor_fn`.
Until then, this agent uses GridEnvironment's baseline demand as the base signal.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.environment.grid_physics import GridEnvironment
from .demand_shaping_agent import DemandShapingAgent
from .renewable_impact_agent import RenewableImpactAgent
from .reserve_activation_agent import ReserveActivationAgent


class HourlyFusionAgent:
    """
    Hour-level feature fusion before market order generation.
    """

    def __init__(self, predictor_fn: Optional[Callable[..., Dict[str, float]]] = None):
        self._predictor_fn = predictor_fn
        self._demand_shaper = DemandShapingAgent()
        self._renewable_impact = RenewableImpactAgent()
        self._reserve_agent = ReserveActivationAgent()

    def apply_hour(
        self,
        env: GridEnvironment,
        contexts: Dict[str, Dict[str, Any]],
        hour_index: int,
        base_generation: Dict[str, float],
    ) -> None:
        """
        Update env node demand/generation for one hour.
        """
        base_demand = self._predict_base_demand(env, hour_index)

        for nid, node in env.nodes.items():
            ctx = contexts.get(nid, {})
            raw_edm = float(ctx.get("economic_demand_multiplier", 1.0))
            gcm = float(ctx.get("generation_capacity_multiplier", 1.0))
            anomaly = self._hourly_anomaly(ctx, hour_index)
            demand_risk = str(ctx.get("demand_spike_risk", "LOW"))

            edm = self._demand_shaper.effective_edm(raw_edm, demand_risk)
            thermal_factor = self._demand_shaper.thermal_factor(anomaly)
            node.adjusted_demand_mw = float(base_demand.get(nid, node.demand_mw)) * edm * thermal_factor

            condition_map = ctx.get("hourly_condition", {})
            condition = condition_map.get(hour_index, condition_map.get(str(hour_index), ctx.get("current_condition", "clear sky")))

            baseline_gen = float(base_generation.get(nid, node.generation_mw))
            scaled_gen = baseline_gen * gcm
            node.generation_mw = self._renewable_impact.apply(nid, scaled_gen, condition)

        self._reserve_agent.ensure_dispatchable_surplus(env, base_generation)

    def apply_day(
        self,
        env: GridEnvironment,
        contexts: Dict[str, Dict[str, Any]],
        base_generation: Dict[str, float],
    ) -> None:
        """
        Daily fusion pass (non-hourly):
        - Uses daily multipliers from intelligence/state context.
        - Keeps hourly weather reserved for routing-time decision only.
        """
        base_demand = self._predict_base_demand(env, hour_index=0)

        for nid, node in env.nodes.items():
            ctx = contexts.get(nid, {})
            raw_edm = float(ctx.get("economic_demand_multiplier", 1.0))
            gcm = float(ctx.get("generation_capacity_multiplier", 1.0))
            anomaly = float(ctx.get("temperature_anomaly", 0.0))
            demand_risk = str(ctx.get("demand_spike_risk", "LOW"))

            edm = self._demand_shaper.effective_edm(raw_edm, demand_risk)
            thermal_factor = self._demand_shaper.thermal_factor(anomaly)
            node.adjusted_demand_mw = float(base_demand.get(nid, node.demand_mw)) * edm * thermal_factor

            condition = str(ctx.get("current_condition", "clear sky"))
            baseline_gen = float(base_generation.get(nid, node.generation_mw))
            scaled_gen = baseline_gen * gcm
            node.generation_mw = self._renewable_impact.apply(nid, scaled_gen, condition)

        self._reserve_agent.ensure_dispatchable_surplus(env, base_generation)

    def _predict_base_demand(self, env: GridEnvironment, hour_index: int) -> Dict[str, float]:
        """
        Returns node-level baseline demand prediction.
        If predictor_fn is provided, this calls it. Otherwise uses current env demand.
        """
        if self._predictor_fn is not None:
            return self._predictor_fn(env=env, hour_index=hour_index)
        return {nid: float(node.demand_mw) for nid, node in env.nodes.items()}

    @staticmethod
    def _hourly_anomaly(ctx: Dict[str, Any], hour_index: int) -> float:
        hourly_anomaly = ctx.get("hourly_temperature_anomaly", {})
        if isinstance(hourly_anomaly, dict):
            val = hourly_anomaly.get(hour_index, hourly_anomaly.get(str(hour_index)))
            if val is not None:
                return float(val)
        return float(ctx.get("temperature_anomaly", 0.0))
