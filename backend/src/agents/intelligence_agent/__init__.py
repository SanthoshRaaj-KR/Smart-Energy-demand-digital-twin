"""
intelligence_agent package

Modular, single-responsibility LLM sub-agents for the India Grid Digital Twin.

Agent roster (execution order):
  FilterAgent           — Phase 1.5  noise killer (quality gate)
  CityIntelAgent        — Phase 0    city power-sector profile (cache-first)
  EventRadarAgent       — Phase 2    demand-shifting event detection
  SignalExtractorAgent  — Phase 3A   grid supply/demand signal extraction
  ImpactNarratorAgent   — Phase 3B   expert narrative (chain-of-thought)
  MultiplierSynthAgent  — Phase 3C   terminal numeric JSON output

Orchestration:
  NodeOrchestrator         — per-city pipeline runner
  SmartGridIntelligenceAgent — top-level entry point
"""

from .base_agent             import BaseLLMAgent
from .filter_agent           import FilterAgent
from .city_intel_agent       import CityIntelAgent
from .event_radar_agent      import EventRadarAgent
from .signal_extractor_agent import SignalExtractorAgent
from .impact_narrator_agent  import ImpactNarratorAgent
from .multiplier_synth_agent import MultiplierSynthAgent
from .orchestrator           import NodeOrchestrator, SmartGridIntelligenceAgent

__all__ = [
    "BaseLLMAgent",
    "FilterAgent",
    "CityIntelAgent",
    "EventRadarAgent",
    "SignalExtractorAgent",
    "ImpactNarratorAgent",
    "MultiplierSynthAgent",
    "NodeOrchestrator",
    "SmartGridIntelligenceAgent",
]
