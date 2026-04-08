"""Unified Orchestrator (simulator.py).

Execution core:
- Reads baseline from APrioriBrain
- Reads daily multipliers from StochasticTrigger
- Computes Delta = (Baseline * Multiplier) - Baseline
- Runs waterfall when Delta > 0
- Maintains 3-day memory via UnifiedRoutingOrchestrator
"""

from __future__ import annotations

import json
import io
import contextlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from engine import APrioriBrain
from intelligence import StochasticTrigger
from src.agents.routing_agent.unified_routing_orchestrator import UnifiedRoutingOrchestrator
from src.agents.routing_agent.parameter_autopsy_agent import ParameterAutopsyAgent


class UnifiedOrchestrator:
    """End-to-end deterministic + stochastic + waterfall + memory simulator."""

    def __init__(self, backend_dir: Path | None = None) -> None:
        self.backend_dir = backend_dir or Path(__file__).resolve().parent
        self.outputs_dir = self.backend_dir / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

        self.brain = APrioriBrain(self.backend_dir)
        self.trigger = StochasticTrigger(self.backend_dir)
        self.waterfall = UnifiedRoutingOrchestrator()
        self.autopsy = ParameterAutopsyAgent()

    def _load_grid_config(self) -> Dict[str, Any]:
        cfg_path = self.backend_dir / "config" / "grid_config.json"
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    def _load_edge_capacities(self, cfg: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
        caps: Dict[Tuple[str, str], float] = {}
        for c in cfg.get("corridors", []):
            src = str(c.get("src", ""))
            dst = str(c.get("dst", ""))
            cap = float(c.get("capacity_mw", 0.0))
            if src and dst:
                caps[(src, dst)] = cap
                caps[(dst, src)] = cap
        return caps

    def _load_battery_maps(self, cfg: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, float]]:
        soc: Dict[str, float] = {}
        cap: Dict[str, float] = {}
        for state_id, node in cfg.get("nodes", {}).items():
            battery = node.get("battery", {})
            soc[state_id] = float(battery.get("initial_charge", 0.0))
            cap[state_id] = float(battery.get("capacity", 0.0))
        return soc, cap

    def run(self, *, start_date: str = "2026-04-01", days: int = 30) -> Dict[str, Any]:
        master_schedule = self.brain.generate_30_day_forecast(start_date=start_date, days=days)
        self.brain.save_master_schedule(master_schedule)

        cfg = self._load_grid_config()
        state_ids = list(cfg.get("nodes", {}).keys())
        edge_caps = self._load_edge_capacities(cfg)
        battery_soc, battery_cap = self._load_battery_maps(cfg)
        total_grid_capacity_mw = sum(float(cfg["nodes"][sid].get("generation_mw", 0.0)) for sid in state_ids)

        start = datetime.fromisoformat(start_date)
        day_reports: List[Dict[str, Any]] = []

        for day_index in range(days):
            date_str = (start + timedelta(days=day_index)).strftime("%Y-%m-%d")
            baseline_day = master_schedule["schedule"][day_index]

            intel = self.trigger.generate_daily_report(
                day_index=day_index,
                date_str=date_str,
                state_ids=state_ids,
            )

            delta_by_state: Dict[str, float] = {}
            actual_by_state: Dict[str, float] = {}

            for state_id in state_ids:
                baseline_demand = float(baseline_day["states"][state_id]["baseline_demand_mw"])
                mult = float(intel["state_multipliers"].get(state_id, 1.0))
                actual = baseline_demand * mult
                delta = actual - baseline_demand
                actual_by_state[state_id] = round(actual, 2)
                delta_by_state[state_id] = round(delta, 2)

            total_positive_delta = round(sum(max(v, 0.0) for v in delta_by_state.values()), 2)
            wake = total_positive_delta > 0.0

            waterfall_output: Dict[str, Any] | None = None
            if wake:
                deficits = {k: float(v) for k, v in delta_by_state.items() if v > 0}
                surpluses = {k: abs(float(v)) for k, v in delta_by_state.items() if v < 0}
                # Existing waterfall module prints Unicode symbols; capture stdout so
                # Windows cp1252 consoles do not fail on encoding.
                with contextlib.redirect_stdout(io.StringIO()):
                    wf = self.waterfall.execute_waterfall(
                        deficit_states_mw=deficits,
                        surplus_states_mw=surpluses,
                        battery_soc=battery_soc,
                        battery_capacity=battery_cap,
                        daily_edge_capacities_mw=edge_caps,
                        total_grid_capacity_mw=total_grid_capacity_mw,
                        dr_clearing_price=6.0,
                        day_index=day_index,
                        date_str=date_str,
                        intel_report=intel,          # Feature 2 (DLR) + Feature 5 (event flags)
                    )
                waterfall_output = {
                    "steps_executed": len(wf.steps_executed),
                    "total_resolved_mw": round(float(wf.total_resolved_mw), 2),
                    "load_shedding_mw": {k: round(float(v), 2) for k, v in wf.load_shedding_mw.items()},
                    "memory_warning": wf.memory_warning,
                    "waterfall_complete": wf.waterfall_complete,
                    # Feature 1: include dialogue log snapshot for this day
                    "dialogue_log_entries": len(self.waterfall.dialogue_log),
                    # Feature 3: frequency status
                    "grid_frequency_hz": round(self.waterfall._freq_monitor.get_current_frequency(), 3),
                    "frequency_log": self.waterfall._freq_monitor.get_log()[-1:],  # last event
                    # Feature 2: DLR + carbon log
                    "carbon_spatial_log": self.waterfall._carbon_spatial_agent.get_full_log(),
                    # Feature 5: battery lock log
                    "battery_lock_log": self.waterfall._event_flag_battery_agent.get_log(),
                }

            day_reports.append(
                {
                    "day_index": day_index,
                    "date": date_str,
                    "baseline": baseline_day["states"],
                    "intelligence": intel,
                    "actual_demand_mw": actual_by_state,
                    "delta_mw": delta_by_state,
                    "total_positive_delta_mw": total_positive_delta,
                    "wake": wake,
                    "waterfall": waterfall_output,
                    "memory_buffer": self.waterfall.get_memory_state(),
                }
            )

        result = {
            "start_date": start_date,
            "days": days,
            "states": state_ids,
            "master_schedule_model_loaded": master_schedule.get("model_loaded", False),
            "memory_window_size": self.waterfall.MEMORY_WINDOW_SIZE,
            "daily": day_reports,
            # Feature 1: full dialogue log for all 30 days
            "dialogue_log": self.waterfall.dialogue_log,
            # Feature 3: frequency monitor summary
            "frequency_monitor": self.waterfall._freq_monitor.get_status_summary(),
        }

        out = self.outputs_dir / f"simulator_result_{start_date}.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["saved_path"] = str(out)

        # ===================================================================
        # FEATURE 4: Parameter Autopsy — runs AFTER the 30-day loop
        # ===================================================================
        all_warnings = [
            day["waterfall"]["memory_warning"]
            for day in day_reports
            if day.get("waterfall") and day["waterfall"].get("memory_warning")
        ]
        if all_warnings:
            config_path = self.backend_dir / "config" / "simulation_config.json"
            autopsy_result = self.autopsy.run_autopsy(
                warnings=all_warnings,
                config_path=config_path,
                output_dir=self.outputs_dir,
            )
            result["autopsy_result"] = autopsy_result
        else:
            result["autopsy_result"] = {"status": "NO_WARNINGS", "message": "Clean run — no config changes needed."}

        return result
