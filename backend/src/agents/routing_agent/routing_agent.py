"""
routing_agent/routing_agent.py
================================
Implements the `RoutingAgent` — the singleton National Market Maker and
LLM-validated Autonomous Router for the India Grid Digital Twin.

Responsibilities
----------------
1. **Market Clearing**   — Match BUY orders (highest bid first) against SELL
                           orders (lowest ask first).
2. **Delivered Cost Math**— Factor in path tolls, transmission-loss penalties,
                           and (optionally) a green carbon tariff.
3. **Dynamic Line Rating**— Derate path capacity for heatwave conditions before
                           accepting a route.
4. **LLM Safety Check**  — Forward every candidate route to a cognitive-override
                           stub; retry on rejection.
5. **XAI Dispatch Log**  — Print an explainable human-readable log entry for
                           every successful transfer.

Integration Points
------------------
- `grid_env.py`          : Must expose `get_paths(buyer_id, seller_id)` returning
                           a list of Path objects.  Each Path must have:
                               .description       (str)   — e.g. "MUM->NAG->DEL"
                               .bottleneck_capacity (float) — MW nameplate rating
                               .total_cost()      (float) — ₹/MW (tolls + loss penalty)
- `state_agent.py`       : Produces the `Order` objects this agent consumes.
- `news_agent.py`        : LLM context dicts are accessed via the city objects in
                           `grid_env`.  Each city must have a `.llm_context` dict
                           containing at least `temperature_anomaly` (float).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any

from ..shared.models    import Order, OrderType, DispatchRecord
from .llm_safety_stub import verify_route_safety_with_llm
from .dlr_calculator  import calculate_effective_capacity
from .carbon_tariff   import calculate_carbon_tax
from .path_climate_agent import PathClimateAgent
from .dispatch_window_agent import DispatchWindowAgent
from .route_score_agent import RouteScoreAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal working copy of an order (mutable remaining quantity)
# ---------------------------------------------------------------------------

@dataclass
class _ActiveOrder:
    """
    Wraps an immutable Order with a mutable `remaining_mw` so we can partially
    fill orders across multiple trades in the same clearing round.
    """
    order         : Order
    remaining_mw  : float = field(init=False)

    def __post_init__(self):
        self.remaining_mw = self.order.quantity_mw

    @property
    def city_id(self)      -> str:   return self.order.city_id
    @property
    def price_per_mw(self) -> float: return self.order.price_per_mw
    @property
    def order_type(self)   -> OrderType: return self.order.order_type


# ---------------------------------------------------------------------------
# RoutingAgent
# ---------------------------------------------------------------------------

class RoutingAgent:
    """
    National Market Maker for the India Grid Autonomous Energy Stock Market.

    Parameters
    ----------
    grid_env    : The GridEnvironment object from grid_env.py.
                  Used to look up pre-enumerated paths and city LLM contexts.
    green_mode  : If True, a carbon tax is added to the delivered cost of
                  fossil-heavy sellers, incentivising renewable sourcing.
                  Default: False.

    Usage
    -----
        agent = RoutingAgent(grid_env=env, green_mode=True)
        dispatch_log = agent.clear_market(orders)
        # dispatch_log is also printed to stdout in XAI format.
    """

    def __init__(self, grid_env: Any, green_mode: bool = False) -> None:
        self.grid_env   = grid_env
        self.green_mode = green_mode
        self._path_climate_agent = PathClimateAgent()
        self._dispatch_window_agent = DispatchWindowAgent(self._path_climate_agent)
        self._route_score_agent = RouteScoreAgent()
        logger.info(
            "[RoutingAgent] Initialised. green_mode=%s", green_mode
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_market(
        self,
        orders: list[Order],
        hour_index: int | None = None,
        day_index: int = 0,
    ) -> list[DispatchRecord]:
        """
        Run one full market-clearing round.

        Steps:
        ------
        1. Separate orders into buyers and sellers.
        2. Sort: buyers descending by bid, sellers ascending by ask.
        3. For each (buyer, seller) pair:
           a. Find candidate paths.
           b. Apply DLR derating.
           c. Check capacity.
           d. Compute delivered cost.
           e. Check if bid ≥ delivered cost.
           f. LLM safety check (retry on rejection).
           g. Execute transfer; emit XAI log.
        4. Return list of DispatchRecord objects for downstream use.

        Parameters
        ----------
        orders : List of Order objects from all StateAgents this tick.

        Returns
        -------
        List of DispatchRecord — one per successful transfer.
        """
        buy_queue  = sorted(
            [_ActiveOrder(o) for o in orders if o.order_type == OrderType.BUY],
            key=lambda x: x.price_per_mw,
            reverse=True,   # highest bidder first
        )
        sell_queue = sorted(
            [_ActiveOrder(o) for o in orders if o.order_type == OrderType.SELL],
            key=lambda x: x.price_per_mw,
            # lowest ask first
        )

        logger.info(
            "[RoutingAgent] Market open — %d BUY orders, %d SELL orders.",
            len(buy_queue), len(sell_queue),
        )

        dispatch_log: list[DispatchRecord] = []

        from .syndicate_agent import SyndicateBroker
        syndicate_broker = SyndicateBroker(self)

        for buyer in buy_queue:
            if buyer.remaining_mw <= 0:
                continue

            # Attempt Syndicate deal first for the remaining order
            synd_record = syndicate_broker.attempt_syndicate_trade(
                buyer,
                sell_queue,
                hour_index=hour_index,
                day_index=day_index
            )
            
            if synd_record:
                dispatch_log.append(synd_record)
                self._print_syndicate_log(synd_record)
                if buyer.remaining_mw <= 0:
                    continue

            for seller in sell_queue:
                if seller.remaining_mw <= 0:
                    continue
                if buyer.remaining_mw <= 0:
                    break

                record = self._attempt_trade(
                    buyer,
                    seller,
                    hour_index=hour_index,
                    day_index=day_index,
                )
                if record:
                    dispatch_log.append(record)

        logger.info(
            "[RoutingAgent] Market closed — %d dispatches executed.", len(dispatch_log)
        )
        return dispatch_log

    # ------------------------------------------------------------------
    # Core trade-matching logic
    # ------------------------------------------------------------------

    def _attempt_trade(
        self,
        buyer  : _ActiveOrder,
        seller : _ActiveOrder,
        hour_index: int | None = None,
        day_index: int = 0,
    ) -> DispatchRecord | None:
        """
        Try every available path between seller and buyer.
        Applies DLR, cost check, and LLM safety validation.
        Returns a DispatchRecord on success, None if no viable path exists.
        """
        paths = self._get_paths(seller.city_id, buyer.city_id)

        if not paths:
            logger.debug(
                "[RoutingAgent] No pre-enumerated paths from %s to %s.",
                seller.city_id, buyer.city_id,
            )
            return None

        selected_hour = hour_index
        # Retrieve LLM contexts for DLR
        src_ctx_raw  = self._get_llm_context(seller.city_id)
        dest_ctx_raw = self._get_llm_context(buyer.city_id)
        city_contexts = self._all_city_contexts()
        buyer_risk = str(dest_ctx_raw.get("demand_spike_risk", "LOW"))

        if selected_hour is None:
            selected_hour = self._dispatch_window_agent.best_dispatch_hour(
                candidate_paths=paths,
                day_index=day_index,
                city_contexts=city_contexts,
                buyer_risk=buyer_risk,
            )

        src_ctx = self._resolve_hourly_context(src_ctx_raw, selected_hour)
        dest_ctx = self._resolve_hourly_context(dest_ctx_raw, selected_hour)

        if hour_index is not None and not self._dispatch_window_agent.should_dispatch_now(
            candidate_paths=paths,
            hour_index=hour_index,
            city_contexts=city_contexts,
            buyer_risk=buyer_risk,
        ):
            logger.debug(
                "[RoutingAgent] Deferring %s→%s at hour %s (outside preferred cool window).",
                seller.city_id,
                buyer.city_id,
                hour_index,
            )
            return None

        # Carbon tax (₹0 if green_mode is False)
        carbon_tax, carbon_intensity = calculate_carbon_tax(
            seller.city_id, self.green_mode
        )

        scored_paths = sorted(
            paths,
            key=lambda p: self._route_score_agent.score(
                path=p,
                path_temp_c=self._path_climate_agent.path_temp_c(
                    p, selected_hour or 0, city_contexts
                ),
                carbon_tax=carbon_tax,
            ),
        )

        for path in scored_paths:
            # ---- Step 1: Dynamic Line Rating ----------------------------------------
            effective_capacity, dlr_applied = calculate_effective_capacity(
                path, src_ctx, dest_ctx
            )

            # How many MW can we actually move on this path this tick?
            transfer_mw = min(buyer.remaining_mw, seller.remaining_mw, effective_capacity)

            if transfer_mw <= 0:
                logger.debug(
                    "[RoutingAgent] Path %s capacity insufficient after DLR (%.1f MW).",
                    getattr(path, "description", path), effective_capacity,
                )
                continue

            # ---- Step 2: Delivered-cost check ---------------------------------------
            path_cost      = float(path.total_cost())
            delivered_cost = seller.price_per_mw + path_cost + carbon_tax

            if buyer.price_per_mw < delivered_cost:
                # Trigger LLM-to-LLM Negotiation
                from .negotiator import negotiate_trade
                buyer_risk = dest_ctx.get("demand_spike_risk", "UNKNOWN")
                
                success, new_price, transcript = negotiate_trade(
                    buyer_city=buyer.city_id,
                    seller_city=seller.city_id,
                    buyer_bid=buyer.price_per_mw,
                    seller_ask=seller.price_per_mw,
                    tolls_and_carbon=path_cost + carbon_tax,
                    buyer_risk=buyer_risk
                )
                
                if not success:
                    logger.debug(
                        "[RoutingAgent] Negotation failed for %s\u2192%s. Bid \u20b9%.2f vs Ask \u20b9%.2f",
                        seller.city_id, buyer.city_id, buyer.price_per_mw, delivered_cost
                    )
                    continue
                    
                # Agreement reached!
                delivered_cost = new_price
                print(transcript)  # Print to console for XAI log

            # ---- Step 3: LLM cognitive-override safety check ------------------------
            approved, llm_reason = verify_route_safety_with_llm(path)

            if not approved:
                logger.warning(
                    "[RoutingAgent] LLM REJECTED path %s: %s — trying next path.",
                    getattr(path, "description", path), llm_reason,
                )
                continue   # retry with next-best path

            # ---- Step 4: Execute the trade ------------------------------------------
            self._apply_flow(path, transfer_mw)
            buyer.remaining_mw  -= transfer_mw
            seller.remaining_mw -= transfer_mw

            record = DispatchRecord(
                buyer_city_id      = buyer.city_id,
                seller_city_id     = seller.city_id,
                transfer_mw        = transfer_mw,
                cleared_price_mw   = delivered_cost,
                seller_ask         = seller.price_per_mw,
                path_cost          = path_cost,
                carbon_tax         = carbon_tax,
                buyer_bid          = buyer.price_per_mw,
                path_description   = (
                    f"{getattr(path, 'description', str(path))} @hour {selected_hour % 24:02d}:00"
                    if selected_hour is not None
                    else getattr(path, "description", str(path))
                ),
                llm_safety_status  = "APPROVED",
                dlr_applied        = dlr_applied,
                effective_capacity = effective_capacity,
            )

            self._print_xai_log(record, carbon_intensity)
            return record   # one successful path per (buyer, seller) pair per tick

        # All paths tried and failed
        logger.warning(
            "[RoutingAgent] No valid path found for %s→%s after all attempts.",
            seller.city_id, buyer.city_id,
        )
        return None

    def _resolve_hourly_context(
        self,
        base_ctx: dict[str, Any],
        hour_index: int | None,
    ) -> dict[str, Any]:
        """
        Build hour-aware context view.
        If hourly anomaly map exists, override temperature_anomaly for that hour.
        """
        if hour_index is None:
            return base_ctx

        hourly_anomaly = base_ctx.get("hourly_temperature_anomaly", {})
        if isinstance(hourly_anomaly, dict):
            hour_value = hourly_anomaly.get(hour_index, hourly_anomaly.get(str(hour_index)))
            if hour_value is None:
                merged = dict(base_ctx)
            else:
                merged = dict(base_ctx)
                merged["temperature_anomaly"] = float(hour_value)

            hourly_temp = base_ctx.get("hourly_temperature_c", {})
            if isinstance(hourly_temp, dict):
                temp_value = hourly_temp.get(hour_index, hourly_temp.get(str(hour_index)))
                if temp_value is not None:
                    merged["temperature_c"] = float(temp_value)
            return merged
        return base_ctx

    # ------------------------------------------------------------------
    # XAI Dispatch Log
    # ------------------------------------------------------------------

    def _print_xai_log(
        self,
        record           : DispatchRecord,
        carbon_intensity : float,
    ) -> None:
        """
        Print a human-readable Explainable AI dispatch log entry to stdout.

        Example output
        --------------
        [DISPATCH] 300 MW MUM->DEL via Nagpur. Cleared at ₹6.00/MW
          (Mumbai Ask: ₹3.00 | Tolls/Loss: ₹3.00 | Carbon Tax: ₹0.00)
          Delhi Bid: ₹15.00 | Surplus: ₹9.00/MW
          LLM Safety Check: APPROVED
          DLR: Applied (effective capacity: 1840.0 MW)
          Green Mode: ON | Seller carbon intensity: 0.40
        """
        surplus = record.buyer_bid - record.cleared_price_mw

        carbon_note = ""
        if self.green_mode:
            carbon_note = (
                f"\n  Green Mode: ON  |  "
                f"Seller {record.seller_city_id} carbon intensity: {carbon_intensity:.2f}  |  "
                f"Carbon Tax applied: ₹{record.carbon_tax:.2f}/MW"
            )

        dlr_note = ""
        if record.dlr_applied:
            dlr_note = (
                f"\n  ⚡ DLR Active — heatwave derating applied  |  "
                f"Effective capacity: {record.effective_capacity:.0f} MW"
            )

        log_line = (
            f"\n{'═'*72}\n"
            f"[DISPATCH] {record.transfer_mw:.0f} MW  "
            f"{record.seller_city_id} → {record.buyer_city_id}  "
            f"via {record.path_description}\n"
            f"  Cleared at  : ₹{record.cleared_price_mw:.2f}/MW\n"
            f"  Cost breakdown: "
            f"{record.seller_city_id} Ask ₹{record.seller_ask:.2f}  +  "
            f"Tolls/Loss ₹{record.path_cost:.2f}  +  "
            f"Carbon Tax ₹{record.carbon_tax:.2f}\n"
            f"  {record.buyer_city_id} Bid : ₹{record.buyer_bid:.2f}/MW  "
            f"(Buyer surplus: ₹{surplus:.2f}/MW)\n"
            f"  LLM Safety Check: APPROVED"
            f"{dlr_note}"
            f"{carbon_note}\n"
            f"{'═'*72}"
        )

        logger.info(log_line)

    def _print_syndicate_log(self, record):
        surplus = record.buyer_bid - record.cleared_price_mw
        node_names = ", ".join(record.syndicate_sellers)

        log_line = (
            f"\n{'═'*72}\n"
            f"[SYNDICATE DISPATCH] {record.transfer_mw:.0f} MW  "
            f"Syndicate({node_names}) → {record.buyer_city_id}\n"
            f"  Cleared at  : ₹{record.cleared_price_mw:.2f}/MW\n"
            f"  Breakdown   : \n    + {record.breakdown_log}\n"
            f"  {record.buyer_city_id} Bid : ₹{record.buyer_bid:.2f}/MW  "
            f"(Buyer surplus: ₹{surplus:.2f}/MW)\n"
            f"  LLM Safety Check: APPROVED (for all legs)\n"
            f"{'═'*72}"
        )
        logger.info(log_line)

    # ------------------------------------------------------------------
    # Grid environment adapters
    # (thin wrappers — change only these when integrating grid_env.py)
    # ------------------------------------------------------------------

    def _get_paths(self, seller_id: str, buyer_id: str) -> list[Any]:
        """
        Retrieve pre-enumerated paths from the GridEnvironment.

        Expects `grid_env.get_paths(seller_id, buyer_id)` to return a list.
        Falls back gracefully if the method is absent (e.g. during unit tests).
        """
        if hasattr(self.grid_env, "get_paths"):
            return self.grid_env.get_paths(seller_id, buyer_id)
        # Fallback for testing — return the mock paths if stored directly
        if hasattr(self.grid_env, "paths"):
            return [
                p for p in self.grid_env.paths
                if getattr(p, "source", None) == seller_id
                and getattr(p, "destination", None) == buyer_id
            ]
        logger.error("[RoutingAgent] GridEnvironment has no get_paths() method.")
        return []

    def _get_llm_context(self, city_id: str) -> dict[str, Any]:
        """
        Retrieve the LLM context dict for a city from the GridEnvironment.

        Expects `grid_env.cities[city_id].llm_context` dict.
        Returns an empty dict on failure so DLR defaults to 0 °C anomaly.
        """
        try:
            return self.grid_env.cities[city_id].llm_context
        except (AttributeError, KeyError, TypeError):
            logger.warning(
                "[RoutingAgent] Could not retrieve LLM context for city '%s'. "
                "DLR will default to 0 °C anomaly.", city_id
            )
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

    def _apply_flow(self, path: Any, transfer_mw: float) -> None:
        """
        Feed executed dispatch back into physical grid state when available.
        This enables congestion/capacity feedback for subsequent trades.
        """
        try:
            if hasattr(self.grid_env, "apply_flow"):
                self.grid_env.apply_flow(path, transfer_mw)
                return
            if hasattr(self.grid_env, "apply_transfer_flow"):
                self.grid_env.apply_transfer_flow(path, transfer_mw)
                return
        except Exception as exc:
            logger.warning(
                "[RoutingAgent] Flow feedback failed for path %s (%.1f MW): %s",
                getattr(path, "description", str(path)),
                transfer_mw,
                exc,
            )
