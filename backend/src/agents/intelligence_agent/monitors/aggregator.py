"""
monitors/aggregator.py
======================
Aggregates EnrichedEvents → per-state AnomalyDelta and IntelligenceReport.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

try:
    from .classifier import EnrichedEvent, STATE_PEAK_MW, REGION_MAP
except ImportError:  # pragma: no cover - fallback for script-mode imports
    from monitors.classifier import EnrichedEvent, STATE_PEAK_MW, REGION_MAP


# ---------------------------------------------------------------------------
# OUTPUT MODELS
# ---------------------------------------------------------------------------

@dataclass
class StateAnomalyDelta:
    state_code: str
    total_delta_mw: float
    demand_up_mw: float
    supply_down_mw: float
    supply_up_mw: float
    dominant_direction: str
    severity: str
    top_events: List[str]  # event titles
    confidence: float


@dataclass
class IntelligenceReport:
    generated_at: str
    total_events_scraped: int
    total_events_classified: int

    # Per-state grid impact
    state_deltas: Dict[str, StateAnomalyDelta]

    # Aggregated across all states
    total_anomaly_delta_mw: float
    national_severity: str
    should_wake_orchestrator: bool

    # Breakdowns by category
    events_by_category: Dict[str, int]
    top_events: List[EnrichedEvent]  # top 20 by impact

    # Human-readable
    headline: str
    full_summary: str


# ---------------------------------------------------------------------------
# AGGREGATOR
# ---------------------------------------------------------------------------

class IntelligenceAggregator:
    """
    Takes a list of EnrichedEvents and produces an IntelligenceReport.

    Logic:
    - Events affecting specific states → accumulated into state deltas
    - National events → split proportionally across all modeled states
    - Per-state delta = demand_up - supply_down + supply_up
    - Total anomaly = sum of |state_deltas|
    """

    WAKE_THRESHOLD_MW = 50.0       # Wake orchestrator above this
    HIGH_SEVERITY_MW  = 500.0
    CRITICAL_MW       = 1000.0
    TOP_N_EVENTS      = 20

    ALL_STATES = sorted(STATE_PEAK_MW.keys())

    def aggregate(
        self,
        events: List[EnrichedEvent],
        total_scraped: int = 0,
    ) -> IntelligenceReport:
        now = datetime.utcnow().isoformat()

        # ── 1. Separate national vs state-specific
        state_events: Dict[str, List[EnrichedEvent]] = defaultdict(list)
        national_events: List[EnrichedEvent] = []

        for ev in events:
            if ev.is_national or not ev.affected_states:
                national_events.append(ev)
            else:
                for s in ev.affected_states:
                    state_events[s].append(ev)

        # ── 2. Compute per-state deltas
        state_deltas: Dict[str, StateAnomalyDelta] = {}

        all_active_states = set(state_events.keys()) | set(self.ALL_STATES)

        for state in all_active_states:
            local_evs = state_events.get(state, [])
            # Add proportional share of national events
            national_share = self._national_share(state, national_events)
            all_evs = local_evs + national_share

            delta = self._compute_state_delta(state, all_evs)
            state_deltas[state] = delta

        # ── 3. Total anomaly
        total_mw = sum(abs(d.total_delta_mw) for d in state_deltas.values())
        total_mw = round(total_mw, 1)

        # ── 4. National severity
        if total_mw >= self.CRITICAL_MW:
            nat_sev = "CRITICAL"
        elif total_mw >= self.HIGH_SEVERITY_MW:
            nat_sev = "HIGH"
        elif total_mw >= self.WAKE_THRESHOLD_MW:
            nat_sev = "MEDIUM"
        else:
            nat_sev = "LOW"

        wake = total_mw >= self.WAKE_THRESHOLD_MW

        # ── 5. Category breakdown
        cat_counts: Dict[str, int] = defaultdict(int)
        for ev in events:
            cat_counts[ev.category] += 1

        # ── 6. Top events by MW impact
        top = sorted(events, key=lambda e: e.estimated_delta_mw, reverse=True)[: self.TOP_N_EVENTS]

        # ── 7. Headline and summary
        headline = self._build_headline(nat_sev, total_mw, top)
        summary = self._build_summary(state_deltas, top, total_mw, nat_sev, now)

        return IntelligenceReport(
            generated_at=now,
            total_events_scraped=total_scraped,
            total_events_classified=len(events),
            state_deltas=state_deltas,
            total_anomaly_delta_mw=total_mw,
            national_severity=nat_sev,
            should_wake_orchestrator=wake,
            events_by_category=dict(cat_counts),
            top_events=top,
            headline=headline,
            full_summary=summary,
        )

    # ------------------------------------------------------------------

    def _national_share(
        self, state: str, national_events: List[EnrichedEvent]
    ) -> List[EnrichedEvent]:
        """
        Proportionally allocate national-level events to a state.
        Creates modified copies with scaled delta_mw.
        """
        if not national_events:
            return []
        state_peak = STATE_PEAK_MW.get(state, 5000)
        total_peak = sum(STATE_PEAK_MW.values())
        share = state_peak / total_peak

        scaled = []
        import copy
        for ev in national_events:
            ev_copy = copy.copy(ev)
            ev_copy.estimated_delta_mw = round(ev.estimated_delta_mw * share, 1)
            ev_copy.affected_states = [state]
            scaled.append(ev_copy)
        return scaled

    def _compute_state_delta(
        self, state: str, events: List[EnrichedEvent]
    ) -> StateAnomalyDelta:
        demand_up = 0.0
        supply_down = 0.0
        supply_up = 0.0

        top_titles = []
        confidences = []

        for ev in events:
            mw = ev.estimated_delta_mw * ev.confidence  # weight by confidence
            d = ev.impact_direction
            if d == "demand_up":
                demand_up += mw
            elif d == "supply_down":
                supply_down += mw
            elif d == "supply_up":
                supply_up += mw
            elif d == "both":
                supply_down += mw * 0.5
                demand_up += mw * 0.5
            elif d == "demand_down":
                demand_up -= mw  # reduces demand pressure

            if ev.estimated_delta_mw > 50:
                top_titles.append(ev.title[:80])
            confidences.append(ev.confidence)

        total = round(demand_up + supply_down - supply_up, 1)
        avg_conf = round(sum(confidences) / len(confidences), 3) if confidences else 0.5

        if abs(total) >= 500:
            sev = "CRITICAL"
        elif abs(total) >= 200:
            sev = "HIGH"
        elif abs(total) >= 50:
            sev = "MEDIUM"
        else:
            sev = "LOW"

        if demand_up >= supply_down:
            dom_dir = "demand_up"
        else:
            dom_dir = "supply_down"

        return StateAnomalyDelta(
            state_code=state,
            total_delta_mw=total,
            demand_up_mw=round(demand_up, 1),
            supply_down_mw=round(supply_down, 1),
            supply_up_mw=round(supply_up, 1),
            dominant_direction=dom_dir,
            severity=sev,
            top_events=top_titles[:3],
            confidence=avg_conf,
        )

    def _build_headline(
        self, severity: str, total_mw: float, top: List[EnrichedEvent]
    ) -> str:
        if not top:
            return f"[{severity}] No significant anomalies detected."
        driver = top[0].title[:80]
        return f"[{severity}] Anomaly_ΔMW = {total_mw:+,.0f} MW | Top driver: {driver}"

    def _build_summary(
        self,
        state_deltas: Dict[str, StateAnomalyDelta],
        top_events: List[EnrichedEvent],
        total_mw: float,
        severity: str,
        timestamp: str,
    ) -> str:
        lines = [
            f"=== INDIA ENERGY INTELLIGENCE REPORT ===",
            f"Generated : {timestamp} UTC",
            f"Severity  : {severity}",
            f"Total Δ MW: {total_mw:+,.0f} MW",
            "",
            "── TOP IMPACTED STATES ──",
        ]
        sorted_states = sorted(
            state_deltas.items(),
            key=lambda x: abs(x[1].total_delta_mw),
            reverse=True,
        )[:10]
        for code, d in sorted_states:
            if abs(d.total_delta_mw) < 1:
                continue
            lines.append(
                f"  {code:4s} [{d.severity:8s}] Δ{d.total_delta_mw:+8.0f} MW  "
                f"(demand↑{d.demand_up_mw:.0f} supply↓{d.supply_down_mw:.0f})"
            )

        lines += ["", "── TOP EVENTS BY IMPACT ──"]
        for i, ev in enumerate(top_events[:10], 1):
            lines.append(
                f"  {i:2d}. [{ev.severity:8s}] [{ev.category:12s}] "
                f"Δ{ev.estimated_delta_mw:+7.0f} MW | {ev.title[:75]}"
            )
            lines.append(f"      Source: {ev.source} | States: {', '.join(ev.affected_states) or 'national'}")

        return "\n".join(lines)
