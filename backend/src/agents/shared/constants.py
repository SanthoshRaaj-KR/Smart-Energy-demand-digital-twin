"""
shared/constants.py
===================
All tunable financial and physical constants in one place.
Change a value here and every agent picks it up automatically.
"""

# ---------------------------------------------------------------------------
# Pricing constants  (₹ / MW)
# ---------------------------------------------------------------------------
BASELINE_ASK_PRICE      = 3.0    # Normal seller ask
DISTRESSED_ASK_PRICE    = 1.5    # Seller ask when battery SoC > 90% (must offload)
BASELINE_BID_PRICE      = 5.0    # Normal buyer bid
PANIC_BID_PRICE         = 15.0   # Buyer bid when hoard_flag or CRITICAL risk

# Battery state-of-charge threshold above which seller is desperate to offload
BATTERY_FULL_SOC_THRESHOLD = 90.0   # percent

# ---------------------------------------------------------------------------
# Carbon / Green-mode constants  (₹ / MW)
# ---------------------------------------------------------------------------
CARBON_TAX_RATE = 5.0   # ₹ per MW per unit of carbon_intensity (0-1 scale)

# Mock carbon intensity scores per city (0 = pure green, 1 = pure coal)
CARBON_INTENSITY: dict[str, float] = {
    "UP": 0.8,    # Heavy coal
    "BHR": 0.85,  # Heavy coal
    "WB": 0.9,    # Heavy coal
    "KAR": 0.3,   # Heavy renewables (hydro, solar, wind)
}
DEFAULT_CARBON_INTENSITY = 0.5   # Used if a city has no entry above

# ---------------------------------------------------------------------------
# Dynamic Line Rating (DLR) constants
# ---------------------------------------------------------------------------
# For every +1 °C of temperature_anomaly, capacity is reduced by this fraction.
DLR_REDUCTION_PER_DEGREE = 0.02    # 2% per °C above baseline

# ---------------------------------------------------------------------------
# LLM safety check mock constants
# ---------------------------------------------------------------------------
LLM_APPROVAL_PROBABILITY = 0.90    # 90% chance of approval