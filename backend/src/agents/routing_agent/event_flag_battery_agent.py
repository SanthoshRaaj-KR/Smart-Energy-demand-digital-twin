"""
event_flag_battery_agent.py
============================
Feature 5: Predictive "Event-Flag" Battery Pre-Charge

When the intelligence report flags a state with "stadium_surge" (or any
surge-type event flag), the Orchestrator locks that state's battery during
Step 1 (Temporal/Battery discharge).

The locked state's battery is NOT drained in the morning. 100% of battery
capacity is preserved specifically for the evening demand spike.

Logic:
    BEFORE Step 1:
        locked_states = EventFlagBatteryAgent.get_locked_states(intel_report)
    DURING Step 1:
        if state_id in locked_states:
            skip battery discharge for this state

Reasoning storage:
    Every lock decision is recorded in self.lock_log with:
        - Which state was locked
        - Which flag triggered the lock
        - How much battery capacity was preserved (MW)
        - The original deficit that would have been resolved
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Surge flag keywords that trigger battery lock
# ---------------------------------------------------------------------------

SURGE_FLAG_KEYWORDS = {
    "stadium_surge",
    "mega_event_surge",
    "election_surge",
    "festival_surge",
    "industrial_surge",
    "peak_demand_emergency",
}

# These flags also trigger a lock (partial or full)
PARTIAL_LOCK_KEYWORDS = {
    "ipl_match",
    "cricket_match",
    "concert_event",
    "scheduled_event_surge",
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class BatteryLockDecision:
    """Records a battery lock decision for one state."""
    def __init__(
        self,
        state_id: str,
        flag_triggered: str,
        battery_soc_preserved_mw: float,
        deficit_not_resolved_mw: float,
        lock_type: str,   # "FULL_LOCK" | "PARTIAL_LOCK"
        reasoning: str,
    ):
        self.state_id = state_id
        self.flag_triggered = flag_triggered
        self.battery_soc_preserved_mw = battery_soc_preserved_mw
        self.deficit_not_resolved_mw = deficit_not_resolved_mw
        self.lock_type = lock_type
        self.reasoning = reasoning
        self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_id": self.state_id,
            "flag_triggered": self.flag_triggered,
            "battery_soc_preserved_mw": round(self.battery_soc_preserved_mw, 2),
            "deficit_not_resolved_mw": round(self.deficit_not_resolved_mw, 2),
            "lock_type": self.lock_type,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class EventFlagBatteryAgent:
    """
    Pre-charge / battery lockout agent driven by intelligence event flags.

    When the intelligence report for a state contains a surge flag
    (e.g. stadium_surge, festival_surge), this agent instructs Step 1
    of the waterfall to skip battery discharge for that state.

    The logic: if there's a big event tonight, don't waste the battery
    this morning just to resolve a mild delta. Save it for the real spike.

    Full lock states: No discharge at all (stadium_surge, election_surge, etc.)
    Partial lock states: Only discharge up to 50% of available SOC (IPL, concerts)
    """

    def __init__(self) -> None:
        self.lock_log: List[BatteryLockDecision] = []

    def clear_log(self) -> None:
        """Clear lock log at start of each day."""
        self.lock_log.clear()

    def get_locked_states(
        self,
        intel_report: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Scan the intelligence report for surge flags and return a dict of
        state_id → lock_type for states that should have their batteries locked.

        Args:
            intel_report: Daily intelligence report from StochasticTrigger.
                          Contains 'events' list with 'active_flags' per state.

        Returns:
            Dict mapping state_id → "FULL_LOCK" | "PARTIAL_LOCK"
            Empty dict if no surge flags detected.
        """
        locked: Dict[str, str] = {}

        if not intel_report:
            return locked

        for row in intel_report.get("events", []):
            state_id = str(row.get("state_id", ""))
            if not state_id:
                continue

            active_flags: List[str] = list(row.get("active_flags", []) or [])
            # Also check scheduled events for flag signals
            for sched_evt in row.get("scheduled_events", []) or []:
                evt_flags = sched_evt.get("flags", []) or []
                active_flags.extend(evt_flags)

            # Normalise flags to lowercase
            active_flags_lower = [f.lower() for f in active_flags]

            # Check for full lock keywords
            triggered_full = [
                f for f in active_flags_lower
                if any(kw in f for kw in SURGE_FLAG_KEYWORDS)
            ]
            if triggered_full:
                locked[state_id] = "FULL_LOCK"
                continue

            # Check for partial lock keywords
            triggered_partial = [
                f for f in active_flags_lower
                if any(kw in f for kw in PARTIAL_LOCK_KEYWORDS)
            ]
            if triggered_partial:
                locked[state_id] = "PARTIAL_LOCK"

        if locked:
            print(f"  [EVENT-FLAG] Battery locks applied: {locked}")

        return locked

    def record_lock_applied(
        self,
        state_id: str,
        lock_type: str,
        flag_triggered: str,
        battery_soc_preserved_mw: float,
        deficit_not_resolved_mw: float,
    ) -> None:
        """Record that a battery lock was actually applied during Step 1."""
        if lock_type == "FULL_LOCK":
            reasoning = (
                f"State '{state_id}' has surge flag '{flag_triggered}'. "
                f"FULL_LOCK applied: battery fully preserved ({battery_soc_preserved_mw:.0f} MW SOC). "
                f"Morning deficit of {deficit_not_resolved_mw:.0f} MW will NOT be resolved by battery. "
                f"The battery capacity is saved for the predicted evening demand spike."
            )
        else:
            reasoning = (
                f"State '{state_id}' has event flag '{flag_triggered}'. "
                f"PARTIAL_LOCK applied: battery capped at 50% discharge. "
                f"Preserved {battery_soc_preserved_mw:.0f} MW SOC for evening peak. "
                f"Morning deficit of {deficit_not_resolved_mw:.0f} MW partially unresolved."
            )

        decision = BatteryLockDecision(
            state_id=state_id,
            flag_triggered=flag_triggered,
            battery_soc_preserved_mw=battery_soc_preserved_mw,
            deficit_not_resolved_mw=deficit_not_resolved_mw,
            lock_type=lock_type,
            reasoning=reasoning,
        )
        self.lock_log.append(decision)
        print(f"  [EVENT-FLAG] {lock_type}: {state_id} | {battery_soc_preserved_mw:.0f} MW preserved | flag={flag_triggered}")

    def compute_allowed_discharge(
        self,
        state_id: str,
        available_soc_mw: float,
        lock_type: str,
    ) -> float:
        """
        Compute how much battery can be discharged given the lock type.

        FULL_LOCK  → 0 MW discharge allowed
        PARTIAL_LOCK → max 50% of available SOC
        No lock    → full SOC available

        Args:
            state_id: State identifier (for logging)
            available_soc_mw: Current battery SOC in MW
            lock_type: "FULL_LOCK" | "PARTIAL_LOCK" | None

        Returns:
            Maximum MW that can be discharged this step.
        """
        if lock_type == "FULL_LOCK":
            return 0.0
        elif lock_type == "PARTIAL_LOCK":
            return available_soc_mw * 0.50   # Cap at 50% SOC
        else:
            return available_soc_mw            # No lock → full discharge

    def get_primary_flag(
        self,
        state_id: str,
        intel_report: Optional[Dict[str, Any]],
    ) -> str:
        """Get the primary surge flag for a state (for logging)."""
        if not intel_report:
            return "unknown_flag"
        for row in intel_report.get("events", []):
            if str(row.get("state_id", "")) != state_id:
                continue
            flags = list(row.get("active_flags", []) or [])
            for sched in row.get("scheduled_events", []) or []:
                flags.extend(sched.get("flags", []) or [])
            if flags:
                return flags[0]
        return "surge_flag"

    def get_log(self) -> List[Dict[str, Any]]:
        """Return full lock log as list of dicts."""
        return [d.to_dict() for d in self.lock_log]
