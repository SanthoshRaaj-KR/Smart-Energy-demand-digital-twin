"""
run_simulation.py
=================
Phase-driven Grid MAS simulation.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, ".")

from src.environment.grid_physics import GridEnvironment, TransmissionPath
from src.agents.state_agent.state_agent import StateAgent
from src.agents.routing_agent.routing_agent import RoutingAgent
from src.agents.routing_agent.settlement import SettlementAgent
from src.agents.routing_agent.syndicate_xai import SyndicateXAI
from src.agents.fusion_agent.inference import load_artefacts, predict_all_regions
from src.agents.shared.models import Order, DispatchRecord

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

SIMULATION_DAYS = 1


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
        bal = node.raw_balance_mw
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
    print("=" * 80)
    print("INDIA GRID DIGITAL TWIN - PHASED MAS SIMULATION")
    print(f"Simulation days: {SIMULATION_DAYS} start={date.today().isoformat()}")
    print("=" * 80)

    env = GridEnvironment(seed=42)
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
                "om_temp_mean": [25.0] * 7,
                "nasa_solar": [2.5] * 7,
                "om_dewpoint": [15.0] * 7,
                "om_wind_gusts": [20.0] * 7,
            }
        predictions = predict_all_regions(inputs_by_region, lgb_model, scaler_climate, scaler_lagroll)
        print("[INFO] LightGBM forecasts loaded for all regions.")
    except Exception as exc:
        print(f"[WARN] LightGBM load failed: {exc}. Falling back to static demand baselines.")

    adapter = GridEnvAdapter(env, contexts)
    router = RoutingAgent(grid_env=adapter, green_mode=True)
    settlement = SettlementAgent(ledger_path="outputs/state_capacities.json")
    xai = SyndicateXAI()

    all_dispatches: List[DispatchRecord] = []
    all_load_shedding: List[dict[str, Any]] = []
    all_decision_logs: List[dict[str, Any]] = []
    all_xai_logs: List[str] = []
    all_phase_logs: Dict[str, List[str]] = {}
    last_ledger: dict[str, Any] = {}

    for day in range(SIMULATION_DAYS):
        sim_date = (date.today() + timedelta(days=day)).isoformat()
        print(f"\nDAY {day + 1} - {sim_date}")

        env.current_day = day
        env.set_daily_demand()
        env.reset_flows()

        orders: List[Order] = []
        state_positions: Dict[str, Any] = {}
        battery_soc_map: Dict[str, float] = {}

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
                # --- Smart Mock: Force Day 3 Heatwave for UP to trigger logic if model missing ---
                if nid == "UP":
                    forecast_7d[2] = today_forecast * 1.25 # 25% spike on Day 3
                if nid == "KAR":
                    # Give KAR a surplus today so it can choose to hoard vs sell
                    # But the physics env sets KAR generation high already.
                    pass

            state_agent_math = StateAgent(
                city_id=nid,
                net_mw=0.0,
                battery_soc=battery_soc,
                llm_context=ctx,
            )
            pos = state_agent_math.evaluate_state_position(
                forecast_7d_mw=forecast_7d,
                todays_demand_forecast_mw=today_forecast,
                intelligence=ctx,
                safety_buffer=1.05,
                pre_event_hoard_hour=3,
                normal_dispatch_hour=14,
            )
            state_positions[nid] = pos
            
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
                f"net={pos.net_position_mw:+.2f} dispatch_hint={pos.dispatch_hour_hint:02d}:00"
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

        last_ledger = settlement.settle_day(
            env=env,
            dispatches=dispatches,
            load_shedding=load_shedding,
            simulation_date=sim_date,
        )

        env.advance_day()

    write_simulation_result(
        dispatches_all_days=all_dispatches,
        env=env,
        load_shedding=all_load_shedding,
        decision_log=all_decision_logs,
        xai_logs=all_xai_logs,
        phase_logs=all_phase_logs,
        settlement_ledger=last_ledger,
    )

    print("\nSIMULATION COMPLETE")


def write_simulation_result(
    dispatches_all_days: List[Any],
    env: GridEnvironment,
    load_shedding: List[dict[str, Any]],
    decision_log: List[dict[str, Any]],
    xai_logs: List[str],
    phase_logs: Dict[str, List[str]],
    settlement_ledger: Dict[str, Any],
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
            "battery_soc": round(node.battery.soc, 4) if node.battery else None,
        }

    result = {
        "date": date.today().isoformat(),
        "dispatches": output,
        "load_shedding": load_shedding,
        "decision_log": decision_log,
        "xai_log": xai_logs,
        "phase_logs": phase_logs,
        "settlement_ledger": settlement_ledger,
        "summary": summary,
    }

    out_path = Path("outputs") / f"simulation_result_{date.today().isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results JSON -> {out_path}")


if __name__ == "__main__":
    run_simulation()
