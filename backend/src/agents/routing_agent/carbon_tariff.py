"""
routing_agent/carbon_tariff.py
================================
Green Priority Routing — carbon intensity penalty for fossil-heavy sellers.

Economic Rationale
------------------
When `green_mode = True` the RoutingAgent adds a *Carbon Tax* to the
delivered cost of power sourced from carbon-intensive cities.  This makes
dirty power (Kolkata, coal-heavy) appear more expensive than it actually is,
so the market naturally routes purchases toward cleaner sources (Chennai,
wind/solar) even when the raw ask price would otherwise favour the dirty
seller.

Formula
-------
    carbon_tax_₹ = carbon_intensity × CARBON_TAX_RATE
    delivered_cost = seller_ask + path_cost + carbon_tax_₹

where `carbon_intensity` ∈ [0.0, 1.0] is a per-city score
(see `shared/constants.py`) and `CARBON_TAX_RATE` is ₹5/MW.

Example
-------
    KOL intensity = 0.9  →  tax = 0.9 × 5 = ₹4.5/MW
    CHE intensity = 0.2  →  tax = 0.2 × 5 = ₹1.0/MW

    A Chennai ask of ₹3/MW delivers at ₹3 + path + ₹1 = ₹4 + path
    A Kolkata ask of ₹3/MW delivers at ₹3 + path + ₹4.5 = ₹7.5 + path

    → Chennai wins even at the same raw ask price.

Why a separate module?
----------------------
Keeps tariff logic testable and swappable for a dynamic pricing policy
(e.g. real-time CERC carbon intensity certificates) without touching
market-clearing code.
"""

from __future__ import annotations
import logging

from ..shared.constants import CARBON_TAX_RATE, CARBON_INTENSITY, DEFAULT_CARBON_INTENSITY

logger = logging.getLogger(__name__)


def get_carbon_intensity(city_id: str) -> float:
    """
    Return the carbon intensity score (0.0–1.0) for a city.
    Falls back to DEFAULT_CARBON_INTENSITY for unknown cities.
    """
    intensity = CARBON_INTENSITY.get(city_id, DEFAULT_CARBON_INTENSITY)
    if city_id not in CARBON_INTENSITY:
        logger.warning(
            "[CARBON] Unknown city '%s' — using default intensity %.2f",
            city_id, DEFAULT_CARBON_INTENSITY,
        )
    return intensity


def calculate_carbon_tax(seller_city_id: str, green_mode: bool) -> tuple[float, float]:
    """
    Calculate the per-MW carbon tax for a given seller.

    Parameters
    ----------
    seller_city_id : City ID of the seller (e.g. "KOL").
    green_mode     : If False, returns (0.0, 0.0) immediately — no penalty.

    Returns
    -------
    carbon_tax_per_mw : float  — ₹/MW added to delivered cost.
    carbon_intensity  : float  — Raw intensity score (logged in dispatch).
    """
    if not green_mode:
        return 0.0, 0.0

    intensity     = get_carbon_intensity(seller_city_id)
    tax_per_mw    = intensity * CARBON_TAX_RATE

    logger.debug(
        "[CARBON] Seller %s intensity=%.2f → carbon tax ₹%.2f/MW",
        seller_city_id, intensity, tax_per_mw,
    )

    return tax_per_mw, intensity