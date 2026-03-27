"""
state_agent/state_agent.py
==========================
Implements the `StateAgent` class — one instance per city.

Role
----
Reads the city's physical state (net_mw, battery SoC) and the LLM context
JSON produced by news_agent.py, then generates a single financial Order
(BUY or SELL) that reflects the city's desperation level.

Design principle
----------------
All magic numbers live in `shared/constants.py`.  The agent itself is pure
decision logic with no hard-coded prices.
"""

from __future__ import annotations
import logging
from typing import Any

from ..shared.models    import Order, OrderType, RiskLevel
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
    Local trading agent for a single city node in the India Grid Digital Twin.

    Parameters
    ----------
    city_id     : Short identifier for the city, e.g. "DEL", "MUM".
    net_mw      : Signed MW balance.
                    > 0  →  surplus (wants to sell)
                    < 0  →  deficit (wants to buy)
                    = 0  →  balanced (no order generated)
    battery_soc : Battery State-of-Charge in percent (0–100).
                  Used to detect a "full battery" distress condition for sellers.
    llm_context : Dictionary produced by news_agent.py for this city.
                  Expected keys:
                    - "hoard_flag"         (bool)   : True if a mega-event is imminent.
                    - "demand_spike_risk"  (str)    : "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
                    - "temperature_anomaly" (float) : °C above seasonal baseline
                      (used downstream by RoutingAgent for DLR; stored here for completeness)
    """

    def __init__(
        self,
        city_id    : str,
        net_mw     : float,
        battery_soc: float,
        llm_context: dict[str, Any],
    ) -> None:
        self.city_id     = city_id
        self.net_mw      = net_mw
        self.battery_soc = battery_soc
        self.llm_context = llm_context

        # Parse LLM context once at construction time for clean downstream use
        self.hoard_flag          : bool      = bool(llm_context.get("hoard_flag", False))
        self.demand_spike_risk   : RiskLevel = self._parse_risk(llm_context.get("demand_spike_risk", "LOW"))
        self.temperature_anomaly : float     = float(llm_context.get("temperature_anomaly", 0.0))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_order(self) -> Order | None:
        """
        Evaluate the city's state and produce a BUY or SELL Order.

        Returns None if the city is perfectly balanced (net_mw == 0).
        """
        if self.net_mw > 0:
            return self._build_sell_order()
        elif self.net_mw < 0:
            return self._build_buy_order()
        else:
            logger.info("[%s] Net MW is zero — no order generated.", self.city_id)
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_sell_order(self) -> Order:
        """
        Surplus city → SELL order.

        Pricing tiers
        -------------
        • Battery nearly full (SoC > threshold) → distressed ask (₹1.5/MW)
          The city MUST offload or waste renewable generation.
        • Normal surplus → baseline ask (₹3/MW).
        """
        battery_full = self.battery_soc > BATTERY_FULL_SOC_THRESHOLD

        if battery_full:
            price  = DISTRESSED_ASK_PRICE
            reason = (
                f"Battery SoC is {self.battery_soc:.1f}% (>{BATTERY_FULL_SOC_THRESHOLD}%). "
                f"Desperate to offload surplus — distressed ask of ₹{price}/MW."
            )
        else:
            price  = BASELINE_ASK_PRICE
            reason = (
                f"Normal surplus of {self.net_mw:.1f} MW with battery at {self.battery_soc:.1f}%. "
                f"Standard ask of ₹{price}/MW."
            )

        logger.debug("[%s] SELL order: %.1f MW @ ₹%.2f/MW | %s", self.city_id, self.net_mw, price, reason)

        return Order(
            city_id      = self.city_id,
            order_type   = OrderType.SELL,
            quantity_mw  = self.net_mw,          # always positive for surplus
            price_per_mw = price,
            reason       = reason,
        )

    def _build_buy_order(self) -> Order:
        """
        Deficit city → BUY order.

        Pricing tiers
        -------------
        • hoard_flag is True  → panic bid (₹15/MW): mega-event imminent, buy at any cost.
        • demand_spike_risk is CRITICAL → panic bid (₹15/MW): grid-level emergency.
        • Otherwise → baseline bid (₹5/MW).
        """
        quantity = abs(self.net_mw)   # always positive

        # Agentic Panic condition
        panic = self.hoard_flag or (self.demand_spike_risk == RiskLevel.CRITICAL)

        if panic:
            price = PANIC_BID_PRICE
            triggers = []
            if self.hoard_flag:
                triggers.append("hoard_flag=True (mega-event imminent)")
            if self.demand_spike_risk == RiskLevel.CRITICAL:
                triggers.append("demand_spike_risk=CRITICAL")
            reason = (
                f"PANIC BID triggered by: {', '.join(triggers)}. "
                f"City will pay up to ₹{price}/MW to secure power."
            )
        else:
            price  = BASELINE_BID_PRICE
            reason = (
                f"Normal deficit of {quantity:.1f} MW. "
                f"Risk level: {self.demand_spike_risk.value}. "
                f"Standard bid of ₹{price}/MW."
            )

        logger.debug("[%s] BUY order: %.1f MW @ ₹%.2f/MW | %s", self.city_id, quantity, price, reason)

        return Order(
            city_id      = self.city_id,
            order_type   = OrderType.BUY,
            quantity_mw  = quantity,
            price_per_mw = price,
            reason       = reason,
        )

    @staticmethod
    def _parse_risk(raw: str) -> RiskLevel:
        """
        Safely coerce the LLM context string to a RiskLevel enum.
        Defaults to LOW if the value is unrecognised.
        """
        try:
            return RiskLevel(raw.upper())
        except (ValueError, AttributeError):
            logger.warning("Unrecognised demand_spike_risk value '%s' — defaulting to LOW.", raw)
            return RiskLevel.LOW

    def __repr__(self) -> str:
        return (
            f"<StateAgent city={self.city_id} net_mw={self.net_mw:+.1f} "
            f"soc={self.battery_soc:.1f}% hoard={self.hoard_flag} "
            f"risk={self.demand_spike_risk.value}>"
        )