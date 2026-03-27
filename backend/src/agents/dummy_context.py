"""
dummy_context.py
================
Provides realistic dummy LLM intelligence context for all 5 Indian grid
cities across 3 simulated days.

This replaces the live `intelligence_agent` pipeline so the full agentic
stock-market simulation can run end-to-end without API keys.

Each city-day record mirrors the output shape of the real intelligence agent:
    hoard_flag, demand_spike_risk, temperature_anomaly,
    economic_demand_multiplier, generation_capacity_multiplier
"""

from __future__ import annotations
from typing import Any, Dict, List


# ──────────────────────────────────────────────────────────────────────────
# Dummy context data:  5 cities × 3 days
# ──────────────────────────────────────────────────────────────────────────

DUMMY_CONTEXT: Dict[int, Dict[str, Dict[str, Any]]] = {

    # ── DAY 0: Normal operations, mild Delhi heatwave ─────────────────
    0: {
        "DEL": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "MEDIUM",
            "temperature_anomaly"           : 3.5,
            "economic_demand_multiplier"    : 1.08,
            "generation_capacity_multiplier": 0.97,
            "narrative": "Pre-monsoon heat building. AC load rising. NTPC Dadri Unit 5 on planned maintenance.",
        },
        "MUM": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 1.0,
            "economic_demand_multiplier"    : 0.95,
            "generation_capacity_multiplier": 1.02,
            "narrative": "Comfortable coastal weather. Tata Power surplus from new 500 MW solar farm commissioning.",
        },
        "KOL": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "MEDIUM",
            "temperature_anomaly"           : 2.0,
            "economic_demand_multiplier"    : 1.05,
            "generation_capacity_multiplier": 0.90,
            "narrative": "Humid heat onset. DVC Mejia Unit 3 tripped. Coal stock at 4-day cover — below comfortable margin.",
        },
        "CHE": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 0.5,
            "economic_demand_multiplier"    : 0.92,
            "generation_capacity_multiplier": 1.05,
            "narrative": "Strong NE monsoon tail — wind generation at 110% of seasonal average. TANGEDCO exporting surplus.",
        },
        "NAG": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 2.5,
            "economic_demand_multiplier"    : 1.00,
            "generation_capacity_multiplier": 1.00,
            "narrative": "Nagpur hub stable. WCL coal dispatch normal. Koradi units all online.",
        },
    },

    # ── DAY 1: IPL Final in Delhi — PANIC scenario ───────────────────
    1: {
        "DEL": {
            "hoard_flag"                    : True,
            "demand_spike_risk"             : "CRITICAL",
            "temperature_anomaly"           : 5.2,
            "economic_demand_multiplier"    : 1.35,
            "generation_capacity_multiplier": 0.93,
            "narrative": "IPL Final at Feroz Shah Kotla — TV pickup + stadium floodlights. 45°C heatwave. BSES warns of rolling shortages.",
        },
        "MUM": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "MEDIUM",
            "temperature_anomaly"           : 2.0,
            "economic_demand_multiplier"    : 1.10,
            "generation_capacity_multiplier": 1.00,
            "narrative": "TV viewership spike for IPL Final. Normal generation. Some AC load increase.",
        },
        "KOL": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "HIGH",
            "temperature_anomaly"           : 3.8,
            "economic_demand_multiplier"    : 1.15,
            "generation_capacity_multiplier": 0.85,
            "narrative": "Coal shortage worsens. DVC forced outage now 3 units. Heat index 48°C. TV pickup load on top.",
        },
        "CHE": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 1.0,
            "economic_demand_multiplier"    : 0.98,
            "generation_capacity_multiplier": 1.08,
            "narrative": "Wind output elevated. Comfortable temperatures. Chennai positioned as net exporter.",
        },
        "NAG": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "MEDIUM",
            "temperature_anomaly"           : 4.0,
            "economic_demand_multiplier"    : 1.02,
            "generation_capacity_multiplier": 0.95,
            "narrative": "Extreme heat reducing Koradi Unit 6 output (cooling water temp high). Hub transit demand normal.",
        },
    },

    # ── DAY 2: Post-event recovery, Kolkata bandh ────────────────────
    2: {
        "DEL": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "MEDIUM",
            "temperature_anomaly"           : 4.0,
            "economic_demand_multiplier"    : 1.12,
            "generation_capacity_multiplier": 0.95,
            "narrative": "Post-IPL demand normalising. Heatwave persists but cooling slightly. NTPC Dadri back online.",
        },
        "MUM": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 1.5,
            "economic_demand_multiplier"    : 0.98,
            "generation_capacity_multiplier": 1.03,
            "narrative": "Normal coastal operations. Adani Electricity commissioning 200 MW gas peaker.",
        },
        "KOL": {
            "hoard_flag"                    : True,
            "demand_spike_risk"             : "CRITICAL",
            "temperature_anomaly"           : 2.5,
            "economic_demand_multiplier"    : 0.70,
            "generation_capacity_multiplier": 0.80,
            "narrative": "State-wide bandh called. Industrial load collapsed. But DVC coal crisis deepens—only 2-day stock. Hospitals on backup.",
        },
        "CHE": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 0.8,
            "economic_demand_multiplier"    : 1.00,
            "generation_capacity_multiplier": 1.06,
            "narrative": "Stable. Wind tapering but solar strong. TANGEDCO grid-balanced.",
        },
        "NAG": {
            "hoard_flag"                    : False,
            "demand_spike_risk"             : "LOW",
            "temperature_anomaly"           : 3.0,
            "economic_demand_multiplier"    : 1.00,
            "generation_capacity_multiplier": 0.98,
            "narrative": "Koradi Unit 6 back to 80% capacity. Hub congestion easing from yesterday's peak.",
        },
    },
}


def get_context_for_day(day: int) -> Dict[str, Dict[str, Any]]:
    """Return the dummy LLM context dict for a given simulation day."""
    if day not in DUMMY_CONTEXT:
        raise ValueError(f"No dummy context for day {day}. Available: {list(DUMMY_CONTEXT.keys())}")
    return DUMMY_CONTEXT[day]


def get_all_city_ids() -> List[str]:
    """Return all city IDs that have dummy context data."""
    return list(DUMMY_CONTEXT[0].keys())
