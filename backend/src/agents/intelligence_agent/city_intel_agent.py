"""
city_intel_agent.py
===================
Phase 2 — City Intelligence Agent

SINGLE RESPONSIBILITY:
  Given RAW, UNFILTERED recent news headlines for a city, produce a richly 
  structured CityIntelligence profile that captures:
    - Current generation mix & fuel sources
    - Physical supply-chain routes
    - Known vulnerability points
    - Seasonal demand patterns & key load drivers
    - Cross-border power exchange corridors

WHY THIS AGENT EXISTS SEPARATELY AND READS RAW NEWS:
  City intelligence is a slow-changing, cacheable asset (7-day TTL).
  It reads RAW news before the noise filter because sometimes local 
  infrastructure clues are buried in "business" or "political" news that 
  a filter might aggressively drop.
  It must NOT be polluted by today's event headlines or live weather —
  those come later. A focused prompt here produces sharper, more specific
  city profiles than if the LLM were simultaneously thinking about events.

PIPELINE POSITION:
  Output → feeds into SignalExtractorAgent (as city context window) and
           ImpactNarratorAgent (as structural background).
  The orchestrator will skip this agent entirely if a fresh cache hit exists.
"""

from __future__ import annotations

import json
import textwrap
from datetime import date
from typing import Any, Dict, List

from .base_agent import BaseLLMAgent
from .setup import CityIntelligence, MAX_HEADLINES_TO_LLM


class CityIntelAgent(BaseLLMAgent):
    """
    Constructs a structured, LLM-generated intelligence profile for a city's
    power grid. Designed to be called cold (cache miss) and saved with a TTL.

    What it knows about the future:
      Its output is the 'ground truth context' that 3 downstream agents
      (SignalExtractor, ImpactNarrator, MultiplierSynth) will all reference.
      Accuracy and specificity here multiplies downstream quality — vague
      profiles produce vague forecasts.
    """

    AGENT_ROLE = "CityIntelAgent"

    def build_city_intelligence(
        self,
        node_id  : str,
        reg      : Dict[str, Any],
        headlines: List[str],
    ) -> CityIntelligence:
        """
        Parameters
        ----------
        node_id   : Registry key (e.g. "DEL", "MUM")
        reg       : City registry entry from CITY_REGISTRY
        headlines : RAW, UNFILTERED recent news headlines for this city

        Returns
        -------
        CityIntelligence dataclass — serialisable, cacheable, TTL-aware.
        """
        system = textwrap.dedent(f"""
            You are an expert Indian power system analyst with deep knowledge of
            {reg['name']}, {reg['state']}.

            ── YOUR ROLE IN THE PIPELINE ──────────────────────────────────────────
            You are Agent 2 in the India Grid Intelligence Pipeline.
            IMPORTANT: You are receiving RAW, UNFILTERED headlines. There will be 
            some noise. Ignore the noise and extract only structural grid facts.
            Your output is a structured city profile that 3 downstream agents
            will use as their core context. Think of it as building the 'city
            knowledge base' that everything else references.

            Downstream agents who will read your output NEED to know:
              ① Which specific power plants exist and their typical reliability
              ② Named coal mines, gas sources, import corridors (not generic)
              ③ Physical chokepoints: rail sidings, ports, substations
              ④ What makes THIS city's grid distinctly fragile vs resilient
              ⑤ Which industries drive peak load and when
              ⑥ How neighbouring states transfer power in/out

            ── QUALITY RULES ──────────────────────────────────────────────────────
            SPECIFICITY OVER GENERICS:
              Bad : "Coal shortage is a risk"
              Good: "WCL Wardha mines supply Koradi & Khaparkheda via Central
                     Railway — a derailment at Hingoli yard cuts ~40% of coal
                     within 48 hours."

            EVIDENCE HIERARCHY:
              Primary  — Explicit news headlines provided below
              Secondary — Your expert knowledge of Indian power sector

            If news evidence is thin for a fact, prepend it with "likely" or
            "approx." and lower your llm_confidence score accordingly.

            MINIMUM 6 key_vulnerabilities that are SPECIFIC and ACTIONABLE.

            ── OUTPUT ─────────────────────────────────────────────────────────────
            Respond ONLY in JSON. No preamble. No markdown fences.

            {{
                "generation_mix"         : "<concise % breakdown with named plants>",
                "primary_fuel_sources"   : ["<named source>", ...],
                "fuel_supply_routes"     : ["<physical route description>", ...],
                "key_vulnerabilities"    : ["<specific failure mode>", ...],
                "seasonal_demand_factors": ["<season + load impact>", ...],
                "demand_drivers"         : ["<industry or segment>", ...],
                "neighboring_exchange"   : ["<corridor + typical MW>", ...],
                "sources_used"           : ["<news source names used>", ...],
                "llm_confidence"         : <float 0.0–1.0>
            }}
        """).strip()

        news_block = "\n".join(f"- {h}" for h in headlines[:MAX_HEADLINES_TO_LLM])
        user = (
            f"CITY: {reg['name']}, {reg['state']}\n"
            f"TYPICAL PEAK LOAD: ~{reg['typical_peak_mw']} MW\n"
            f"CLIMATE ZONE: {reg.get('climate_zone', 'unknown')}\n"
            f"PRIMARY DISCOMs: {', '.join(reg.get('primary_discom', []))}\n\n"
            f"RECENT NEWS HEADLINES (RAW / UNFILTERED):\n{news_block}"
        )

        raw = self._chat(system, user, node_id, temp=0.10, json_mode=True)

        try:
            data = json.loads(raw)
            return CityIntelligence(
                node_id                = node_id,
                city_name              = reg["name"],
                generated_on           = date.today().isoformat(),
                generation_mix         = data.get("generation_mix", "Unknown"),
                primary_fuel_sources   = data.get("primary_fuel_sources", []),
                fuel_supply_routes     = data.get("fuel_supply_routes", []),
                key_vulnerabilities    = data.get("key_vulnerabilities", []),
                seasonal_demand_factors= data.get("seasonal_demand_factors", []),
                demand_drivers         = data.get("demand_drivers", []),
                neighboring_exchange   = data.get("neighboring_exchange", []),
                llm_confidence         = float(data.get("llm_confidence", 0.5)),
                sources_used           = data.get("sources_used", []),
            )
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"    [!] CityIntelAgent parse error for {node_id}: {exc}")
            return CityIntelligence(
                node_id=node_id, city_name=reg["name"],
                generated_on=date.today().isoformat(),
                generation_mix="Unknown — LLM parse failed",
                primary_fuel_sources=[], fuel_supply_routes=[],
                key_vulnerabilities=["Profile generation failed — manual review needed"],
                seasonal_demand_factors=[], demand_drivers=[],
                neighboring_exchange=[], llm_confidence=0.0,
                sources_used=[],
            )
