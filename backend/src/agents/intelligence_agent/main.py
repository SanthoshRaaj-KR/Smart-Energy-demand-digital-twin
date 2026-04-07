"""
realtime_intel/main.py
======================
Main Entry Point — Real-Time India Energy Intelligence System

Usage:
    python main.py                   # Full scrape + report
    python main.py --quick           # Official + Energy feeds only
    python main.py --json            # Output JSON
    python main.py --watch 30        # Watch mode, refresh every 30 min
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.multi_source import MultiSourceScraper, RawArticle
from monitors.classifier import EventClassifier
from monitors.aggregator import IntelligenceAggregator


def run(
    full_scrape: bool = True,
    include_gdelt: bool = True,
    output_json: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Run one full intelligence cycle.

    Returns the report as a dict.
    """
    t0 = time.time()

    # ── STEP 1: Scrape ──────────────────────────────────────────────
    scraper = MultiSourceScraper()
    if full_scrape:
        raw_articles = scraper.scrape_all(include_gdelt=include_gdelt)
    else:
        raw_articles = scraper.scrape_targeted()

    elapsed_scrape = round(time.time() - t0, 1)
    if not quiet:
        print(f"\n[STEP 1] Scraped {len(raw_articles)} raw articles in {elapsed_scrape}s")

    # ── STEP 2: Classify ─────────────────────────────────────────────
    classifier = EventClassifier()
    enriched = classifier.classify_batch(raw_articles)
    elapsed_classify = round(time.time() - t0 - elapsed_scrape, 1)

    if not quiet:
        print(f"[STEP 2] Classified {len(enriched)} grid-relevant events in {elapsed_classify}s")
        _print_category_breakdown(enriched)

    # ── STEP 3: Aggregate ────────────────────────────────────────────
    aggregator = IntelligenceAggregator()
    report = aggregator.aggregate(enriched, total_scraped=len(raw_articles))
    elapsed_total = round(time.time() - t0, 1)

    if not quiet:
        print(f"\n[STEP 3] Aggregation complete in {elapsed_total}s total\n")
        print(report.full_summary)
        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR: {'WAKE UP ⚡' if report.should_wake_orchestrator else 'DORMANT 😴'}")
        print(f"TOTAL Δ MW  : {report.total_anomaly_delta_mw:+,.0f} MW")
        print(f"SEVERITY    : {report.national_severity}")
        print(f"{'='*60}")

    # ── STEP 4: Save outputs ─────────────────────────────────────────
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Save text report
    report_path = out_dir / f"reports/intel_report_{ts}.txt"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(report.full_summary, encoding="utf-8")

    # Build dict for JSON output
    report_dict = _report_to_dict(report)

    if output_json:
        json_path = out_dir / f"reports/intel_report_{ts}.json"
        json_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        if not quiet:
            print(f"\n[OUTPUT] JSON saved → {json_path}")

    # Always save latest
    (out_dir / "latest_report.json").write_text(
        json.dumps(report_dict, indent=2), encoding="utf-8"
    )
    (out_dir / "latest_report.txt").write_text(report.full_summary, encoding="utf-8")

    if not quiet:
        print(f"[OUTPUT] Text report → {report_path}")
        print(f"[OUTPUT] Latest      → {out_dir}/latest_report.json")

    return report_dict


def _print_category_breakdown(enriched):
    from collections import Counter
    cats = Counter(e.category for e in enriched)
    print("\n  Category breakdown:")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {cat:20s}: {cnt}")


def _report_to_dict(report) -> dict:
    return {
        "generated_at": report.generated_at,
        "total_events_scraped": report.total_events_scraped,
        "total_events_classified": report.total_events_classified,
        "national_severity": report.national_severity,
        "total_anomaly_delta_mw": report.total_anomaly_delta_mw,
        "should_wake_orchestrator": report.should_wake_orchestrator,
        "headline": report.headline,
        "events_by_category": report.events_by_category,
        "state_deltas": {
            code: {
                "total_delta_mw": d.total_delta_mw,
                "demand_up_mw": d.demand_up_mw,
                "supply_down_mw": d.supply_down_mw,
                "supply_up_mw": d.supply_up_mw,
                "dominant_direction": d.dominant_direction,
                "severity": d.severity,
                "top_events": d.top_events,
                "confidence": d.confidence,
            }
            for code, d in report.state_deltas.items()
        },
        "top_events": [
            {
                "event_id": e.event_id,
                "title": e.title,
                "category": e.category,
                "subcategory": e.subcategory,
                "severity": e.severity,
                "estimated_delta_mw": e.estimated_delta_mw,
                "impact_direction": e.impact_direction,
                "affected_states": e.affected_states,
                "is_national": e.is_national,
                "source": e.source,
                "published": e.published,
                "url": e.url,
                "keywords_matched": e.keywords_matched,
                "confidence": e.confidence,
            }
            for e in report.top_events
        ],
        "full_summary": report.full_summary,
    }


def watch_mode(interval_minutes: int = 30, **kwargs):
    """Run continuously, refreshing every N minutes."""
    print(f"\n[WATCH] Refreshing every {interval_minutes} minutes. Ctrl+C to stop.\n")
    cycle = 0
    while True:
        cycle += 1
        print(f"\n{'='*60}")
        print(f"[WATCH] Cycle #{cycle} at {datetime.utcnow().isoformat()} UTC")
        print(f"{'='*60}")
        try:
            run(**kwargs)
        except Exception as e:
            print(f"[WATCH] Error in cycle #{cycle}: {e}")
        print(f"\n[WATCH] Sleeping {interval_minutes} minutes...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Real-Time India Energy Intelligence System"
    )
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: official + energy feeds only")
    parser.add_argument("--no-gdelt", action="store_true",
                        help="Skip GDELT API")
    parser.add_argument("--json", action="store_true",
                        help="Save JSON report")
    parser.add_argument("--watch", type=int, metavar="MINUTES",
                        help="Watch mode: refresh every N minutes")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress detailed output")

    args = parser.parse_args()

    kwargs = dict(
        full_scrape=not args.quick,
        include_gdelt=not args.no_gdelt,
        output_json=args.json,
        quiet=args.quiet,
    )

    if args.watch:
        watch_mode(interval_minutes=args.watch, **kwargs)
    else:
        run(**kwargs)
