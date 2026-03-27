"""
reserve_activation_agent.py
===========================
Specialized fallback agent to ensure dispatchable supply windows exist.
"""

from __future__ import annotations

from typing import Dict

from src.environment.grid_physics import GridEnvironment


class ReserveActivationAgent:
    """
    Activates peaker/spinning reserve when all nodes are in deficit.
    """

    def __init__(self, max_reserve_frac: float = 0.25, target_surplus_mw: float = 600.0):
        self._max_reserve_frac = max_reserve_frac
        self._target_surplus_mw = target_surplus_mw

    def ensure_dispatchable_surplus(
        self,
        env: GridEnvironment,
        base_generation: Dict[str, float],
    ) -> None:
        balances = {nid: n.raw_balance_mw for nid, n in env.nodes.items()}
        deficits = [nid for nid, v in balances.items() if v < 0]
        if not deficits:
            return

        def can_trade_to_any_deficit(seller_id: str) -> bool:
            return any(len(env.get_paths_for(seller_id, d)) > 0 for d in deficits if d != seller_id)

        tradable_sellers = [nid for nid, v in balances.items() if v > 0 and can_trade_to_any_deficit(nid)]
        if tradable_sellers:
            return

        # Choose least-deficit tradable node as reserve anchor.
        tradable_candidates = [nid for nid in balances if can_trade_to_any_deficit(nid)]
        if not tradable_candidates:
            return

        anchor_id = max(tradable_candidates, key=lambda nid: balances[nid])
        anchor = env.nodes[anchor_id]
        anchor_balance = balances[anchor_id]

        max_reserve = float(base_generation.get(anchor_id, anchor.generation_mw)) * self._max_reserve_frac
        needed = abs(anchor_balance) + self._target_surplus_mw
        reserve_add = min(max_reserve, needed)

        if reserve_add > 0:
            anchor.generation_mw += reserve_add
