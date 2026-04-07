"""
carbon_spatial_agent.py
========================
Feature 2: DLR-Aware "Carbon-Spatial" Routing

Two responsibilities:
  1. DLR Weather Multipliers — adjusts edge capacities based on live weather
     from the intelligence report BEFORE trades are proposed:
       • Bihar-UP corridor: wind_speed > 20 km/h → capacity × 1.1 (wind cools wires)
       • Any corridor: temperature > 40°C → capacity × 0.9 (heat degrades ampacity)

  2. Carbon Penalty BFS — re-ranks Phase 6 trade proposals by penalising
     carbon-intensive (coal) seller states and rewarding clean (solar/wind) sellers.
     Cost = edge_distance_proxy + carbon_penalty
     The BFS naturally prefers routing Karnataka solar over UP coal.

Reasoning storage:
  All adjustments are logged in a `adjustment_log` list of dicts that is returned
  alongside the modified edge caps. Each entry captures WHY the capacity changed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Carbon Intensity Map
# ---------------------------------------------------------------------------
# Scale 0.0 (clean) → 1.0 (very dirty coal)
# Sources: CEA India 2024 approximate fuel mix
CARBON_INTENSITY: Dict[str, float] = {
    "KAR": 0.15,   # Karnataka — ~70% solar/wind/hydro
    "WB":  0.65,   # West Bengal — coal-heavy thermal
    "BHR": 0.70,   # Bihar — coal-heavy, limited renewable
    "UP":  0.80,   # Uttar Pradesh — highest coal dependency
}

# Carbon penalty weight in cost function (scale relative to edge distance proxy)
CARBON_PENALTY_WEIGHT = 500.0   # Each unit of intensity = 500 virtual km of cost


# ---------------------------------------------------------------------------
# State → Region Weather Map (which intel key carries wind/temp for corridors)
# ---------------------------------------------------------------------------
# Maps state_id → the key to look up in the intelligence report weather section
_STATE_WEATHER_KEYS: Dict[str, str] = {
    "BHR": "BHR",
    "UP":  "UP",
    "WB":  "WB",
    "KAR": "KAR",
}

# Wind speed threshold for DLR boost (km/h)
DLR_WIND_BOOST_THRESHOLD_KMH = 20.0
DLR_WIND_BOOST_FACTOR = 1.10         # +10% capacity when windy

# Temperature threshold for DLR derating (°C)
DLR_TEMP_DERATE_THRESHOLD_C = 40.0
DLR_TEMP_DERATE_FACTOR = 0.90        # -10% capacity when scorching


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class EdgeAdjustment:
    """Records a single edge capacity adjustment for the reasoning log."""
    def __init__(
        self,
        edge: Tuple[str, str],
        original_cap: float,
        adjusted_cap: float,
        reason: str,
        adjustment_type: str,  # "DLR_WIND_BOOST" | "DLR_TEMP_DERATE" | "CARBON_PENALTY"
    ):
        self.edge = edge
        self.original_cap = original_cap
        self.adjusted_cap = adjusted_cap
        self.change_pct = round(((adjusted_cap - original_cap) / max(original_cap, 1)) * 100, 2)
        self.reason = reason
        self.adjustment_type = adjustment_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge": f"{self.edge[0]}→{self.edge[1]}",
            "original_cap_mw": round(self.original_cap, 2),
            "adjusted_cap_mw": round(self.adjusted_cap, 2),
            "change_pct": self.change_pct,
            "reason": self.reason,
            "adjustment_type": self.adjustment_type,
        }


class TradeRanking:
    """Stores carbon-adjusted cost for a trade proposal."""
    def __init__(
        self,
        buyer: str,
        seller: str,
        carbon_intensity: float,
        carbon_penalty: float,
        base_cost: float,
        total_cost: float,
    ):
        self.buyer = buyer
        self.seller = seller
        self.carbon_intensity = carbon_intensity
        self.carbon_penalty = carbon_penalty
        self.base_cost = base_cost
        self.total_cost = total_cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade": f"{self.seller}→{self.buyer}",
            "seller_carbon_intensity": self.carbon_intensity,
            "carbon_penalty_applied": round(self.carbon_penalty, 2),
            "base_cost": round(self.base_cost, 2),
            "total_cost_with_carbon": round(self.total_cost, 2),
        }


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class CarbonSpatialAgent:
    """
    Two-phase carbon-spatial routing intelligence:

    Phase A — DLR Weather Multipliers:
      Reads wind_speed and temperature from the intelligence report and
      adjusts edge capacities before Phase 6 negotiation.
      Specific rules:
        • BHR-UP corridor: wind > 20 km/h → ×1.1 (Bihar wind cools wires)
        • Any edge: max temp on either endpoint > 40°C → ×0.9

    Phase B — Carbon BFS:
      After Phase 6 proposes trades, re-ranks them by true cost:
        cost = base_distance_proxy + (carbon_intensity × CARBON_PENALTY_WEIGHT)
      karnataka solar (0.15) beats UP coal (0.80) automatically.
    """

    def __init__(self) -> None:
        self.dlr_adjustment_log: List[EdgeAdjustment] = []
        self.carbon_ranking_log: List[TradeRanking] = []

    def clear_logs(self) -> None:
        """Clear logs at start of each day."""
        self.dlr_adjustment_log.clear()
        self.carbon_ranking_log.clear()

    # ------------------------------------------------------------------
    # PHASE A: DLR WEATHER MULTIPLIERS
    # ------------------------------------------------------------------

    def apply_dlr_weather_multipliers(
        self,
        edge_caps: Dict[Tuple[str, str], float],
        intel_report: Optional[Dict[str, Any]],
    ) -> Dict[Tuple[str, str], float]:
        """
        Adjust edge capacities using live weather from the intelligence report.

        Rules:
          1. Bihar-UP corridor: wind_speed > 20 km/h → ×1.10
          2. Any corridor: temperature > 40°C at either endpoint → ×0.90

        Args:
            edge_caps: Current edge capacities (will NOT be mutated — returns new dict)
            intel_report: Daily intelligence report from StochasticTrigger

        Returns:
            New edge_caps dict with weather-adjusted capacities
        """
        adjusted = dict(edge_caps)  # defensive copy

        if not intel_report:
            return adjusted

        # Build per-state weather lookup
        weather = self._extract_weather(intel_report)

        for edge, cap in list(edge_caps.items()):
            src, dst = edge
            src_weather = weather.get(src, {})
            dst_weather = weather.get(dst, {})

            new_cap = cap

            # --- Rule 1: Wind boost on Bihar-UP corridor ---
            if {src, dst} == {"BHR", "UP"}:
                wind_bhr = src_weather.get("wind_speed_kmh", 0.0) if src == "BHR" else dst_weather.get("wind_speed_kmh", 0.0)
                wind_up  = dst_weather.get("wind_speed_kmh", 0.0) if dst == "UP"  else src_weather.get("wind_speed_kmh", 0.0)
                max_wind = max(wind_bhr, wind_up)
                if max_wind > DLR_WIND_BOOST_THRESHOLD_KMH:
                    boosted = new_cap * DLR_WIND_BOOST_FACTOR
                    self.dlr_adjustment_log.append(EdgeAdjustment(
                        edge=edge,
                        original_cap=cap,
                        adjusted_cap=boosted,
                        reason=(
                            f"Bihar-UP corridor: wind_speed={max_wind:.1f} km/h > "
                            f"{DLR_WIND_BOOST_THRESHOLD_KMH} km/h threshold. "
                            f"Wind cools overhead conductors, boosting ampacity by 10%."
                        ),
                        adjustment_type="DLR_WIND_BOOST",
                    ))
                    new_cap = boosted

            # --- Rule 2: Heat derating on any corridor ---
            src_temp = src_weather.get("temperature_c", 25.0)
            dst_temp = dst_weather.get("temperature_c", 25.0)
            max_temp = max(src_temp, dst_temp)

            if max_temp > DLR_TEMP_DERATE_THRESHOLD_C:
                derated = new_cap * DLR_TEMP_DERATE_FACTOR
                self.dlr_adjustment_log.append(EdgeAdjustment(
                    edge=edge,
                    original_cap=cap,
                    adjusted_cap=derated,
                    reason=(
                        f"Extreme heat: max_temp={max_temp:.1f}°C > "
                        f"{DLR_TEMP_DERATE_THRESHOLD_C}°C threshold. "
                        f"High ambient temperature degrades conductor ampacity by 10%."
                    ),
                    adjustment_type="DLR_TEMP_DERATE",
                ))
                new_cap = derated

            adjusted[edge] = round(new_cap, 2)

        if self.dlr_adjustment_log:
            print(f"  [CARBON-SPATIAL] DLR weather adjustments applied: {len(self.dlr_adjustment_log)} corridor(s)")
            for adj in self.dlr_adjustment_log:
                print(f"    {adj.edge[0]}→{adj.edge[1]}: {adj.original_cap:.0f}MW → {adj.adjusted_cap:.0f}MW ({adj.adjustment_type})")

        return adjusted

    def _extract_weather(
        self, intel_report: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:
        """
        Pull wind_speed and temperature per state from the intelligence report.
        Tries multiple keys since the report format has nested structures.
        """
        weather: Dict[str, Dict[str, float]] = {}

        # Try the `events` list first (StochasticTrigger format)
        for row in intel_report.get("events", []):
            state_id = str(row.get("state_id", ""))
            if not state_id:
                continue
            node_cls = row.get("node_classification", {}) or {}
            # Temperature and wind are stored in agent_payload under state key
            weather[state_id] = {
                "wind_speed_kmh": float(node_cls.get("wind_speed_kmh", 0.0)),
                "temperature_c":  float(node_cls.get("temperature_c", 25.0)),
            }

        # Also try agent_payload directly
        agent_payload = intel_report.get("agent_payload", {}) or {}
        for state_id in ["BHR", "UP", "WB", "KAR"]:
            if state_id in weather:
                continue
            state_data = agent_payload.get(state_id, {}) or {}
            multipliers = state_data.get("grid_multipliers", {}) or {}
            weather[state_id] = {
                "wind_speed_kmh": float(multipliers.get("wind_speed_kmh", 0.0)),
                "temperature_c":  float(multipliers.get("temperature_c", 25.0)),
            }

        return weather

    def get_dlr_context_for_trade(
        self, buyer: str, seller: str
    ) -> Optional[str]:
        """Return a human-readable DLR context string for the dialogue log."""
        relevant = [
            a for a in self.dlr_adjustment_log
            if a.edge[0] in (buyer, seller) or a.edge[1] in (buyer, seller)
        ]
        if not relevant:
            return None
        best = relevant[0]
        return (
            f"{best.adjustment_type}: {best.edge[0]}→{best.edge[1]} "
            f"{best.original_cap:.0f}MW→{best.adjusted_cap:.0f}MW "
            f"({best.change_pct:+.1f}%). {best.reason}"
        )

    # ------------------------------------------------------------------
    # PHASE B: CARBON PENALTY BFS
    # ------------------------------------------------------------------

    def apply_carbon_penalty(
        self,
        proposed_trades: List[Any],   # List[ProposedTrade]
        edge_caps: Dict[Tuple[str, str], float],
    ) -> List[Any]:
        """
        Re-rank proposed trades by carbon-aware total cost.

        Cost formula (lower = better, BFS will prefer):
            total_cost = base_cost + (seller_carbon_intensity × CARBON_PENALTY_WEIGHT)

        Where base_cost is approximated from the edge capacity (inverse proxy —
        higher-capacity corridors have lower effective distance cost).

        Args:
            proposed_trades: List of ProposedTrade from Phase 6 negotiation
            edge_caps: Current edge capacities (used for base cost proxy)

        Returns:
            Re-ranked list of ProposedTrade (lowest carbon cost first)
        """
        self.carbon_ranking_log.clear()

        scored: List[tuple] = []
        for trade in proposed_trades:
            seller = trade.seller_state
            buyer = trade.buyer_state
            edge_key = (seller, buyer)
            cap = float(edge_caps.get(edge_key, 1000.0))

            # Base cost proxy: 10000 / capacity (higher cap = lower distance cost)
            base_cost = 10000.0 / max(cap, 1.0)

            # Carbon penalty
            carbon_intensity = CARBON_INTENSITY.get(seller, 0.5)
            carbon_penalty = carbon_intensity * CARBON_PENALTY_WEIGHT

            total_cost = base_cost + carbon_penalty

            ranking = TradeRanking(
                buyer=buyer,
                seller=seller,
                carbon_intensity=carbon_intensity,
                carbon_penalty=carbon_penalty,
                base_cost=base_cost,
                total_cost=total_cost,
            )
            self.carbon_ranking_log.append(ranking)
            scored.append((total_cost, trade))

        # Sort ascending — lowest carbon cost first (BFS prefers clean)
        scored.sort(key=lambda x: x[0])
        reranked = [t for _, t in scored]

        if self.carbon_ranking_log:
            print(f"  [CARBON-SPATIAL] Carbon BFS re-ranking {len(reranked)} trades:")
            for r in self.carbon_ranking_log:
                print(
                    f"    {r.seller}→{r.buyer}: "
                    f"carbon_intensity={r.carbon_intensity:.2f}, "
                    f"total_cost={r.total_cost:.1f}"
                )

        return reranked

    def get_carbon_context_for_trade(
        self, buyer: str, seller: str
    ) -> Optional[str]:
        """Return a human-readable carbon context string for the dialogue log."""
        for r in self.carbon_ranking_log:
            if r.buyer == buyer and r.seller == seller:
                intensity_label = (
                    "solar/clean" if r.carbon_intensity < 0.3
                    else "mixed" if r.carbon_intensity < 0.6
                    else "coal-heavy"
                )
                return (
                    f"Seller carbon intensity={r.carbon_intensity:.2f} ({intensity_label}). "
                    f"Carbon penalty={r.carbon_penalty:.0f} virtual-km. "
                    f"BFS total_cost={r.total_cost:.1f}."
                )
        return None

    def get_full_log(self) -> Dict[str, Any]:
        """Return complete DLR + carbon log for JSON export."""
        return {
            "dlr_adjustments": [a.to_dict() for a in self.dlr_adjustment_log],
            "carbon_rankings": [r.to_dict() for r in self.carbon_ranking_log],
        }
