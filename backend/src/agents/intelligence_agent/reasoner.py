"""
reasoner.py — Backward-compatibility shim.

The LLMReasoner class has been decomposed into 6 focused sub-agents:
  FilterAgent           → filter_agent.py
  CityIntelAgent        → city_intel_agent.py
  EventRadarAgent       → event_radar_agent.py
  SignalExtractorAgent  → signal_extractor_agent.py
  ImpactNarratorAgent   → impact_narrator_agent.py
  MultiplierSynthAgent  → multiplier_synth_agent.py

This file is kept to avoid breaking external imports.
Import the specific agent you need from its own module.
"""

# noqa: F401 — kept for backward compatibility
from .city_intel_agent       import CityIntelAgent
from .event_radar_agent      import EventRadarAgent
from .signal_extractor_agent import SignalExtractorAgent
from .impact_narrator_agent  import ImpactNarratorAgent
from .multiplier_synth_agent import MultiplierSynthAgent

# Legacy alias — do not use in new code
LLMReasoner = CityIntelAgent
