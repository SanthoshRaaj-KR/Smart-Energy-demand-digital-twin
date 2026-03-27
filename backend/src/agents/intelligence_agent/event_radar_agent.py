"""
event_radar_agent.py
====================
Phase 3 — Event Radar Agent

SINGLE RESPONSIBILITY:
  Scan RAW, unfiltered headlines and detect ANY gathering, disruption, or
  broadcast event that will materially shift electricity demand in this
  city within the next 7 days.

WHY THIS AGENT RECEIVES UNFILTERED NEWS:
  It used to receive filtered news, but the noise filter would frequently 
  delete sports and entertainment news, completely blinding this agent to 
  massive stadium concerts and IPL cricket finals! It now runs before the 
  filter so it can see everything.

HOW IT DETECTS WITHOUT HARDCODING EVENT NAMES:
  The agent reasons from FOUR universal grid-impact mechanisms. A cricket
  final, a political rally, a rock concert, and an air-show all share the
  same underlying mechanism (MASS_GATHERING or TV_PICKUP). The agent maps
  to the mechanism — it never hunts for named events. This makes it
  future-proof: any event that creates the same physical electricity effect
  will be caught, even if the agent has never heard of it.

PIPELINE POSITION:
  Input  ← noise-filtered headlines
  Output → List[DetectedEvent] consumed by ImpactNarratorAgent and
           MultiplierSynthAgent to calculate pre-event hoarding signals.
  The orchestrator will pass this list directly to the next two agents —
  they will NOT re-read the headlines for event info.
"""

from __future__ import annotations

import json
import textwrap
from typing import List

from .base_agent import BaseLLMAgent
from .setup import DetectedEvent, MAX_HEADLINES_TO_LLM


class EventRadarAgent(BaseLLMAgent):
    """
    Detects electricity-demand-altering events from headlines using
    first-principles grid-impact mechanism reasoning.

    No event names, sports names, or cultural references are hardcoded.
    Detection fires on the PHYSICAL EFFECT an event will produce on the grid.
    """

    AGENT_ROLE = "EventRadarAgent"

    def detect_large_events(
        self,
        city_name : str,
        headlines : List[str],
        today_str : str,
    ) -> List[DetectedEvent]:
        """
        Parameters
        ----------
        city_name : Human-readable city name (e.g. "Delhi")
        headlines : Noise-filtered headline list for this city
        today_str : ISO date string for the 7-day horizon anchor

        Returns
        -------
        List[DetectedEvent] — may be empty. Hard-capped at 7-day horizon.
        """
        system = textwrap.dedent(f"""
            You are a grid demand analyst specialising in real-time event detection
            for {city_name}, India. Today's date: {today_str}.

            ── YOUR ROLE IN THE PIPELINE ──────────────────────────────────────────
            You are Agent 3 in the India Grid Intelligence Pipeline.
            IMPORTANT: You are receiving RAW, UNFILTERED headlines. There will be 
            a lot of noise (e.g., Bollywood gossip, daily sports scores). Do not 
            get distracted. Your job is to hunt through the noise to find MASSIVE 
            EVENTS that impact the power grid.
            
            Your detection results flow directly into two downstream agents:
              → ImpactNarrator : uses your events to write the demand outlook
              → MultiplierSynth: uses your events to set pre-event hoard flags and
                                 adjust demand multipliers

            This means your output must be PRECISE AND STRUCTURED — downstream
            agents will not re-read headlines. If you miss an event, the forecast
            will underestimate demand. If you hallucinate one, it will cause a
            false demand spike warning. Accuracy is critical.

            ── 7-DAY HARD HORIZON ─────────────────────────────────────────────────
            ONLY include events that START or are ONGOING within the next 7 days.
            days_away MUST be an integer 0–7. Events further away = IGNORE.

            ── HOW TO DETECT (MECHANISM-FIRST, NOT NAME-FIRST) ────────────────────
            You NEVER search for specific event names, sport names, team names,
            artist names, or brand names. Instead, you ask:

              "Does this headline imply one of these four physical effects
               on the electricity grid?"

            ┌─────────────────────────────────────────────────────────────────┐
            │ MECHANISM 1 — TV / STREAMING PICKUP                            │
            │ Tens of millions of people simultaneously switching on TVs,     │
            │ set-top boxes, ACs, and devices to watch a live broadcast.      │
            │ Effect: Synchronized city-wide residential load spike.          │
            │                                                                 │
            │ Clues in headlines:                                             │
            │   "live broadcast", "final", "grand finale", "viewership",      │
            │   "nationwide telecast", "prime-time special", "streaming",     │
            │   "millions expected to watch", "record audience",              │
            │   "watch party", "free-to-air", "live on TV"                  │
            ├─────────────────────────────────────────────────────────────────┤
            │ MECHANISM 2 — HEAVY TEMPORARY INFRASTRUCTURE LOAD              │
            │ A physical venue requiring sustained high-wattage equipment:    │
            │ stadium floodlights (3–10 MW), broadcast trucks, AV rigs,      │
            │ temporary cooling, refrigerated food storage, large screens.   │
            │ Effect: Steady additional load at a single feeder point.        │
            │                                                                 │
            │ Clues in headlines:                                             │
            │   "stadium", "arena", "venue", "expo", "convention centre",     │
            │   "trade show", "air show", "floodlights", "temporary power",   │
            │   "broadcast hub", "media centre", "exhibition", "pavilion"    │
            ├─────────────────────────────────────────────────────────────────┤
            │ MECHANISM 3 — SYNCHRONIZED ROUTINE DISRUPTION                  │
            │ An entire city's daily rhythm shifts at the same time.          │
            │ DEMAND DROP: offices/factories close (election day, bandh,     │
            │   public holiday, hartal, curfew).                              │
            │ DEMAND SPIKE: everyone home simultaneously (WFH order,         │
            │   school closure, night curfew with daytime crowds).            │
            │ Effect: City-wide baseline shift up or down.                    │
            │                                                                 │
            │ Clues in headlines:                                             │
            │   "voting", "counting day", "election result", "bandh",         │
            │   "hartal", "shutdown", "holiday declared", "curfew",           │
            │   "lockdown", "public holiday", "work-from-home order",         │
            │   "schools closed", "offices shut", "commercial shutdown"      │
            ├─────────────────────────────────────────────────────────────────┤
            │ MECHANISM 4 — MASS PHYSICAL GATHERING                          │
            │ 10,000+ people concentrated at one location needing cooling,   │
            │ lighting, sound, catering, and security infrastructure.         │
            │ Effect: Sustained additional load; possible traffic congestion  │
            │   causing localised voltage dips on access roads.              │
            │                                                                 │
            │ Clues in headlines:                                             │
            │   "rally", "gathering", "procession", "march", "mela",          │
            │   "yatra", "pilgrimage", "concert", "festival grounds",         │
            │   "inauguration", "summit", "conference", "championship",       │
            │   "tournament", "semi-final", "final match", "prize ceremony",  │
            │   "cultural event", "grand celebration", "public event",        │
            │   "tens of thousands", "lakhs expected", "massive crowd"       │
            └─────────────────────────────────────────────────────────────────┘

            ── CONFIDENCE CALIBRATION ─────────────────────────────────────────────
            high   — Headline explicitly states date, location, and scale in {city_name}
            medium — Event is implied or location is nearby / statewide
            low    — Only weak signals; include only if MW impact could be >50 MW

            ── OUTPUT FORMAT ──────────────────────────────────────────────────────
            Return a JSON array. If nothing qualifies, return [].
            Respond ONLY with the JSON. No preamble, no markdown fences.

            Each element:
            {{
                "event_type"      : "<sports|political|cultural|religious|trade|disaster|other>",
                "event_name"      : "<descriptive name — what it IS, not who organised it>",
                "location"        : "<venue or area in {city_name}>",
                "dates"           : "<ISO date or range e.g. 2026-03-27 to 2026-03-29>",
                "days_away"       : <integer 0-7 ONLY>,
                "duration_days"   : <integer>,
                "grid_mechanism"  : "<TV_PICKUP|HEAVY_INFRA|ROUTINE_DISRUPTION|MASS_GATHERING>",
                "est_attendees"   : "<count range or 'city-wide' for TV pickup>",
                "est_mw_impact"   : "<e.g. +150 to +300 MW residential spike>",
                "demand_direction": "<increase|decrease|mixed>",
                "confidence"      : "<low|medium|high>",
                "source_headlines": ["<verbatim triggering headline(s)>"]
            }}
        """).strip()

        news_block = "\n".join(f"- {h}" for h in headlines[:MAX_HEADLINES_TO_LLM])
        raw = self._chat(system, news_block, city_name, temp=0.10, json_mode=True)

        try:
            parsed = json.loads(raw)
            items  = parsed.get("events", parsed) if isinstance(parsed, dict) else parsed
            
            # Defensive check: if it's not a list, wrap it
            if not isinstance(items, list):
                items = [items]

            events = []
            for item in items:
                # If the LLM just gave us a string (hallucination format), we skip or try to parse
                if not isinstance(item, dict):
                    continue
                    
                days_away = int(item.get("days_away", 0))
                if days_away > 7:
                    continue   # Hard enforcement — LLM occasionally ignores the rule
                events.append(DetectedEvent(
                    event_type       = item.get("event_type", "other"),
                    event_name       = item.get("event_name", "Unknown"),
                    location         = item.get("location", "Unknown"),
                    dates            = item.get("dates", "Unknown"),
                    days_away        = days_away,
                    duration_days    = int(item.get("duration_days", 1)),
                    grid_mechanism   = item.get("grid_mechanism", "MASS_GATHERING"),
                    est_attendees    = item.get("est_attendees", "Unknown"),
                    est_mw_impact    = item.get("est_mw_impact", "Unknown"),
                    demand_direction = item.get("demand_direction", "increase"),
                    confidence       = item.get("confidence", "low"),
                    source_headlines = item.get("source_headlines", []),
                ))
            return events

        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            print(f"    [!] EventRadarAgent parse error for {city_name}: {exc}")
            return []
