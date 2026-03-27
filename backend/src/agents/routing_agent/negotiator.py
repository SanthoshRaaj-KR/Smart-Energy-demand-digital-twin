"""
routing_agent/negotiator.py
===========================
LLM-to-LLM Multi-Agent Negotiation (The Decentralized Haggler)

When a buyer's bid is lower than a seller's delivered cost (Ask + Tolls + Carbon Tax),
the RoutingAgent calls this module to simulate a haggling session rather than
outright rejecting the trade.

Two independent LLM calls act as the 'State Agents' arguing their case.
"""

from __future__ import annotations
import logging
from typing import Tuple
from openai import OpenAI

from ..intelligence_agent.setup import LLM_MODEL

logger = logging.getLogger(__name__)


def negotiate_trade(
    buyer_city: str,
    seller_city: str,
    buyer_bid: float,
    seller_ask: float,
    tolls_and_carbon: float,
    buyer_risk: str,
) -> Tuple[bool, float, str]:
    """
    Simulates a 2-turn haggling session using GPT-4o-mini.
    Returns:
        success: bool      - True if an agreement is reached
        final_price: float - The agreed delivered price
        log: str           - The transcript of the negotiation
    """
    client = OpenAI()
    delivered_cost = seller_ask + tolls_and_carbon
    
    # ─── TURN 1: Buyer's Opening Argument ───
    buyer_system = (
        f"You are the grid agent for {buyer_city}. You need power. "
        f"You bid \u20b9{buyer_bid:.2f}/MW, but {seller_city} wants \u20b9{delivered_cost:.2f}/MW "
        f"(including \u20b9{tolls_and_carbon:.2f} in transmission/carbon taxes). "
        f"Your current grid risk level is {buyer_risk}. Haggle for a lower price. "
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
        logger.warning(f"Negotiation failed (Buyer LLM Error): {e}")
        return False, 0.0, ""

    # ─── TURN 2: Seller's Decision ───
    seller_system = (
        f"You are the grid agent for {seller_city}. You have surplus power. "
        f"Your base ask was \u20b9{seller_ask:.2f}/MW. With tolls/taxes (\u20b9{tolls_and_carbon:.2f}), "
        f"the total cost is \u20b9{delivered_cost:.2f}/MW. "
        f"The buyer ({buyer_city}) just said: '{buyer_argument}'\n\n"
        f"Decide whether to accept their counter-offer, compromise, or hold firm at \u20b9{delivered_cost:.2f}. "
        f"You MUST output exactly two lines:\n"
        f"Explanation: <your 1-sentence reasoning>\n"
        f"FinalPrice: <a number>"
    )
    
    try:
        seller_resp = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.3,
            messages=[{"role": "system", "content": seller_system}, {"role": "user", "content": "Respond to the buyer."}]
        )
        seller_reply = seller_resp.choices[0].message.content.strip()
        
        # Parse output
        lines = seller_reply.split('\n')
        final_price = delivered_cost
        for line in lines:
            if line.startswith("FinalPrice:"):
                try:
                    price_str = line.split("FinalPrice:")[1].replace('\u20b9', '').strip()
                    final_price = float(price_str)
                except ValueError:
                    pass
                    
        # If the seller went lower than the buyer's absolute max or buyer's new offer
        # We assume success if the final price is within 20% of the buyer's original bid, 
        # or if the seller dropped their price at all.
        success = final_price <= (buyer_bid * 1.3)
        
        transcript = (
            f"\n    [LLM NEGOTIATION] {buyer_city} vs {seller_city}\n"
            f"    {buyer_city}: {buyer_argument}\n"
            f"    {seller_city}: {lines[0] if len(lines)>0 else seller_reply}\n"
            f"    Result: {'AGREEMENT' if success else 'FAILED'} at \u20b9{final_price:.2f}/MW"
        )
        return success, final_price, transcript
        
    except Exception as e:
        logger.warning(f"Negotiation failed (Seller LLM Error): {e}")
        return False, 0.0, ""
