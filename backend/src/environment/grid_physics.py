#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
grid_env.py
============
India 4-Region Power Grid — Environment Simulation
Nodes   : Delhi, Mumbai, Kolkata, Chennai, Nagpur (hub)
Edges   : Real shared transmission corridors
Battery : Each region node has a battery cell (Nagpur has none)
Congestion: Emerges from actual shared edge usage across flows

Run standalone to see a full daily simulation printout:
    python grid_env.py
"""

import networkx as nx
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# In[2]:


# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────

ALPHA = 0.4   # weight for transmission loss  in cost function
BETA  = 0.3   # weight for distance           in cost function
GAMMA = 0.3   # weight for congestion         in cost function

EDGE_CAPACITY_MW = 3000.0   # default max flow on any single edge (MW)


# In[3]:


@dataclass
class BatteryCell:
    """
    Simple energy storage attached to a region node.
    Units: MWh
    """
    node_id   : str
    capacity  : float          # max storable energy (MWh)
    charge    : float          # current charge level (MWh)
    charge_eff: float = 0.95   # efficiency on charge (5% loss)
    discharge_eff: float = 0.95  # efficiency on discharge

    # ── state ──────────────────────────────────
    @property
    def soc(self) -> float:
        """State of Charge as fraction 0→1."""
        return self.charge / self.capacity

    @property
    def available(self) -> float:
        """Energy available to discharge (MWh)."""
        return self.charge * self.discharge_eff

    @property
    def headroom(self) -> float:
        """Spare capacity for charging (MWh)."""
        return self.capacity - self.charge

    # ── actions ────────────────────────────────
    def store(self, energy_mwh: float) -> float:
        """
        Push energy into battery.
        Returns actual energy stored (limited by headroom).
        """
        storable = min(energy_mwh * self.charge_eff, self.headroom)
        self.charge += storable
        return storable

    def discharge(self, demand_mwh: float) -> float:
        """
        Pull energy from battery to meet demand.
        Returns actual energy supplied.
        """
        available = self.charge * self.discharge_eff
        supplied  = min(demand_mwh, available)
        self.charge -= supplied / self.discharge_eff   # reverse efficiency
        self.charge  = max(self.charge, 0.0)
        return supplied

    def __repr__(self):
        return (f"Battery({self.node_id}: "
                f"{self.charge:.0f}/{self.capacity:.0f} MWh  "
                f"SoC={self.soc:.0%})")




# In[4]:


# ─────────────────────────────────────────────
#  REGION NODE
# ─────────────────────────────────────────────

@dataclass
class RegionNode:
    """
    One region in the grid.
    generation_gw : installed capacity (assumed always available here)
    demand_mw     : today's predicted demand (set each timestep)
    battery       : optional BatteryCell (Nagpur hub has None)
    coords        : (lat, lon) for reference
    """
    node_id       : str
    name          : str
    generation_mw : float
    coords        : Tuple[float, float]
    battery       : Optional[BatteryCell] = None

    # set each day by simulation
    demand_mw     : float = 0.0
    adjusted_demand_mw: float = 0.0   # after context agent adjusts

    @property
    def raw_balance_mw(self) -> float:
        """Positive = surplus, Negative = deficit. Before battery."""
        return self.generation_mw - self.adjusted_demand_mw

    def __repr__(self):
        bal = self.raw_balance_mw
        sign = "+" if bal >= 0 else ""
        return (f"[{self.node_id}] {self.name:8s} "
                f"gen={self.generation_mw:.0f} MW  "
                f"demand={self.adjusted_demand_mw:.0f} MW  "
                f"balance={sign}{bal:.0f} MW  "
                f"batt={self.battery}")




# In[5]:


# ─────────────────────────────────────────────
#  TRANSMISSION EDGE
# ─────────────────────────────────────────────

@dataclass
class TransmissionEdge:
    """
    A directed transmission corridor between two nodes.
    loss_pct   : fraction of energy lost in transit (0.02 = 2%)
    distance_km: physical length (affects cost)
    capacity_mw: max flow this edge can carry
    tariff      : cost per MWh transmitted (₹/MWh)
    current_flow: running total of MW being pushed through right now
    """
    src         : str
    dst         : str
    distance_km : float
    loss_pct    : float
    capacity_mw : float
    tariff      : float    # ₹/MWh

    current_flow: float = 0.0   # updated each timestep

    @property
    def congestion(self) -> float:
        """0 = empty, 1 = fully saturated."""
        return min(self.current_flow / self.capacity_mw, 1.0)

    @property
    def remaining_capacity(self) -> float:
        return max(self.capacity_mw - self.current_flow, 0.0)

    def edge_cost(self) -> float:
        """
        Composite cost for routing decisions.
        Cost = α·loss + β·distance_norm + γ·congestion
        distance is normalised to [0,1] against max Indian corridor (~2000 km)
        """
        dist_norm = self.distance_km / 2000.0
        return (ALPHA * self.loss_pct * 10        # scale loss to ~[0,1]
              + BETA  * dist_norm
              + GAMMA * self.congestion)

    def push_flow(self, mw: float) -> float:
        """
        Register flow through this edge.
        Returns energy that actually arrives at destination (after loss).
        Raises if edge would be overloaded.
        """
        if mw > self.remaining_capacity + 1e-6:
            raise ValueError(
                f"Edge {self.src}→{self.dst} overloaded: "
                f"tried {mw:.0f} MW, remaining {self.remaining_capacity:.0f} MW"
            )
        self.current_flow += mw
        return mw * (1.0 - self.loss_pct)

    def reset_flow(self):
        self.current_flow = 0.0

    def __repr__(self):
        return (f"Edge {self.src}→{self.dst}  "
                f"{self.distance_km:.0f}km  "
                f"loss={self.loss_pct:.0%}  "
                f"tariff=₹{self.tariff}  "
                f"flow={self.current_flow:.0f}/{self.capacity_mw:.0f} MW  "
                f"cong={self.congestion:.0%}")


# In[6]:


# ─────────────────────────────────────────────
#  PRE-ENUMERATED PATHS
# ─────────────────────────────────────────────

@dataclass
class TransmissionPath:
    """
    A named route from source to destination through a sequence of edges.
    The agent picks from these — no dynamic routing needed.
    """
    path_id  : str
    src      : str
    dst      : str
    hops     : List[str]          # sequence of node IDs  e.g. [Delhi, Nagpur, Chennai]
    edge_keys: List[Tuple[str,str]]  # edge (src, dst) pairs along the path
    label    : str                # human-readable description

    def total_cost(self, edges: Dict[Tuple[str,str], TransmissionEdge]) -> float:
        return sum(edges[k].edge_cost() for k in self.edge_keys)

    def total_loss_pct(self, edges: Dict[Tuple[str,str], TransmissionEdge]) -> float:
        """Compound loss across all hops."""
        survived = 1.0
        for k in self.edge_keys:
            survived *= (1.0 - edges[k].loss_pct)
        return 1.0 - survived

    def bottleneck_capacity(self, edges: Dict[Tuple[str,str], TransmissionEdge]) -> float:
        """Max MW this path can carry right now (limited by most congested edge)."""
        return min(edges[k].remaining_capacity for k in self.edge_keys)

    def __repr__(self):
        return f"Path[{self.path_id}] {' → '.join(self.hops)}  ({self.label})"


# In[7]:


# ─────────────────────────────────────────────
#  GRID ENVIRONMENT
# ─────────────────────────────────────────────

class GridEnvironment:
    """
    The full India grid simulation environment.

    Topology
    --------
    Nodes: Delhi, Mumbai, Kolkata, Chennai, Nagpur (hub — no storage)
    Edges: Real shared corridors. Nagpur is the central bottleneck.

    Paths (pre-enumerated, agent picks from these):
    ─────────────────────────────────────────────
    Delhi → Kolkata:
        P1  Direct                                 (fast, costly)
        P2  Delhi → Nagpur → Kolkata               (balanced)

    Delhi → Chennai:
        P3  Delhi → Nagpur → Chennai               (medium)
        P4  Delhi → Mumbai → Chennai               (long, cheap)
        P5  Delhi → Kolkata → Chennai (via east)   (economy)

    Mumbai → Kolkata:
        P6  Mumbai → Nagpur → Kolkata              (main route)
        P7  Mumbai → Chennai → Kolkata             (long south loop)

    Mumbai → Chennai:
        P8  Direct Mumbai → Chennai                (short, ok)
        P9  Mumbai → Nagpur → Chennai              (via hub)

    Chennai → Delhi  /  Kolkata → Delhi  etc.:
    All above paths are bidirectional — reversed edge keys used.
    """

    def __init__(self, seed: int = 42):
        self.rng  = np.random.default_rng(seed)
        self.day  = 0
        self.log  : List[Dict] = []

        self._build_nodes()
        self._build_edges()
        self._build_paths()
        self._build_graph()   # networkx graph (for visualisation/reference)

    # ── construction ──────────────────────────

    def _build_nodes(self):
        self.nodes: Dict[str, RegionNode] = {
            "BHR": RegionNode(
                node_id="BHR", name="Bihar",
                generation_mw=9000,
                coords=(25.59, 85.13),
                battery=BatteryCell("BHR", capacity=500, charge=250)
            ),
            "UP": RegionNode(
                node_id="UP", name="NR UP",
                generation_mw=15000,
                coords=(26.84, 80.94),
                battery=BatteryCell("UP", capacity=800, charge=400)
            ),
            "WB": RegionNode(
                node_id="WB", name="West Bengal",
                generation_mw=11000,
                coords=(22.57, 88.36),
                battery=BatteryCell("WB", capacity=600, charge=300)
            ),
            "KAR": RegionNode(
                node_id="KAR", name="SR Karnataka",
                generation_mw=14000,
                coords=(12.97, 77.59),
                battery=BatteryCell("KAR", capacity=1000, charge=500)
            ),
        }

    def _build_edges(self):
        """
        All edges are bidirectional but stored directionally.
        Each physical corridor appears twice (A→B and B→A).
        """
        corridors = [
            # (src, dst, km,   loss,  capacity_mw, tariff ₹/MWh)
            ("BHR", "UP",   500, 0.015, 3000, 4.0),
            ("BHR", "WB",   600, 0.018, 2500, 3.0),
            ("BHR", "KAR", 1800, 0.040, 2000, 8.0),
            ("UP",  "WB",  1000, 0.025, 3500, 5.0),
            ("UP",  "KAR", 1600, 0.035, 3500, 7.0),
            ("WB",  "KAR", 1700, 0.038, 3000, 6.0),
        ]

        self.edges: Dict[Tuple[str,str], TransmissionEdge] = {}
        for src, dst, km, loss, cap, tariff in corridors:
            self.edges[(src, dst)] = TransmissionEdge(src, dst, km, loss, cap, tariff)
            self.edges[(dst, src)] = TransmissionEdge(dst, src, km, loss, cap, tariff)

    def _build_paths(self):
        """
        Pre-enumerate all meaningful paths between region pairs.
        Agent will receive the list for its OD pair and score them.
        """
        self.paths: Dict[str, TransmissionPath] = {}

        def add(pid, src, dst, hops, label):
            edges = [(hops[i], hops[i+1]) for i in range(len(hops)-1)]
            self.paths[pid] = TransmissionPath(pid, src, dst, hops, edges, label)

        add("BHR_UP_1",  "BHR", "UP",  ["BHR", "UP"],  "Direct BHR-UP")
        add("BHR_WB_1",  "BHR", "WB",  ["BHR", "WB"],  "Direct BHR-WB")
        add("BHR_KAR_1", "BHR", "KAR", ["BHR", "KAR"], "Direct BHR-KAR")
        add("UP_WB_1",   "UP",  "WB",  ["UP", "WB"],   "Direct UP-WB")
        add("UP_KAR_1",  "UP",  "KAR", ["UP", "KAR"],  "Direct UP-KAR")
        add("WB_KAR_1",  "WB",  "KAR", ["WB", "KAR"],  "Direct WB-KAR")

        # ── Reverse directions (reuse same hops reversed) ──
        reverses = [
            ("UP_BHR_1",  "UP",  "BHR", ["UP", "BHR"],   "Direct reverse"),
            ("WB_BHR_1",  "WB",  "BHR", ["WB", "BHR"],   "Direct reverse"),
            ("KAR_BHR_1", "KAR", "BHR", ["KAR", "BHR"],  "Direct reverse"),
            ("WB_UP_1",   "WB",  "UP",  ["WB", "UP"],    "Direct reverse"),
            ("KAR_UP_1",  "KAR", "UP",  ["KAR", "UP"],   "Direct reverse"),
            ("KAR_WB_1",  "KAR", "WB",  ["KAR", "WB"],   "Direct reverse"),
        ]
        for pid, src, dst, hops, label in reverses:
            add(pid, src, dst, hops, label)

    def _build_graph(self):
        """NetworkX graph — used for visualisation and path validation."""
        self.G = nx.DiGraph()
        for nid, node in self.nodes.items():
            self.G.add_node(nid, **{
                "name"    : node.name,
                "gen_mw"  : node.generation_mw,
                "coords"  : node.coords,
                "has_batt": node.battery is not None,
            })
        for (src, dst), edge in self.edges.items():
            self.G.add_edge(src, dst, **{
                "distance_km": edge.distance_km,
                "loss_pct"   : edge.loss_pct,
                "capacity_mw": edge.capacity_mw,
                "tariff"     : edge.tariff,
            })

    # ── daily demand generation ────────────────

    def set_daily_demand(self, demand_override: Optional[Dict[str, float]] = None):
        """
        Set predicted demand for each node.
        If no override provided, use stochastic generation based on typical profiles.
        Units: MW
        """
        # typical peak demand fractions of installed capacity
        base_fractions = {
            "BHR": 1.10,
            "UP":  1.05,
            "WB":  1.15,
            "KAR": 0.90,
        }

        for nid, node in self.nodes.items():
            if demand_override and nid in demand_override:
                node.demand_mw = demand_override[nid]
            else:
                frac  = base_fractions[nid]
                noise = self.rng.normal(0, 0.05)   # ±5% stochastic noise
                node.demand_mw = node.generation_mw * max(frac + noise, 0.5)

            node.adjusted_demand_mw = node.demand_mw  # context agent modifies this later

    # ── congestion management ─────────────────

    def reset_flows(self):
        """Clear all edge flows at start of each timestep."""
        for edge in self.edges.values():
            edge.reset_flow()

    def apply_flow(self, path: TransmissionPath, flow_mw: float) -> float:
        """
        Push flow_mw through all edges of a path.
        Returns energy delivered at destination (after compound loss).
        Raises if any edge is overloaded.
        """
        delivered = flow_mw
        for key in path.edge_keys:
            delivered = self.edges[key].push_flow(delivered)
        return delivered

    def get_paths_for(self, src: str, dst: str) -> List[TransmissionPath]:
        """Return all pre-enumerated paths between src and dst."""
        return [p for p in self.paths.values()
                if p.src == src and p.dst == dst]

    # ── battery helpers ──────────────────────

    def store_surplus(self, node_id: str, surplus_mw: float) -> float:
        """
        Try to store surplus into local battery.
        Returns how much was actually stored (MWh — daily timestep = 1 day ≈ 24h).
        We treat MW as MWh/h so 1 timestep = 1 unit for simplicity.
        """
        node = self.nodes[node_id]
        if node.battery is None:
            return 0.0
        return node.battery.store(surplus_mw)

    def discharge_deficit(self, node_id: str, deficit_mw: float) -> float:
        """
        Try to cover deficit from local battery.
        Returns how much was actually supplied.
        """
        node = self.nodes[node_id]
        if node.battery is None:
            return 0.0
        return node.battery.discharge(deficit_mw)

    # ── status helpers ───────────────────────

    def get_balances(self) -> Dict[str, float]:
        """Return raw balance (gen - demand) for each node."""
        return {nid: n.raw_balance_mw for nid, n in self.nodes.items()}

    def get_surplus_nodes(self) -> List[str]:
        return [nid for nid, bal in self.get_balances().items() if bal > 0]

    def get_deficit_nodes(self) -> List[str]:
        return [nid for nid, bal in self.get_balances().items() if bal < 0]

    def edge_congestion_summary(self) -> pd.DataFrame:
        rows = []
        for (src, dst), e in self.edges.items():
            rows.append({
                "edge"       : f"{src}→{dst}",
                "distance_km": e.distance_km,
                "flow_mw"    : round(e.current_flow, 1),
                "capacity_mw": e.capacity_mw,
                "congestion" : round(e.congestion, 3),
                "loss_pct"   : f"{e.loss_pct:.1%}",
                "tariff"     : e.tariff,
            })
        return pd.DataFrame(rows)

    def node_status_summary(self) -> pd.DataFrame:
        rows = []
        for nid, n in self.nodes.items():
            batt_soc  = f"{n.battery.soc:.0%}" if n.battery else "—"
            batt_mwh  = f"{n.battery.charge:.0f}" if n.battery else "—"
            rows.append({
                "node"       : f"{nid} {n.name}",
                "gen_mw"     : n.generation_mw,
                "demand_mw"  : round(n.adjusted_demand_mw, 1),
                "balance_mw" : round(n.raw_balance_mw, 1),
                "batt_soc"   : batt_soc,
                "batt_mwh"   : batt_mwh,
            })
        return pd.DataFrame(rows)

    # ── logging ──────────────────────────────

    def log_event(self, event_type: str, detail: dict):
        entry = {"day": self.day, "event": event_type, **detail}
        self.log.append(entry)

    def get_log_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)

    def advance_day(self):
        self.day += 1


# In[8]:


# ─────────────────────────────────────────────
#  STANDALONE TEST — run: python grid_env.py
# ─────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("  INDIA GRID ENVIRONMENT — Standalone Smoke Test")
    print("=" * 60)

    env = GridEnvironment(seed=7)

    # ── Day 1 ───────────────────────────────
    env.set_daily_demand()
    print(f"\n{'─'*60}")
    print(f"  DAY {env.day}  —  Node Status")
    print(f"{'─'*60}")
    print(env.node_status_summary().to_string(index=False))

    print(f"\n  Surplus nodes : {env.get_surplus_nodes()}")
    print(f"  Deficit nodes : {env.get_deficit_nodes()}")

    # ── Show all available paths for a specific OD pair ──
    print(f"\n{'─'*60}")
    print("  Available paths  BHR → KAR:")
    print(f"{'─'*60}")
    for p in env.get_paths_for("BHR", "KAR"):
        cost = p.total_cost(env.edges)
        loss = p.total_loss_pct(env.edges)
        cap  = p.bottleneck_capacity(env.edges)
        print(f"  {p.path_id:12s}  {p.label:40s}"
              f"  cost={cost:.3f}  loss={loss:.1%}  "
              f"  avail_cap={cap:.0f} MW")

    # ── Simulate a manual flow ───────────────
    print(f"\n{'─'*60}")
    print("  Simulating flow: BHR → KAR  (1000 MW)")
    print(f"{'─'*60}")
    env.reset_flows()
    path   = env.paths["BHR_KAR_1"]
    delivered = env.apply_flow(path, 1000)
    print(f"  Sent     : 1000 MW")
    print(f"  Delivered: {delivered:.1f} MW  "
          f"(loss = {1000 - delivered:.1f} MW  "
          f"= {(1000-delivered)/1000:.1%})")

    # ── A second flow through overlapping edges ──
    print(f"\n  Now routing another 2000 MW:  UP → KAR")
    path2 = env.paths["UP_KAR_1"]
    try:
        delivered2 = env.apply_flow(path2, 2000)
        print(f"  Delivered: {delivered2:.1f} MW")
    except ValueError as e:
        print(f"  ⚠ Overload blocked: {e}")

    # ── Edge congestion after flows ──────────
    print(f"\n{'─'*60}")
    print("  Edge Congestion After Flows:")
    print(f"{'─'*60}")
    cong = env.edge_congestion_summary()
    cong = cong[cong["flow_mw"] > 0].copy()
    print(cong.to_string(index=False))

    # ── Battery interaction ──────────────────
    print(f"\n{'─'*60}")
    print("  Battery Tests:")
    print(f"{'─'*60}")
    stored   = env.store_surplus("UP", 300)
    supplied = env.discharge_deficit("WB", 500)
    print(f"  UP stored surplus      : {stored:.1f} MWh")
    print(f"  WB drew from cell      : {supplied:.1f} MWh")
    print(f"  UP battery after       : {env.nodes['UP'].battery}")
    print(f"  WB battery after       : {env.nodes['WB'].battery}")

    print(f"\n{'─'*60}")
    print("  ✓ GridEnvironment initialised and validated.")
    print(f"{'─'*60}\n")

