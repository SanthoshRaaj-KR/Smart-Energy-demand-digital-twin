"""
routing_agent/dlr_calculator.py
================================
Dynamic Line Rating (DLR) — weather-aware physical capacity reduction.

Physics Background
------------------
Overhead transmission conductors lose current-carrying capacity (ampacity)
as ambient temperature rises.  In the India Grid Digital Twin we model this
as a simple linear derating: each +1 °C of *temperature_anomaly* (the
deviation from the seasonal baseline, as reported in the LLM context JSON)
reduces the cable's nameplate `bottleneck_capacity` by `DLR_REDUCTION_PER_DEGREE`.

Formula
-------
    effective_capacity = bottleneck_capacity
                         × (1 - DLR_REDUCTION_PER_DEGREE × max(anomaly, 0))

where `anomaly` is the *maximum* temperature anomaly across the source and
destination cities.  We take the maximum because the hottest point on the
corridor sets the binding constraint.

Negative anomalies (colder-than-normal weather) are clamped to 0 — we do
not model capacity *increases* from cold weather to stay conservative.

Why a separate module?
----------------------
Keeps the physics formula isolated so it can be unit-tested and tuned
independently of market-clearing logic.
"""

from __future__ import annotations
import logging
from typing import Any

from ..shared.constants import DLR_REDUCTION_PER_DEGREE

logger = logging.getLogger(__name__)


def calculate_effective_capacity(
    path               : Any,
    source_llm_context : dict[str, Any],
    dest_llm_context   : dict[str, Any],
) -> tuple[float, bool]:
    """
    Compute the weather-derated effective capacity of a transmission path.

    Parameters
    ----------
    path               : Path object from grid_env.py.
                         Must expose `path.bottleneck_capacity` (float, MW).
    source_llm_context : LLM context dict for the selling city.
    dest_llm_context   : LLM context dict for the buying city.

    Returns
    -------
    effective_capacity : float  — MW capacity after DLR adjustment.
    dlr_applied        : bool   — True if any derating was applied.
    """
    nameplate: float = float(path.bottleneck_capacity)

    # Extract temperature anomalies (default 0.0 if key absent)
    src_anomaly  = float(source_llm_context.get("temperature_anomaly", 0.0))
    dest_anomaly = float(dest_llm_context.get("temperature_anomaly", 0.0))

    # Conservative: use the hotter end of the corridor
    worst_anomaly = max(src_anomaly, dest_anomaly, 0.0)   # clamp negatives to 0

    if worst_anomaly == 0.0:
        logger.debug(
            "[DLR] No thermal derating — anomaly=0 °C on path %s",
            getattr(path, "description", str(path)),
        )
        return nameplate, False

    derating_factor   = 1.0 - DLR_REDUCTION_PER_DEGREE * worst_anomaly
    # Clamp so capacity never goes below 0
    derating_factor   = max(derating_factor, 0.0)
    effective_capacity = nameplate * derating_factor

    logger.info(
        "[DLR] Path %s: %.0f MW → %.0f MW (anomaly=+%.1f°C, factor=%.4f)",
        getattr(path, "description", str(path)),
        nameplate,
        effective_capacity,
        worst_anomaly,
        derating_factor,
    )

    return effective_capacity, True