"""
impact_narrator_agent.py
========================
Phase 3B — Impact Narrator Agent

SINGLE RESPONSIBILITY:
  Write a detailed, quantified narrative of expected electricity demand and
  supply dynamics for the next 7 days, synthesising weather, events, and
  extracted signals into an operator-ready assessment.

WHY THIS AGENT EXISTS SEPARATELY:
  This is the 'thinking aloud' step. A long-form reasoning narrative
  dramatically improves the accuracy of the numeric multipliers produced
  by MultiplierSynthAgent (Chain-of-Thought in practice). Collapsing 3B
  and 3C into one call forces the LLM to simultaneously reason AND produce
  numbers — accuracy degrades. Keeping them separate makes the chain
  explicit and auditable.

WHAT IT RECEIVES (NOT RAW HEADLINES):
  This agent never sees raw headlines. It receives curated, structured
  inputs only: extracted signals (from SignalExtractor), detected events
  (from EventRadar), and weather data. This keeps the context tight and
  forces each upstream agent to do its job well.

PIPELINE POSITION:
  Input  ← CityIntelligence + extracted signals + detected events + weather
  Output → Narrative string consumed by MultiplierSynthAgent.
  The narrative is also stored in NodeResult.impact_narrative for audit.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, List

from .base_agent import BaseLLMAgent
from .setup import CityIntelligence, DetectedEvent


class ImpactNarratorAgent(BaseLLMAgent):
    """
    Produces a structured expert narrative for the next 7-day demand/supply
    window, ready to be quantified by MultiplierSynthAgent.
    """

    AGENT_ROLE = "ImpactNarratorAgent"

    def deep_impact_analysis(
        self,
        city_name  : str,
        reg        : Dict[str, Any],
        intel      : CityIntelligence,
        signals    : str,
        weather    : Dict[str, Any],
        events     : List[DetectedEvent],
    ) -> str:
        """
        Parameters
        ----------
        city_name : Human-readable city name
        reg       : City registry entry (typical_peak_mw, discoms, state)
        intel     : Populated CityIntelligence profile
        signals   : Bullet-list output from SignalExtractorAgent
        weather   : OWM raw weather dict with 5_day_forecast etc.
        events    : List from EventRadarAgent

        Returns
        -------
        Multi-section narrative string — plain text, for audit and feeding
        directly into MultiplierSynthAgent.
        """
        event_block = (
            "\n".join(
                f"  [{e.event_type.upper()} / {e.grid_mechanism}] "
                f"{e.event_name} @ {e.location} | {e.dates} "
                f"({e.days_away}d away) | est. {e.est_mw_impact} "
                f"| confidence={e.confidence}"
                for e in events
            )
            if events
            else "  No electricity-impacting events detected in the next 7 days."
        )

        system = textwrap.dedent(f"""
            You are a load forecasting expert at {reg['state']}'s State Electricity
            Board, responsible for {city_name}'s grid.

            ── YOUR ROLE IN THE PIPELINE ──────────────────────────────────────────
            You are Agent 4 of 5 in the India Grid Intelligence Pipeline.

            You receive STRUCTURED INTELLIGENCE already curated by upstream agents:
              • Extracted grid signals  (from SignalExtractorAgent)
              • Detected demand events  (from EventRadarAgent)
              • City infrastructure profile (from CityIntelAgent)
              • Live weather forecast   (from OpenWeatherMap API)

            Your output — this narrative — goes directly into MultiplierSynthAgent,
            which will convert your expert reasoning into precise numeric multipliers
            for the grid simulation. The numbers agent cannot reason from scratch;
            it depends entirely on the quality of YOUR narrative. Be the expert.

            ── WHAT A HIGH-QUALITY NARRATIVE LOOKS LIKE ───────────────────────────
            Quantify wherever possible:
              Good: "Heatwave pushing peak demand 12–18% above baseline, adding
                     ~950 MW to {city_name}'s peak, primarily after 14:00."
              Bad : "High temperatures may increase demand."

            Identify compound risk:
              Good: "Plant trip + event spike on same day = potential 8% shortfall
                     with no headroom for unscheduled import."
              Bad : "There are risks on both supply and demand sides."

            Give a clear pre-event hoarding judgement:
              Good: "HOARD: YES — IPL semi-final in 2 days, supply at 95% capacity
                     margin. Recommend pre-booking 200 MW from NTPC pool."
              Bad : "Hoarding may be advisable."

            ── OUTPUT STRUCTURE ───────────────────────────────────────────────────
            Write exactly these 5 sections. No extra sections.

            ## 1. DEMAND OUTLOOK (next 7 days)
            - AC / cooling load driven by temperature forecast
            - Event-driven demand (directly from EventRadar data above)
            - Industrial and commercial activity changes
            - Behavioural shifts (WFH, extended hours, etc.)

            ## 2. SUPPLY OUTLOOK (next 7 days)
            - Generation plant health and expected output
            - Fuel stock levels and delivery pipeline
            - Renewable availability (solar/wind/hydro seasonality)
            - Cross-state import/export position

            ## 3. LOGISTICS RISK
            - Coal / gas delivery risk assessment
            - Rail, road, port, or waterway chokepoints currently in play

            ## 4. RISK FLAGS (deviations >5% from normal baseline)
            - Quantify each risk as a % or MW delta

            ## 5. PRE-EVENT HOARDING RECOMMENDATION
            - Clear YES/NO decision with MW quantum and rationale
        """).strip()

        context = textwrap.dedent(f"""
            CITY: {city_name} ({reg['state']})
            TYPICAL PEAK: ~{reg['typical_peak_mw']} MW
            DISCOMs: {', '.join(reg.get('primary_discom', []))}
            GENERATION MIX: {intel.generation_mix}

            KEY VULNERABILITIES:
            {chr(10).join(f"  • {v}" for v in intel.key_vulnerabilities)}

            SEASONAL DEMAND FACTORS:
            {chr(10).join(f"  • {s}" for s in intel.seasonal_demand_factors)}

            EXTRACTED GRID SIGNALS (from SignalExtractorAgent):
            {signals}

            DETECTED EVENTS (from EventRadarAgent):
            {event_block}

            WEATHER FORECAST (5-day from OWM):
            {json.dumps(weather.get('5_day_forecast', []), indent=2)}
            Week Max Temp      : {weather.get('week_max_c')}°C
            Week Max Heat Index: {weather.get('week_max_heat_index_c')}°C
            Week Total Rain    : {weather.get('week_total_rain_mm')} mm
        """).strip()

        return self._chat(system, context, city_name, temp=0.12)
