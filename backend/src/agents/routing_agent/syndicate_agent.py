"""
syndicate_agent.py
==================
Syndicate Broker Agent (Surplus Sharing).

Evaluates whether multiple sellers can pool their surplus to fulfill a single
buyer's order as a unified block. By blending a cheap seller's power with
an expensive seller's power, a Syndicate can achieve a weighted-average
delivered cost that clears the buyer's bid, avoiding failed standalone trades.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Tuple
from openai import OpenAI

from ..shared.models import DispatchRecord
from .llm_safety_stub import verify_route_safety_with_llm
from ..intelligence_agent.setup import LLM_MODEL

logger = logging.getLogger(__name__)

@dataclass
class SyndicateLeg:
    seller: Any
    transfer_mw: float
    path: Any
    path_cost: float
    carbon_tax: float
    seller_ask: float
    dlr_applied: bool
    effective_capacity: float
    selected_hour: int


def negotiate_syndicate_trade(
    buyer_city: str,
    syndicate_cities: list[str],
    buyer_bid: float,
    blended_ask: float,
    buyer_risk: str,
) -> Tuple[bool, float, str]:
    """
    Simulates a 2-turn haggling session where a Syndicate of sellers
    negotiates collectively against a Buyer using GPT-4o-mini.
    """
    client = OpenAI()
    syndicate_names = ", ".join(syndicate_cities)

    # ─── TURN 1: Buyer's Opening Argument ───
    buyer_system = (
        f"You are the grid agent for {buyer_city}. You need a massive block of power. "
        f"You bid \u20b9{buyer_bid:.2f}/MW. A syndicate of sellers ({syndicate_names}) "
        f"is offering the block at a blended price of \u20b9{blended_ask:.2f}/MW "
        f"(including transmission/carbon taxes). "
        f"Your current grid risk level is {buyer_risk}. Haggle for a lower price from the syndicate. "
        f"Make an emotional or logical argument in 2-3 sentences. End with a specific counter-offer \u20b9X/MW."
    )

    try:
        buyer_resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.7,
            messages=[{"role": "system", "content": buyer_system}, {"role": "user", "content": "Start the negotiation."}]
        )
        buyer_argument = buyer_resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Syndicate Negotiation failed (Buyer Error): {e}")
        return False, 0.0, ""

    # ─── TURN 2: Syndicate's Decision ───
    seller_system = (
        f"You represent a Syndicate of grid agents ({syndicate_names}) pooling surplus power. "
        f"Your blended minimum viable cost is \u20b9{blended_ask:.2f}/MW. "
        f"The buyer ({buyer_city}) just pleaded: '{buyer_argument}'\n\n"
        f"Decide whether the syndicate should accept their counter-offer, compromise, or hold firm at \u20b9{blended_ask:.2f}. "
        f"You MUST output exactly two lines:\n"
        f"Explanation: <your 1-sentence reasoning>\n"
        f"FinalPrice: <a number>"
    )

    try:
        seller_resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.3,
            messages=[{"role": "system", "content": seller_system}, {"role": "user", "content": "Respond to the buyer on behalf of the syndicate."}]
        )
        seller_reply = seller_resp.choices[0].message.content.strip()

        # Parse output
        lines = seller_reply.split('\n')
        final_price = blended_ask
        for line in lines:
            if line.startswith("FinalPrice:"):
                try:
                    price_str = line.split("FinalPrice:")[1].replace('\u20b9', '').strip()
                    final_price = float(price_str)
                except ValueError:
                    pass

        success = final_price <= (buyer_bid * 1.3)
        transcript = (
            f"\n    [SYNDICATE NEGOTIATION] {buyer_city} vs Syndicate({syndicate_names})\n"
            f"    {buyer_city}: {buyer_argument}\n"
            f"    Syndicate: {lines[0] if len(lines)>0 else seller_reply}\n"
            f"    Result: {'AGREEMENT' if success else 'FAILED'} at \u20b9{final_price:.2f}/MW"
        )
        return success, final_price, transcript

    except Exception as e:
        logger.warning(f"Syndicate Negotiation failed (Syndicate Error): {e}")
        return False, 0.0, ""

class SyndicateBroker:
    """
    Evaluates groups of sellers to fulfill a single large buyer order.
    """
    def __init__(self, routing_agent):
        """We hold a reference to RoutingAgent to score paths and apply DLR."""
        self.ra = routing_agent

    def attempt_syndicate_trade(
        self,
        buyer,            # _ActiveOrder
        sell_queue,       # list[_ActiveOrder]
        hour_index: int | None,
        day_index: int
    ) -> Any:
        """
        Attempts to fulfill the buyer's remaining_mw using a pool of top sellers.
        Returns a DispatchRecord (or SyndicateDispatchRecord) if successful.
        """
        if buyer.remaining_mw <= 0:
            return None

        # Filter and sort viable sellers
        viable_sellers = [s for s in sell_queue if s.remaining_mw > 0]
        if len(viable_sellers) < 2:
            return None # Need at least 2 for a syndicate

        # Distribute buyer's demand across top cheap sellers
        target_mw = buyer.remaining_mw
        pool = []
        total_mw_found = 0.0
        
        # We need to compute path costs and DLR for each potential leg
        for seller in viable_sellers:
            # Reusing routing_agent's internal private methods carefully
            paths = self.ra._get_paths(seller.city_id, buyer.city_id)
            if not paths:
                continue

            src_ctx_raw  = self.ra._get_llm_context(seller.city_id)
            dest_ctx_raw = self.ra._get_llm_context(buyer.city_id)
            city_contexts = self.ra._all_city_contexts()
            buyer_risk = str(dest_ctx_raw.get("demand_spike_risk", "LOW"))

            selected_hour = hour_index
            if selected_hour is None:
                selected_hour = self.ra._dispatch_window_agent.best_dispatch_hour(
                    paths, day_index, city_contexts, buyer_risk
                )

            src_ctx = self.ra._resolve_hourly_context(src_ctx_raw, selected_hour)
            dest_ctx = self.ra._resolve_hourly_context(dest_ctx_raw, selected_hour)

            carbon_tax, _ = self.ra._path_climate_agent.__module__ == 'dummy' and (0,0) or __import__('src.agents.routing_agent.carbon_tariff', fromlist=['']).calculate_carbon_tax(seller.city_id, self.ra.green_mode)

            scored_paths = sorted(
                paths,
                key=lambda p: self.ra._route_score_agent.score(
                    path=p,
                    path_temp_c=self.ra._path_climate_agent.path_temp_c(p, selected_hour or 0, city_contexts),
                    carbon_tax=carbon_tax,
                ),
            )

            for path in scored_paths:
                effective_cap, dlr_applied = __import__('src.agents.routing_agent.dlr_calculator', fromlist=['']).calculate_effective_capacity(path, src_ctx, dest_ctx)
                leg_mw = min(seller.remaining_mw, target_mw - total_mw_found, effective_cap)
                
                if leg_mw <= 0:
                    continue

                approved, _ = verify_route_safety_with_llm(path)
                if not approved:
                    continue

                pool.append(SyndicateLeg(
                    seller=seller,
                    transfer_mw=leg_mw,
                    path=path,
                    path_cost=float(path.total_cost()),
                    carbon_tax=carbon_tax,
                    seller_ask=seller.price_per_mw,
                    dlr_applied=dlr_applied,
                    effective_capacity=effective_cap,
                    selected_hour=selected_hour
                ))
                total_mw_found += leg_mw
                break # Just take best path for this seller

            if total_mw_found >= target_mw:
                break

        if len(pool) < 2:
            return None # Not enough participants to form a syndicate

        # Pool assembled. Calculate blended delivered cost.
        total_delivered_cost = 0.0
        for leg in pool:
            leg_delivered = leg.seller_ask + leg.path_cost + leg.carbon_tax
            total_delivered_cost += (leg_delivered * leg.transfer_mw)
        
        blended_ask = total_delivered_cost / total_mw_found

        if buyer.price_per_mw < blended_ask:
            # Haggle!
            dest_ctx_raw = self.ra._get_llm_context(buyer.city_id)
            buyer_risk = str(dest_ctx_raw.get("demand_spike_risk", "UNKNOWN"))
            syndicate_cities = [leg.seller.city_id for leg in pool]

            success, new_price, transcript = negotiate_syndicate_trade(
                buyer.city_id, syndicate_cities, buyer.price_per_mw, blended_ask, buyer_risk
            )

            if not success:
                logger.debug(f"[Syndicate] Failed to negotiate {buyer.city_id} block.")
                return None
            
            blended_ask = new_price
            print(transcript)

        # Execution
        breakdown_lines = []
        for leg in pool:
            self.ra._apply_flow(leg.path, leg.transfer_mw)
            leg.seller.remaining_mw -= leg.transfer_mw
            buyer.remaining_mw      -= leg.transfer_mw
            breakdown_lines.append(f"{leg.transfer_mw:.0f} MW from {leg.seller.city_id} @ \u20b9{leg.seller_ask:.2f} (Path: {getattr(leg.path, 'description', str(leg.path))})")

        from ..shared.models import SyndicateDispatchRecord
        
        record = SyndicateDispatchRecord(
            buyer_city_id=buyer.city_id,
            transfer_mw=total_mw_found,
            cleared_price_mw=blended_ask,
            buyer_bid=buyer.price_per_mw,
            syndicate_sellers=[leg.seller.city_id for leg in pool],
            breakdown_log="\n    + ".join(breakdown_lines)
        )
        return record
