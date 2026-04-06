"""
run_simulation.py
=================
Phase-driven Grid MAS simulation.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, ".")

from src.environment.grid_physics import GridEnvironment, TransmissionPath
from src.agents.state_agent.state_agent import StateAgent
from src.agents.routing_agent.routing_agent import RoutingAgent
from src.agents.routing_agent.phase5_incident_dispatcher_agent import Phase5IncidentDispatcherAgent
from src.agents.routing_agent.phase6_negotiation_agent import Phase6NegotiationAgent
from src.agents.routing_agent.phase7_syndicate_agent import Phase7SyndicateAgent
from src.agents.routing_agent.phase8_xai_agent import Phase8XAIAgent
from src.agents.routing_agent.unified_routing_orchestrator import UnifiedRoutingOrchestrator
from src.agents.routing_agent.settlement import SettlementAgent
from src.agents.routing_agent.syndicate_xai import SyndicateXAI
from src.agents.fusion_agent.inference import load_artefacts, predict_all_regions
from src.agents.shared.models import Order, DispatchRecord
from src.agents.intelligence_agent.setup import GridEvent

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent

DEFAULT_SIMULATION_CONFIG = {
    "simulation_days": 1,
    "default_import_tariff_inr": 10.0,
    "default_dr_clearing_price_inr": 6.0,
    "phase4_risk_tolerance_mw": 500.0,
    "pre_event_hoard_hour": 3,
    "normal_dispatch_hour": 14,
    "model_input_defaults": {
        "om_temp_mean": 25.0,
        "nasa_solar": 2.5,
        "om_dewpoint": 15.0,
        "om_wind_gusts": 20.0,
    },
    "fallback_forecast_multipliers": {
        "default": [1.0] * 7,
    },
}


def load_simulation_config() -> Dict[str, Any]:
    cfg_path = BACKEND_DIR / "config" / "simulation_config.json"
    if not cfg_path.exists():
        return dict(DEFAULT_SIMULATION_CONFIG)
    try:
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_SIMULATION_CONFIG)
    merged = dict(DEFAULT_SIMULATION_CONFIG)
    merged.update(loaded)
    return merged


def load_live_context() -> Dict[str, Dict[str, Any]]:
    import glob
    import os

    contexts: Dict[str, Dict[str, Any]] = {}
    cache_dir = os.path.join("outputs", "context_cache")

    for file_path in glob.glob(os.path.join(cache_dir, "node_*.json")):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        nid = data.get("node_id")
        if not nid:
            continue

        gm = data.get("grid_multipliers", {})
        weather = data.get("weather", {})
        hourly_forecast = weather.get("hourly_forecast_7d", [])

        hourly_temperature_c: Dict[int, float] = {}
        hourly_temperature_anomaly: Dict[int, float] = {}
        hourly_condition: Dict[int, str] = {}
        hourly_wind_kmh: Dict[int, float] = {}

        if hourly_forecast:
            baseline_temp = sum(float(pt.get("temperature_c", 0.0)) for pt in hourly_forecast[:24]) / max(len(hourly_forecast[:24]), 1)
            for i, pt in enumerate(hourly_forecast):
                temp = float(pt.get("temperature_c", baseline_temp))
                hourly_temperature_c[i] = round(temp, 2)
                hourly_temperature_anomaly[i] = round(temp - baseline_temp, 2)
                hourly_condition[i] = str(pt.get("condition", weather.get("current_condition", "clear sky")))
                hourly_wind_kmh[i] = float(pt.get("wind_kmh", 0.0))

        contexts[nid] = {
            "hoard_flag": gm.get("pre_event_hoard", False),
            "pre_event_hoard": gm.get("pre_event_hoard", False),
            "demand_spike_risk": gm.get("demand_spike_risk", "LOW"),
            "temperature_anomaly": gm.get("temperature_anomaly", 0.0),
            "economic_demand_multiplier": gm.get("economic_demand_multiplier", 1.0),
            "generation_capacity_multiplier": gm.get("generation_capacity_multiplier", 1.0),
            "generation_multiplier": gm.get("generation_capacity_multiplier", 1.0),
            "current_condition": weather.get("current_condition", "clear sky"),
            "hourly_temperature_c": hourly_temperature_c,
            "hourly_temperature_anomaly": hourly_temperature_anomaly,
            "hourly_condition": hourly_condition,
            "hourly_wind_kmh": hourly_wind_kmh,
            "narrative": gm.get("reasoning", ""),
            "city_intelligence": data.get("city_intelligence", {}),
            "grid_multipliers": gm,
            "phase_1_grid_events": data.get("phase_1_grid_events", []),
        }

    return contexts


@dataclass
class PathAdapter:
    _path: TransmissionPath
    _edges: dict

    @property
    def bottleneck_capacity(self) -> float:
        return self._path.bottleneck_capacity(self._edges)

    def total_cost(self) -> float:
        return self._path.total_cost(self._edges)

    @property
    def description(self) -> str:
        return self._path.label

    @property
    def source(self) -> str:
        return self._path.src

    @property
    def destination(self) -> str:
        return self._path.dst

    @property
    def raw_path(self) -> TransmissionPath:
        return self._path


class GridEnvAdapter:
    def __init__(self, env: GridEnvironment, llm_contexts: Dict[str, Dict[str, Any]]):
        self._env = env
        self.cities: Dict[str, Any] = {}
        for nid in env.nodes:
            proxy = type("CityProxy", (), {"llm_context": llm_contexts.get(nid, {})})()
            self.cities[nid] = proxy

    def get_paths(self, seller_id: str, buyer_id: str) -> List[PathAdapter]:
        raw_paths = self._env.get_paths_for(seller_id, buyer_id)
        return [PathAdapter(_path=p, _edges=self._env.edges) for p in raw_paths]

    def apply_flow(self, path: PathAdapter, transfer_mw: float) -> float:
        raw_path = path.raw_path if hasattr(path, "raw_path") else path
        return self._env.apply_flow(raw_path, transfer_mw)


def run_battery_phase(env: GridEnvironment) -> Dict[str, str]:
    actions: Dict[str, str] = {}
    for nid, node in env.nodes.items():
        bal = node.residual_balance_mw
        if node.battery is None:
            actions[nid] = f"No battery. Balance {bal:+.2f} MW"
            continue

        if bal > 0:
            stored = env.store_surplus(nid, bal)
            actions[nid] = f"Stored {stored:.2f} MWh. SoC {node.battery.soc:.2%}"
        elif bal < 0:
            supplied = env.discharge_deficit(nid, abs(bal))
            remaining = abs(bal) - supplied
            actions[nid] = (
                f"Discharged {supplied:.2f} MWh. Remaining deficit {remaining:.2f} MW. "
                f"SoC {node.battery.soc:.2%}"
            )
        else:
            actions[nid] = f"Balanced. SoC {node.battery.soc:.2%}"
    return actions


def run_simulation() -> None:
    sim_cfg = load_simulation_config()
    simulation_days = int(sim_cfg.get("simulation_days", 1))
    default_import_tariff = float(sim_cfg.get("default_import_tariff_inr", 10.0))
    default_dr_price = float(sim_cfg.get("default_dr_clearing_price_inr", 6.0))
    phase4_risk_tolerance = float(sim_cfg.get("phase4_risk_tolerance_mw", 500.0))
    pre_event_hoard_hour = int(sim_cfg.get("pre_event_hoard_hour", 3))
    normal_dispatch_hour = int(sim_cfg.get("normal_dispatch_hour", 14))
    model_defaults = sim_cfg.get("model_input_defaults", {})
    fallback_mult = sim_cfg.get("fallback_forecast_multipliers", {})

    print("=" * 80)
    print("INDIA GRID DIGITAL TWIN - PHASED MAS SIMULATION")
    print(f"Simulation days: {simulation_days} start={date.today().isoformat()}")
    print("=" * 80)

    env = GridEnvironment(seed=42, config_path=str(BACKEND_DIR / "config" / "grid_config.json"))
    contexts = load_live_context()
    base_generation = {nid: node.generation_mw for nid, node in env.nodes.items()}

    predictions: Dict[str, Dict[str, Any]] = {}
    try:
        lgb_model, scaler_climate, scaler_lagroll = load_artefacts(
            model_path="model/lightgbm_model.pkl",
            scaler_climate_path="model/utils/scaler_climate.pkl",
            scaler_lagroll_path="model/utils/scaler_lagroll.pkl",
            meta_path="model/utils/inference_meta.json",
        )

        inputs_by_region = {}
        for nid, node in env.nodes.items():
            inputs_by_region[nid] = {
                "Date": [(date.today() - timedelta(days=7 - i)).isoformat() for i in range(7)],
                "State": [nid] * 7,
                "Actual_Drawl": [node.demand_mw if node.demand_mw else base_generation[nid]] * 7,
                "om_temp_mean": [float(model_defaults.get("om_temp_mean", 25.0))] * 7,
                "nasa_solar": [float(model_defaults.get("nasa_solar", 2.5))] * 7,
                "om_dewpoint": [float(model_defaults.get("om_dewpoint", 15.0))] * 7,
                "om_wind_gusts": [float(model_defaults.get("om_wind_gusts", 20.0))] * 7,
            }
        predictions = predict_all_regions(inputs_by_region, lgb_model, scaler_climate, scaler_lagroll)
        print("[INFO] LightGBM forecasts loaded for all regions.")
    except Exception as exc:
        print(f"[WARN] LightGBM load failed: {exc}. Falling back to static demand baselines.")

    adapter = GridEnvAdapter(env, contexts)
    router = RoutingAgent(grid_env=adapter, green_mode=True)
    settlement = SettlementAgent(ledger_path="outputs/state_capacities.json")
    xai = SyndicateXAI()
    phase5_incident_agent = Phase5IncidentDispatcherAgent(default_penalty=0.20)
    phase6_negotiation_agent = Phase6NegotiationAgent()
    phase7_syndicate_agent = Phase7SyndicateAgent()
    phase8_xai_agent = Phase8XAIAgent()
    
    # === UNIFIED ROUTING ORCHESTRATOR WITH SHORT-TERM WORKING MEMORY ===
    # Wraps Phase 6 and Phase 7 agents with a 72-hour sliding window memory buffer
    unified_orchestrator = UnifiedRoutingOrchestrator(
        phase6_agent=phase6_negotiation_agent,
        phase7_agent=phase7_syndicate_agent,
    )
    print("[INIT] UnifiedRoutingOrchestrator initialized with Short-Term Working Memory (max 3 days)")

    all_dispatches: List[DispatchRecord] = []
    all_load_shedding: List[dict[str, Any]] = []
    all_decision_logs: List[dict[str, Any]] = []
    all_xai_logs: List[str] = []
    all_phase_logs: Dict[str, List[str]] = {}
    all_phase7_final_states: List[Dict[str, Any]] = []
    all_phase8_summaries: List[Dict[str, Any]] = []
    all_memory_events: List[Dict[str, Any]] = []  # Track memory write events
    last_ledger: dict[str, Any] = {}

    for day in range(simulation_days):
        sim_date = (date.today() + timedelta(days=day)).isoformat()
        print(f"\nDAY {day + 1} - {sim_date}")
        
        # === MEMORY READ: Display current memory state at start of day ===
        current_memory = unified_orchestrator.get_memory_state()
        if current_memory:
            print(f"  [STWM] Grid Short-Term Memory ({len(current_memory)}/{unified_orchestrator.MEMORY_WINDOW_SIZE} slots):")
            for i, mem in enumerate(current_memory, 1):
                print(f"    [{i}] {mem}")
        
        # Legacy warnings from phase7 agent (for backwards compatibility)
        rag_warnings = phase7_syndicate_agent.warnings_for_day(day_index=day)
        if rag_warnings:
            for warning in rag_warnings:
                print(f"  PHASE6_MEMORY: {warning}")

        env.current_day = day
        env.set_daily_demand()
        env.reset_flows()

        orders: List[Order] = []
        state_positions: Dict[str, Any] = {}
        battery_soc_map: Dict[str, float] = {}
        day_dr_total_savings_inr = 0.0
        day_dr_total_activated_mw = 0.0
        day_initial_deficit_states: Dict[str, float] = {}

        for nid, node in env.nodes.items():
            ctx = contexts.get(nid, {})
            battery_soc = (node.battery.soc * 100.0) if node.battery else 50.0
            battery_soc_map[nid] = battery_soc

            if nid in predictions and predictions[nid].get("predicted_drawl"):
                forecast_7d = [float(x) for x in predictions[nid]["predicted_drawl"]]
                today_forecast = float(forecast_7d[day % len(forecast_7d)])
            else:
                today_forecast = float(node.demand_mw)
                forecast_7d = [today_forecast] * 7
                multipliers = fallback_mult.get(nid, fallback_mult.get("default", [1.0] * 7))
                for idx in range(min(len(forecast_7d), len(multipliers))):
                    forecast_7d[idx] = float(today_forecast) * float(multipliers[idx])

            state_agent_math = StateAgent(
                city_id=nid,
                net_mw=0.0,
                battery_soc=battery_soc,
                llm_context=ctx,
            )
            raw_events = ctx.get("phase_1_grid_events", [])
            grid_events: list[GridEvent] = []
            for evt in raw_events:
                try:
                    grid_events.append(GridEvent.model_validate(evt))
                except Exception:
                    continue

            pos = state_agent_math.evaluate_state_position_with_events(
                forecast_7d_mw=forecast_7d,
                todays_demand_forecast_mw=today_forecast,
                hardcoded_supply_mw=base_generation.get(nid, float(node.generation_mw)),
                grid_events=grid_events,
                current_import_tariff=float(ctx.get("current_import_tariff", default_import_tariff)),
                dr_clearing_price=float(ctx.get("dr_clearing_price", default_dr_price)),
                pre_event_hoard_hour=pre_event_hoard_hour,
                normal_dispatch_hour=normal_dispatch_hour,
            )
            confidence_score = 0.0
            if grid_events:
                event_conf = [evt.confidence_score for evt in grid_events if nid in evt.affected_states]
                confidence_score = max(event_conf) if event_conf else 0.0
            pos = state_agent_math.apply_phase4_lookahead(
                state_position=pos,
                forecast_7d_mw=forecast_7d,
                hardcoded_supply_mw=base_generation.get(nid, float(node.generation_mw)),
                confidence_score=confidence_score,
                tolerance_mw=phase4_risk_tolerance,
            )
            state_positions[nid] = pos
            day_dr_total_savings_inr += float(pos.dr_savings_inr)
            day_dr_total_activated_mw += float(pos.dr_activated_mw)
            day_initial_deficit_states[nid] = float(pos.deficit_mw)
            
            # --- Virtual Battery / Spin-Up Log Integration ---
            phaselog_addition = list(pos.phase_log)
            if pos.pre_event_hoard:
                ramping_log = f"RAMPING: Baseload Thermal Spin-Up for Day {ctx.get('hoard_day', 2)} Event"
                phaselog_addition.append(ramping_log)
                print(f"  {nid}: {ramping_log}")

            all_phase_logs[nid] = all_phase_logs.get(nid, []) + phaselog_addition

            node.adjusted_demand_mw = pos.adjusted_demand_mw
            node.generation_mw = pos.adjusted_supply_mw

            print(
                f"  {nid}: demand={pos.adjusted_demand_mw:.2f} supply={pos.adjusted_supply_mw:.2f} "
                f"net={pos.net_position_mw:+.2f} dr_mw={pos.dr_activated_mw:.2f} "
                f"dr_save={pos.dr_savings_inr:.2f} dispatch_hint={pos.dispatch_hour_hint:02d}:00"
            )

        # Phase 5: apply incident-driven thermal derating to daily edge caps.
        all_day_events: list[GridEvent] = []
        for ctx in contexts.values():
            for evt in ctx.get("phase_1_grid_events", []):
                try:
                    all_day_events.append(GridEvent.model_validate(evt))
                except Exception:
                    continue
        base_caps = {edge_key: edge.capacity_mw for edge_key, edge in env.edges.items()}
        derating = phase5_incident_agent.derive_daily_capacities(base_caps, all_day_events)
        for edge_key, cap in derating.capacities_mw.items():
            env.edges[edge_key].capacity_mw = max(cap, 0.0)
        if derating.impacted_edges:
            impacted_count = len(derating.impacted_edges)
            print(f"  PHASE5: incident derating applied to {impacted_count} edges")

        # Phase 6: schema-bound negotiation with safety override preview.
        # === USING UNIFIED ORCHESTRATOR WITH MEMORY READ LOOP ===
        deficit_states = {
            nid: float(pos.deficit_mw)
            for nid, pos in state_positions.items()
            if float(pos.deficit_mw) > 0.0
        }
        available_surplus_states = {
            nid: float(pos.surplus_mw)
            for nid, pos in state_positions.items()
            if float(pos.surplus_mw) > 0.0 and not bool(pos.pre_event_hoard)
        }
        daily_edge_capacities = {k: float(v.capacity_mw) for k, v in env.edges.items()}
        
        # Store edge capacities at start of day for memory evaluation
        edge_capacities_at_start = dict(daily_edge_capacities)
        
        # === MEMORY READ: Use unified orchestrator for spatial routing ===
        # This injects the short-term memory into the negotiation prompt
        phase6_output = unified_orchestrator.execute_spatial_routing(
            deficit_states_mw=deficit_states,
            available_surplus_states_mw=dict(available_surplus_states),
            daily_edge_capacities_mw=daily_edge_capacities,
        )
        for trade in phase6_output.proposed_trades:
            all_phase_logs[trade.buyer_state] = all_phase_logs.get(trade.buyer_state, []) + [
                (
                    f"PHASE6 | buyer={trade.buyer_state} seller={trade.seller_state} "
                    f"requested={trade.requested_mw:.2f} approved={trade.approved_mw:.2f} "
                    f"reason={trade.reason}"
                )
            ]

        # Phase 7: execute approved trades with direct-neighbor fallback shedding.
        # === USING UNIFIED ORCHESTRATOR FOR SYNDICATE EXECUTION ===
        phase7_result = unified_orchestrator.execute_syndicate(
            proposed_trades=phase6_output.proposed_trades,
            deficit_states_mw=deficit_states,
            surplus_states_mw=available_surplus_states,
            daily_edge_capacities_mw=daily_edge_capacities,
            total_grid_capacity_mw=sum(base_generation.values()),
        )
        # Legacy bottleneck recording (for backwards compatibility)
        phase7_syndicate_agent.record_bottlenecks(day_index=day, observed_bottlenecks=phase7_result.observed_bottlenecks)
        for trade in phase7_result.executed_trades:
            all_phase_logs[trade.buyer_state] = all_phase_logs.get(trade.buyer_state, []) + [
                (
                    f"PHASE7 | executed buyer={trade.buyer_state} seller={trade.seller_state} "
                    f"approved={trade.approved_mw:.2f}MW"
                )
            ]
        for state_id, shed in phase7_result.load_shedding_mw.items():
            all_phase_logs[state_id] = all_phase_logs.get(state_id, []) + [
                f"PHASE7 | forced_load_shedding={shed:.2f}MW"
            ]
        print(
            f"  PHASE7_FREQ: before={phase7_result.grid_frequency_before_hz:.3f}Hz "
            f"after={phase7_result.grid_frequency_after_hz:.3f}Hz "
            f"emergency={phase7_result.frequency_triggered_emergency} "
            f"shed={phase7_result.emergency_shed_mw:.2f}MW"
        )
        all_phase7_final_states.append(
            {
                "day": day + 1,
                "date": sim_date,
                "executed_trades": [
                    {
                        "buyer_state": t.buyer_state,
                        "seller_state": t.seller_state,
                        "requested_mw": t.requested_mw,
                        "approved_mw": t.approved_mw,
                        "reason": t.reason,
                    }
                    for t in phase7_result.executed_trades
                ],
                "load_shedding_mw": dict(phase7_result.load_shedding_mw),
                "remaining_deficit_mw": dict(phase7_result.remaining_deficit_mw),
                "final_surplus_mw": dict(phase7_result.final_surplus_mw),
                "grid_frequency_before_hz": phase7_result.grid_frequency_before_hz,
                "grid_frequency_after_hz": phase7_result.grid_frequency_after_hz,
                "emergency_shed_mw": phase7_result.emergency_shed_mw,
                "frequency_triggered_emergency": phase7_result.frequency_triggered_emergency,
                "observed_bottlenecks": list(phase7_result.observed_bottlenecks),
            }
        )

        # Grid rescue fallback: if everyone is in deficit, activate reserve on least-deficit state.
        balances = {nid: node.raw_balance_mw for nid, node in env.nodes.items()}
        if balances and all(v < 0 for v in balances.values()):
            anchor_id = max(balances, key=lambda x: balances[x])
            max_deficit = max(abs(v) for v in balances.values())
            reserve_add = abs(balances[anchor_id]) + (0.8 * max_deficit)
            env.nodes[anchor_id].generation_mw += reserve_add
            msg = (
                f"PHASE_2_RESCUE reserve_activation state={anchor_id} "
                f"reserve_add={reserve_add:.2f} new_balance={env.nodes[anchor_id].raw_balance_mw:+.2f}"
            )
            all_phase_logs[anchor_id] = all_phase_logs.get(anchor_id, []) + [msg]
            print(f"  {msg}")

        # Build orders after final (possibly rescued) net positions.
        for nid, node in env.nodes.items():
            ctx = contexts.get(nid, {})
            state_agent_order = StateAgent(
                city_id=nid,
                net_mw=node.raw_balance_mw,
                battery_soc=battery_soc_map.get(nid, 50.0),
                llm_context=ctx,
            )
            order = state_agent_order.generate_order()
            if order is not None:
                orders.append(order)

        dispatches = router.clear_market(
            orders=orders,
            hour_index=None,
            day_index=day,
            state_positions=state_positions,
        )
        load_shedding = router.get_load_shedding_log()
        decision_log = router.get_decision_log()

        # Merge Phase 7 explicit fallback shedding into existing load-shedding log.
        if phase7_result.load_shedding_mw:
            existing_states = {entry.get("state_id") for entry in load_shedding}
            for state_id, shed in phase7_result.load_shedding_mw.items():
                if state_id in existing_states:
                    continue
                load_shedding.append(
                    {
                        "state_id": state_id,
                        "shed_mw": float(shed),
                        "level": "LEVEL_1",
                        "dispatch_hour": None,
                        "reason": f"Phase7 fallback load shedding for unresolved deficit {float(shed):.2f} MW",
                    }
                )

        all_dispatches.extend(dispatches)
        all_load_shedding.extend(load_shedding)
        all_decision_logs.extend(decision_log)

        for d in dispatches:
            buyer_pos = state_positions.get(d.buyer_city_id)
            trigger_summary = "demand spike and generation constraints"
            if buyer_pos is not None:
                trigger_summary = (
                    f"EDM={buyer_pos.economic_demand_multiplier:.2f}, "
                    f"GENM={buyer_pos.generation_multiplier:.2f}"
                )
            n = xai.dispatch_narrative(
                record=d,
                buyer_deficit_before_mw=buyer_pos.deficit_mw if buyer_pos else d.requested_mw,
                line_cap_mw=d.line_cap_mw,
                residual_deficit_mw=d.residual_deficit_mw,
                trigger_summary=trigger_summary,
            )
            all_xai_logs.append(n)
            print(f"  XAI: {n}")

        for ls in load_shedding:
            n = xai.load_shedding_narrative(ls)
            all_xai_logs.append(n)
            print(f"  XAI: {n}")

        battery_actions = run_battery_phase(env)
        for nid, action in battery_actions.items():
            print(f"  BATTERY {nid}: {action}")

        print(
            f"  DR SUMMARY: activated={day_dr_total_activated_mw:.2f} MW "
            f"savings={day_dr_total_savings_inr:.2f} INR"
        )

        # Phase 8: explicit KPI line for operator console.
        power_imported_mw = sum(float(t.approved_mw) for t in phase7_result.executed_trades)
        forced_load_shedding_mw = sum(float(v) for v in phase7_result.load_shedding_mw.values())
        phase8_summary = phase8_xai_agent.build_summary(
            initial_deficit_by_state_mw=day_initial_deficit_states,
            dr_activated_total_mw=day_dr_total_activated_mw,
            dr_savings_total_inr=day_dr_total_savings_inr,
            executed_import_total_mw=power_imported_mw,
            load_shedding_total_mw=forced_load_shedding_mw,
        )
        print(f"  DAILY SUMMARY: {phase8_summary.summary_line}")
        all_xai_logs.append(phase8_summary.summary_line)
        all_xai_logs.append(
            f"[Grid Frequency Before Syndicate]={phase7_result.grid_frequency_before_hz:.3f} Hz | "
            f"[Grid Frequency After Syndicate]={phase7_result.grid_frequency_after_hz:.3f} Hz"
        )
        all_phase8_summaries.append(
            {
                "day": day + 1,
                "date": sim_date,
                "total_deficit_mw": phase8_summary.total_deficit_mw,
                "deficit_resolved_via_dr_mw": phase8_summary.deficit_resolved_via_dr_mw,
                "money_saved_by_dr_inr": phase8_summary.money_saved_by_dr_inr,
                "power_imported_mw": phase8_summary.power_imported_mw,
                "forced_load_shedding_mw": phase8_summary.forced_load_shedding_mw,
                "summary_line": phase8_summary.summary_line,
            }
        )

        last_ledger = settlement.settle_day(
            env=env,
            dispatches=dispatches,
            load_shedding=load_shedding,
            simulation_date=sim_date,
        )

        # =================================================================
        # MEMORY WRITE LOOP: End-of-Day Evaluation
        # =================================================================
        # After execute_fallback / Load Shedding is complete, evaluate the
        # grid's performance and write a memory log if failures occurred.
        memory_warning = unified_orchestrator.evaluate_and_write_memory(
            day_index=day,
            date_str=sim_date,
            phase7_result=phase7_result,
            edge_capacities_at_start=edge_capacities_at_start,
        )
        if memory_warning:
            all_memory_events.append({
                "day": day + 1,
                "date": sim_date,
                "warning": memory_warning,
                "memory_buffer_size": len(unified_orchestrator.get_memory_state()),
            })
            # Log to phase logs for each state that experienced issues
            for state_id in phase7_result.load_shedding_mw.keys():
                all_phase_logs[state_id] = all_phase_logs.get(state_id, []) + [
                    f"MEMORY_WRITE | {memory_warning[:80]}..."
                ]

        env.advance_day()

    # Log final memory state
    final_memory = unified_orchestrator.get_memory_state()
    if final_memory:
        print(f"\n[STWM] Final Memory State ({len(final_memory)} items):")
        for i, mem in enumerate(final_memory, 1):
            print(f"  [{i}] {mem}")

    write_simulation_result(
        dispatches_all_days=all_dispatches,
        env=env,
        load_shedding=all_load_shedding,
        decision_log=all_decision_logs,
        xai_logs=all_xai_logs,
        phase_logs=all_phase_logs,
        phase7_final_states=all_phase7_final_states,
        phase8_summaries=all_phase8_summaries,
        settlement_ledger=last_ledger,
        memory_events=all_memory_events,
    )

    print("\nSIMULATION COMPLETE")


def write_simulation_result(
    dispatches_all_days: List[Any],
    env: GridEnvironment,
    load_shedding: List[dict[str, Any]],
    decision_log: List[dict[str, Any]],
    xai_logs: List[str],
    phase_logs: Dict[str, List[str]],
    phase7_final_states: List[Dict[str, Any]],
    phase8_summaries: List[Dict[str, Any]],
    settlement_ledger: Dict[str, Any],
    memory_events: List[Dict[str, Any]] | None = None,
) -> None:
    output = []
    for record in dispatches_all_days:
        if hasattr(record, "syndicate_sellers"):
            output.append(
                {
                    "type": "SYNDICATE",
                    "buyer_city_id": record.buyer_city_id,
                    "transfer_mw": record.transfer_mw,
                    "cleared_price_mw": record.cleared_price_mw,
                    "buyer_bid": record.buyer_bid,
                    "syndicate_sellers": record.syndicate_sellers,
                    "breakdown_log": record.breakdown_log,
                }
            )
        else:
            output.append(
                {
                    "type": "STANDARD",
                    "buyer_city_id": record.buyer_city_id,
                    "seller_city_id": record.seller_city_id,
                    "transfer_mw": record.transfer_mw,
                    "cleared_price_mw": record.cleared_price_mw,
                    "seller_ask": record.seller_ask,
                    "path_cost": record.path_cost,
                    "carbon_tax": record.carbon_tax,
                    "buyer_bid": record.buyer_bid,
                    "path_description": record.path_description,
                    "llm_safety_status": record.llm_safety_status,
                    "dlr_applied": record.dlr_applied,
                    "effective_capacity": record.effective_capacity,
                    "requested_mw": record.requested_mw,
                    "line_cap_mw": record.line_cap_mw,
                    "approved_mw": record.approved_mw,
                    "residual_deficit_mw": record.residual_deficit_mw,
                    "dispatch_hour": record.dispatch_hour,
                    "route_agent": record.route_agent,
                    "decision_trace": list(record.decision_trace),
                }
            )

    summary = {}
    for nid, node in env.nodes.items():
        summary[nid] = {
            "generation_mw": round(node.generation_mw, 3),
            "demand_mw": round(node.adjusted_demand_mw, 3),
            "balance_mw": round(node.raw_balance_mw, 3),
            "net_trade_mw": round(node.net_trade_mw, 3),
            "battery_soc": round(node.battery.soc, 4) if node.battery else None,
        }

    result = {
        "date": date.today().isoformat(),
        "dispatches": output,
        "load_shedding": load_shedding,
        "decision_log": decision_log,
        "xai_log": xai_logs,
        "phase_logs": phase_logs,
        "phase7_final_grid_state": phase7_final_states,
        "phase8_daily_summaries": phase8_summaries,
        "settlement_ledger": settlement_ledger,
        "summary": summary,
        "short_term_memory_events": memory_events or [],
    }

    out_path = Path("outputs") / f"simulation_result_{date.today().isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results JSON -> {out_path}")


if __name__ == "__main__":
    run_simulation()
