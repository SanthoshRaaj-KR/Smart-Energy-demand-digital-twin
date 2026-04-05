"""
multiplier_synth_agent.py
=========================
Phase 3C — Multiplier Synthesis Agent

SINGLE RESPONSIBILITY:
  Convert the rich narrative from ImpactNarratorAgent into a precise,
  schema-validated set of numeric multipliers used by the grid simulation.

WHY THIS AGENT EXISTS SEPARATELY:
  Numeric extraction from narrative is a precision task — it requires
  the LLM to interpret expert prose and map it to constrained numeric
  ranges. Mixing this with the actual reasoning (Phase 3B) causes the LLM
  to trade off between 'being a good analyst' and 'outputting valid JSON'.
  Keeping them separate lets each stage excel at its one job.

WHY IT ONLY READS THE NARRATIVE (not headlines, events, or city intel):
  The narrator already synthesised those into human-readable form.
  Feeding raw inputs here would only dilute the signal. The chain-of-
  thought created in Phase 3B is exactly the context this agent needs.

PIPELINE POSITION:
  Input  ← impact narrative (from ImpactNarratorAgent) + event list summary
  Output → GridMultipliers dataclass — the terminal output of the pipeline.
  These multipliers flow into run_simulation.py to adjust node demand/supply.

FUTURE ORCHESTRATOR NOTE:
  This agent's output is the final JSON contract with the simulation engine.
  The orchestrator may cache this output separately from the narrative and
  selectively re-run only this agent (without re-running upstream steps) if
  the operator wants to manually override the narrative and re-derive numbers.
"""

from __future__ import annotations

import json
import textwrap
from typing import List

from .base_agent import BaseLLMAgent
from .setup import DetectedEvent, GridMultipliers


class MultiplierSynthAgent(BaseLLMAgent):
    """
    Converts a narrative impact analysis into validated GridMultipliers.
    This is the terminal, JSON-mode agent — no prose output.
    """

    AGENT_ROLE = "MultiplierSynthAgent"

    def synthesise_multipliers(
        self,
        city_name       : str,
        typical_peak_mw : int,
        impact_analysis : str,
        events          : List[DetectedEvent],
    ) -> GridMultipliers:
        """
        Parameters
        ----------
        city_name       : Human-readable city name
        typical_peak_mw : Normal peak demand for calibration
        impact_analysis : Full narrative from ImpactNarratorAgent
        events          : Detected events list (for pre-event hoard logic)

        Returns
        -------
        GridMultipliers dataclass — used directly by run_simulation.py
        """
        system = textwrap.dedent(f"""
            You are the Quantitative Output Agent for {city_name}'s grid model.
            Typical peak demand: ~{typical_peak_mw} MW.

            ── YOUR ROLE IN THE PIPELINE ──────────────────────────────────────────
            You are the FINAL Agent (5 of 5) in the India Grid Intelligence Pipeline.
            Your outputs are the numeric multipliers consumed directly by the
            physics-based grid simulation engine. These numbers SET the simulation's
            demand/supply balance for the next 7-day window.

            You receive one input: the expert narrative written by ImpactNarratorAgent.
            That narrative already contains all the reasoning. Your job is purely
            numeric extraction and range enforcement — do NOT add new reasoning.

            ── MULTIPLIER DEFINITIONS ─────────────────────────────────────────────
            economic_demand_multiplier (EDM):
              1.00 = normal weekday baseline for {city_name}
              >1.00 = elevated demand (heatwave AC, festival lighting, industrial surge,
                      event crowds, IPL-scale TV pickup, mass gatherings)
              <1.00 = suppressed demand (bandh, election closure, cyclone shutdown,
                      public holiday — offices and factories empty)
              Valid range: [0.55, 1.50]

            temperature_anomaly (°C above seasonal normal):
              Positive → hotter → more AC load (each +1°C above 35°C ≈ +1.0–1.5% peak)
              Negative → cooler than normal
              Valid range: [-10.0, +14.0]

            generation_capacity_multiplier (GCM):
              1.00 = all generation plants running at normal declared capacity
              <1.00 = forced outage, fuel shortage, hydro low water, maintenance
              >1.00 = new plant online, surplus import confirmed
              Valid range: [0.55, 1.12]

            pre_event_hoard (boolean):
              true ONLY when ALL of these hold:
                ① A high-confidence (medium or high) demand-spiking event exists within 7 days
                ② GCM < 0.95 (supply margin tight) OR supply_shortfall_risk = HIGH/CRITICAL
                ③ The narrative explicitly recommends pre-booking/hoarding

            demand_spike_risk: LOW | MEDIUM | HIGH | CRITICAL
              CRITICAL = projected >15% demand surge AND <5% generation headroom

            supply_shortfall_risk: LOW | MEDIUM | HIGH | CRITICAL

            seven_day_demand_forecast_mw_delta (integer):
              Net MW change from normal {typical_peak_mw} MW baseline.
              Positive = more demand than usual. Derive from EDM × peak.

            confidence (0.0–1.0):
              Quality of the evidence chain. Reflects how much of the
              narrative was backed by specific signals vs. assumptions.

            ── OUTPUT ─────────────────────────────────────────────────────────────
            Respond STRICTLY in JSON. No preamble. No markdown. No comments.
            {{
                "pre_event_hoard"                : <boolean>,
                "temperature_anomaly"            : <float>,
                "economic_demand_multiplier"     : <float>,
                "generation_capacity_multiplier" : <float>,
                "demand_spike_risk"              : "<string>",
                "supply_shortfall_risk"          : "<string>",
                "7_day_demand_forecast_mw_delta" : <integer>,
                "confidence"                     : <float>,
                "key_driver"                     : "<single most important factor>",
                "reasoning"                      : "<2–3 sentence summary>"
            }}
        """).strip()

        event_summary = (
            "\n".join(
                f"- {e.event_name}: {e.est_mw_impact} "
                f"(mechanism={e.grid_mechanism}, confidence={e.confidence}, "
                f"days_away={e.days_away})"
                for e in events
            )
            or "No electricity-impacting events detected."
        )

        user = (
            f"IMPACT NARRATIVE (from ImpactNarratorAgent):\n{impact_analysis}\n\n"
            f"EVENT RADAR SUMMARY (from EventRadarAgent):\n{event_summary}"
        )
        raw = self._chat(system, user, city_name, temp=0.05, json_mode=True)

        try:
            data = json.loads(raw)
            return GridMultipliers(
                pre_event_hoard                = bool(data.get("pre_event_hoard", False)),
                temperature_anomaly            = float(data.get("temperature_anomaly", 0.0)),
                economic_demand_multiplier     = float(data.get("economic_demand_multiplier", 1.0)),
                generation_capacity_multiplier = float(data.get("generation_capacity_multiplier", 1.0)),
                demand_spike_risk              = data.get("demand_spike_risk", "UNKNOWN"),
                supply_shortfall_risk          = data.get("supply_shortfall_risk", "UNKNOWN"),
                seven_day_demand_forecast_mw_delta = int(data.get("7_day_demand_forecast_mw_delta", 0)),
                confidence                     = float(data.get("confidence", 0.5)),
                key_driver                     = data.get("key_driver", "Unknown"),
                reasoning                      = data.get("reasoning", ""),
                severity_level                 = int(data.get("severity_level", 1)),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"    [!] MultiplierSynthAgent parse error for {city_name}: {exc}")
            return GridMultipliers(
                pre_event_hoard=False, temperature_anomaly=0.0,
                economic_demand_multiplier=1.0, generation_capacity_multiplier=1.0,
                demand_spike_risk="UNKNOWN", supply_shortfall_risk="UNKNOWN",
                seven_day_demand_forecast_mw_delta=0, confidence=0.0,
                key_driver="Parse error", reasoning=str(exc),
                severity_level=1,
            )
