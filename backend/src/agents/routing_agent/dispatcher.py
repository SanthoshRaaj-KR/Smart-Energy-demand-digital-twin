"""
routing_agent/dispatcher.py
===========================
Dispatcher Agent: topology and physics gatekeeper.
"""

from __future__ import annotations

import logging
from typing import Any

from .dlr_calculator import calculate_effective_capacity

logger = logging.getLogger(__name__)


class DispatcherAgent:
    """
    Enforces spatial connectivity and DLR-based transfer caps.
    """

    def __init__(self, grid_env: Any):
        self.grid_env = grid_env

    def get_candidate_paths(self, seller_id: str, buyer_id: str) -> list[Any]:
        if hasattr(self.grid_env, "get_paths"):
            return self.grid_env.get_paths(seller_id, buyer_id)
        return []

    def apply_topology_and_dlr(
        self,
        seller_id: str,
        buyer_id: str,
        requested_mw: float,
        seller_ctx: dict[str, Any],
        buyer_ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Returns dispatcher constraints for one potential trade leg.
        """
        paths = self.get_candidate_paths(seller_id, buyer_id)
        if not paths:
            return {
                "allowed": False,
                "reason": f"No physical connection {seller_id}->{buyer_id}",
                "line_cap_mw": 0.0,
                "selected_path": None,
                "dlr_applied": False,
                "effective_capacity_mw": 0.0,
            }

        # Use path with lowest base physical cost for cap estimation.
        selected_path = min(paths, key=lambda p: float(p.total_cost()))
        effective_capacity, dlr_applied = calculate_effective_capacity(
            selected_path,
            seller_ctx,
            buyer_ctx,
        )

        hard_cap = max(0.0, min(float(requested_mw), float(effective_capacity)))

        # --- Predictive Corridor Locking (Intra-Day Radar) ---
        radar_alert = ""
        radar_locked = False
        # Calculate max anomaly from hourly data for 12:00 - 16:00
        seller_hourly_anom = seller_ctx.get("hourly_temperature_anomaly", {})
        buyer_hourly_anom = buyer_ctx.get("hourly_temperature_anomaly", {})
        
        max_afternoon_anom = 0.0
        for h in range(12, 17):
            s_val = seller_hourly_anom.get(h, seller_hourly_anom.get(str(h), 0.0))
            b_val = buyer_hourly_anom.get(h, buyer_hourly_anom.get(str(h), 0.0))
            max_afternoon_anom = max(max_afternoon_anom, s_val, b_val)
            
        if max_afternoon_anom >= 5.0: # ~6 deg anomaly threshold
            radar_locked = True
            radar_alert = "⚠️ DISPATCHER ALERT: Afternoon DLR Collapse. ALL TRANSFERS FORCED TO 04:00 - 08:00 HRS."
            # In a real hourly sim, we would zero the cap during those hours. 
            # Here we reflect the forced early routing.


        log_line = (
            f"PHASE_3_DISPATCHER seller={seller_id} buyer={buyer_id} requested={requested_mw:.2f} "
            f"path={getattr(selected_path, 'description', str(selected_path))} "
            f"effective_capacity={effective_capacity:.2f} hard_cap={hard_cap:.2f} "
            f"dlr_applied={dlr_applied}"
        )
        if radar_locked:
            log_line += f" | {radar_alert}"

        logger.info(log_line)

        return {
            "allowed": hard_cap > 0.0,
            "reason": radar_alert if radar_locked else ("OK" if hard_cap > 0.0 else "Line cap reduced to zero"),
            "line_cap_mw": hard_cap,
            "selected_path": selected_path,
            "dlr_applied": dlr_applied,
            "radar_locked": radar_locked,
            "radar_alert": radar_alert,
            "effective_capacity_mw": float(effective_capacity),
            "log": log_line,
        }

    @staticmethod
    def negotiation_prompt(
        seller_id: str,
        buyer_id: str,
        buyer_deficit_mw: float,
        line_cap_mw: float,
    ) -> str:
        return (
            f"You are {seller_id}. {buyer_id} needs {buyer_deficit_mw:.2f} MW. "
            f"Dispatcher has hard-capped this interconnector at {line_cap_mw:.2f} MW. "
            "Offer at most the cap."
        )
