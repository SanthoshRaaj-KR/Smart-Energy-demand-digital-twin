"""
state_agent/state_agent.py
==========================
Deterministic state-node logic for calibration, intelligence injection,
and order generation.
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.models import Order, OrderType, RiskLevel, StatePosition
from ..shared.constants import (
    BASELINE_ASK_PRICE,
    DISTRESSED_ASK_PRICE,
    BASELINE_BID_PRICE,
    PANIC_BID_PRICE,
    BATTERY_FULL_SOC_THRESHOLD,
)

logger = logging.getLogger(__name__)


class StateAgent:
    """
    Local trading agent for one state node.

    Backward-compatible constructor fields (`net_mw`, `battery_soc`, `llm_context`)
    are preserved for existing market order generation.
    """

    def __init__(
        self,
        city_id: str,
        net_mw: float,
        battery_soc: float,
        llm_context: dict[str, Any],
    ) -> None:
        self.city_id = city_id
        self.net_mw = net_mw
        self.battery_soc = battery_soc
        self.llm_context = llm_context

        self.hoard_flag: bool = bool(
            llm_context.get("hoard_flag", llm_context.get("pre_event_hoard", False))
        )
        self.demand_spike_risk: RiskLevel = self._parse_risk(
            llm_context.get("demand_spike_risk", "LOW")
        )
        self.temperature_anomaly: float = float(llm_context.get("temperature_anomaly", 0.0))

    # ------------------------------------------------------------------
    # Phase-1 + Phase-2 deterministic math
    # ------------------------------------------------------------------

    @staticmethod
    def calibrate_baseline_supply(
        forecast_7d_mw: list[float],
        safety_buffer: float = 1.05,
    ) -> float:
        if not forecast_7d_mw:
            return 0.0
        avg_forecast = sum(float(v) for v in forecast_7d_mw) / float(len(forecast_7d_mw))
        return avg_forecast * float(safety_buffer)

    def evaluate_state_position(
        self,
        forecast_7d_mw: list[float],
        todays_demand_forecast_mw: float,
        intelligence: dict[str, Any],
        safety_buffer: float = 1.05,
        pre_event_hoard_hour: int = 3,
        normal_dispatch_hour: int = 14,
    ) -> StatePosition:
        """
        Implements exact daily math sequence:
        1) baseline supply calibration from 7-day forecast
        2) intelligence multiplier injection
        3) mathematically verified net deficit/surplus
        4) temporal pre-event dispatch hint
        """
        edm = float(
            intelligence.get(
                "economic_demand_multiplier",
                intelligence.get("demand_multiplier", 1.0),
            )
        )
        gmm = float(
            intelligence.get(
                "generation_multiplier",
                intelligence.get("generation_capacity_multiplier", 1.0),
            )
        )
        pre_event_hoard = bool(
            intelligence.get("pre_event_hoard", intelligence.get("hoard_flag", False))
        )

        avg_forecast = (
            sum(float(v) for v in forecast_7d_mw) / float(len(forecast_7d_mw))
            if forecast_7d_mw
            else 0.0
        )
        baseline_supply = self.calibrate_baseline_supply(forecast_7d_mw, safety_buffer=safety_buffer)

        adjusted_demand = float(todays_demand_forecast_mw) * edm
        adjusted_supply = baseline_supply * gmm
        net = adjusted_supply - adjusted_demand
        deficit = abs(net) if net < 0 else 0.0
        surplus = net if net > 0 else 0.0

        # --- Selfish Seller / Self-Preservation Logic ---
        future_hoard_triggered = False
        future_deficit_mw = 0.0
        hoard_day = 0
        if forecast_7d_mw and len(forecast_7d_mw) > 1 and surplus > 0:
            # Check for massive deficit in the next 1-6 days
            for i, future_demand in enumerate(forecast_7d_mw[1:], start=1):
                # Using today's supply as baseline expected future supply
                day_net = adjusted_supply - future_demand
                if day_net < 0 and abs(day_net) > (0.05 * adjusted_supply):  # > 5% deficit
                    future_hoard_triggered = True
                    future_deficit_mw = abs(day_net)
                    hoard_day = i
                    break
        
        if future_hoard_triggered:
            pre_event_hoard = True
            # Force net to 0, hoarding the surplus
            surplus = 0.0
            net = 0.0

        dispatch_hour_hint = pre_event_hoard_hour if pre_event_hoard else normal_dispatch_hour

        phase_log = [
            (
                f"CALIBRATION | Baseline set to {baseline_supply:.0f} MW | "
                f"avg_forecast={avg_forecast:.2f} safety_buffer={safety_buffer:.2f}"
            ),
            (
                f"AUDIT | Net position: {net:+.1f} MW | "
                f"demand_adj={edm:.3f} supply_adj={gmm:.3f} "
                f"deficit={deficit:.1f} surplus={surplus:.1f}"
            ),
            (
                f"TEMPORAL | Dispatch window: {dispatch_hour_hint:02d}:00 | "
                f"pre_event_hoard={pre_event_hoard}"
            ),
        ]

        if future_hoard_triggered:
            phase_log.append(
                f"SELF-PRESERVATION | Hoarding for Day {hoard_day} | "
                f"future_deficit={future_deficit_mw:.1f} MW. Surplus retained for local security."
            )
            intelligence["pre_event_hoard"] = True
            intelligence["hoard_day"] = hoard_day

        return StatePosition(
            state_id=self.city_id,
            forecast_7d_mw=[float(v) for v in forecast_7d_mw],
            avg_forecast_mw=avg_forecast,
            baseline_supply_mw=baseline_supply,
            todays_demand_forecast_mw=float(todays_demand_forecast_mw),
            adjusted_demand_mw=adjusted_demand,
            adjusted_supply_mw=adjusted_supply,
            net_position_mw=net,
            deficit_mw=deficit,
            surplus_mw=surplus,
            economic_demand_multiplier=edm,
            generation_multiplier=gmm,
            pre_event_hoard=pre_event_hoard,
            dispatch_hour_hint=dispatch_hour_hint,
            reasoning=str(intelligence.get("narrative", intelligence.get("reasoning", ""))),
            phase_log=phase_log,
        )

    def negotiation_line(
        self,
        state_position: StatePosition,
        counterparty: str,
        hard_cap_mw: float,
        role: str,
    ) -> str:
        """
        One-sentence LLM-style negotiation line grounded in math constraints.
        """
        if role.upper() == "BUYER":
            return (
                f"REQUEST | {self.city_id} buying {state_position.deficit_mw:.1f} MW | "
                f"deficit_risk={self.demand_spike_risk.value} dispatch_window={state_position.dispatch_hour_hint:02d}:00 "
                f"dispatcher_cap={hard_cap_mw:.1f} MW"
            )
        return (
            f"OFFER | {self.city_id} selling {hard_cap_mw:.1f} MW | "
            f"available_surplus={state_position.surplus_mw:.1f} MW under current constraint"
        )

    # ------------------------------------------------------------------
    # Backward-compatible order generation
    # ------------------------------------------------------------------

    def generate_order(self) -> Order | None:
        if self.net_mw > 0:
            return self._build_sell_order()
        if self.net_mw < 0:
            return self._build_buy_order()
        logger.info("[%s] Net MW is zero; no order generated.", self.city_id)
        return None

    def _build_sell_order(self) -> Order:
        battery_full = self.battery_soc > BATTERY_FULL_SOC_THRESHOLD

        if battery_full:
            price = DISTRESSED_ASK_PRICE
            reason = (
                f"Battery SoC {self.battery_soc:.1f}% (> {BATTERY_FULL_SOC_THRESHOLD}%). "
                f"Distressed ask {price:.2f} INR/MW."
            )
        else:
            price = BASELINE_ASK_PRICE
            reason = (
                f"Normal surplus {self.net_mw:.1f} MW with battery {self.battery_soc:.1f}%. "
                f"Standard ask {price:.2f} INR/MW."
            )

        return Order(
            city_id=self.city_id,
            order_type=OrderType.SELL,
            quantity_mw=self.net_mw,
            price_per_mw=price,
            reason=reason,
        )

    def _build_buy_order(self) -> Order:
        quantity = abs(self.net_mw)
        panic = self.hoard_flag or (self.demand_spike_risk == RiskLevel.CRITICAL)

        if panic:
            price = PANIC_BID_PRICE
            triggers = []
            if self.hoard_flag:
                triggers.append("pre_event_hoard=True")
            if self.demand_spike_risk == RiskLevel.CRITICAL:
                triggers.append("demand_spike_risk=CRITICAL")
            reason = (
                f"PANIC BID due to {', '.join(triggers)}. "
                f"Max bid {price:.2f} INR/MW."
            )
        else:
            price = BASELINE_BID_PRICE
            reason = (
                f"Normal deficit {quantity:.1f} MW, risk {self.demand_spike_risk.value}. "
                f"Standard bid {price:.2f} INR/MW."
            )

        return Order(
            city_id=self.city_id,
            order_type=OrderType.BUY,
            quantity_mw=quantity,
            price_per_mw=price,
            reason=reason,
        )

    @staticmethod
    def _parse_risk(raw: str) -> RiskLevel:
        try:
            return RiskLevel(str(raw).upper())
        except (ValueError, AttributeError):
            logger.warning("Unrecognized demand_spike_risk '%s'; defaulting to LOW.", raw)
            return RiskLevel.LOW

    def __repr__(self) -> str:
        return (
            f"<StateAgent city={self.city_id} net_mw={self.net_mw:+.1f} "
            f"soc={self.battery_soc:.1f}% hoard={self.hoard_flag} "
            f"risk={self.demand_spike_risk.value}>"
        )
