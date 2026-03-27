"""
filter_agent.py
===============
Phase 4 — Filter Agent (The Noise Killer)

SINGLE RESPONSIBILITY:
  Receive raw headlines from 4 GNews queries + NewsData + RSS feeds,
  and aggressively discard anything that has NO plausible path to
  grid supply or demand changes.

WHY THIS AGENT EXISTS AND RUNS IN PHASE 4:
  We run this AFTER EventRadar and CityIntel because if we kill "sports news" 
  or "cultural news" too early, we might drop the exact headline that tells us 
  an IPL final or massive concert is happening tomorrow.
  Once events are detected, this agent acts as a quality gate for the 
  remaining downstream agents (SignalExtractor & ImpactNarrator).

WHAT 'NOISE' MEANS IN THIS CONTEXT:
  Not all irrelevant news — just news that structurally cannot affect
  electricity supply or demand within 7 days. Bollywood gossip, sports
  scores, routine political debates, and celebrity news all fall here.

PIPELINE POSITION:
  Input  ← raw headlines from all news APIs and RSS
  Output → cleaned list passed to SignalExtractor and ImpactNarrator.
"""

from __future__ import annotations

import json
import textwrap
from typing import List

from .base_agent import BaseLLMAgent


class FilterAgent(BaseLLMAgent):
    """
    Noise-killing filter: removes headlines with no grid relevance before
    they enter the main intelligence pipeline.
    """

    AGENT_ROLE = "FilterAgent"

    def filter_headlines(self, headlines: List[str]) -> List[str]:
        """
        Parameters
        ----------
        headlines : Raw, deduplicated headline strings (may include noise)

        Returns
        -------
        Filtered list containing only high-signal headlines.
        Falls back to the original list on any API failure.
        """
        if not headlines:
            return []

        system = textwrap.dedent("""
            You are the Noise Killer — Agent 4 in the India Grid
            Intelligence Pipeline. Your output is consumed by TWO downstream
            specialist agents, so the quality of your filtering is multiplied.

            ── YOUR ROLE IN THE PIPELINE ──────────────────────────────────────────
            You sit directly before the supply/demand analysis phase.
            Every headline you let through will be processed by:
              → SignalExtractorAgent (finds supply/demand causal signals)
              → ImpactNarratorAgent (writes 7-day grid outlook)

            A kept headline costs context in both downstream agents.
            A dropped relevant headline means that intelligence is GONE.
            Err on the side of KEEPING if there is any reasonable doubt.

            ── KEEP — anything with a plausible grid impact path ──────────────────
              ✓ Power grid, electricity supply, load shedding, blackout, outage
              ✓ Coal, gas, oil: mines, rail rakes, port stockpiles, prices
              ✓ Power plant: commissioning, tripping, fire, maintenance, explosion
              ✓ Severe or extreme weather: cyclone, heatwave (38°C+), heavy fog,
                flood warnings, unseasonal cold
              ✓ Large infrastructure disruption: rail strikes, port closures,
                highway blockades (could affect fuel delivery)
              ✓ Mass events that could shift city electricity demand:
                  Large stadium events, major elections or counting days,
                  national holidays, large gatherings (100k+ people),
                  popular live broadcasts (finals, grand events)
              ✓ Industrial news: large factory opening/shutdown, labour disputes
                at steel/cement/mining/refinery facilities
              ✓ Reservoir/dam/water body status affecting hydro power
              ✓ Government energy policy: tariff revisions, interstate agreements,
                grid code changes, renewable curtailment orders

            ── DISCARD — definitively no grid impact path ─────────────────────────
              ✗ Entertainment and celebrity news
              ✗ Routine political speeches, party infighting, minor court verdicts
              ✗ Sports results and scores (KEEP large tournament/match previews
                IF it implies a mass gathering or broadcast event)
              ✗ Generic business news (share prices, banking, fintech)
              ✗ Health news (unless it triggers closures or mass movement)
              ✗ Education, lifestyle, fashion, food, travel

            ── OUTPUT ─────────────────────────────────────────────────────────────
            Return a JSON object:
            {
                "headlines": ["<exact headline string>", ...]
            }
            Include ONLY the exact strings of headlines you KEEP.
            Do not rewrite, summarise, or truncate any headline text.
        """).strip()

        try:
            raw = self._chat(
                system,
                json.dumps({"headlines": headlines}),
                tag      = f"batch_{len(headlines)}",
                temp     = 0.0,
                json_mode= True,
            )
            result = json.loads(raw)
            if isinstance(result, dict) and "headlines" in result:
                kept = result["headlines"]
            elif isinstance(result, list):
                kept = result
            else:
                kept = headlines  # Unexpected format — pass through

            return [h for h in kept if isinstance(h, str)]

        except Exception as exc:
            print(f"    [!] FilterAgent failed: {exc}. Passing through all {len(headlines)} headlines.")
            return headlines
