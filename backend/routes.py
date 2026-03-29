"""
backend/routes.py
=================
All FastAPI routes for the India Grid Digital Twin.

Endpoints expose COMPLETE intelligence details:
- Grid multipliers (EDM, GCM, temp anomaly)
- Risk flags (demand spike, supply shortfall, hoard)
- Detected events (mass gatherings, broadcasts, disruptions)
- Impact narratives & extracted signals
- Weather forecasts
- Dispatch records with full market details

Routes
------
GET  /api/health                    — Health check
POST /api/generate-intelligence     — Fetch/generate intelligence for today
GET  /api/intelligence              — Return cached intelligence (all details)
GET  /api/grid-status               — Live node balances + intelligence context
GET  /api/dispatch-log              — All dispatch records from last simulation
POST /api/run-simulation            — Execute simulation (stream output)
GET  /api/simulation-result         — Latest simulation JSON result
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# ── Make sure the backend src tree is importable ──────────────────────────────
ROOT = Path(__file__).parent.parent  # repo root
sys.path.insert(0, str(ROOT))

from src.environment.grid_physics import GridEnvironment
from src.agents.intelligence_agent.orchestrator import SmartGridIntelligenceAgent
from src.agents.intelligence_agent.setup import CITY_REGISTRY

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


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_node_cache() -> Dict[str, Dict]:
    """Load all node_*.json files from today's context cache."""
    result: Dict[str, Dict] = {}
    today_iso = date.today().isoformat()
    
    # Try today's files first
    import glob as glob_module
    pattern = str(CACHE_DIR / f"node_*_{today_iso}.json")
    for fp in glob_module.glob(pattern):
        try:
            data = json.loads(Path(fp).read_text(encoding="utf-8"))
            nid = data.get("node_id")
            if nid:
                result[nid] = data
        except Exception:
            pass

    # Fallback: load any node_*.json if today's files don't exist
    if not result:
        for fp in glob_module.glob(str(CACHE_DIR / "node_*.json")):
            try:
                data = json.loads(Path(fp).read_text(encoding="utf-8"))
                nid = data.get("node_id")
                if nid and nid not in result:
                    result[nid] = data
            except Exception:
                pass
    return result


def _load_latest_dispatch_log() -> List[Dict]:
    """Find the most recent simulation_result_*.json and extract dispatches."""
    import glob as glob_module
    sim_files = sorted(OUTPUTS_DIR.glob("simulation_result_*.json"), reverse=True)
    if sim_files:
        try:
            return json.loads(sim_files[0].read_text(encoding="utf-8")).get("dispatches", [])
        except Exception:
            pass
    return []


def _build_fallback_intelligence() -> Dict[str, Dict[str, Any]]:
    """Construct a safe fallback intelligence payload when cache is empty."""
    fallback = {}
    for nid, meta in CITY_REGISTRY.items():
        fallback[nid] = {
            "node_id": nid,
            "city": meta.get("name", nid),
            "generated_at": date.today().isoformat(),
            "grid_multipliers": {
                "economic_demand_multiplier": 1.0,
                "generation_capacity_multiplier": 1.0,
                "temperature_anomaly": 0.0,
                "demand_spike_risk": "UNKNOWN",
                "supply_shortfall_risk": "UNKNOWN",
                "pre_event_hoard": False,
                "seven_day_demand_forecast_mw_delta": 0,
                "confidence": 0.0,
                "key_driver": "No cache",
                "reasoning": "Run /api/generate-intelligence to populate.",
            },
            "detected_events": [],
            "impact_narrative": "(No intelligence generated yet)",
            "extracted_signals": "No signals available.",
            "weather": {
                "current_temp_c": 30.0,
                "current_humidity_pct": 60,
                "current_condition": "clear sky",
                "week_max_c": 34.0,
                "week_max_heat_index_c": 37.0,
                "week_total_rain_mm": 0.0,
                "forecast_days": [],
                "hourly_forecast_7d": [],
            },
        }
    return fallback


def _generate_intelligence() -> Dict[str, Any]:
    """Run the intelligence pipeline and persist cache."""
    try:
        agent = SmartGridIntelligenceAgent()
        intelligence = agent.run_all_regions()
        SmartGridIntelligenceAgent.print_summary_table(intelligence)
        
        # Save to outputs/grid_intelligence_<date>.json for auditing
        output_path = OUTPUTS_DIR / f"grid_intelligence_{date.today().isoformat()}.json"
        output_path.write_text(json.dumps(intelligence, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return intelligence
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Intelligence generation failed: {str(exc)}")


# ═════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    """Health check."""
    return {"status": "ok", "date": date.today().isoformat()}


@app.post("/api/generate-intelligence")
def generate_intelligence():
    """
    Generate intelligence for all nodes.
    Runs the full LLM pipeline (news fetch → analysis → multipliers).
    Overwrites previous cache.
    """
    _ensure_cache_dir()
    intelligence = _generate_intelligence()
    return {
        "status": "ok",
        "message": "Intelligence pipeline completed",
        "nodes_generated": list(intelligence.keys()),
        "date": date.today().isoformat(),
    }


@app.get("/api/intelligence")
def intelligence():
    """
    Return complete LLM intelligence context for all nodes.
    Includes: grid_multipliers, detected_events, impact_narrative,
    extracted_signals, weather, confidence, risk flags, hoard flags.
    """
    _ensure_cache_dir()
    node_cache = _load_node_cache()

    # If empty, try auto-generation once
    if not node_cache:
        try:
            _generate_intelligence()
            node_cache = _load_node_cache()
        except Exception:
            pass

    # If still empty, return fallback that still shows structure
    if not node_cache:
        return _build_fallback_intelligence()

    # Return cached data with all details
    result: Dict[str, Any] = {}
    for nid, data in node_cache.items():
        gm = data.get("grid_multipliers", {})
        result[nid] = {
            "node_id": nid,
            "city": data.get("city", nid),
            "generated_at": data.get("generated_at", ""),
            # All multipliers & flags
            "grid_multipliers": {
                "economic_demand_multiplier": gm.get("economic_demand_multiplier", 1.0),
                "generation_capacity_multiplier": gm.get("generation_capacity_multiplier", 1.0),
                "temperature_anomaly": gm.get("temperature_anomaly", 0.0),
                "demand_spike_risk": gm.get("demand_spike_risk", "UNKNOWN"),
                "supply_shortfall_risk": gm.get("supply_shortfall_risk", "UNKNOWN"),
                "pre_event_hoard": gm.get("pre_event_hoard", False),
                "seven_day_demand_forecast_mw_delta": gm.get("seven_day_demand_forecast_mw_delta", 0),
                "confidence": gm.get("confidence", 0.0),
                "key_driver": gm.get("key_driver", ""),
                "reasoning": gm.get("reasoning", ""),
            },
            "detected_events": data.get("detected_events", []),
            "impact_narrative": data.get("impact_narrative", ""),
            "extracted_signals": data.get("extracted_signals", ""),
            "weather": data.get("weather", {}),
        }
    return result


@app.get("/api/grid-status")
def grid_status():
    """
    Live node balances, battery SoC, transmission congestion.
    Also includes intelligence context (risk flags, temperature anomaly, hoard flag).
    """
    _ensure_cache_dir()
    env = GridEnvironment(seed=42)
    env.set_daily_demand()

    node_cache = _load_node_cache()

    # Apply multipliers from cache if present
    for nid, node in env.nodes.items():
        ctx = node_cache.get(nid, {})
        gm = ctx.get("grid_multipliers", {})
        gcm = float(gm.get("generation_capacity_multiplier", 1.0))
        node.generation_mw = node.generation_mw * gcm
        node.adjusted_demand_mw = node.demand_mw

    nodes = []
    for nid, node in env.nodes.items():
        ctx = node_cache.get(nid, {})
        gm = ctx.get("grid_multipliers", {})
        weather = ctx.get("weather", {})

        nodes.append({
            "id": nid,
            "name": node.name,
            "generation_mw": round(node.generation_mw, 1),
            "demand_mw": round(node.demand_mw, 1),
            "adjusted_demand_mw": round(node.adjusted_demand_mw, 1),
            "balance_mw": round(node.raw_balance_mw, 1),
            # ── Intelligence context ──
            "intelligence": {
                "demand_spike_risk": gm.get("demand_spike_risk", "UNKNOWN"),
                "supply_shortfall_risk": gm.get("supply_shortfall_risk", "UNKNOWN"),
                "temperature_anomaly": gm.get("temperature_anomaly", 0.0),
                "economic_demand_multiplier": gm.get("economic_demand_multiplier", 1.0),
                "generation_capacity_multiplier": gm.get("generation_capacity_multiplier", 1.0),
                "pre_event_hoard": gm.get("pre_event_hoard", False),
                "confidence": gm.get("confidence", 0.0),
                "detected_events": ctx.get("detected_events", []),
            },
            "weather": weather,
            # ── Battery ──
            "battery": {
                "soc": round(node.battery.soc, 4),
                "charge": round(node.battery.charge, 1),
                "capacity": node.battery.capacity,
            } if node.battery else None,
        })

    edges = []
    for (src, dst), edge in env.edges.items():
        edges.append({
            "src": src,
            "dst": dst,
            "distance_km": edge.distance_km,
            "flow_mw": round(edge.current_flow, 1),
            "capacity_mw": edge.capacity_mw,
            "congestion": round(edge.congestion, 4),
            "loss_pct": edge.loss_pct,
            "tariff": edge.tariff,
        })

    return {"nodes": nodes, "edges": edges, "date": date.today().isoformat()}


@app.get("/api/dispatch-log")
def dispatch_log():
    """
    Return dispatch records from most recent simulation.
    Includes: type (STANDARD/SYNDICATE/NEGOTIATED), parties, MW, price,
    path cost, carbon tax, DLR status, LLM safety approval.
    """
    records = _load_latest_dispatch_log()
    if not records:
        return []
    return records


@app.post("/api/run-simulation")
async def run_simulation_endpoint():
    """
    Stream simulation output (run_simulation.py) back to client.
    Generates dispatch records and updates outputs/simulation_result_<date>.json.
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
    """
    Return latest simulation_result JSON.
    Includes: dispatch records, grid summary, date.
    """
    import glob as glob_module
    files = sorted(OUTPUTS_DIR.glob("simulation_result_*.json"), reverse=True)
    if not files:
        return {"status": "no_result", "dispatches": [], "summary": {}, "date": None}
    return json.loads(files[0].read_text(encoding="utf-8"))
