"""Intelligence orchestrator for 4-node smart grid simulation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .setup import CITY_REGISTRY
from .scrapers.multi_source import MultiSourceScraper
from .monitors.classifier import EventClassifier
from .monitors.aggregator import IntelligenceAggregator


class WeatherScraper:
    """Lightweight weather stub used by engine model features."""

    def fetch_forecast_7d(self, *, lat: float, lon: float, city_name: str) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat() + "Z"
        daily = []
        for i in range(7):
            daily.append(
                {
                    "date": f"day+{i+1}",
                    "max_c": 34.0 + (0.2 * i),
                    "min_c": 25.0 + (0.1 * i),
                    "heat_index_c": 37.0 + (0.25 * i),
                    "precipitation_mm": 2.0 if i in (2, 5) else 0.0,
                    "condition": "partly cloudy",
                }
            )

        return {
            "city": city_name,
            "lat": lat,
            "lon": lon,
            "generated_at": now,
            "current_temp_c": 31.0,
            "current_humidity_pct": 58,
            "current_condition": "partly cloudy",
            "week_max_c": max(d["max_c"] for d in daily),
            "week_max_heat_index_c": max(d["heat_index_c"] for d in daily),
            "week_total_rain_mm": sum(d["precipitation_mm"] for d in daily),
            "forecast_days": daily,
            "hourly_forecast_7d": [],
            "daily_forecast_7d": daily,
        }


class SmartGridIntelligenceAgent:
    """3-phase intelligence stack: fuel-path signals -> direct region events -> impact mapping."""

    TARGET_NODES = ["UP", "BHR", "WB", "KAR"]

    def __init__(self) -> None:
        self.scraper = MultiSourceScraper()
        self.classifier = EventClassifier()
        self.aggregator = IntelligenceAggregator()
        self.weather = WeatherScraper()

    def run_all_regions(self) -> Dict[str, Any]:
        raw_articles = self.scraper.scrape_all(include_gdelt=True)
        enriched = self.classifier.classify_batch(raw_articles)
        report = self.aggregator.aggregate(enriched, total_scraped=len(raw_articles))

        payload: Dict[str, Any] = {
            "scraped_articles": [
                {
                    "title": a.title,
                    "summary": a.description,
                    "source": a.source_name,
                    "published": a.published,
                    "url": a.url,
                    "feed_type": a.feed_type,
                }
                for a in raw_articles
            ],
            "meta": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "total_scraped": len(raw_articles),
                "total_classified": len(enriched),
                "national_severity": report.national_severity,
            },
        }

        for node_id in self.TARGET_NODES:
            payload[node_id] = self._build_region_payload(
                node_id=node_id,
                raw_articles=raw_articles,
                enriched_events=enriched,
                report=report,
            )

        return payload

    def _build_region_payload(
        self,
        *,
        node_id: str,
        raw_articles: List[Any],
        enriched_events: List[Any],
        report: Any,
    ) -> Dict[str, Any]:
        meta = CITY_REGISTRY.get(node_id, {})
        aliases = [a.lower() for a in meta.get("aliases", [])]

        # Phase 1: all node fuel-path and infra-chain relevant headlines.
        node_raw = []
        for a in raw_articles:
            text = f"{a.title} {a.description}".lower()
            if any(k in text for k in aliases) or any(
                kw in text
                for kw in [
                    "coal", "lng", "gas", "pipeline", "rail", "port", "transmission",
                    "nldc", "posoco", "grid", "powergrid", "thermal", "fuel supply",
                ]
            ):
                node_raw.append(a)

        phase_1_grid_events = [
            {
                "event_name": a.title,
                "source": a.source_name,
                "published": a.published,
                "url": a.url,
                "reason": "Fuel path / grid chain relevance",
            }
            for a in node_raw[:40]
        ]

        # Phase 2: direct region events from classifier output.
        node_events = []
        for e in enriched_events:
            if node_id in (e.affected_states or []) or e.is_national:
                node_events.append(e)

        # Weather de-prioritization except severe storms/floods/cyclones.
        filtered_events = []
        for e in node_events:
            if e.category != "weather":
                filtered_events.append(e)
                continue
            if e.subcategory in {"cyclone", "flood"} or e.severity in {"HIGH", "CRITICAL"}:
                filtered_events.append(e)

        detected_events = [
            {
                "title": e.title,
                "category": e.category,
                "subcategory": e.subcategory,
                "severity": e.severity,
                "estimated_delta_mw": e.estimated_delta_mw,
                "impact_direction": e.impact_direction,
                "reason": f"{e.category}/{e.subcategory} impacts node {node_id}",
                "source": e.source,
            }
            for e in filtered_events[:25]
        ]

        # Phase 3: map to impact + multipliers.
        state_delta = report.state_deltas.get(node_id)
        total_delta = float(state_delta.total_delta_mw) if state_delta else 0.0
        demand_mult = max(0.5, min(2.0, 1.0 + (total_delta / 5000.0)))
        gen_mult = 0.95 if (state_delta and state_delta.supply_down_mw > 100.0) else 1.0

        risk = "LOW"
        if state_delta:
            if state_delta.severity == "CRITICAL":
                risk = "CRITICAL"
            elif state_delta.severity == "HIGH":
                risk = "HIGH"
            elif state_delta.severity == "MEDIUM":
                risk = "MEDIUM"

        weather = self.weather.fetch_forecast_7d(
            lat=float(meta.get("lat", 0.0)),
            lon=float(meta.get("lon", 0.0)),
            city_name=str(meta.get("name", node_id)),
        )

        signals = []
        for e in detected_events[:8]:
            signals.append(
                f"{e['category']}/{e['subcategory']}: {e['title']} "
                f"(impact {e['estimated_delta_mw']:+.0f} MW)"
            )
        extracted_signals = "\n".join(signals)

        key_driver = detected_events[0]["title"] if detected_events else "No critical driver"
        impact_narrative = (
            f"{meta.get('name', node_id)} outlook: {len(detected_events)} relevant events mapped. "
            f"Primary driver: {key_driver}. Fuel-path and grid-chain signals were prioritized; "
            f"weather contributes only for severe events."
        )

        gm = {
            "economic_demand_multiplier": round(demand_mult, 4),
            "generation_capacity_multiplier": round(gen_mult, 4),
            "temperature_anomaly": round(float(weather.get("week_max_c", 0.0)) - 32.0, 2),
            "demand_spike_risk": risk,
            "supply_shortfall_risk": risk if (state_delta and state_delta.supply_down_mw > 0) else "LOW",
            "pre_event_hoard": any("fuel" in d["title"].lower() or "coal" in d["title"].lower() for d in detected_events),
            "seven_day_demand_forecast_mw_delta": round(total_delta, 2),
            "confidence": round(float(state_delta.confidence) if state_delta else 0.55, 3),
            "key_driver": key_driver,
            "reasoning": impact_narrative,
            "severity_level": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(risk, 1),
        }

        phase_trace = {
            "phase_1": {
                "raw_headline_count": len(raw_articles),
                "raw_headline_samples": [a.title for a in raw_articles[:10]],
                "phase_1_grid_events": phase_1_grid_events,
            },
            "phase_4": {
                "input_count": len(node_events),
                "output_count": len(filtered_events),
                "kept_headlines_sample": [e.title for e in filtered_events[:10]],
            },
            "phase_7": {
                "name": "Multiplier Synthesis",
                "status": "completed",
                "before_multiplier": {
                    "economic_demand_multiplier": 1.0,
                    "generation_capacity_multiplier": 1.0,
                    "temperature_anomaly": 0.0,
                },
                "after_multiplier": {
                    "economic_demand_multiplier": gm["economic_demand_multiplier"],
                    "generation_capacity_multiplier": gm["generation_capacity_multiplier"],
                    "temperature_anomaly": gm["temperature_anomaly"],
                },
            },
        }

        return {
            "node_id": node_id,
            "city": meta.get("name", node_id),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "grid_multipliers": gm,
            "detected_events": detected_events,
            "impact_narrative": impact_narrative,
            "extracted_signals": extracted_signals,
            "weather": weather,
            "city_intelligence": {
                "llm_confidence": gm["confidence"],
                "key_vulnerabilities": meta.get("key_vulnerabilities", []),
                "primary_fuel_sources": meta.get("primary_fuel_sources", []),
                "fuel_supply_routes": meta.get("fuel_supply_routes", []),
                "neighboring_exchange": meta.get("neighboring_exchange", []),
                "seasonal_demand_factors": meta.get("seasonal_demand_factors", []),
            },
            "phase_trace": phase_trace,
            "phase_1_grid_events": phase_1_grid_events,
        }

    @staticmethod
    def print_summary_table(intelligence: Dict[str, Any]) -> None:
        print("\n=== Intelligence Summary ===")
        for node in ["UP", "BHR", "WB", "KAR"]:
            d = intelligence.get(node, {})
            gm = d.get("grid_multipliers", {})
            print(
                f"{node:>3} | demand_x={gm.get('economic_demand_multiplier', 1.0):.3f} "
                f"| gen_x={gm.get('generation_capacity_multiplier', 1.0):.3f} "
                f"| events={len(d.get('detected_events', []))}"
            )

