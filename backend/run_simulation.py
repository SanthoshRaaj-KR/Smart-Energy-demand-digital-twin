"""
run_simulation.py
=================
Full Agentic Pipeline — 3-Day India Grid Digital Twin Simulation

Pipeline per day:
    1. GridEnvironment sets daily demand (stochastic)
    2. Dummy LLM context adjusts demand via multipliers
    3. StateAgent per city evaluates (net_mw, battery_soc, llm_context) → generates Order
    4. RoutingAgent clears market → DLR + carbon tariff + LLM safety → DispatchRecords
    5. Battery absorbs remaining surplus / covers residual deficit
    6. Summary table printed

Run:
    python run_simulation.py
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import json
from pathlib import Path

# ── Adjust path so src.agents package is importable ───────────────────
sys.path.insert(0, ".")

from src.environment.grid_physics import GridEnvironment, TransmissionPath
from src.agents.state_agent.state_agent import StateAgent
from src.agents.routing_agent.routing_agent import RoutingAgent
from src.agents.fusion_agent import HourlyFusionAgent
from src.agents.shared.models import Order, DispatchRecord
from src.agents.fusion_agent.inference import load_artefacts, predict_all_regions

def load_live_context() -> Dict[str, Dict[str, Any]]:
    import glob
    import json
    import os
    
    contexts = {}
    cache_dir = os.path.join("outputs", "context_cache")
    for file_path in glob.glob(os.path.join(cache_dir, "node_*.json")):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            nid = data.get("node_id")
            if not nid: continue
            
            # Map grid_multipliers + weather to the shape run_simulation expects
            gm = data.get("grid_multipliers", {})
            weather = data.get("weather", {})
            hourly_forecast = weather.get("hourly_forecast_7d", [])

            hourly_temperature_c: Dict[int, float] = {}
            hourly_temperature_anomaly: Dict[int, float] = {}
            hourly_condition: Dict[int, str] = {}
            hourly_wind_kmh: Dict[int, float] = {}

            if hourly_forecast:
                baseline_temp = sum(
                    float(pt.get("temperature_c", 0.0)) for pt in hourly_forecast[:24]
                ) / max(len(hourly_forecast[:24]), 1)
                for i, pt in enumerate(hourly_forecast):
                    temp = float(pt.get("temperature_c", baseline_temp))
                    hourly_temperature_c[i] = round(temp, 2)
                    hourly_temperature_anomaly[i] = round(temp - baseline_temp, 2)
                    hourly_condition[i] = str(pt.get("condition", weather.get("current_condition", "clear sky")))
                    hourly_wind_kmh[i] = float(pt.get("wind_kmh", 0.0))
            elif weather.get("forecast_days"):
                # Fallback for cache files without explicit hourly forecast.
                forecast_days = weather.get("forecast_days", [])
                for day_i, day_pt in enumerate(forecast_days[:7]):
                    max_c = float(day_pt.get("max_c", weather.get("current_temp_c", 30.0)))
                    min_c = float(day_pt.get("min_c", weather.get("current_temp_c", 24.0)))
                    baseline_temp = (max_c + min_c) / 2.0
                    for h in range(24):
                        idx = day_i * 24 + h
                        temp = min_c + (max_c - min_c) * max(0.0, 1.0 - abs(h - 14) / 10.0)
                        hourly_temperature_c[idx] = round(temp, 2)
                        hourly_temperature_anomaly[idx] = round(temp - baseline_temp, 2)
                        hourly_condition[idx] = str(weather.get("current_condition", "clear sky"))
                        hourly_wind_kmh[idx] = 0.0

            contexts[nid] = {
                "hoard_flag": gm.get("pre_event_hoard", False),
                "demand_spike_risk": gm.get("demand_spike_risk", "LOW"),
                "temperature_anomaly": gm.get("temperature_anomaly", 0.0),
                "economic_demand_multiplier": gm.get("economic_demand_multiplier", 1.0),
                "generation_capacity_multiplier": gm.get("generation_capacity_multiplier", 1.0),
                "current_condition": weather.get("current_condition", "clear sky"),
                "hourly_temperature_c": hourly_temperature_c,
                "hourly_temperature_anomaly": hourly_temperature_anomaly,
                "hourly_condition": hourly_condition,
                "hourly_wind_kmh": hourly_wind_kmh,
                "narrative": gm.get("reasoning", "")
            }
    return contexts

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

# Force UTF-8 output on Windows consoles
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SIMULATION_DAYS = 1


# ─────────────────────────────────────────────────────────────────────────
#  ADAPTER LAYER
#  Bridges GridEnvironment's path API to RoutingAgent's expected interface
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class PathAdapter:
    """
    Wraps a TransmissionPath so that `bottleneck_capacity` and `total_cost()`
    can be called without passing the edges dict each time.
    The RoutingAgent expects:
        path.bottleneck_capacity   → float (property)
        path.total_cost()          → float (no-arg method)
        path.description           → str
        path.source / path.destination (optional, for filtering)
    """
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
    """
    Adapter that gives the RoutingAgent the interface it expects:
        - get_paths(seller_id, buyer_id) → List[PathAdapter]
        - cities[city_id].llm_context    → dict
    """

    def __init__(self, env: GridEnvironment, llm_contexts: Dict[str, Dict[str, Any]]):
        self._env = env

        # Build city proxy objects with llm_context attribute
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


# ─────────────────────────────────────────────────────────────────────────
#  DEMAND ADJUSTMENT
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
#  BATTERY PHASE
# ─────────────────────────────────────────────────────────────────────────

def run_battery_phase(env: GridEnvironment) -> Dict[str, str]:
    """
    After market clearing, absorb remaining surplus into batteries
    and cover residual deficit from batteries.
    Returns a dict of battery action logs per city.
    """
    actions: Dict[str, str] = {}
    for nid, node in env.nodes.items():
        bal = node.raw_balance_mw
        if node.battery is None:
            actions[nid] = f"No battery (hub). Balance: {bal:+.0f} MW"
            continue

        if bal > 0:
            stored = env.store_surplus(nid, bal)
            actions[nid] = f"Stored {stored:.0f} MWh surplus. SoC: {node.battery.soc:.0%}"
        elif bal < 0:
            supplied = env.discharge_deficit(nid, abs(bal))
            remaining = abs(bal) - supplied
            actions[nid] = (
                f"Discharged {supplied:.0f} MWh. "
                f"{'Deficit covered.' if remaining < 1 else f'Remaining deficit: {remaining:.0f} MW'} "
                f"SoC: {node.battery.soc:.0%}"
            )
        else:
            actions[nid] = f"Balanced. SoC: {node.battery.soc:.0%}"
    return actions


# ─────────────────────────────────────────────────────────────────────────
#  PRINT HELPERS
# ─────────────────────────────────────────────────────────────────────────

def print_day_header(day: int, sim_date: str) -> None:
    print(f"\n{'━' * 80}")
    print(f"  📅 DAY {day}  —  {sim_date}")
    print(f"{'━' * 80}")


def print_context_summary(contexts: Dict[str, Dict[str, Any]]) -> None:
    print(f"\n  {'CITY':<6} {'RISK':<10} {'T-ANOM':>7} {'EDM':>6} {'GCM':>6} {'HOARD':>6}  NARRATIVE")
    print(f"  {'─'*90}")
    for nid, ctx in contexts.items():
        print(
            f"  {nid:<6} "
            f"{ctx.get('demand_spike_risk', '?'):<10} "
            f"{ctx.get('temperature_anomaly', 0):>+6.1f}° "
            f"{ctx.get('economic_demand_multiplier', 1.0):>5.2f} "
            f"{ctx.get('generation_capacity_multiplier', 1.0):>5.2f} "
            f"{'🚨 YES' if ctx.get('hoard_flag') else '  no':>6}  "
            f"{ctx.get('narrative', '')[:60]}"
        )


def print_orders(orders: List[Order]) -> None:
    print(f"\n  📋 ORDERS GENERATED ({len(orders)} total):")
    print(f"  {'─'*70}")
    for o in orders:
        icon = "🔴 BUY " if o.order_type.value == "BUY" else "🟢 SELL"
        print(f"    {icon}  {o.city_id}  {o.quantity_mw:>8.1f} MW @ ₹{o.price_per_mw:.2f}/MW")
        print(f"          └─ {o.reason[:80]}")


def print_battery_actions(actions: Dict[str, str]) -> None:
    print(f"\n  🔋 BATTERY PHASE:")
    print(f"  {'─'*60}")
    for nid, action in actions.items():
        print(f"    {nid}: {action}")


def print_dispatch_summary(dispatches: List[DispatchRecord]) -> None:
    if not dispatches:
        print("\n  ⚠️  No dispatches executed this day.")
        return
    print(f"\n  📊 DISPATCH SUMMARY ({len(dispatches)} transfers):")
    print(f"  {'─'*70}")
    total_mw = 0.0
    total_revenue = 0.0
    for d in dispatches:
        total_mw += d.transfer_mw
        total_revenue += d.transfer_mw * d.cleared_price_mw
    print(f"    Total MW transferred : {total_mw:,.0f} MW")
    print(f"    Total market value   : ₹{total_revenue:,.0f}")
    print(f"    Avg cleared price    : ₹{total_revenue/total_mw:.2f}/MW" if total_mw > 0 else "")


def print_grid_status(env: GridEnvironment) -> None:
    print(f"\n  📈 GRID STATUS (post-market, post-battery):")
    print(env.node_status_summary().to_string(index=False))


# ─────────────────────────────────────────────────────────────────────────
#  MAIN SIMULATION LOOP
# ─────────────────────────────────────────────────────────────────────────

def run_simulation():
    print("=" * 80)
    print("  ⚡ INDIA GRID DIGITAL TWIN — AUTONOMOUS ENERGY STOCK MARKET")
    print(f"  🗓  Simulation: {SIMULATION_DAYS} days starting {date.today().isoformat()}")
    print("  🌿 Green Mode: ON (carbon tariff active)")
    print("=" * 80)

    env = GridEnvironment(seed=42)
    contexts = load_live_context()
    if contexts:
        print_context_summary(contexts)
    else:
        print("\n  [WARN] No live context cache found. Running with neutral defaults.")

    base_generation = {nid: node.generation_mw for nid, node in env.nodes.items()}

    print("\n  [INFO] Loading LightGBM inference artefacts...")
    try:
        lgb_model, scaler_climate, scaler_lagroll = load_artefacts(
            model_path='model/lightgbm_model.pkl',
            scaler_climate_path='model/utils/scaler_climate.pkl',
            scaler_lagroll_path='model/utils/scaler_lagroll.pkl',
            meta_path='model/utils/inference_meta.json',
        )
        print("  [INFO] Artefacts loaded successfully. ML Inference Active.")

        # Seed 7-day trailing context to generate 7-day forecasts
        inputs_by_region = {}
        for nid, node in env.nodes.items():
            inputs_by_region[nid] = {
                'Date': [(date.today() - timedelta(days=7-i)).isoformat() for i in range(7)],
                'State': [nid] * 7,
                'Actual_Drawl': [node.demand_mw] * 7,
                'om_temp_mean': [25.0] * 7,
                'nasa_solar': [2.5] * 7,
                'om_dewpoint': [15.0] * 7,
                'om_wind_gusts': [20.0] * 7,
            }
        
        predictions = predict_all_regions(
            inputs_by_region, lgb_model, scaler_climate, scaler_lagroll
        )

        def lgb_predictor(env, hour_index):
            day_idx = getattr(env, 'current_day', 0) % 7
            return {n: predictions[n]['predicted_drawl'][day_idx] for n in env.nodes}

    except Exception as e:
        print(f"  [WARN] Failed to load LightGBM artefacts ({e}). Falling back to static defaults.")
        lgb_predictor = None

    fusion_agent = HourlyFusionAgent(predictor_fn=lgb_predictor)
    adapter = GridEnvAdapter(env, contexts)
    router = RoutingAgent(grid_env=adapter, green_mode=True)

    for day in range(SIMULATION_DAYS):
        env.current_day = day
        sim_date = (date.today() + timedelta(days=day)).isoformat()
        print_day_header(day + 1, sim_date)

        env.set_daily_demand()
        env.reset_flows()
        fusion_agent.apply_day(env, contexts, base_generation)

        orders: List[Order] = []
        for nid, node in env.nodes.items():
            llm_ctx = contexts.get(nid, {})
            net_mw = node.raw_balance_mw
            battery_soc = (node.battery.soc * 100) if node.battery else 50.0

            agent = StateAgent(
                city_id=nid,
                net_mw=net_mw,
                battery_soc=battery_soc,
                llm_context=llm_ctx,
            )
            order = agent.generate_order()
            if order is not None:
                orders.append(order)

        print_orders(orders)
        dispatches = router.clear_market(orders, hour_index=None, day_index=day)
        print_dispatch_summary(dispatches)

        battery_actions = run_battery_phase(env)
        print_battery_actions(battery_actions)
        print_grid_status(env)
        env.advance_day()

    def _write_simulation_result(dispatches_all_days, env):
    """Serialise dispatch records to JSON for the API server."""
    output = []
    for record in dispatches_all_days:
        # Handle both DispatchRecord and SyndicateDispatchRecord
        if hasattr(record, "syndicate_sellers"):
            output.append({
                "type":               "SYNDICATE",
                "buyer_city_id":      record.buyer_city_id,
                "transfer_mw":        record.transfer_mw,
                "cleared_price_mw":   record.cleared_price_mw,
                "buyer_bid":          record.buyer_bid,
                "syndicate_sellers":  record.syndicate_sellers,
                "breakdown_log":      record.breakdown_log,
            })
        else:
            output.append({
                "type":               "STANDARD",
                "buyer_city_id":      record.buyer_city_id,
                "seller_city_id":     record.seller_city_id,
                "transfer_mw":        record.transfer_mw,
                "cleared_price_mw":   record.cleared_price_mw,
                "seller_ask":         record.seller_ask,
                "path_cost":          record.path_cost,
                "carbon_tax":         record.carbon_tax,
                "buyer_bid":          record.buyer_bid,
                "path_description":   record.path_description,
                "llm_safety_status":  record.llm_safety_status,
                "dlr_applied":        record.dlr_applied,
                "effective_capacity": record.effective_capacity,
            })

    # Grid summary
    summary = {}
    for nid, node in env.nodes.items():
        summary[nid] = {
            "generation_mw":      round(node.generation_mw, 1),
            "demand_mw":          round(node.adjusted_demand_mw, 1),
            "balance_mw":         round(node.raw_balance_mw, 1),
            "battery_soc":        round(node.battery.soc, 4) if node.battery else None,
        }

    result = {
        "date":       date.today().isoformat(),
        "dispatches": output,
        "summary":    summary,
    }

    out_path = Path("outputs") / f"simulation_result_{date.today().isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Results JSON → {out_path}")


    # ─── Final summary ──────────────────────────────────────────────
    print(f"\n{'━' * 80}")
    print("  ✅ SIMULATION COMPLETE")
    print(f"  📅 Days simulated: {SIMULATION_DAYS}")
    print(f"  🏭 Regions: BHR, UP, WB, KAR")
    print(f"{'━' * 80}\n")

if __name__ == "__main__":
    run_simulation()
