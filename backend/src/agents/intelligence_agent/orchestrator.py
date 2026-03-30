"""
orchestrator.py
===============
Top-level and per-node orchestrator for the Intelligence Agent pipeline.

This module wires together 6 specialized sub-agents into a clean,
auditable pipeline. Each agent appears explicitly by name so the
data flow is readable without tracing method calls.

AGENT EXECUTION ORDER PER NODE:
  Phase 1    DataFetcher         (raw weather + news + RSS — no LLM)
  Phase 2    CityIntelAgent      (city profile — cache-first, from raw news)
  Phase 3    EventRadarAgent     (mass events / broadcast / disruption detection — from raw news)
  Phase 4    FilterAgent         (noise kill — quality gate, cleans news for extraction)
  Phase 5    SignalExtractorAgent (infrastructure & supply-chain signals)
  Phase 6    ImpactNarratorAgent (expert narrative — chain-of-thought step)
  Phase 7    MultiplierSynthAgent(numeric JSON multipliers — terminal output)

FUTURE ORCHESTRATOR INTEGRATION:
  NodeOrchestrator is intentionally designed so that an outer LLM-based
  orchestrator can:
    - Inspect each agent by its AGENT_ROLE string
    - Skip phases (e.g. skip Phase 0 on cache hit, reported via _ci_cache)
    - Re-run a single phase without re-running the whole pipeline
    - Inject mock agents for testing
  To support this, all agents are stored in self._agents dict and each
  phase result is explicitly named before being passed to the next step.
"""

from __future__ import annotations

import json
import os
import textwrap
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .setup import (
    CITY_REGISTRY, HEADLINE_DEDUP_CHARS,
    CityIntelligenceCache, NodeResult, WeatherSummary,
)
from .fetching_details import DataFetcher

# ── Import all sub-agents explicitly ─────────────────────────────────────────
from .filter_agent           import FilterAgent
from .city_intel_agent       import CityIntelAgent
from .event_radar_agent      import EventRadarAgent
from .signal_extractor_agent import SignalExtractorAgent
from .impact_narrator_agent  import ImpactNarratorAgent
from .multiplier_synth_agent import MultiplierSynthAgent

BACKEND_DIR = Path(__file__).resolve().parents[3]


class NodeOrchestrator:
    """
    Runs the full 7-phase intelligence pipeline for a single city node.

    Receives fully-constructed agent instances from SmartGridIntelligenceAgent
    (shared across nodes) to avoid per-node client construction overhead.
    """

    def __init__(
        self,
        fetcher         : DataFetcher,
        ci_cache        : CityIntelligenceCache,
        rss_flat        : List[str],
        today_str       : str,
        # ── sub-agents (injected, shared) ──────────────────────────
        filter_agent    : FilterAgent,
        city_intel_agent: CityIntelAgent,
        event_radar_agent: EventRadarAgent,
        signal_extractor: SignalExtractorAgent,
        impact_narrator : ImpactNarratorAgent,
        multiplier_synth: MultiplierSynthAgent,
    ):
        self._fetcher     = fetcher
        self._ci_cache    = ci_cache
        self._rss_flat    = rss_flat
        self._today_str   = today_str

        # Named for future dynamic dispatch by orchestrator agent
        self._agents = {
            FilterAgent.AGENT_ROLE          : filter_agent,
            CityIntelAgent.AGENT_ROLE       : city_intel_agent,
            EventRadarAgent.AGENT_ROLE      : event_radar_agent,
            SignalExtractorAgent.AGENT_ROLE : signal_extractor,
            ImpactNarratorAgent.AGENT_ROLE  : impact_narrator,
            MultiplierSynthAgent.AGENT_ROLE : multiplier_synth,
        }

    def _build_headline_list(self, articles: List[Dict], rss: List[str]) -> List[str]:
        lines: List[str] = []
        for art in articles:
            title = (art.get("title") or "").strip()
            desc  = (art.get("description") or "")[:200].strip()
            if title:
                lines.append(f"{title}  {desc}" if desc else title)
        lines.extend(rss)

        seen: set = set()
        unique: List[str] = []
        for h in lines:
            key = h[:HEADLINE_DEDUP_CHARS].lower()
            if key not in seen:
                seen.add(key)
                unique.append(h)
        return unique

    @staticmethod
    def _baseline_multipliers() -> Dict[str, Any]:
        return {
            "pre_event_hoard": False,
            "temperature_anomaly": 0.0,
            "economic_demand_multiplier": 1.0,
            "generation_capacity_multiplier": 1.0,
            "demand_spike_risk": "UNKNOWN",
            "supply_shortfall_risk": "UNKNOWN",
            "seven_day_demand_forecast_mw_delta": 0,
            "confidence": 0.0,
            "key_driver": "Baseline",
            "reasoning": "Neutral defaults before multiplier synthesis.",
        }

    def _build_phase_trace(
        self,
        reg: Dict[str, Any],
        weather: Optional[WeatherSummary],
        all_headlines: List[str],
        clean_headlines: List[str],
        intel: Any,
        detected_events: List[Any],
        signals: str,
        impact: str,
        multipliers: Any,
    ) -> Dict[str, Any]:
        after_multiplier = asdict(multipliers)
        before_multiplier = self._baseline_multipliers()
        return {
            "phase_1": {
                "name": "Data Fetch",
                "status": "completed",
                "raw_headline_count": len(all_headlines),
                "raw_headline_samples": all_headlines[:5],
                "weather_snapshot": {
                    "current_temp_c": weather.current_temp_c if weather else 0.0,
                    "week_max_c": weather.week_max_c if weather else 0.0,
                    "week_total_rain_mm": weather.week_total_rain_mm if weather else 0.0,
                },
            },
            "phase_2": {
                "name": "City Intelligence Profile",
                "status": "completed",
                "llm_confidence": float(getattr(intel, "llm_confidence", 0.0)),
                "key_vulnerabilities": list(getattr(intel, "key_vulnerabilities", [])[:6]),
                "primary_fuel_sources": list(getattr(intel, "primary_fuel_sources", [])[:6]),
                "fuel_supply_routes": list(getattr(intel, "fuel_supply_routes", [])[:6]),
                "neighboring_exchange": list(getattr(intel, "neighboring_exchange", [])[:6]),
            },
            "phase_3": {
                "name": "Event Radar",
                "status": "completed",
                "event_count": len(detected_events),
                "events": [asdict(e) for e in detected_events],
            },
            "phase_4": {
                "name": "Headline Filtering",
                "status": "completed",
                "input_count": len(all_headlines),
                "output_count": len(clean_headlines),
                "retained_samples": clean_headlines[:5],
            },
            "phase_5": {
                "name": "Signal Extraction",
                "status": "completed",
                "summary": signals,
            },
            "phase_6": {
                "name": "Impact Narrative",
                "status": "completed",
                "narrative": impact,
            },
            "phase_7": {
                "name": "Multiplier Synthesis",
                "status": "completed",
                "before_multiplier": before_multiplier,
                "after_multiplier": after_multiplier,
                "flags": {
                    "pre_event_hoard": bool(after_multiplier.get("pre_event_hoard", False)),
                    "demand_spike_risk": after_multiplier.get("demand_spike_risk", "UNKNOWN"),
                    "supply_shortfall_risk": after_multiplier.get("supply_shortfall_risk", "UNKNOWN"),
                },
                "path_dependency_signals": {
                    "fuel_supply_routes": list(getattr(intel, "fuel_supply_routes", [])[:6]),
                    "neighboring_exchange": list(getattr(intel, "neighboring_exchange", [])[:6]),
                    "regional_state": reg.get("state", ""),
                },
            },
        }

    def run(self, node_id: str) -> NodeResult:
        reg  = CITY_REGISTRY[node_id]
        city = reg["name"]
        print(f"\n{'═'*60}")
        print(f"  NODE {node_id}  {city} ({reg['state']})")
        print(f"{'═'*60}")

        # ── Phase 1: Data Fetch (no LLM) ────────────────────────────────────
        print(f"  [Phase 1] Fetching weather...")
        wx_raw = self._fetcher.fetch_owm_forecast(city, reg["lat"], reg["lon"])
        wx_hourly = self._fetcher.fetch_hourly_forecast_7d(city, reg["lat"], reg["lon"])
        if "error" in wx_raw:
            print(f"    [!] Weather error: {wx_raw['error']}")
        if "error" in wx_hourly:
            print(f"    [!] Hourly weather error: {wx_hourly['error']}")

        weather = WeatherSummary(
            current_temp_c        = wx_raw.get("current_temp_c", 0.0),
            current_humidity_pct  = wx_raw.get("current_humidity_pct", 0),
            current_condition     = wx_raw.get("current_condition", "unknown"),
            week_max_c            = wx_raw.get("week_max_c", 0.0),
            week_max_heat_index_c = wx_raw.get("week_max_heat_index_c", 0.0),
            week_total_rain_mm    = wx_raw.get("week_total_rain_mm", 0.0),
            forecast_days         = wx_raw.get("5_day_forecast", []),
            hourly_forecast_7d    = wx_hourly.get("hourly_forecast_7d", []),
        ) if "error" not in wx_raw else None

        print(f"  [Phase 1] Fetching news (4 GNews queries + NewsData)...")
        all_articles: List[Dict] = []

        q_city  = f'"{city}" OR "{reg["state"]}" electricity OR power OR energy OR coal OR grid'
        q_plant = f'"{city}" power plant OR generation OR outage OR tripping OR commissioning'
        q_fuel  = f'"{city}" OR "{reg["state"]}" coal mine OR railway freight OR fuel shortage OR gas pipeline'
        q_event = (
            f'"{city}" stadium OR tournament OR match OR broadcast OR polling OR '
            f'voting OR bandh OR rally OR mela OR concert OR summit OR exhibition'
        )

        for query, label in [
            (q_city,  "city-energy"),
            (q_plant, "plant-events"),
            (q_fuel,  "fuel-logistics"),
            (q_event, "event-radar"),
        ]:
            all_articles.extend(self._fetcher.fetch_gnews(query, f"{node_id}_{label}"))
            time.sleep(0.4)

        nd_query = f"{city} electricity power coal grid energy"
        all_articles.extend(self._fetcher.fetch_newsdata(nd_query, node_id))

        all_headlines = self._build_headline_list(all_articles, self._rss_flat)
        print(f"  [Phase 1] {len(all_headlines)} raw unique headlines")

        # ── Phase 2: CityIntelAgent — cache-first ───────────────────────────
        print(f"  [Phase 2] CityIntelAgent: loading city profile from raw headlines...")
        intel = self._ci_cache.load(node_id)
        if intel is None:
            print(f"  [Phase 2] Cache miss — generating fresh city profile...")
            intel = self._agents[CityIntelAgent.AGENT_ROLE].build_city_intelligence(
                node_id, reg, all_headlines
            )
            self._ci_cache.save(intel)
            print(f"  [Phase 2] City profile ready (confidence={intel.llm_confidence:.2f})")

        # ── Phase 3: EventRadarAgent — detect demand-shifting events ────────
        print(f"  [Phase 3] EventRadarAgent: scanning raw headlines for demand-shifting events...")
        detected_events = self._agents[EventRadarAgent.AGENT_ROLE].detect_large_events(
            city, all_headlines, self._today_str
        )
        print(f"  [Phase 3] {len(detected_events)} events detected")
        for ev in detected_events:
            print(f"     [{ev.grid_mechanism}] {ev.event_name} | {ev.est_mw_impact} | conf={ev.confidence}")

        # ── Phase 4: FilterAgent — quality gate for signal extraction ───────
        print(f"  [Phase 4] FilterAgent: killing noise from headlines...")
        clean_headlines = self._agents[FilterAgent.AGENT_ROLE].filter_headlines(all_headlines)
        print(f"  [Phase 4] {len(clean_headlines)} high-signal headlines remain")

        # ── Phase 5: SignalExtractorAgent — grid signal extraction ─────────
        print(f"  [Phase 5] SignalExtractorAgent: extracting grid signals from clean headlines...")
        signals = self._agents[SignalExtractorAgent.AGENT_ROLE].extract_grid_signals(
            city, intel, clean_headlines
        )

        # ── Phase 6: ImpactNarratorAgent — expert narrative (CoT) ─────────
        print(f"  [Phase 6] ImpactNarratorAgent: writing demand/supply narrative...")
        impact = self._agents[ImpactNarratorAgent.AGENT_ROLE].deep_impact_analysis(
            city, reg, intel, signals, wx_raw, detected_events
        )

        # ── Phase 7: MultiplierSynthAgent — numeric terminal output ────────
        print(f"  [Phase 7] MultiplierSynthAgent: synthesising numeric multipliers...")
        multipliers = self._agents[MultiplierSynthAgent.AGENT_ROLE].synthesise_multipliers(
            city, reg["typical_peak_mw"], impact, detected_events
        )
        print(
            f"  [Done] EDM={multipliers.economic_demand_multiplier:.2f} | "
            f"GCM={multipliers.generation_capacity_multiplier:.2f} | "
            f"D-Risk={multipliers.demand_spike_risk} | "
            f"S-Risk={multipliers.supply_shortfall_risk}"
        )

        phase_trace = self._build_phase_trace(
            reg=reg,
            weather=weather,
            all_headlines=all_headlines,
            clean_headlines=clean_headlines,
            intel=intel,
            detected_events=detected_events,
            signals=signals,
            impact=impact,
            multipliers=multipliers,
        )

        return NodeResult(
            node_id           = node_id,
            city              = city,
            generated_at      = self._today_str,
            weather           = weather,
            city_intelligence = intel,
            detected_events   = detected_events,
            extracted_signals = signals,
            impact_narrative  = impact,
            grid_multipliers  = multipliers,
            phase_trace       = phase_trace,
        )


class SmartGridIntelligenceAgent:
    """
    Top-level orchestrator. Constructs all sub-agents once, then runs
    each city node through the NodeOrchestrator pipeline.

    Manages:
    - Per-run output cache (1-day TTL per node)
    - Raw API dump for full auditability (one file per run)
    - Summary table and JSON export
    """

    def __init__(self):
        self._client = OpenAI()

        gnews_key    = os.getenv("GNEWS_API_KEY")
        newsdata_key = os.getenv("NEWSDATA_API_KEY")
        owm_key      = os.getenv("OWM_API_KEY")

        if not all([gnews_key, newsdata_key, owm_key]):
            raise EnvironmentError(
                "Missing API keys. Set GNEWS_API_KEY, NEWSDATA_API_KEY, OWM_API_KEY in .env"
            )

        self._today_str = date.today().isoformat()
        self._outputs_dir = BACKEND_DIR / "outputs"
        self._cache_dir = self._outputs_dir / "context_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._dump_path = self._cache_dir / f"raw_api_dump_{self._today_str}.txt"
        self._dump_path.write_text(f"=== RAW API DUMP {self._today_str} ===\n")

        def _log(tag: str, data: str):
            with self._dump_path.open("a", encoding="utf-8") as f:
                f.write(f"\n\n── {tag} ──\n{data}\n{'─'*60}\n")

        self._fetcher  = DataFetcher(gnews_key, newsdata_key, owm_key, log_fn=_log)
        self._ci_cache = CityIntelligenceCache(self._cache_dir / "city_intel")

        # ── Construct all sub-agents ONCE — shared across nodes ──────────────
        self._filter_agent     = FilterAgent(self._client, log_fn=_log)
        self._city_intel_agent = CityIntelAgent(self._client, log_fn=_log)
        self._event_radar      = EventRadarAgent(self._client, log_fn=_log)
        self._signal_extractor = SignalExtractorAgent(self._client, log_fn=_log)
        self._impact_narrator  = ImpactNarratorAgent(self._client, log_fn=_log)
        self._multiplier_synth = MultiplierSynthAgent(self._client, log_fn=_log)

    def _daily_cache_path(self, node_id: str) -> Path:
        return self._cache_dir / f"node_{node_id}_{self._today_str}.json"

    def _load_daily_cache(self, node_id: str) -> Optional[Dict]:
        p = self._daily_cache_path(node_id)
        if p.exists():
            print(f"  [CACHE] Daily result cached for {node_id} — loading.")
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def _save_daily_cache(self, node_id: str, data: Dict) -> None:
        self._daily_cache_path(node_id).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _result_to_dict(r: NodeResult) -> Dict[str, Any]:
        return {
            "node_id"          : r.node_id,
            "city"             : r.city,
            "generated_at"     : r.generated_at,
            "error"            : r.error,
            "weather"          : asdict(r.weather) if r.weather else None,
            "city_intelligence": asdict(r.city_intelligence) if r.city_intelligence else None,
            "detected_events"  : [asdict(e) for e in r.detected_events],
            "extracted_signals": r.extracted_signals,
            "impact_narrative" : r.impact_narrative,
            "grid_multipliers" : asdict(r.grid_multipliers) if r.grid_multipliers else None,
            "phase_trace"      : r.phase_trace or {},
        }

    def run_all_regions(self) -> Dict[str, Dict]:
        print("═" + "═"*58 + "═")
        print("   SMART GRID INTELLIGENCE AGENT  — MODULAR EDITION v4.0  ")
        print(f"   Date: {self._today_str:<48} ")
        print("═" + "═"*58 + "═")
        print(f"\n  Active agents:")
        print(f"    Phase 2: CityIntelAgent")
        print(f"    Phase 3: EventRadarAgent")
        print(f"    Phase 4: FilterAgent")
        print(f"    Phase 5: SignalExtractorAgent")
        print(f"    Phase 6: ImpactNarratorAgent")
        print(f"    Phase 7: MultiplierSynthAgent\n")

        print("\n[Phase 1] Scraping national RSS feeds...")
        rss_data = self._fetcher.scrape_rss_feeds()
        rss_flat: List[str] = [h for lines in rss_data.values() for h in lines]

        final: Dict[str, Dict] = {}

        for node_id in CITY_REGISTRY:
            cached = self._load_daily_cache(node_id)
            if cached:
                final[node_id] = cached
                continue

            try:
                orchestrator = NodeOrchestrator(
                    fetcher          = self._fetcher,
                    ci_cache         = self._ci_cache,
                    rss_flat         = rss_flat,
                    today_str        = self._today_str,
                    filter_agent     = self._filter_agent,
                    city_intel_agent = self._city_intel_agent,
                    event_radar_agent= self._event_radar,
                    signal_extractor = self._signal_extractor,
                    impact_narrator  = self._impact_narrator,
                    multiplier_synth = self._multiplier_synth,
                )
                result      = orchestrator.run(node_id)
                result_dict = self._result_to_dict(result)
                self._save_daily_cache(node_id, result_dict)
                final[node_id] = result_dict

            except Exception as exc:
                print(f"  [ERROR] Node {node_id} failed: {exc}")
                final[node_id] = {"node_id": node_id, "error": str(exc)}

            time.sleep(2)

        return final

    @staticmethod
    def print_summary_table(intelligence: Dict[str, Dict]) -> None:
        """Pretty-print a compact operational summary table."""
        RISK_EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴", "CRITICAL": "🚨", "UNKNOWN": "⚪"}

        header = (
            f"\n{'NODE':<6} {'CITY':<12} {'EDM':>5} {'TC':>6} {'GCM':>5} "
            f"{'D-RISK':<10} {'S-RISK':<10} {'HOARD':>6} {'MW Δ':>7} {'CONF':>5}"
        )
        print("\n" + "─"*75)
        print("  GRID INTELLIGENCE SUMMARY TABLE")
        print("─"*75)
        print(header)
        print("─"*75)

        for nid, data in intelligence.items():
            if data.get("error"):
                print(f"{nid:<6} {'ERROR':<12}  {data['error'][:40]}")
                continue
            gm   = data.get("grid_multipliers") or {}
            city = data.get("city", nid)
            dr   = gm.get("demand_spike_risk", "?")
            sr   = gm.get("supply_shortfall_risk", "?")
            hoard = "🚨 YES" if gm.get("pre_event_hoard") else "   no"

            events   = data.get("detected_events", [])
            ev_count = len(events)

            print(
                f"{nid:<6} {city:<12}"
                f" {gm.get('economic_demand_multiplier', 0):>5.2f}"
                f" {gm.get('temperature_anomaly', 0):>+6.1f}"
                f" {gm.get('generation_capacity_multiplier', 0):>5.2f}"
                f" {RISK_EMOJI.get(dr, '')+dr:<9}"
                f" {RISK_EMOJI.get(sr, '')+sr:<9}"
                f" {hoard:>6}"
                f" {gm.get('seven_day_demand_forecast_mw_delta', 0):>+7}"
                f" {gm.get('confidence', 0):>5.2f}"
            )
            if events:
                ev_labels = list(set(
                    f"{e['event_type']}({e.get('grid_mechanism','?')})"
                    for e in events
                ))
                print(f"        {ev_count} event(s): {', '.join(ev_labels)}")

        print("─"*75)

        print("\n  KEY DRIVERS:")
        for nid, data in intelligence.items():
            if data.get("error"):
                continue
            gm  = data.get("grid_multipliers") or {}
            kd  = gm.get("key_driver", "")
            rsn = gm.get("reasoning", "")
            print(f"  {nid} — {kd}")
            if rsn:
                for line in textwrap.wrap(rsn, width=65):
                    print(f"       {line}")

        print()
        print(f"  Raw API dump → outputs/context_cache/raw_api_dump_{date.today().isoformat()}.txt")
        print()
