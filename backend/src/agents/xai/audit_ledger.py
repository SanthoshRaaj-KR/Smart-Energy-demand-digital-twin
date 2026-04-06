"""
XAI daily audit ledger utilities.

Creates human-readable 7-stage records from simulation outputs so regulators and
operators can understand what happened, why, and with what outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List


@dataclass(frozen=True)
class AuditPhaseEntry:
    phase_number: int
    phase_name: str
    actor: str
    action: str
    execution: str
    result: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_number": self.phase_number,
            "phase_name": self.phase_name,
            "actor": self.actor,
            "action": self.action,
            "execution": self.execution,
            "result": self.result,
            "details": self.details,
        }


class XAIDailyAuditLedger:
    """Builds a single-day 7-phase ledger payload."""

    def build(
        self,
        *,
        sim_date: str,
        day_index: int,
        initial_deficits: Dict[str, float],
        dr_activated_mw: float,
        dr_savings_inr: float,
        executed_trades: List[Dict[str, Any]],
        load_shedding: Dict[str, float],
        memory_warning: str | None,
        memory_state: List[str],
        frequency_before_hz: float | None,
        frequency_after_hz: float | None,
        xai_phase_trace_path: str | None,
        baseline_day: Dict[str, Any] | None,
        delta_event: Dict[str, Any] | None,
        llm_wake_threshold_mw: float = 50.0,
    ) -> Dict[str, Any]:
        total_initial_deficit = sum(max(0.0, float(v)) for v in initial_deficits.values())
        transferred_mw = sum(float(t.get("approved_mw", 0.0)) for t in executed_trades)
        shed_mw = sum(max(0.0, float(v)) for v in load_shedding.values())
        resolved_without_shedding = max(0.0, total_initial_deficit - shed_mw)
        remaining_after_resolution = max(0.0, total_initial_deficit - resolved_without_shedding)

        llm_enabled = False
        national_net_mw = None
        max_state_imbalance_mw = None
        if baseline_day:
            llm_enabled = bool(baseline_day.get("llm_agents_enabled", False))
            national_net_mw = baseline_day.get("national_net_mw")
            max_state_imbalance_mw = baseline_day.get("max_state_imbalance_mw")

        phase_entries = [
            AuditPhaseEntry(
                phase_number=1,
                phase_name="A Priori Planner",
                actor="ForwardMarketPlanner",
                action="Load baseline forecast and decide LLM wake/sleep",
                execution=(
                    f"Used 30-day baseline day_index={day_index}; "
                    f"threshold={llm_wake_threshold_mw:.1f} MW"
                ),
                result="LLM awake" if llm_enabled else "LLM dormant (baseline only)",
                details={
                    "baseline_day": baseline_day or {},
                    "national_net_mw": national_net_mw,
                    "max_state_imbalance_mw": max_state_imbalance_mw,
                    "llm_agents_enabled": llm_enabled,
                },
            ),
            AuditPhaseEntry(
                phase_number=2,
                phase_name="Intelligence Extraction",
                actor="IntelligenceAgent",
                action="Compute anomaly/delta signal",
                execution="Generated/loaded delta trigger event",
                result="Delta detected" if delta_event else "No delta event",
                details={"delta_event": delta_event or {}},
            ),
            AuditPhaseEntry(
                phase_number=3,
                phase_name="Strict Waterfall - Temporal+Economic",
                actor="UnifiedRoutingOrchestrator + StateAgent",
                action="Resolve deficit via battery first, then DR",
                execution=(
                    f"Initial deficit={total_initial_deficit:.2f} MW; "
                    f"DR activated={dr_activated_mw:.2f} MW"
                ),
                result="Temporal/Economic step completed",
                details={
                    "initial_deficits_mw": initial_deficits,
                    "dr_activated_mw": dr_activated_mw,
                    "dr_savings_inr": dr_savings_inr,
                },
            ),
            AuditPhaseEntry(
                phase_number=4,
                phase_name="Strict Waterfall - Spatial",
                actor="Phase6NegotiationAgent + Phase7SyndicateAgent",
                action="Route inter-state transfers via transmission network",
                execution=f"Executed trades={len(executed_trades)}",
                result=f"Transferred {transferred_mw:.2f} MW across corridors",
                details={"executed_trades": executed_trades},
            ),
            AuditPhaseEntry(
                phase_number=5,
                phase_name="Strict Waterfall - Fallback",
                actor="UnifiedRoutingOrchestrator",
                action="Apply controlled fallback if deficit remains",
                execution=(
                    f"Residual check after routing; frequency "
                    f"{frequency_before_hz if frequency_before_hz is not None else 'n/a'} -> "
                    f"{frequency_after_hz if frequency_after_hz is not None else 'n/a'} Hz"
                ),
                result=(
                    f"Load shedding {shed_mw:.2f} MW" if shed_mw > 0 else "No forced load shedding"
                ),
                details={
                    "load_shedding_mw": load_shedding,
                    "grid_frequency_before_hz": frequency_before_hz,
                    "grid_frequency_after_hz": frequency_after_hz,
                },
            ),
            AuditPhaseEntry(
                phase_number=6,
                phase_name="Settlement + XAI Trace",
                actor="SettlementAgent + XAIAgent",
                action="Publish operational and explainability records",
                execution="Wrote settlement summary and phase trace artifacts",
                result="Daily records committed",
                details={"xai_phase_trace_path": xai_phase_trace_path},
            ),
            AuditPhaseEntry(
                phase_number=7,
                phase_name="Self-Healing Memory",
                actor="XAIAgent + grid_short_term_memory",
                action="Store warning for next-day adaptive behavior",
                execution=f"Memory size={len(memory_state)} / 3",
                result="Warning stored" if memory_warning else "No new warning",
                details={
                    "memory_warning": memory_warning,
                    "memory_state": memory_state,
                },
            ),
        ]

        return {
            "document_type": "xai_daily_audit_ledger",
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "date": sim_date,
            "day_index": day_index,
            "summary": {
                "initial_total_deficit_mw": total_initial_deficit,
                "resolved_without_shedding_mw": resolved_without_shedding,
                "remaining_after_resolution_mw": remaining_after_resolution,
                "load_shedding_mw": shed_mw,
                "dr_activated_mw": dr_activated_mw,
                "dr_savings_inr": dr_savings_inr,
                "transferred_mw": transferred_mw,
                "llm_agents_enabled": llm_enabled,
            },
            "phases": [entry.to_dict() for entry in phase_entries],
        }

