"""
routing_agent/routing_agent.py
==============================
Phase-driven market clearing with dispatcher gates, syndicate verification,
and route execution traces.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..shared.models import Order, OrderType, DispatchRecord
from .carbon_tariff import calculate_carbon_tax
from .dispatch_window_agent import DispatchWindowAgent
from .dlr_calculator import calculate_effective_capacity
from .llm_safety_stub import verify_route_safety_with_llm
from .path_climate_agent import PathClimateAgent
from .route_score_agent import RouteScoreAgent
from .dispatcher import DispatcherAgent
from .syndicate_decider import SyndicateDecider

logger = logging.getLogger(__name__)


@dataclass
class _ActiveOrder:
    order: Order
    remaining_mw: float = field(init=False)

    def __post_init__(self):
        self.remaining_mw = float(self.order.quantity_mw)

    @property
    def city_id(self) -> str:
        return self.order.city_id

    @property
    def price_per_mw(self) -> float:
        return float(self.order.price_per_mw)

    @property
    def order_type(self) -> OrderType:
        return self.order.order_type


class RoutingAgent:
    """
    National market maker + routing executor.
    """

    def __init__(self, grid_env: Any, green_mode: bool = False) -> None:
        self.grid_env = grid_env
        self.green_mode = bool(green_mode)

        self._path_climate_agent = PathClimateAgent()
        self._dispatch_window_agent = DispatchWindowAgent(self._path_climate_agent)
        self._route_score_agent = RouteScoreAgent()
        self._dispatcher = DispatcherAgent(grid_env)
        self._decider = SyndicateDecider(macro_safety_margin_mw=0.0)

        self._decision_log: list[dict[str, Any]] = []
        self._load_shedding_log: list[dict[str, Any]] = []

    def clear_market(
        self,
        orders: list[Order],
        hour_index: int | None = None,
        day_index: int = 0,
        state_positions: dict[str, Any] | None = None,
    ) -> list[DispatchRecord]:
        """
        Executes phase-3/4/5 with strict constraints and full decision logs.
        """
        self._decision_log = []
        self._load_shedding_log = []

        positions = state_positions or {}

        buy_queue = sorted(
            [_ActiveOrder(o) for o in orders if o.order_type == OrderType.BUY],
            key=lambda x: x.remaining_mw,
            reverse=True,
        )
        sell_queue = sorted(
            [_ActiveOrder(o) for o in orders if o.order_type == OrderType.SELL],
            key=lambda x: x.price_per_mw,
        )

        dispatch_log: list[DispatchRecord] = []

        for buyer in buy_queue:
            if buyer.remaining_mw <= 0:
                continue

            buyer_ctx_raw = self._get_llm_context(buyer.city_id)
            buyer_pos = positions.get(buyer.city_id)
            dispatch_hour = hour_index
            if dispatch_hour is None:
                if buyer_pos is not None and hasattr(buyer_pos, "dispatch_hour_hint"):
                    dispatch_hour = int(buyer_pos.dispatch_hour_hint)
                else:
                    dispatch_hour = day_index * 24 + 14

            buyer_need_before = float(buyer.remaining_mw)
            self._decision_log.append(
                {
                    "phase": "PHASE_3_REQUEST",
                    "buyer": buyer.city_id,
                    "requested_mw": buyer_need_before,
                    "dispatch_hour": dispatch_hour,
                }
            )

            for seller in sell_queue:
                if buyer.remaining_mw <= 0:
                    break
                if seller.remaining_mw <= 0:
                    continue
                if seller.city_id == buyer.city_id:
                    continue

                seller_ctx_raw = self._get_llm_context(seller.city_id)
                seller_ctx = self._resolve_hourly_context(seller_ctx_raw, dispatch_hour)
                buyer_ctx = self._resolve_hourly_context(buyer_ctx_raw, dispatch_hour)

                request_mw = float(min(buyer.remaining_mw, seller.remaining_mw))
                gate = self._dispatcher.apply_topology_and_dlr(
                    seller_id=seller.city_id,
                    buyer_id=buyer.city_id,
                    requested_mw=request_mw,
                    seller_ctx=seller_ctx,
                    buyer_ctx=buyer_ctx,
                )

                self._decision_log.append(
                    {
                        "phase": "PHASE_3_DISPATCHER",
                        "buyer": buyer.city_id,
                        "seller": seller.city_id,
                        "requested_mw": request_mw,
                        "allowed": gate["allowed"],
                        "line_cap_mw": gate["line_cap_mw"],
                        "reason": gate["reason"],
                        "dlr_applied": gate["dlr_applied"],
                        "effective_capacity_mw": gate["effective_capacity_mw"],
                    }
                )

                if not gate["allowed"]:
                    continue

                # Phase 4: deterministic LLM-style negotiation transcript
                buyer_line = (
                    f"NEGOTIATE | {buyer.city_id} buying {buyer.remaining_mw:.1f} MW | "
                    f"critical_shortfall requiring immediate transfer"
                )
                seller_line = (
                    f"NEGOTIATE | {seller.city_id} offering capped flow | "
                    f"dispatcher_limit={gate['line_cap_mw']:.1f} MW under thermal corridor limits"
                )
                self._decision_log.append(
                    {
                        "phase": "PHASE_4_NEGOTIATION",
                        "buyer": buyer.city_id,
                        "seller": seller.city_id,
                        "buyer_line": buyer_line,
                        "seller_line": seller_line,
                    }
                )

                proposed_mw = min(
                    float(buyer.remaining_mw),
                    float(seller.remaining_mw),
                    float(gate["line_cap_mw"]),
                )

                decider = self._decider.verify_trade(
                    buyer_id=buyer.city_id,
                    seller_id=seller.city_id,
                    requested_mw=proposed_mw,
                    dispatcher_cap_mw=float(gate["line_cap_mw"]),
                    seller_available_mw=float(seller.remaining_mw),
                    path=gate["selected_path"],
                )
                self._decision_log.append(
                    {
                        "phase": "PHASE_5_SYNDICATE",
                        "buyer": buyer.city_id,
                        "seller": seller.city_id,
                        "requested_mw": proposed_mw,
                        "approved": decider["approved"],
                        "approved_mw": decider["approved_mw"],
                        "reason": decider["reason"],
                    }
                )

                if not decider["approved"]:
                    continue

                path_choice = self._select_route_double_dqn_proxy(
                    seller_id=seller.city_id,
                    buyer_id=buyer.city_id,
                    dispatch_hour=dispatch_hour,
                )
                if path_choice is None:
                    self._decision_log.append(
                        {
                            "phase": "PHASE_5_ROUTING",
                            "buyer": buyer.city_id,
                            "seller": seller.city_id,
                            "approved": False,
                            "reason": "No route candidates after scoring",
                        }
                    )
                    continue

                path, route_score, route_trace = path_choice

                safe, safe_reason = verify_route_safety_with_llm(path)
                if not safe:
                    self._decision_log.append(
                        {
                            "phase": "PHASE_5_ROUTING",
                            "buyer": buyer.city_id,
                            "seller": seller.city_id,
                            "approved": False,
                            "reason": safe_reason,
                        }
                    )
                    continue

                # Cap again on chosen path to honor physical capacity.
                chosen_eff_cap, chosen_dlr = calculate_effective_capacity(path, seller_ctx, buyer_ctx)
                transfer_mw = min(decider["approved_mw"], float(chosen_eff_cap))
                if transfer_mw <= 0:
                    continue

                self._apply_flow(path, transfer_mw)
                buyer.remaining_mw -= transfer_mw
                seller.remaining_mw -= transfer_mw

                carbon_tax, _ = calculate_carbon_tax(seller.city_id, self.green_mode)
                path_cost = float(path.total_cost())
                cleared_price = float(seller.price_per_mw) + path_cost + carbon_tax

                trace = [
                    f"GATE | {gate.get('reason', 'Thermal corridor check')} | "
                    f"line_cap={gate['line_cap_mw']:.1f} MW dlr_applied={gate['dlr_applied']}",
                    buyer_line,
                    seller_line,
                    f"ROUTE | Score: {route_score:.4f} | "
                    f"dqn_proxy_trace={','.join(route_trace[:2])}",
                    f"SYNDICATE | {decider['reason']} | "
                    f"approved_mw={decider['approved_mw']:.1f}",
                    f"SAFETY | {safe_reason} | "
                    f"path_validation_done",
                ]

                record = DispatchRecord(
                    buyer_city_id=buyer.city_id,
                    seller_city_id=seller.city_id,
                    transfer_mw=transfer_mw,
                    cleared_price_mw=cleared_price,
                    seller_ask=seller.price_per_mw,
                    path_cost=path_cost,
                    carbon_tax=carbon_tax,
                    buyer_bid=buyer.price_per_mw,
                    path_description=getattr(path, "description", str(path)),
                    llm_safety_status="APPROVED",
                    dlr_applied=chosen_dlr,
                    effective_capacity=float(chosen_eff_cap),
                    requested_mw=request_mw,
                    line_cap_mw=float(gate["line_cap_mw"]),
                    approved_mw=float(decider["approved_mw"]),
                    residual_deficit_mw=max(float(buyer.remaining_mw), 0.0),
                    dispatch_hour=int(dispatch_hour) if dispatch_hour is not None else None,
                    radar_locked=gate.get("radar_locked", False),
                    radar_alert=gate.get("radar_alert", ""),
                    route_agent="DOUBLE_DQN_PROXY",
                    decision_trace=trace,
                )
                dispatch_log.append(record)

                self._decision_log.append(
                    {
                        "phase": "PHASE_5_EXECUTION",
                        "buyer": buyer.city_id,
                        "seller": seller.city_id,
                        "transfer_mw": transfer_mw,
                        "residual_deficit_mw": max(float(buyer.remaining_mw), 0.0),
                        "path": getattr(path, "description", str(path)),
                    }
                )

            if buyer.remaining_mw > 0:
                ls = self._decider.mandate_load_shedding(
                    buyer_id=buyer.city_id,
                    unresolved_deficit_mw=float(buyer.remaining_mw),
                    dispatch_hour=int(dispatch_hour) if dispatch_hour is not None else None,
                )
                self._load_shedding_log.append(ls)
                self._decision_log.append({"phase": "PHASE_5_LOAD_SHEDDING", **ls})

        return dispatch_log

    def get_decision_log(self) -> list[dict[str, Any]]:
        return list(self._decision_log)

    def get_load_shedding_log(self) -> list[dict[str, Any]]:
        return list(self._load_shedding_log)

    # ------------------------------------------------------------------
    # Route selection
    # ------------------------------------------------------------------

    def _select_route_double_dqn_proxy(
        self,
        seller_id: str,
        buyer_id: str,
        dispatch_hour: int | None,
    ) -> tuple[Any, float, list[str]] | None:
        paths = self._get_paths(seller_id, buyer_id)
        if not paths:
            return None

        city_contexts = self._all_city_contexts()
        carbon_tax, _ = calculate_carbon_tax(seller_id, self.green_mode)
        hour = int(dispatch_hour or 0)

        scored: list[tuple[float, Any, str]] = []
        for p in paths:
            path_temp = self._path_climate_agent.path_temp_c(p, hour, city_contexts)
            score = self._route_score_agent.score(
                path=p,
                path_temp_c=path_temp,
                carbon_tax=carbon_tax,
            )
            expl = (
                f"ROUTE_SCORE path={getattr(p, 'description', str(p))} "
                f"temp_c={path_temp:.2f} score={score:.4f}"
            )
            scored.append((score, p, expl))

        scored.sort(key=lambda x: x[0])
        best_score, best_path, _ = scored[0]
        trace = [item[2] for item in scored]
        return best_path, best_score, trace

    # ------------------------------------------------------------------
    # Environment adapters
    # ------------------------------------------------------------------

    def _get_paths(self, seller_id: str, buyer_id: str) -> list[Any]:
        if hasattr(self.grid_env, "get_paths"):
            return self.grid_env.get_paths(seller_id, buyer_id)
        if hasattr(self.grid_env, "paths"):
            return [
                p
                for p in self.grid_env.paths
                if getattr(p, "source", None) == seller_id
                and getattr(p, "destination", None) == buyer_id
            ]
        return []

    def _get_llm_context(self, city_id: str) -> dict[str, Any]:
        try:
            return self.grid_env.cities[city_id].llm_context
        except Exception:
            return {}

    def _all_city_contexts(self) -> dict[str, dict[str, Any]]:
        contexts: dict[str, dict[str, Any]] = {}
        try:
            cities = getattr(self.grid_env, "cities", {})
            for city_id, obj in cities.items():
                contexts[city_id] = getattr(obj, "llm_context", {}) or {}
        except Exception:
            return {}
        return contexts

    def _resolve_hourly_context(
        self,
        base_ctx: dict[str, Any],
        hour_index: int | None,
    ) -> dict[str, Any]:
        if hour_index is None:
            return base_ctx

        merged = dict(base_ctx)
        hourly_anomaly = base_ctx.get("hourly_temperature_anomaly", {})
        if isinstance(hourly_anomaly, dict):
            val = hourly_anomaly.get(hour_index, hourly_anomaly.get(str(hour_index)))
            if val is not None:
                merged["temperature_anomaly"] = float(val)

        hourly_temp = base_ctx.get("hourly_temperature_c", {})
        if isinstance(hourly_temp, dict):
            temp_val = hourly_temp.get(hour_index, hourly_temp.get(str(hour_index)))
            if temp_val is not None:
                merged["temperature_c"] = float(temp_val)

        return merged

    def _apply_flow(self, path: Any, transfer_mw: float) -> None:
        if hasattr(self.grid_env, "apply_flow"):
            self.grid_env.apply_flow(path, transfer_mw)
