"""
demo_runner.py
==============
Demonstrates the full pipeline with realistic simulated articles.
Use this to verify the classifier + aggregator work correctly.
In production, MultiSourceScraper.scrape_all() provides the real data.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrapers.multi_source import RawArticle
from monitors.classifier import EventClassifier
from monitors.aggregator import IntelligenceAggregator

NOW = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# REALISTIC SIMULATED NEWS FEED (mimics what scraper would return)
# ---------------------------------------------------------------------------

SIMULATED_ARTICLES = [
    # ── ENERGY ──────────────────────────────────────────────────────────────
    RawArticle(
        source_name="Grid-India NLDC",
        source_url="https://grid-india.in/feed/",
        title="Coal stock at thermal plants critically low in Uttar Pradesh, Bihar - NLDC Alert",
        description=(
            "The National Load Dispatch Centre (NLDC) has issued an alert over critically low coal stocks "
            "at several thermal power plants in Uttar Pradesh and Bihar. Multiple 500 MW units have been "
            "shut down due to coal shortage. The coal stock has fallen below the 4-day critical threshold. "
            "UPPCL and NBPDCL have been asked to arrange emergency coal rakes."
        ),
        url="https://grid-india.in/alert/coal-stock-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_official",
    ),
    RawArticle(
        source_name="ET Energy",
        source_url="https://energy.economictimes.indiatimes.com",
        title="Severe heatwave across Rajasthan, Maharashtra pushes electricity demand to record 48 GW",
        description=(
            "An intense heatwave with temperatures soaring to 46 degrees Celsius in Rajasthan and 44 degrees "
            "in Maharashtra has pushed electricity demand to an all-time high of 48 GW nationally. "
            "Maharashtra State Electricity Distribution Company Limited (MSEDCL) is facing a demand of "
            "31,000 MW against a supply of only 27,000 MW. Load shedding of 4-6 hours is being reported "
            "across rural Maharashtra. Rajasthan is also facing an acute power shortage of 3,000 MW."
        ),
        url="https://energy.economictimes.indiatimes.com/heatwave-demand-record",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_energy",
    ),
    RawArticle(
        source_name="PIB India",
        source_url="https://pib.gov.in",
        title="Ministry of Power approves emergency 2000 MW power purchase for deficit states",
        description=(
            "The Ministry of Power has approved emergency power purchase of 2000 MW from the day-ahead "
            "market (DAM) on Indian Energy Exchange (IEX) to meet the deficit in northern and western states. "
            "The spot price at IEX has surged to Rs 12 per kWh, more than 30% above the normal rate."
        ),
        url="https://pib.gov.in/press/emergency-power-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_official",
    ),
    RawArticle(
        source_name="Business Standard Power",
        source_url="https://www.business-standard.com",
        title="Cyclone Dana makes landfall in Odisha, 4000 MW generation capacity knocked offline",
        description=(
            "Super Cyclone Dana made landfall near Paradip in Odisha with wind speeds of 185 km/h, "
            "knocking out 4000 MW of generation capacity including the Paradip Thermal Plant. "
            "The ERLDC has declared a grid emergency for the eastern region. West Bengal's WBSEDCL "
            "is also affected with 1200 MW of transmission lines tripped due to the cyclone."
        ),
        url="https://business-standard.com/cyclone-dana-odisha-power",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_energy",
    ),

    # ── ECONOMIC ─────────────────────────────────────────────────────────────
    RawArticle(
        source_name="Reuters Business",
        source_url="https://feeds.reuters.com",
        title="Brent crude surges 18% as OPEC+ announces surprise production cut; India import bill to spike",
        description=(
            "Brent crude oil prices surged 18% to $112 per barrel after OPEC+ announced an unexpected "
            "production cut of 2 million barrels per day. India, which imports 85% of its crude requirements, "
            "faces a significant rise in import costs. The rupee fell to 87.4 against the dollar. "
            "Gas-dependent power plants in Gujarat and Tamil Nadu are expected to face higher fuel costs, "
            "potentially increasing electricity tariffs by 15-20%."
        ),
        url="https://reuters.com/opec-production-cut-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_geo",
    ),
    RawArticle(
        source_name="LiveMint Energy",
        source_url="https://www.livemint.com",
        title="LNG spot price hits $35/MMBtu; Petronet LNG suspends spot cargo purchases",
        description=(
            "LNG spot prices have surged to $35 per MMBtu in Asia due to supply disruptions from the "
            "Middle East. Petronet LNG has suspended spot cargo purchases due to prohibitive costs. "
            "This will affect gas supply to power plants in Gujarat, Tamil Nadu, and Andhra Pradesh. "
            "Approximately 8,000 MW of gas-based generation could be curtailed."
        ),
        url="https://livemint.com/lng-price-surge-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_energy",
    ),
    RawArticle(
        source_name="ET Economy",
        source_url="https://economictimes.indiatimes.com",
        title="CERC approves 12% electricity tariff hike for 8 states; consumer tariffs to rise from May",
        description=(
            "The Central Electricity Regulatory Commission (CERC) has approved a 12% tariff hike for "
            "power distribution companies in 8 states including Uttar Pradesh, Maharashtra, Rajasthan, "
            "Karnataka, West Bengal, Bihar, Odisha, and Madhya Pradesh. The tariff order comes into effect "
            "from May 1. This is expected to moderately reduce residential electricity demand but improve "
            "DISCOM financial health."
        ),
        url="https://economictimes.com/cerc-tariff-hike-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_energy",
    ),

    # ── POLITICAL ────────────────────────────────────────────────────────────
    RawArticle(
        source_name="The Hindu",
        source_url="https://www.thehindu.com",
        title="Power workers strike in West Bengal: CESC and WBSEDCL employees down tools for 48 hours",
        description=(
            "Electricity employees of CESC and West Bengal State Electricity Distribution Company Limited "
            "(WBSEDCL) have gone on a 48-hour strike demanding wage revision. The strike has affected "
            "maintenance operations across West Bengal. Emergency skeleton staff are operating critical "
            "installations. Kolkata has reported sporadic power cuts in several districts."
        ),
        url="https://thehindu.com/wb-power-workers-strike-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_india",
    ),
    RawArticle(
        source_name="NDTV India",
        source_url="https://www.ndtv.com",
        title="Bharat Bandh called by opposition parties; rail and road transport to be disrupted across India",
        description=(
            "Major opposition parties have called a Bharat Bandh on Thursday in protest against rising "
            "fuel prices and inflation. The bandh is expected to affect commercial activity across India. "
            "Industrial demand for electricity is expected to drop by 15-20% during the day. However, "
            "residential demand may spike as workers stay home. States like Maharashtra, West Bengal, "
            "Karnataka, and Tamil Nadu are likely to see significant bandh impact."
        ),
        url="https://ndtv.com/bharat-bandh-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_india",
    ),
    RawArticle(
        source_name="Indian Express",
        source_url="https://indianexpress.com",
        title="Punjab elections scheduled for April 15; model code of conduct to restrict industrial activity",
        description=(
            "Punjab assembly elections have been scheduled for April 15. The Election Commission of India "
            "has imposed the Model Code of Conduct. Major industrial units in Ludhiana and Amritsar are "
            "expected to operate at reduced capacity during election week. Punjab's peak electricity "
            "demand during elections typically increases by 800 MW due to campaign activity."
        ),
        url="https://indianexpress.com/punjab-elections-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_india",
    ),

    # ── MILITARY / GEOPOLITICAL ──────────────────────────────────────────────
    RawArticle(
        source_name="Reuters World",
        source_url="https://feeds.reuters.com",
        title="Iran attacks shipping in Strait of Hormuz; oil tanker routes disrupted, crude prices surge",
        description=(
            "Iran's Revolutionary Guard Corps attacked three oil tankers in the Strait of Hormuz, "
            "disrupting shipping lanes used by 20% of global oil trade. Brent crude surged $8 per barrel "
            "on the news. India's crude imports from the Gulf are at risk. The Indian Navy has put "
            "its western fleet on high alert. Analysts warn of prolonged supply disruption that could "
            "push India's fuel import costs up by $15-20 billion annually if the situation escalates."
        ),
        url="https://reuters.com/iran-hormuz-attack-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_geo",
    ),
    RawArticle(
        source_name="BBC South Asia",
        source_url="https://feeds.bbci.co.uk",
        title="India-Pakistan border tension escalates at LoC; military mobilization in Jammu & Kashmir",
        description=(
            "India-Pakistan tensions have escalated along the Line of Control (LoC) in Jammu and Kashmir "
            "following a series of cross-border firing incidents. India has mobilized additional military "
            "units to the border area. Civilian movement has been restricted in several districts of "
            "Jammu and Kashmir. Industrial activity near the border has been halted. Power supply to "
            "border areas is being managed under emergency protocols."
        ),
        url="https://bbc.co.uk/india-pakistan-loc-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_geo",
    ),
    RawArticle(
        source_name="Al Jazeera",
        source_url="https://www.aljazeera.com",
        title="Russia cuts gas exports to Europe by 40%; global LNG demand spikes, India spot imports threatened",
        description=(
            "Russia has cut natural gas exports to Europe by 40% following a new round of sanctions, "
            "triggering a global scramble for LNG. Asian spot LNG prices are expected to rise sharply "
            "as European buyers outbid Asian importers. India's gas-based power plants, which import "
            "significant volumes of LNG, face potential supply disruptions. The crisis is expected to "
            "persist for 6-12 months."
        ),
        url="https://aljazeera.com/russia-gas-cut-europe-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_geo",
    ),

    # ── WEATHER ──────────────────────────────────────────────────────────────
    RawArticle(
        source_name="TOI India",
        source_url="https://timesofindia.indiatimes.com",
        title="IMD issues red alert for heatwave in Telangana, Andhra Pradesh; temperature to touch 48°C",
        description=(
            "The India Meteorological Department (IMD) has issued a red alert for an extreme heatwave "
            "in Telangana and Andhra Pradesh, with temperatures expected to touch 48 degrees Celsius over "
            "the next 5 days. Power distribution companies TSSPDCL and APSPDCL are on high alert. "
            "Air conditioning demand is expected to surge by 25% above normal. The Hyderabad region "
            "alone may see an additional 1,200 MW demand."
        ),
        url="https://timesofindia.com/telangana-heatwave-red-alert-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_india",
    ),
    RawArticle(
        source_name="NDTV India",
        source_url="https://www.ndtv.com",
        title="Flash floods in Assam damage power infrastructure; 800 MW generation affected",
        description=(
            "Severe flash floods in Assam have damaged power infrastructure across 12 districts. "
            "The Kopili Hydro Electric Project (800 MW) has been shut down due to flood damage. "
            "Over 200 distribution transformers have been washed away. APDCL is working on restoration. "
            "Power supply to 3 million households in Assam has been disrupted."
        ),
        url="https://ndtv.com/assam-floods-power-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_india",
    ),

    # ── POSITIVE (supply addition) ───────────────────────────────────────────
    RawArticle(
        source_name="PIB India",
        source_url="https://pib.gov.in",
        title="PM inaugurates 3,000 MW solar park in Rajasthan; largest single solar plant in India",
        description=(
            "Prime Minister inaugurated the 3,000 MW Bhadla Solar Park Phase 4 in Rajasthan, making it "
            "the largest single solar installation in India. The park will supply electricity to "
            "Rajasthan, Haryana, and Delhi under long-term PPAs at Rs 2.1 per kWh. The capacity addition "
            "is expected to reduce Rajasthan's power deficit significantly."
        ),
        url="https://pib.gov.in/bhadla-solar-inauguration-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_official",
    ),

    # ── COAL MINE DISRUPTION ─────────────────────────────────────────────────
    RawArticle(
        source_name="Business Standard Power",
        source_url="https://www.business-standard.com",
        title="Coal mine workers strike in Jharkhand affects 15 million tonne annual production; thermal plants at risk",
        description=(
            "Coal mine workers in Jharkhand have gone on an indefinite strike, affecting coal production "
            "from mines supplying 15 million tonnes annually to thermal power plants in Jharkhand, "
            "West Bengal, and Bihar. Eastern India's power plants may face acute coal shortage within "
            "10 days if the strike continues. ERLDC has begun contingency planning."
        ),
        url="https://business-standard.com/jharkhand-coal-mine-strike-2026",
        published=NOW,
        scraped_at=NOW,
        feed_type="rss_energy",
    ),
]


def run_demo():
    print("\n" + "=" * 70)
    print("DEMO MODE — Real-Time India Energy Intelligence System")
    print("=" * 70)
    print(f"[DEMO] Using {len(SIMULATED_ARTICLES)} realistic simulated articles")
    print("[DEMO] In production, MultiSourceScraper fetches from 45+ live feeds\n")

    # ── Classify
    classifier = EventClassifier()
    enriched = classifier.classify_batch(SIMULATED_ARTICLES)

    print(f"[CLASSIFIER] {len(SIMULATED_ARTICLES)} raw → {len(enriched)} classified\n")

    # Print classified events
    print("── CLASSIFIED EVENTS (sorted by MW impact) ──")
    for i, ev in enumerate(enriched, 1):
        print(
            f"  {i:2d}. [{ev.severity:8s}] [{ev.category:13s}/{ev.subcategory:20s}] "
            f"Δ{ev.estimated_delta_mw:+8.0f} MW  {ev.impact_direction}"
        )
        print(f"       States: {', '.join(ev.affected_states) or '(national)':40s}  "
              f"National={ev.is_national}  Conf={ev.confidence:.2f}")
        print(f"       Source: {ev.source}")
        print(f"       Title : {ev.title[:85]}")
        if ev.keywords_matched:
            print(f"       KWs   : {ev.keywords_matched[:5]}")
        print()

    # ── Aggregate
    aggregator = IntelligenceAggregator()
    report = aggregator.aggregate(enriched, total_scraped=len(SIMULATED_ARTICLES))

    print("\n" + "=" * 70)
    print(report.full_summary)

    print(f"\n{'='*70}")
    print(f"ORCHESTRATOR : {'⚡ WAKE UP' if report.should_wake_orchestrator else '😴 DORMANT'}")
    print(f"TOTAL Δ MW   : {report.total_anomaly_delta_mw:+,.0f} MW")
    print(f"SEVERITY     : {report.national_severity}")
    print(f"{'='*70}\n")

    # ── Per-state table
    print("── PER-STATE ANOMALY TABLE (top 15) ──")
    print(f"{'State':5s} {'Severity':10s} {'Δ Total MW':>12s} {'↑Demand':>10s} {'↓Supply':>10s} {'Direction':15s}")
    print("-" * 75)
    sorted_states = sorted(
        report.state_deltas.items(),
        key=lambda x: abs(x[1].total_delta_mw),
        reverse=True,
    )
    for code, d in sorted_states[:15]:
        if abs(d.total_delta_mw) < 0.5:
            continue
        print(
            f"{code:5s} {d.severity:10s} {d.total_delta_mw:>+12.0f} MW "
            f"{d.demand_up_mw:>10.0f} MW {d.supply_down_mw:>10.0f} MW  "
            f"{d.dominant_direction}"
        )

    # ── JSON output
    out = Path("outputs/demo_report.json")
    out.parent.mkdir(exist_ok=True)
    report_dict = {
        "generated_at": report.generated_at,
        "national_severity": report.national_severity,
        "total_anomaly_delta_mw": report.total_anomaly_delta_mw,
        "should_wake_orchestrator": report.should_wake_orchestrator,
        "events_by_category": report.events_by_category,
        "state_deltas": {
            code: {
                "total_delta_mw": d.total_delta_mw,
                "demand_up_mw": d.demand_up_mw,
                "supply_down_mw": d.supply_down_mw,
                "severity": d.severity,
                "dominant_direction": d.dominant_direction,
                "top_events": d.top_events,
            }
            for code, d in report.state_deltas.items()
        },
        "top_events": [
            {
                "title": e.title,
                "category": e.category,
                "subcategory": e.subcategory,
                "severity": e.severity,
                "delta_mw": e.estimated_delta_mw,
                "direction": e.impact_direction,
                "states": e.affected_states,
                "is_national": e.is_national,
                "source": e.source,
            }
            for e in report.top_events
        ],
    }
    out.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    print(f"\n[OUTPUT] Demo JSON → {out}")
    print("[OUTPUT] In production: python main.py --json\n")


if __name__ == "__main__":
    run_demo()
