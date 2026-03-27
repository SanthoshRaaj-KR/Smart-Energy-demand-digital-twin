"""
backend/server.py
=================
FastAPI server for the India Grid Digital Twin UI.

Routes
------
GET  /api/grid-status       — Live node balances, battery SoC, edge congestion
GET  /api/intelligence      — LLM multipliers from outputs/context_cache/node_*.json
GET  /api/dispatch-log      — Last simulation dispatch records (from outputs/)
POST /api/run-simulation    — Trigger run_simulation.py, stream log lines back
GET  /api/health            — Simple health check

Run
---
    cd backend
    uvicorn server:app --reload --port 8000

Frontend proxy already points to http://localhost:8000 in package.json.
"""

from __future__ import annotations

import asyncio
import dataclasses
import glob
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# ── Make sure the backend src tree is importable ──────────────────────────────
ROOT = Path(__file__).parent.parent  # repo root  (backend/../ = project root)
sys.path.insert(0, str(ROOT))

from src.environment.grid_physics import GridEnvironment

app = FastAPI(title="Grid Twin API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ─────────────────────────────────────────────────────────────────────
CACHE_DIR   = ROOT / "outputs" / "context_cache"
OUTPUTS_DIR = ROOT / "outputs"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_node_cache() -> Dict[str, Dict]:
    """Load all node_*.json files from today's context cache."""
    result: Dict[str, Dict] = {}
    pattern = str(CACHE_DIR / f"node_*_{date.today().isoformat()}.json")
    for fp in glob.glob(pattern):
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
            nid = data.get("node_id")
            if nid:
                result[nid] = data
        except Exception:
            pass

    # Fallback: load any node_*.json if today's files don't exist yet
    if not result:
        for fp in glob.glob(str(CACHE_DIR / "node_*.json")):
            try:
                data = json.loads(Path(fp).read_text(encoding="utf-8"))
                nid = data.get("node_id")
                if nid and nid not in result:
                    result[nid] = data
            except Exception:
                pass
    return result


def _load_latest_dispatch_log() -> List[Dict]:
    """Find the most recent grid_intelligence_*.json and extract dispatch info."""
    files = sorted(OUTPUTS_DIR.glob("grid_intelligence_*.json"), reverse=True)
    if not files:
        return []
    try:
        raw = json.loads(files[0].read_text(encoding="utf-8"))
        # The intelligence JSON doesn't store dispatch records directly —
        # those come from run_simulation output. Look for a simulation log.
    except Exception:
        pass

    # Look for simulation_result_*.json written by run_simulation
    sim_files = sorted(OUTPUTS_DIR.glob("simulation_result_*.json"), reverse=True)
    if sim_files:
        try:
            return json.loads(sim_files[0].read_text(encoding="utf-8")).get("dispatches", [])
        except Exception:
            pass
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "date": date.today().isoformat()}


@app.get("/api/grid-status")
def grid_status():
    """
    Instantiate a fresh GridEnvironment and return node + edge snapshot.
    Applies context-cache multipliers if available.
    """
    env = GridEnvironment(seed=42)
    env.set_daily_demand()

    node_cache = _load_node_cache()

    # Apply generation_capacity_multiplier from intelligence cache if present
    for nid, node in env.nodes.items():
        ctx = node_cache.get(nid, {})
        gm  = ctx.get("grid_multipliers", {})
        gcm = float(gm.get("generation_capacity_multiplier", 1.0))
        node.generation_mw = node.generation_mw * gcm
        node.adjusted_demand_mw = node.demand_mw  # base; fusion would refine

    nodes = []
    for nid, node in env.nodes.items():
        nodes.append({
            "id":                   nid,
            "name":                 node.name,
            "generation_mw":        round(node.generation_mw, 1),
            "demand_mw":            round(node.demand_mw, 1),
            "adjusted_demand_mw":   round(node.adjusted_demand_mw, 1),
            "balance_mw":           round(node.raw_balance_mw, 1),
            "battery": {
                "soc":      round(node.battery.soc, 4),
                "charge":   round(node.battery.charge, 1),
                "capacity": node.battery.capacity,
            } if node.battery else None,
        })

    edges = []
    for (src, dst), edge in env.edges.items():
        edges.append({
            "src":          src,
            "dst":          dst,
            "distance_km":  edge.distance_km,
            "flow_mw":      round(edge.current_flow, 1),
            "capacity_mw":  edge.capacity_mw,
            "congestion":   round(edge.congestion, 4),
            "loss_pct":     edge.loss_pct,
            "tariff":       edge.tariff,
        })

    return {"nodes": nodes, "edges": edges}


@app.get("/api/intelligence")
def intelligence():
    """
    Return the LLM-generated intelligence context for all nodes.
    Reads from outputs/context_cache/node_*.json.
    """
    node_cache = _load_node_cache()
    if not node_cache:
        raise HTTPException(
            status_code=404,
            detail="No intelligence cache found. Run main.py first to generate context."
        )

    result: Dict[str, Any] = {}
    for nid, data in node_cache.items():
        result[nid] = {
            "city":            data.get("city", nid),
            "generated_at":    data.get("generated_at", ""),
            "grid_multipliers": data.get("grid_multipliers", {}),
            "detected_events":  data.get("detected_events", []),
            "impact_narrative": data.get("impact_narrative", ""),
            "extracted_signals":data.get("extracted_signals", ""),
            "weather":          data.get("weather", {}),
        }
    return result


@app.get("/api/dispatch-log")
def dispatch_log():
    """
    Return dispatch records from the most recent simulation run.
    Reads outputs/simulation_result_<date>.json written by run_simulation.py.
    """
    records = _load_latest_dispatch_log()
    if not records:
        # Return empty list — simulation hasn't been run yet
        return []
    return records


@app.post("/api/run-simulation")
async def run_simulation_endpoint():
    """
    Stream run_simulation.py stdout back to the client as newline-delimited text.
    The frontend reads this as a text stream and renders each line in the terminal.
    """
    sim_script = ROOT / "run_simulation.py"
    if not sim_script.exists():
        raise HTTPException(status_code=404, detail="run_simulation.py not found")

    async def stream_output():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(sim_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT),
        )
        async for line in proc.stdout:
            decoded = line.decode("utf-8", errors="replace")
            yield decoded
        await proc.wait()
        exit_code = proc.returncode
        yield f"\n[DONE] Simulation exited with code {exit_code}\n"

    return StreamingResponse(stream_output(), media_type="text/plain")


@app.get("/api/simulation-result")
def simulation_result():
    """Return the latest simulation_result JSON if it exists."""
    files = sorted(OUTPUTS_DIR.glob("simulation_result_*.json"), reverse=True)
    if not files:
        return {"status": "no_result", "dispatches": [], "summary": {}}
    return json.loads(files[0].read_text(encoding="utf-8"))
