"""Stochastic Trigger (intelligence.py).

Uses the real intelligence-agent pipeline (trusted RSS/event scraping) and
persists day-indexed cache payloads for simulator/API consumers.

ENHANCED with:
- Scheduled event integration (IPL, elections, festivals)
- Node-specific LLM classification (UP, BHR, WB, KAR)
- Energy impact prediction with reasoning
- Semantic load profile flags
"""

from __future__ import annotations

import json
import io
import contextlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Load .env from backend folder
from dotenv import load_dotenv

# Load environment variables from backend/.env
_backend_dir = Path(__file__).resolve().parent
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Fallback to current directory

from src.agents.intelligence_agent.orchestrator import SmartGridIntelligenceAgent
from src.agents.intelligence_agent.scrapers.scheduled_events import (
    fetch_scheduled_events,
    fetch_events_for_state,
    get_date_summary
)
from src.agents.intelligence_agent.monitors.node_classifier import (
    NodeClassifierLLM,
    save_node_classifications_json
)


class StochasticTrigger:
    """Daily intelligence layer backed by real event scraping + scheduled events + LLM node classification."""

    def __init__(self, backend_dir: Path | None = None, enable_llm: bool = True) -> None:
        self.backend_dir = backend_dir or Path(__file__).resolve().parent
        self.cache_dir = self.backend_dir / "outputs" / "intelligence_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._agent = SmartGridIntelligenceAgent()
        
        # Node-specific LLM classifier
        self.enable_llm = enable_llm
        self._node_classifier = NodeClassifierLLM(llm_provider="openai") if enable_llm else None

    def _cache_path(self, day_index: int) -> Path:
        return self.cache_dir / f"day_{day_index:03d}.json"

    @staticmethod
    def _extract_primary_event_name(raw: Dict[str, Any]) -> str:
        events = raw.get("phase_1_grid_events", []) or []
        if events and isinstance(events, list):
            first = events[0] or {}
            name = str(first.get("event_name", "")).strip()
            if name:
                return name
        return "no_grid_event_detected"

    def generate_daily_report(
        self,
        *,
        day_index: int,
        date_str: str,
        state_ids: List[str],
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Return comprehensive daily intelligence report with:
        - RSS news scraping
        - Scheduled events (IPL, elections, festivals)
        - Node-specific LLM classification
        - Energy impact predictions with reasoning
        """
        cache = self._cache_path(day_index)
        if cache.exists() and not force_refresh:
            return json.loads(cache.read_text(encoding="utf-8"))

        rows: List[Dict[str, Any]] = []
        state_multipliers: Dict[str, float] = {}
        raw_agent_payload: Dict[str, Any] = {}
        
        # ==================================================================
        # STEP 1: Fetch Scheduled Events
        # ==================================================================
        print(f"\n[INTELLIGENCE] Step 1: Fetching scheduled events for {date_str}...")
        scheduled_events = fetch_scheduled_events(date_str)
        scheduled_summary = get_date_summary(date_str)
        
        print(f"  Found {len(scheduled_events)} scheduled events:")
        for evt in scheduled_events:
            print(f"    • {evt.event_name}: {evt.estimated_demand_delta_mw:+.0f} MW")
        
        # ==================================================================
        # STEP 2: Scrape RSS News
        # ==================================================================
        print(f"\n[INTELLIGENCE] Step 2: Scraping real-time news...")
        try:
            # Runs the real intelligence stack:
            # SmartGridIntelligenceAgent -> DeviationDetector -> EventScraper.
            with contextlib.redirect_stdout(io.StringIO()):
                raw_agent_payload = self._agent.run_all_regions()
            
            news_article_count = len(raw_agent_payload.get("scraped_articles", []))
            print(f"  Scraped {news_article_count} news articles")

        except Exception as exc:
            print(f"  [WARNING] RSS scraping failed: {exc}")
            raw_agent_payload = {}
        
        # ==================================================================
        # STEP 3: LLM Node Classification (if enabled)
        # ==================================================================
        node_classifications = {}
        node_summaries = {}
        
        if self.enable_llm and self._node_classifier:
            print(f"\n[INTELLIGENCE] Step 3: LLM node classification for UP, BHR, WB, KAR...")
            
            # Prepare articles for classification
            articles_to_classify = []
            scraped_articles = raw_agent_payload.get("scraped_articles", [])
            
            for i, article in enumerate(scraped_articles[:20]):  # Limit to top 20 to save API costs
                articles_to_classify.append({
                    "id": f"article_{day_index}_{i}",
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                    "source": article.get("source", ""),
                    "published": article.get("published", "")
                })
            
            # Run LLM classification
            scheduled_events_for_llm = scheduled_summary.get("events", [])
            classifications = self._node_classifier.classify_batch(
                articles_to_classify,
                scheduled_events=scheduled_events_for_llm
            )
            
            # Save classifications
            classifications_path = self.cache_dir / f"day_{day_index:03d}_node_classifications.json"
            save_node_classifications_json(classifications, str(classifications_path))
            
            # Generate node summaries
            for node_id in ["UP", "BHR", "WB", "KAR"]:
                summary = self._node_classifier.get_node_summary(node_id)
                node_summaries[node_id] = summary
                print(f"  {node_id}: {summary['relevant_article_count']} articles, {summary['total_impact_mw']:+.0f} MW impact")
        
        else:
            print(f"\n[INTELLIGENCE] Step 3: LLM classification DISABLED")
        
        # ==================================================================
        # STEP 4: Combine Everything into State Rows
        # ==================================================================
        print(f"\n[INTELLIGENCE] Step 4: Aggregating final report...")
        
        for state_id in state_ids:
            # Default multiplier from original agent
            data = raw_agent_payload.get(state_id, {}) or {}
            multipliers = data.get("grid_multipliers", {}) or {}
            base_demand_multiplier = float(multipliers.get("economic_demand_multiplier", 1.0))
            event_name = self._extract_primary_event_name(data)
            source_event_count = len(data.get("phase_1_grid_events", []) or [])
            
            # Scheduled events for this state
            state_scheduled_events = [
                {
                    "event_id": evt.event_id,
                    "event_name": evt.event_name,
                    "event_type": evt.event_type,
                    "estimated_delta_mw": evt.estimated_demand_delta_mw,
                    "flags": evt.flags,
                    "confidence": evt.confidence
                }
                for evt in scheduled_events
                if state_id in evt.affected_states or evt.is_national
            ]
            
            # Calculate total scheduled impact
            scheduled_delta_mw = sum(evt.estimated_demand_delta_mw for evt in scheduled_events 
                                     if state_id in evt.affected_states or evt.is_national)
            
            # Node classification summary
            node_summary = node_summaries.get(state_id, {
                "relevant_article_count": 0,
                "total_impact_mw": 0.0,
                "active_flags": [],
                "relevant_articles": []
            })
            
            # Combined demand multiplier
            # Base multiplier + scheduled events + news impact
            combined_delta_mw = scheduled_delta_mw + node_summary.get("total_impact_mw", 0.0)
            # Assume base demand is ~5000 MW per state (adjust as needed)
            assumed_base_demand_mw = 5000.0
            combined_multiplier = base_demand_multiplier + (combined_delta_mw / assumed_base_demand_mw)
            combined_multiplier = max(0.5, min(2.0, combined_multiplier))  # Clamp to reasonable range
            
            state_multipliers[state_id] = combined_multiplier
            
            rows.append({
                "state_id": state_id,
                "event_name": event_name,
                "demand_multiplier": round(combined_multiplier, 4),
                "base_multiplier": round(base_demand_multiplier, 4),
                "scheduled_delta_mw": round(scheduled_delta_mw, 2),
                "news_delta_mw": round(node_summary.get("total_impact_mw", 0.0), 2),
                "combined_delta_mw": round(combined_delta_mw, 2),
                "source": "intelligence_agent_enhanced",
                "source_event_count": source_event_count,
                "scheduled_event_count": len(state_scheduled_events),
                "news_article_count": node_summary.get("relevant_article_count", 0),
                "active_flags": node_summary.get("active_flags", []),
                "scheduled_events": state_scheduled_events,
                "node_classification": node_summary
            })
        
        print(f"\n[INTELLIGENCE] Report generation complete!")
        print(f"  Scheduled events: {len(scheduled_events)}")
        print(f"  News articles classified: {len(node_summaries)}")
        print(f"  State rows generated: {len(rows)}")

        report = {
            "day_index": day_index,
            "date": date_str,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "events": rows,
            "state_multipliers": state_multipliers,
            "scheduled_events_summary": scheduled_summary,
            "node_classifications": {
                node_id: {
                    "relevant_articles": summary["relevant_article_count"],
                    "total_impact_mw": summary["total_impact_mw"],
                    "active_flags": summary["active_flags"]
                }
                for node_id, summary in node_summaries.items()
            },
            "agent_payload": raw_agent_payload,
        }
        cache.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent
    trigger = StochasticTrigger(backend_dir=backend_dir, enable_llm=True)
    default_states = ["UP", "BHR", "WB", "KAR"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = trigger.generate_daily_report(
        day_index=0,
        date_str=today,
        state_ids=default_states,
        force_refresh=True,
    )
    out_path = backend_dir / "outputs" / "intelligence_cache" / "latest_full_pipeline.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n[INTELLIGENCE] Full pipeline report saved to: {out_path}")
