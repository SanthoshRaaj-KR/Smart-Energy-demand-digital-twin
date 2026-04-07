"""
frequency_monitor_agent.py
===========================
Feature 3: The "Lifeboat" Graph-Cut — Grid Frequency Monitor

Tracks a synthetic grid_frequency variable (starting at 50.0 Hz).

Physics model:
  • Every 100 MW of unresolved deficit drops frequency by 0.1 Hz
  • Formula: frequency = 50.0 - (unresolved_mw / 100) × 0.1

Critical threshold:
  • If grid_frequency <= 49.2 Hz → trigger Lifeboat Protocol (graph-cut islanding)

After islanding:
  • The sacrificed state's demand is zeroed out
  • Grid frequency resets to 50.0 Hz for remaining healthy states

Reasoning storage:
  Every frequency update and every Lifeboat trigger is recorded in
  self.frequency_log with full context (deficit_mw, frequency_hz, trigger, decision).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_FREQUENCY_HZ = 50.0
LIFEBOAT_TRIGGER_HZ = 49.2          # Below this → activate Lifeboat
DROP_PER_100_MW = 0.1               # Hz dropped per 100 MW unresolved deficit
MW_PER_HZ_DROP = 100.0              # Inverse: 100 MW causes 0.1 Hz drop


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class FrequencyEvent:
    """Records a single frequency update or lifeboat trigger."""
    timestamp: str
    day_index: int
    date_str: str
    unresolved_mw: float
    frequency_before_hz: float
    frequency_after_hz: float
    lifeboat_triggered: bool
    lifeboat_sacrificed_states: List[str]
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "day_index": self.day_index,
            "date": self.date_str,
            "unresolved_mw": round(self.unresolved_mw, 2),
            "frequency_before_hz": round(self.frequency_before_hz, 3),
            "frequency_after_hz": round(self.frequency_after_hz, 3),
            "lifeboat_triggered": self.lifeboat_triggered,
            "lifeboat_sacrificed_states": self.lifeboat_sacrificed_states,
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class FrequencyMonitorAgent:
    """
    Tracks synthetic grid frequency and triggers the Lifeboat Protocol
    (graph-cut islanding via LifeboatProtocol) when frequency drops to
    or below 49.2 Hz.

    This agent does NOT implement the islanding itself — it delegates to the
    existing LifeboatProtocol class. It only:
      1. Maintains grid_frequency state
      2. Computes frequency drops from deficit
      3. Decides when to pull the trigger
      4. Resets frequency after islanding
    """

    def __init__(self) -> None:
        self.grid_frequency: float = BASE_FREQUENCY_HZ
        self.frequency_log: List[FrequencyEvent] = []

    def reset(self) -> None:
        """Full reset for new simulation run."""
        self.grid_frequency = BASE_FREQUENCY_HZ
        self.frequency_log.clear()

    def update_frequency(
        self,
        unresolved_deficit_mw: float,
        day_index: int = 0,
        date_str: str = "",
    ) -> float:
        """
        Compute new grid frequency from unresolved deficit.

        Formula:
            frequency = 50.0 - (unresolved_mw / 100) * 0.1

        Each 100MW of unresolved deficit drops frequency by 0.1Hz.
        Frequency cannot go below 47.0Hz (physical minimum before total collapse).

        Returns the new frequency in Hz.
        """
        freq_before = self.grid_frequency
        drop = (max(unresolved_deficit_mw, 0.0) / MW_PER_HZ_DROP) * DROP_PER_100_MW
        new_freq = max(BASE_FREQUENCY_HZ - drop, 47.0)
        self.grid_frequency = new_freq

        reasoning = (
            f"Unresolved deficit={unresolved_deficit_mw:.0f} MW causes "
            f"frequency drop of {drop:.3f} Hz "
            f"(formula: {unresolved_deficit_mw:.0f} / {MW_PER_HZ_DROP} × {DROP_PER_100_MW}). "
            f"New frequency: {new_freq:.3f} Hz."
        )
        if new_freq <= LIFEBOAT_TRIGGER_HZ:
            reasoning += f" ⚠️ CRITICAL: {new_freq:.3f} Hz ≤ {LIFEBOAT_TRIGGER_HZ} Hz threshold. Lifeboat Protocol armed."

        self.frequency_log.append(FrequencyEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            day_index=day_index,
            date_str=date_str,
            unresolved_mw=unresolved_deficit_mw,
            frequency_before_hz=freq_before,
            frequency_after_hz=new_freq,
            lifeboat_triggered=False,  # Will be updated if lifeboat fires
            lifeboat_sacrificed_states=[],
            reasoning=reasoning,
        ))

        return new_freq

    def should_trigger_lifeboat(self) -> bool:
        """
        Return True if current grid frequency has reached or fallen below
        the Lifeboat trigger threshold of 49.2 Hz.
        """
        return self.grid_frequency <= LIFEBOAT_TRIGGER_HZ

    def reset_after_island(
        self,
        sacrificed_states: List[str],
        day_index: int = 0,
        date_str: str = "",
    ) -> None:
        """
        After the Lifeboat Protocol islands the failing state(s), reset
        grid frequency to 50.0 Hz for the surviving healthy grid.

        Updates the last log entry to mark the lifeboat as triggered.
        """
        freq_before = self.grid_frequency
        self.grid_frequency = BASE_FREQUENCY_HZ

        reasoning = (
            f"Lifeboat activated. States islanded: {sacrificed_states}. "
            f"Their load zeroed. Surviving grid frequency reset from "
            f"{freq_before:.3f} Hz → {BASE_FREQUENCY_HZ} Hz. "
            f"Grid stabilised."
        )

        # Update last log entry
        if self.frequency_log:
            last = self.frequency_log[-1]
            self.frequency_log[-1] = FrequencyEvent(
                timestamp=last.timestamp,
                day_index=day_index,
                date_str=date_str,
                unresolved_mw=last.unresolved_mw,
                frequency_before_hz=last.frequency_before_hz,
                frequency_after_hz=BASE_FREQUENCY_HZ,
                lifeboat_triggered=True,
                lifeboat_sacrificed_states=sacrificed_states,
                reasoning=reasoning,
            )
        else:
            self.frequency_log.append(FrequencyEvent(
                timestamp=datetime.utcnow().isoformat() + "Z",
                day_index=day_index,
                date_str=date_str,
                unresolved_mw=0.0,
                frequency_before_hz=freq_before,
                frequency_after_hz=BASE_FREQUENCY_HZ,
                lifeboat_triggered=True,
                lifeboat_sacrificed_states=sacrificed_states,
                reasoning=reasoning,
            ))

        print(f"  [FREQUENCY] Lifeboat reset: {freq_before:.3f} Hz → {BASE_FREQUENCY_HZ} Hz")
        print(f"  [FREQUENCY] Islanded states: {sacrificed_states}")

    def get_current_frequency(self) -> float:
        """Return current grid frequency in Hz."""
        return self.grid_frequency

    def get_log(self) -> List[Dict[str, Any]]:
        """Return full frequency event log as list of dicts."""
        return [e.to_dict() for e in self.frequency_log]

    def get_status_summary(self) -> Dict[str, Any]:
        """Return current status summary for API/frontend."""
        total_lifeboat_events = sum(
            1 for e in self.frequency_log if e.lifeboat_triggered
        )
        min_frequency = min(
            (e.frequency_after_hz for e in self.frequency_log),
            default=BASE_FREQUENCY_HZ,
        )
        return {
            "current_frequency_hz": round(self.grid_frequency, 3),
            "base_frequency_hz": BASE_FREQUENCY_HZ,
            "lifeboat_trigger_hz": LIFEBOAT_TRIGGER_HZ,
            "is_critical": self.grid_frequency <= LIFEBOAT_TRIGGER_HZ,
            "is_stable": self.grid_frequency >= 49.8,
            "total_lifeboat_events": total_lifeboat_events,
            "minimum_frequency_recorded_hz": round(min_frequency, 3),
            "total_events_logged": len(self.frequency_log),
        }
