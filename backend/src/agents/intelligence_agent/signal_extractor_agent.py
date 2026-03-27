"""
signal_extractor_agent.py
=========================
Phase 5 — Signal Extractor Agent

SINGLE RESPONSIBILITY:
  Given NOISE-FILTERED headlines AND the city intelligence profile, extract
  ONLY the headlines that have a direct causal path to electricity supply or
  demand within the next 7 days. Annotate each retained signal.

WHY THIS AGENT EXISTS SEPARATELY:
  Signal extraction is fundamentally different from event detection (Phase 3).
  EventRadarAgent hunts for mass-behaviour triggers (crowds, broadcasts).
  This agent hunts for infrastructure and supply-chain facts: power plant
  trips, coal train derailments, reservoir levels, factory shutdowns.
  Both need the same headlines but use completely different reasoning frames —
  keeping them separate prevents context contamination.

WHY IT NEEDS CITY INTEL AS INPUT:
  Without knowing that Bihar's coal comes from Jharkhand mines via the
  Central Railway, a derailment headline 200 km away looks unrelated.
  With city intel, the agent can make that causal link precisely.

PIPELINE POSITION:
  Input  ← noise-filtered headlines + CityIntelligence profile
  Output → structured bullet-list string consumed by ImpactNarratorAgent.
  The narrator will NOT re-read the raw headlines — only your extracted
  signals. Signal quality directly sets the ceiling of forecast accuracy.
"""

from __future__ import annotations

import textwrap
from typing import List

from .base_agent import BaseLLMAgent
from .setup import CityIntelligence, MAX_HEADLINES_TO_LLM


class SignalExtractorAgent(BaseLLMAgent):
    """
    Filters the headline firehose to grid-relevant supply/demand signals,
    annotating each with its causal mechanism.
    """

    AGENT_ROLE = "SignalExtractorAgent"

    def extract_grid_signals(
        self,
        city_name    : str,
        intel        : CityIntelligence,
        all_headlines: List[str],
    ) -> str:
        """
        Parameters
        ----------
        city_name     : Human-readable city name
        intel         : The fully populated CityIntelligence for this city
        all_headlines : Noise-filtered deduplicated headlines

        Returns
        -------
        A structured bullet-list string, one signal per line.
        Returns "NO GRID-RELEVANT SIGNALS DETECTED." if nothing qualifies.
        """
        vuln_block   = "\n".join(f"  • {v}" for v in intel.key_vulnerabilities)
        fuel_block   = "\n".join(f"  • {s}" for s in intel.primary_fuel_sources)
        route_block  = "\n".join(f"  • {r}" for r in intel.fuel_supply_routes)
        driver_block = "\n".join(f"  • {d}" for d in intel.demand_drivers)

        system = textwrap.dedent(f"""
            You are a senior power-systems analyst at POSOCO — India's national
            grid operator — responsible for {city_name}.

            ── YOUR ROLE IN THE PIPELINE ──────────────────────────────────────────
            You are Agent 5 in the India Grid Intelligence Pipeline.
            You have already received clean, NOISE-FREE headlines from the FilterAgent.
            second layer of filtering: drop anything that lacks a causal path
            to electricity supply or demand.

            Your output (a structured signal list) goes DIRECTLY into the
            ImpactNarratorAgent, which will write the full demand/supply
            outlook for grid operators. The narrator will NOT re-read the
            raw headlines — only your extracted signals. So:
              → If you miss a signal, the narrator will miss it too.
              → If you include a non-signal, the narrator will waste context
                writing about something irrelevant.

            ── CITY INTELLIGENCE CONTEXT ──────────────────────────────────────────
            Use this specific knowledge to make causality judgments.

            City: {city_name} | Peak load: ~{intel.generation_mix}

            Known vulnerabilities (headline ↔ vulnerability matches = HIGH priority):
            {vuln_block}

            Primary fuel sources (disruptions here = supply risk):
            {fuel_block}

            Fuel delivery routes (disruptions here = logistics risk):
            {route_block}

            Key demand drivers (shutdowns/openings here = demand shift):
            {driver_block}

            ── EXTRACTION RULES ───────────────────────────────────────────────────
            EXTRACT and annotate these signal types:
              [WEATHER]     Cyclone, heatwave, fog, flood, extreme cold
              [FUEL-SUPPLY] Coal/gas/oil supply chain events — strikes, derailments,
                            port congestion, import delays, price shocks
              [PLANT]       Power plant trip, forced outage, new commissioning,
                            explosion, fire, maintenance unit offline
              [INDUSTRIAL]  Factory opening/shutdown, large industrial load change,
                            labour dispute at MW-scale facility  
              [LOGISTICS]   Rail, road, port, waterway disruption affecting fuel delivery
              [HYDRO]       Reservoir levels, river flow, dam releases
              [GRID-EVENT]  Frequency excursion, transformer failure, transmission
                            line outage, substation fire
              [POLICY]      GRAP restrictions, load-shedding orders, cross-state
                            power purchase agreements, regulatory orders

            DISCARD these:
              ✗ Pure political speeches or court verdicts with no grid impact
              ✗ Crime or accidents unless grid infrastructure is directly damaged
              ✗ Celebrity, entertainment, routine sports results
              ✗ Business news with no heavy-industry or energy angle
              ✗ Events already flagged by Event Radar (mass gatherings, broadcasts)
                — those are handled separately; do not duplicate them here

            ── OUTPUT FORMAT ──────────────────────────────────────────────────────
            One signal per bullet line. No prose introduction.
            Format: [TYPE] Signal description — causal link to grid supply/demand

            Example:
              [FUEL-SUPPLY] Coal rake delays at Vizag port — Simhadri STPP may
                            face 3-day fuel buffer crunch, ~400 MW at risk.
              [WEATHER] IMD warns of heatwave (42°C+) in {city_name} next 3 days
                        — AC load could jump 12–18% above seasonal norm.

            If nothing qualifies: output exactly "NO GRID-RELEVANT SIGNALS DETECTED."
        """).strip()

        news_block = "\n".join(f"- {h}" for h in all_headlines[:MAX_HEADLINES_TO_LLM])
        return self._chat(
            system,
            f"CLEAN HEADLINES (noise-filtered by previous agent):\n{news_block}",
            city_name,
            temp=0.05,
        )
