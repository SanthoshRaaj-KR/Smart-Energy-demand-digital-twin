#!/usr/bin/env python
# coding: utf-8

# In[3]:


"""
agents.py
==========
Three-Agent System for the India Grid Digital Twin
────────────────────────────────────────────────────
Agent 1 — ContextAgent
    Reads external signals (festival, weather) and adjusts
    each region's demand before state agents see it.

Agent 2 — StateAgent  (one instance per region)
    Decides: STORE surplus | USE_BATTERY for deficit | REQUEST from grid | EXPORT to grid
    Runs after context adjustment, before grid routing.

Agent 3 — GridOperatorAgent
    Receives all EXPORT offers and REQUEST orders.
    Scores pre-enumerated paths and dispatches flows.
    Fully explainable — every decision is logged with reasons.

Run full multi-day simulation:
    python agents.py
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum

from digital_twin import GridEnvironment, TransmissionPath


# In[3]:


# ─────────────────────────────────────────────
#  SHARED DATA STRUCTURES
# ─────────────────────────────────────────────

class StateDecision(Enum):
    STORE      = "STORE"        # surplus → push into battery
    EXPORT     = "EXPORT"       # surplus → offer to grid
    USE_BATTERY= "USE_BATTERY"  # deficit covered by local battery
    REQUEST    = "REQUEST"      # deficit → ask grid for energy
    BALANCED   = "BALANCED"     # generation ≈ demand, no action needed


@dataclass
class StateAction:
    """Output of a StateAgent for one timestep."""
    node_id   : str
    decision  : StateDecision
    quantity_mw: float          # MW to store / export / request
    reason    : str             # plain-English explanation
    battery_soc_before: float   # SoC before this decision


@dataclass
class FlowOrder:
    """A resolved transfer the GridOperatorAgent will execute."""
    src       : str
    dst       : str
    requested_mw: float
    path      : TransmissionPath
    path_score: float
    delivered_mw: float = 0.0
    explanation : str   = ""


@dataclass
class WhatIfAnalysis:
    """Comparison of chosen path vs runner-up."""
    chosen_path   : str
    chosen_score  : float
    alt_path      : str
    alt_score     : float
    cost_saving   : float
    reason        : str


# ─────────────────────────────────────────────
#  AGENT 1 — CONTEXT AGENT
# ─────────────────────────────────────────────

class ContextAgent:
    """
    Provides external signals that inflate or deflate regional demand
    before state agents run their decisions.

    Signals (structured dict, never raw text):
        {
          "is_festival"         : bool,
          "temperature_anomaly" : float,   # °C above seasonal avg
          "is_weekend"          : bool,
          "confidence"          : float    # 0→1
        }

    Impact rules
    ────────────
    Festival         → demand × 1.15  (lighting, cooking, events)
    Temperature +1°C → demand × 1.02  (each degree, compounding AC load)
    Weekend          → demand × 0.93  (industry offline)
    """

    # region-specific sensitivity (some regions react more to heat)
    TEMP_SENSITIVITY = {
        "DEL": 0.025,   # North — extreme summers
        "MUM": 0.015,   # Coastal — moderate
        "KOL": 0.020,   # Humid — AC heavy
        "CHE": 0.030,   # South — hottest baseline
        "NAG": 0.018,
    }

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng(0)
        self.log : List[Dict] = []

    def generate_context(self, day: int) -> Dict:
        """
        Simulate or receive external context for today.
        In production this would read from a live API / calendar.
        """
        # festivals cluster around certain days (simplified)
        is_festival = day in {3, 7, 14, 20, 25}
        is_weekend  = (day % 7) in {0, 6}
        temp_anomaly = float(self.rng.normal(0, 2.0))   # ±2°C std
        confidence   = float(self.rng.uniform(0.7, 1.0))

        return {
            "is_festival"         : is_festival,
            "temperature_anomaly" : round(temp_anomaly, 2),
            "is_weekend"          : is_weekend,
            "confidence"          : round(confidence, 3),
        }

    def adjust_demand(self, env: GridEnvironment, context: Dict) -> Dict[str, float]:
        """
        Apply context signals to each node's demand.
        Modifies env.nodes[*].adjusted_demand_mw in-place.
        Returns dict of {node_id: adjustment_factor}.
        """
        factors: Dict[str, float] = {}
        explanations: List[str]   = []

        for nid, node in env.nodes.items():
            base   = node.demand_mw
            factor = 1.0
            parts  = []

            if context["is_festival"]:
                factor *= 1.15
                parts.append("festival +15%")

            temp = context["temperature_anomaly"]
            if abs(temp) > 0.5:
                sens = self.TEMP_SENSITIVITY[nid]
                t_factor = 1.0 + sens * temp
                factor *= t_factor
                parts.append(f"temp {temp:+.1f}°C → {t_factor - 1:+.1%}")

            if context["is_weekend"]:
                factor *= 0.93
                parts.append("weekend −7%")

            adj = base * factor
            node.adjusted_demand_mw = adj
            factors[nid] = round(factor, 4)
            explanations.append(
                f"  {nid} {node.name:8s}: {base:.0f} MW × {factor:.3f} "
                f"= {adj:.0f} MW  [{', '.join(parts) or 'no adjustment'}]"
            )

        self.log.append({
            "day"         : env.day,
            "context"     : context,
            "adjustments" : "\n".join(explanations),
        })
        return factors


# ─────────────────────────────────────────────
#  AGENT 2 — STATE AGENT (per region)
# ─────────────────────────────────────────────

class StateAgent:
    """
    One StateAgent per region node.
    Decides what to do with surplus or deficit using:
      - current balance (gen - adjusted demand)
      - battery state of charge
      - day of simulation (proxy for next-day expectation)

    Decision logic (strict priority order)
    ───────────────────────────────────────
    SURPLUS path:
      1. If battery SoC < 80% → STORE up to headroom, export rest
      2. If battery SoC >= 80% → EXPORT all surplus

    DEFICIT path:
      1. If battery has charge → USE_BATTERY to cover deficit
      2. If battery empty or deficit > battery → REQUEST from grid
         (for the uncovered portion)

    BALANCED:
      If |balance| < 100 MW → BALANCED (noise tolerance)
    """

    BALANCE_TOLERANCE_MW = 100.0    # below this → treated as balanced
    BATTERY_STORE_THRESHOLD = 0.80  # charge battery up to 80% SoC before exporting

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.history : List[StateAction] = []

    def decide(self, env: GridEnvironment) -> List[StateAction]:
        """
        Evaluate the region's situation and return 1–2 StateActions.
        Two actions can occur: e.g. USE_BATTERY + REQUEST (partial cover).
        """
        node    = env.nodes[self.node_id]
        balance = node.raw_balance_mw
        battery = node.battery
        soc     = battery.soc if battery else 0.0
        actions : List[StateAction] = []

        # ── BALANCED ────────────────────────────────────────
        if abs(balance) < self.BALANCE_TOLERANCE_MW:
            a = StateAction(
                node_id  = self.node_id,
                decision = StateDecision.BALANCED,
                quantity_mw = 0.0,
                reason   = (f"{node.name} is balanced "
                            f"(balance = {balance:+.0f} MW < tolerance "
                            f"{self.BALANCE_TOLERANCE_MW} MW)."),
                battery_soc_before = soc,
            )
            actions.append(a)
            self.history.append(a)
            return actions

        # ── SURPLUS ─────────────────────────────────────────
        if balance > 0:
            surplus = balance
            stored  = 0.0

            if battery and soc < self.BATTERY_STORE_THRESHOLD:
                headroom  = battery.headroom
                to_store  = min(surplus, headroom)
                stored    = battery.store(to_store)
                surplus  -= to_store   # reduce exportable surplus

                actions.append(StateAction(
                    node_id     = self.node_id,
                    decision    = StateDecision.STORE,
                    quantity_mw = stored,
                    reason      = (f"{node.name} battery SoC={soc:.0%} "
                                   f"< {self.BATTERY_STORE_THRESHOLD:.0%} threshold. "
                                   f"Storing {stored:.0f} MWh to raise SoC "
                                   f"to {battery.soc:.0%}."),
                    battery_soc_before = soc,
                ))

            if surplus > self.BALANCE_TOLERANCE_MW:
                actions.append(StateAction(
                    node_id     = self.node_id,
                    decision    = StateDecision.EXPORT,
                    quantity_mw = surplus,
                    reason      = (f"{node.name} exporting {surplus:.0f} MW surplus "
                                   f"(after storing {stored:.0f} MWh locally). "
                                   f"Battery SoC now {battery.soc:.0%}." if battery
                                   else f"{node.name} exporting {surplus:.0f} MW surplus "
                                        f"(no battery installed)."),
                    battery_soc_before = soc,
                ))

        # ── DEFICIT ─────────────────────────────────────────
        else:
            deficit   = abs(balance)
            remaining = deficit

            if battery and battery.charge > 1.0:
                supplied   = battery.discharge(remaining)
                remaining -= supplied

                actions.append(StateAction(
                    node_id     = self.node_id,
                    decision    = StateDecision.USE_BATTERY,
                    quantity_mw = supplied,
                    reason      = (f"{node.name} deficit = {deficit:.0f} MW. "
                                   f"Battery discharged {supplied:.0f} MWh "
                                   f"(SoC {soc:.0%} → {battery.soc:.0%}). "
                                   f"Remaining deficit after battery: {remaining:.0f} MW."),
                    battery_soc_before = soc,
                ))

            if remaining > self.BALANCE_TOLERANCE_MW:
                batt_info = (f"Battery depleted (SoC={battery.soc:.0%})."
                             if battery else "No battery.")
                actions.append(StateAction(
                    node_id     = self.node_id,
                    decision    = StateDecision.REQUEST,
                    quantity_mw = remaining,
                    reason      = (f"{node.name} still needs {remaining:.0f} MW "
                                   f"from grid. {batt_info}"),
                    battery_soc_before = soc,
                ))

        for a in actions:
            self.history.append(a)
        return actions


# ─────────────────────────────────────────────
#  AGENT 3 — GRID OPERATOR AGENT
# ─────────────────────────────────────────────

class GridOperatorAgent:
    """
    Resolves all EXPORT offers and REQUEST orders by:
      1. Pairing surplus nodes with deficit nodes (largest surplus → largest deficit)
      2. Scoring all available paths using the cost function
      3. Dispatching flows and registering congestion
      4. Logging full explanation + what-if analysis for every transfer

    Cost function (per path)
    ────────────────────────
    score = α·loss + β·dist_norm + γ·congestion
          (see grid_env constants: ALPHA, BETA, GAMMA)

    Conflict resolution
    ───────────────────
    If multiple flows compete for the same edge (Nagpur bottleneck),
    the flow with the lower path score gets priority.
    Others reroute or are partially served.
    """

    def __init__(self):
        self.flow_orders : List[FlowOrder]      = []
        self.what_ifs    : List[WhatIfAnalysis] = []
        self.log         : List[Dict]           = []

    def _score_path(self, path: TransmissionPath, env: GridEnvironment) -> float:
        return path.total_cost(env.edges)

    def _best_path(
        self,
        src: str,
        dst: str,
        need_mw: float,
        env: GridEnvironment,
    ) -> Tuple[Optional[TransmissionPath], Optional[WhatIfAnalysis]]:
        """
        Return the lowest-cost feasible path from src to dst,
        plus a what-if analysis comparing it to the runner-up.
        """
        candidates = env.get_paths_for(src, dst)
        if not candidates:
            return None, None

        # filter to paths with enough remaining capacity
        feasible = [
            p for p in candidates
            if p.bottleneck_capacity(env.edges) >= need_mw * 0.5  # at least 50% deliverable
        ]

        if not feasible:
            # relax constraint — take highest capacity path even if insufficient
            feasible = sorted(candidates,
                              key=lambda p: p.bottleneck_capacity(env.edges),
                              reverse=True)

        # score all feasible paths
        scored = sorted(feasible, key=lambda p: self._score_path(p, env))
        best   = scored[0]

        what_if = None
        if len(scored) >= 2:
            runner_up = scored[1]
            saving    = self._score_path(runner_up, env) - self._score_path(best, env)
            what_if   = WhatIfAnalysis(
                chosen_path  = best.path_id,
                chosen_score = round(self._score_path(best, env), 4),
                alt_path     = runner_up.path_id,
                alt_score    = round(self._score_path(runner_up, env), 4),
                cost_saving  = round(saving, 4),
                reason       = (
                    f"Chose {best.path_id} ({best.label}) "
                    f"over {runner_up.path_id} ({runner_up.label}). "
                    f"Score difference: {saving:.4f} "
                    f"({'congestion' if env.edges[best.edge_keys[0]].congestion > 0.5 else 'distance/loss'} "
                    f"was decisive factor)."
                ),
            )
        return best, what_if

    def dispatch(
        self,
        export_offers : Dict[str, float],   # {node_id: surplus_mw}
        import_requests: Dict[str, float],  # {node_id: deficit_mw}
        env           : GridEnvironment,
    ) -> List[FlowOrder]:
        """
        Match exports to imports, score paths, apply flows to the environment.
        Returns list of executed FlowOrders.
        """
        self.flow_orders = []
        self.what_ifs    = []

        if not export_offers or not import_requests:
            self._log(env.day, "No transfers needed — either no surplus or no deficit.", {})
            return []

        # sort: largest surplus first, largest deficit first
        surplus_sorted = sorted(export_offers.items(),   key=lambda x: x[1], reverse=True)
        deficit_sorted = sorted(import_requests.items(), key=lambda x: x[1], reverse=True)

        # running tracker for remaining surplus/deficit
        remaining_surplus  = dict(surplus_sorted)
        remaining_deficit  = dict(deficit_sorted)

        for dst, d_need in deficit_sorted:
            need = remaining_deficit[dst]
            if need <= 0:
                continue

            for src, s_avail in surplus_sorted:
                if remaining_surplus.get(src, 0) <= 0:
                    continue
                if src == dst:
                    continue

                # how much can we actually move?
                transfer_mw = min(need, remaining_surplus[src])

                # find best path
                path, what_if = self._best_path(src, dst, transfer_mw, env)
                if path is None:
                    self._log(env.day, f"No path found {src}→{dst}", {})
                    continue

                # check bottleneck
                cap = path.bottleneck_capacity(env.edges)
                if cap < 1.0:
                    self._log(env.day,
                              f"Path {path.path_id} fully congested, skipping.",
                              {"src": src, "dst": dst})
                    continue

                actual_transfer = min(transfer_mw, cap)

                # apply flow to environment
                try:
                    delivered = env.apply_flow(path, actual_transfer)
                except ValueError as e:
                    self._log(env.day, f"Flow rejected: {e}", {})
                    continue

                # build explanation
                score   = self._score_path(path, env)
                loss_mw = actual_transfer - delivered
                explanation = (
                    f"Transfer {src}→{dst} via {path.path_id} ({path.label}). "
                    f"Requested {transfer_mw:.0f} MW, "
                    f"sent {actual_transfer:.0f} MW (cap limit), "
                    f"delivered {delivered:.0f} MW "
                    f"(loss {loss_mw:.0f} MW = {loss_mw/actual_transfer:.1%}). "
                    f"Path score = {score:.4f} "
                    f"[α·loss={path.total_loss_pct(env.edges):.2%} "
                    f"β·dist={path.edge_keys} "
                    f"γ·cong={max(env.edges[k].congestion for k in path.edge_keys):.0%}]."
                )

                order = FlowOrder(
                    src=src, dst=dst,
                    requested_mw=transfer_mw,
                    path=path,
                    path_score=score,
                    delivered_mw=delivered,
                    explanation=explanation,
                )
                self.flow_orders.append(order)
                if what_if:
                    self.what_ifs.append(what_if)

                # update remaining balances
                remaining_surplus[src] -= actual_transfer
                remaining_deficit[dst] -= delivered
                need -= delivered
                if need <= self.BALANCE_TOLERANCE:
                    break

        self._log(env.day, f"Dispatched {len(self.flow_orders)} flow orders.",
                  {"orders": len(self.flow_orders)})
        return self.flow_orders

    BALANCE_TOLERANCE = 50.0   # MW — stop requesting once within this

    def _log(self, day: int, msg: str, extra: dict):
        self.log.append({"day": day, "msg": msg, **extra})

    def print_dispatch_report(self):
        print(f"\n  {'─'*54}")
        print(f"  Grid Operator — Dispatch Report  ({len(self.flow_orders)} transfers)")
        print(f"  {'─'*54}")
        if not self.flow_orders:
            print("  No transfers executed.")
            return
        for o in self.flow_orders:
            print(f"\n  ▶ {o.src} → {o.dst}  |  {o.path.path_id}")
            print(f"    {o.explanation}")
        if self.what_ifs:
            print(f"\n  What-If Analysis:")
            for w in self.what_ifs:
                print(f"    ✓ {w.reason}")
                print(f"      Score saved vs alternative: {w.cost_saving:.4f}")


# ─────────────────────────────────────────────
#  SIMULATION ORCHESTRATOR
# ─────────────────────────────────────────────

class GridSimulation:
    """
    Ties all three agents together and runs multi-day simulation.

    Day flow (per timestep)
    ────────────────────────
    1. ContextAgent  → generate signals, adjust demand
    2. StateAgents   → decide per region (store/export/use_batt/request)
    3. GridOperator  → score paths, dispatch flows, log congestion
    4. Log + advance day
    """

    def __init__(self, seed: int = 42):
        self.env            = GridEnvironment(seed=seed)
        self.context_agent  = ContextAgent(rng=self.env.rng)
        self.state_agents   = {
            nid: StateAgent(nid) for nid in self.env.nodes
        }
        self.grid_operator  = GridOperatorAgent()
        self.daily_metrics  : List[Dict] = []

    def run_day(self, demand_override: Optional[Dict[str, float]] = None, verbose: bool = True):
        day = self.env.day
        if verbose:
            print(f"\n{'═'*60}")
            print(f"  DAY {day}")
            print(f"{'═'*60}")

        # ── Step 1: Set demand + Context adjustment ──────────
        self.env.set_daily_demand(demand_override)
        context = self.context_agent.generate_context(day)
        factors = self.context_agent.adjust_demand(self.env, context)

        if verbose:
            print(f"\n  Context signals:")
            print(f"    Festival    : {context['is_festival']}")
            print(f"    Temp anomaly: {context['temperature_anomaly']:+.1f}°C")
            print(f"    Weekend     : {context['is_weekend']}")
            print(f"    Confidence  : {context['confidence']:.0%}")
            print(f"\n  Demand after context adjustment:")
            print(self.env.node_status_summary().to_string(index=False))

        # ── Step 2: State Agents decide ───────────────────────
        self.env.reset_flows()

        export_offers   : Dict[str, float] = {}
        import_requests : Dict[str, float] = {}

        if verbose:
            print(f"\n  State Agent Decisions:")

        for nid, agent in self.state_agents.items():
            actions = agent.decide(self.env)
            for a in actions:
                if verbose:
                    print(f"\n    [{a.node_id}] {a.decision.value:12s}  "
                          f"{a.quantity_mw:6.0f} MW")
                    print(f"         {a.reason}")

                if a.decision == StateDecision.EXPORT:
                    export_offers[nid] = a.quantity_mw
                elif a.decision == StateDecision.REQUEST:
                    import_requests[nid] = a.quantity_mw

        # ── Step 3: Grid Operator dispatches flows ────────────
        if verbose:
            print(f"\n  Export offers  : { {k: f'{v:.0f} MW' for k,v in export_offers.items()} }")
            print(f"  Import requests: { {k: f'{v:.0f} MW' for k,v in import_requests.items()} }")

        orders = self.grid_operator.dispatch(export_offers, import_requests, self.env)

        if verbose:
            self.grid_operator.print_dispatch_report()

        # ── Step 4: Metrics ───────────────────────────────────
        total_requested  = sum(import_requests.values())
        total_delivered  = sum(o.delivered_mw for o in orders)
        total_loss       = sum(o.requested_mw - o.delivered_mw for o in orders)
        satisfaction     = total_delivered / total_requested if total_requested > 0 else 1.0
        unserved         = total_requested - total_delivered

        cong_df   = self.env.edge_congestion_summary()
        max_cong  = cong_df["congestion"].max() if not cong_df.empty else 0.0
        batt_socs = {
            nid: self.env.nodes[nid].battery.soc
            for nid in self.env.nodes
            if self.env.nodes[nid].battery
        }

        metrics = {
            "day"               : day,
            "is_festival"       : context["is_festival"],
            "temp_anomaly"      : context["temperature_anomaly"],
            "total_requested_mw": round(total_requested, 1),
            "total_delivered_mw": round(total_delivered, 1),
            "satisfaction_rate" : round(satisfaction, 4),
            "unserved_mw"       : round(unserved, 1),
            "transmission_loss_mw": round(total_loss, 1),
            "transfers_count"   : len(orders),
            "max_congestion"    : round(max_cong, 3),
            **{f"batt_soc_{k}": round(v, 3) for k, v in batt_socs.items()},
        }
        self.daily_metrics.append(metrics)

        if verbose:
            print(f"\n  Daily Metrics:")
            print(f"    Demand satisfaction : {satisfaction:.1%}")
            print(f"    Unserved demand     : {unserved:.0f} MW")
            print(f"    Transmission loss   : {total_loss:.0f} MW")
            print(f"    Max edge congestion : {max_cong:.0%}")
            print(f"    Battery SoCs        : "
                  f"{ {k: f'{v:.0%}' for k,v in batt_socs.items()} }")

            # Edge congestion for active edges
            active_cong = cong_df[cong_df["flow_mw"] > 0]
            if not active_cong.empty:
                print(f"\n  Active Edge Congestion:")
                print(active_cong[["edge","flow_mw","capacity_mw","congestion"]
                                  ].to_string(index=False))

        self.env.advance_day()
        return metrics

    def run(self, n_days: int = 10, verbose: bool = True) -> pd.DataFrame:
        """Run n_days and return metrics DataFrame."""
        for _ in range(n_days):
            self.run_day(verbose=verbose)
        return pd.DataFrame(self.daily_metrics)

    def summary(self) -> pd.DataFrame:
        df = pd.DataFrame(self.daily_metrics)
        if df.empty:
            return df
        print(f"\n{'═'*60}")
        print(f"  SIMULATION SUMMARY — {len(df)} days")
        print(f"{'═'*60}")
        print(f"  Avg satisfaction rate : {df['satisfaction_rate'].mean():.1%}")
        print(f"  Avg unserved demand   : {df['unserved_mw'].mean():.0f} MW/day")
        print(f"  Avg transmission loss : {df['transmission_loss_mw'].mean():.0f} MW/day")
        print(f"  Avg max congestion    : {df['max_congestion'].mean():.0%}")
        print(f"  Festival days         : {df['is_festival'].sum()}")
        print(f"  Total transfers       : {df['transfers_count'].sum()}")
        print(f"\n  Per-day metrics:")
        cols = ["day","satisfaction_rate","unserved_mw",
                "transmission_loss_mw","max_congestion","transfers_count"]
        print(df[cols].to_string(index=False))
        return df


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("  INDIA GRID DIGITAL TWIN — 3-Agent Simulation")
    print("=" * 60)

    sim = GridSimulation(seed=42)

    # ── Run 5 days verbosely ─────────────────
    metrics_df = sim.run(n_days=5, verbose=True)

    # ── Print summary ────────────────────────
    sim.summary()

    # ── Show what-if analyses across all days ─
    print(f"\n{'═'*60}")
    print("  ALL WHAT-IF ANALYSES (path selection justifications)")
    print(f"{'═'*60}")
    if sim.grid_operator.what_ifs:
        for i, w in enumerate(sim.grid_operator.what_ifs, 1):
            print(f"\n  {i}. {w.reason}")
            print(f"     Chosen score: {w.chosen_score:.4f}  |  "
                  f"Alt score: {w.alt_score:.4f}  |  "
                  f"Saved: {w.cost_saving:.4f}")
    else:
        print("  No what-if data (single path available for all OD pairs).")

    # ── Export metrics ───────────────────────
    metrics_df.to_csv("/home/claude/simulation_metrics.csv", index=False)
    print(f"\n  Metrics saved → simulation_metrics.csv")
    print(f"{'═'*60}\n")

