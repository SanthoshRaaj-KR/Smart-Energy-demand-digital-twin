"""
backend/routes.py
=================
All FastAPI routes for the India Grid Digital Twin.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

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

OUTPUTS_DIR_CANDIDATES = [
    BACKEND_DIR / "outputs",
    REPO_ROOT / "outputs",  # legacy fallback
]
CACHE_DIR_CANDIDATES = [d / "context_cache" for d in OUTPUTS_DIR_CANDIDATES]
PRIMARY_OUTPUTS_DIR = OUTPUTS_DIR_CANDIDATES[0]
PRIMARY_CACHE_DIR = CACHE_DIR_CANDIDATES[0]


def _ensure_cache_dir() -> None:
    PRIMARY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PRIMARY_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_node_cache() -> Dict[str, Dict]:
    """Load node cache from existing files only; never regenerate here."""
    result: Dict[str, Dict] = {}
    today_iso = date.today().isoformat()

    # Prefer today's files from all known cache locations.
    for cache_dir in CACHE_DIR_CANDIDATES:
        if not cache_dir.exists():
            continue
        for fp in sorted(cache_dir.glob(f"node_*_{today_iso}.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                nid = data.get("node_id")
                if nid:
                    result[nid] = data
            except Exception:
                pass

    # Fallback: pick latest available per node from any cache folder.
    if not result:
        latest_by_node: Dict[str, Path] = {}
        for cache_dir in CACHE_DIR_CANDIDATES:
            if not cache_dir.exists():
                continue
            for fp in cache_dir.glob("node_*.json"):
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    nid = data.get("node_id")
                    if not nid:
                        continue
                    prev = latest_by_node.get(nid)
                    if prev is None or fp.stat().st_mtime > prev.stat().st_mtime:
                        latest_by_node[nid] = fp
                except Exception:
                    pass

        for nid, fp in latest_by_node.items():
            try:
                result[nid] = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                pass

    return result


def _latest_simulation_file() -> Path | None:
    files: List[Path] = []
    for outputs_dir in OUTPUTS_DIR_CANDIDATES:
        if outputs_dir.exists():
            files.extend(outputs_dir.glob("simulation_result_*.json"))
    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def _load_latest_dispatch_log() -> List[Dict]:
    sim_file = _latest_simulation_file()
    if not sim_file:
        return []
    try:
        return json.loads(sim_file.read_text(encoding="utf-8")).get("dispatches", [])
    except Exception:
        return []


def _build_fallback_intelligence() -> Dict[str, Dict[str, Any]]:
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
                "severity_level": 1,
            },
            "detected_events": [],
            "impact_narrative": "(No intelligence generated yet)",
            "extracted_signals": "No signals available.",
            "phase_trace": {
                "phase_7": {
                    "name": "Multiplier Synthesis",
                    "status": "fallback",
                    "before_multiplier": {
                        "economic_demand_multiplier": 1.0,
                        "generation_capacity_multiplier": 1.0,
                        "temperature_anomaly": 0.0,
                    },
                    "after_multiplier": {
                        "economic_demand_multiplier": 1.0,
                        "generation_capacity_multiplier": 1.0,
                        "temperature_anomaly": 0.0,
                    },
                    "flags": {
                        "pre_event_hoard": False,
                        "demand_spike_risk": "UNKNOWN",
                        "supply_shortfall_risk": "UNKNOWN",
                    },
                }
            },
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
    try:
        agent = SmartGridIntelligenceAgent()
        intelligence = agent.run_all_regions()
        SmartGridIntelligenceAgent.print_summary_table(intelligence)

        output_path = PRIMARY_OUTPUTS_DIR / f"grid_intelligence_{date.today().isoformat()}.json"
        output_path.write_text(json.dumps(intelligence, indent=2, ensure_ascii=False), encoding="utf-8")

        return intelligence
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Intelligence generation failed: {str(exc)}")


@app.get("/api/health")
def health():
    return {"status": "ok", "date": date.today().isoformat()}


@app.post("/api/generate-intelligence")
def generate_intelligence():
    """
    Explicit refresh endpoint.
    Only this route runs the intelligence pipeline.
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
    Return complete intelligence context from existing cache files only.
    Does NOT auto-generate new intelligence.
    """
    _ensure_cache_dir()
    node_cache = _load_node_cache()

    if not node_cache:
        return _build_fallback_intelligence()

    result: Dict[str, Any] = {}
    for nid, data in node_cache.items():
        gm = data.get("grid_multipliers", {})
        result[nid] = {
            "node_id": nid,
            "city": data.get("city", nid),
            "generated_at": data.get("generated_at", ""),
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
                "severity_level": gm.get("severity_level", 1),
            },
            "detected_events": data.get("detected_events", []),
            "impact_narrative": data.get("impact_narrative", ""),
            "extracted_signals": data.get("extracted_signals", ""),
            "weather": data.get("weather", {}),
            "city_intelligence": data.get("city_intelligence", {}),
            "phase_trace": data.get("phase_trace", {}),
        }
    return result


@app.get("/api/grid-status")
def grid_status():
    _ensure_cache_dir()
    env = GridEnvironment(seed=42)
    env.set_daily_demand()

    node_cache = _load_node_cache()

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
    records = _load_latest_dispatch_log()
    if not records:
        return []
    return records


@app.post("/api/run-simulation")
async def run_simulation_endpoint():
    sim_script = BACKEND_DIR / "run_simulation.py"
    if not sim_script.exists():
        raise HTTPException(status_code=404, detail="run_simulation.py not found")

    def stream_output():
        proc = subprocess.Popen(
            [sys.executable, str(sim_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(BACKEND_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                yield line
        finally:
            proc.stdout.close()
            exit_code = proc.wait()
            yield f"\n[DONE] Simulation exited with code {exit_code}\n"

    return StreamingResponse(stream_output(), media_type="text/plain")


@app.get("/api/simulation-result")
def simulation_result():
    sim_file = _latest_simulation_file()
    if not sim_file:
        return {"status": "no_result", "dispatches": [], "summary": {}, "date": None}
    return json.loads(sim_file.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# DEMAND FORECAST ENDPOINT - LightGBM 7-Day Predictions
# ---------------------------------------------------------------------------

@app.get("/api/demand-forecast")
def demand_forecast():
    """
    Returns 7-day demand forecasts from the trained LightGBM model.
    Uses cached intelligence data for weather inputs when available.
    """
    from datetime import timedelta
    from src.environment.grid_physics import GridEnvironment
    from src.agents.fusion_agent.inference import load_artefacts, predict_all_regions

    try:
        lgb_model, scaler_climate, scaler_lagroll = load_artefacts(
            model_path=str(BACKEND_DIR / "model" / "lightgbm_model.pkl"),
            scaler_climate_path=str(BACKEND_DIR / "model" / "utils" / "scaler_climate.pkl"),
            scaler_lagroll_path=str(BACKEND_DIR / "model" / "utils" / "scaler_lagroll.pkl"),
            meta_path=str(BACKEND_DIR / "model" / "utils" / "inference_meta.json"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load LightGBM model: {str(exc)}")

    env = GridEnvironment(seed=42)
    env.set_daily_demand()
    node_cache = _load_node_cache()

    inputs_by_region = {}
    for nid, node in env.nodes.items():
        ctx = node_cache.get(nid, {})
        weather = ctx.get("weather", {})
        forecast_days = weather.get("forecast_days", [])
        hourly = weather.get("hourly_forecast_7d", [])

        # Extract weather features from intelligence cache
        temps = [fd.get("max_c", 30.0) for fd in forecast_days[:7]] if forecast_days else [30.0] * 7
        if len(temps) < 7:
            temps.extend([temps[-1] if temps else 30.0] * (7 - len(temps)))

        # Use hourly data for solar if available
        solar_vals = []
        if hourly:
            for h in hourly[:7*24:24]:  # Sample daily
                solar_vals.append(h.get("clouds", 50) / 100 * 5)  # crude solar proxy
        if len(solar_vals) < 7:
            solar_vals = [2.5] * 7

        inputs_by_region[nid] = {
            "Date": [(date.today() - timedelta(days=7 - i)).isoformat() for i in range(7)],
            "State": [nid] * 7,
            "Actual_Drawl": [node.demand_mw if node.demand_mw else 5000.0] * 7,
            "om_temp_mean": temps[:7],
            "nasa_solar": solar_vals[:7],
            "om_dewpoint": [15.0] * 7,
            "om_wind_gusts": [20.0] * 7,
        }

    try:
        predictions = predict_all_regions(inputs_by_region, lgb_model, scaler_climate, scaler_lagroll)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(exc)}")

    # Enrich with metadata
    result = {}
    for nid, pred in predictions.items():
        ctx = node_cache.get(nid, {})
        gm = ctx.get("grid_multipliers", {})
        edm = float(gm.get("economic_demand_multiplier", 1.0))
        confidence = float(gm.get("confidence", 0.5))

        # Apply intelligence multiplier to predictions
        adjusted = [round(p * edm, 2) for p in pred.get("predicted_drawl", [])]

        result[nid] = {
            "dates": pred.get("dates", []),
            "predicted_mw": pred.get("predicted_drawl", []),
            "adjusted_mw": adjusted,  # After intelligence multiplier
            "economic_demand_multiplier": edm,
            "confidence": confidence,
            "key_driver": gm.get("key_driver", ""),
            "city": CITY_REGISTRY.get(nid, {}).get("name", nid),
        }

    return {
        "forecasts": result,
        "model": "lightgbm_7day_autoregressive",
        "generated_at": date.today().isoformat(),
        "feature_inputs": ["om_temp_mean", "nasa_solar", "om_dewpoint", "om_wind_gusts"],
    }


# ---------------------------------------------------------------------------
# 30-DAY EXTENDED FORECAST - Patent-Worthy Innovation
# ---------------------------------------------------------------------------

@app.get("/api/demand-forecast-30day")
def demand_forecast_30day():
    """
    Returns 30-day demand forecasts with confidence decay and uncertainty bands.
    
    Key innovations:
    - Days 1-7: High-confidence LightGBM predictions
    - Days 8-30: Extended forecast with exponential confidence decay
    - Uncertainty bands based on horizon and intelligence confidence
    - Weather extrapolation from 7-day to 30-day using trend damping
    
    This endpoint demonstrates the patent-worthy fusion of:
    - ML time-series forecasting (LightGBM)
    - LLM-based intelligence multipliers
    - Uncertainty quantification for critical infrastructure
    """
    from datetime import timedelta
    from src.environment.grid_physics import GridEnvironment
    from src.agents.fusion_agent.inference import load_artefacts
    from src.agents.fusion_agent.inference_30day import predict_30_days_all_regions

    try:
        lgb_model, scaler_climate, scaler_lagroll = load_artefacts(
            model_path=str(BACKEND_DIR / "model" / "lightgbm_model.pkl"),
            scaler_climate_path=str(BACKEND_DIR / "model" / "utils" / "scaler_climate.pkl"),
            scaler_lagroll_path=str(BACKEND_DIR / "model" / "utils" / "scaler_lagroll.pkl"),
            meta_path=str(BACKEND_DIR / "model" / "utils" / "inference_meta.json"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(exc)}")

    env = GridEnvironment(seed=42)
    env.set_daily_demand()
    node_cache = _load_node_cache()

    # Build inputs for all regions
    inputs_by_region = {}
    for nid, node in env.nodes.items():
        ctx = node_cache.get(nid, {})
        weather = ctx.get("weather", {})
        forecast_days = weather.get("forecast_days", [])

        # Extract weather features
        temps = [fd.get("max_c", 30.0) for fd in forecast_days[:7]] if forecast_days else [30.0] * 7
        while len(temps) < 7:
            temps.append(temps[-1] if temps else 30.0)

        inputs_by_region[nid] = {
            "Date": [(date.today() - timedelta(days=7 - i)).isoformat() for i in range(7)],
            "State": [nid] * 7,
            "Actual_Drawl": [node.demand_mw if node.demand_mw else 5000.0] * 7,
            "om_temp_mean": temps[:7],
            "nasa_solar": [2.5] * 7,
            "om_dewpoint": [15.0] * 7,
            "om_wind_gusts": [20.0] * 7,
        }

    # Build intelligence context
    intelligence_context = {}
    for nid, data in node_cache.items():
        intelligence_context[nid] = data

    try:
        predictions = predict_30_days_all_regions(
            inputs_by_region,
            lgb_model,
            scaler_climate,
            scaler_lagroll,
            intelligence_context=intelligence_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(exc)}")

    # Enrich with city names
    for nid, pred in predictions.items():
        pred["city"] = CITY_REGISTRY.get(nid, {}).get("name", nid)

    return {
        "forecasts": predictions,
        "model": "lightgbm_30day_extended",
        "generated_at": date.today().isoformat(),
        "methodology": {
            "high_confidence_days": 7,
            "extended_forecast_days": 23,
            "confidence_decay_rate": "5% per day",
            "uncertainty_model": "horizon-scaled with intelligence adjustment",
            "weather_extrapolation": "linear trend with damping toward seasonal mean",
        },
        "patent_claims": [
            "Autoregressive LightGBM with confidence decay modeling",
            "LLM intelligence multiplier integration for demand adjustment",
            "Uncertainty quantification combining ML error and NLP confidence",
            "Weather forecast extrapolation with seasonal reversion",
        ],
    }


# ---------------------------------------------------------------------------
# XAI AUDIT ENDPOINT - Phase-by-Phase Intelligence Breakdown
# ---------------------------------------------------------------------------

@app.get("/api/intelligence/{region_id}/audit")
def intelligence_audit(region_id: str):
    """
    Returns detailed phase-by-phase breakdown of intelligence generation.
    Enables XAI visualization of the full decision chain.
    """
    node_cache = _load_node_cache()
    ctx = node_cache.get(region_id)

    if not ctx:
        raise HTTPException(status_code=404, detail=f"No intelligence data for region {region_id}")

    phase_trace = ctx.get("phase_trace", {})
    gm = ctx.get("grid_multipliers", {})
    weather = ctx.get("weather", {})
    detected_events = ctx.get("detected_events", [])
    signals = ctx.get("extracted_signals", "")
    narrative = ctx.get("impact_narrative", "")
    city_intel = ctx.get("city_intelligence", {})

    return {
        "region_id": region_id,
        "city": ctx.get("city", region_id),
        "generated_at": ctx.get("generated_at", ""),
        "phases": {
            "phase_1_data_fetch": {
                "name": "Data Fetching",
                "description": "Raw weather data and news headlines collected",
                "status": "completed",
                "raw_headline_count": phase_trace.get("phase_1", {}).get("raw_headline_count", 0),
                "raw_headline_samples": phase_trace.get("phase_1", {}).get("raw_headline_samples", []),
                "weather_snapshot": {
                    "current_temp_c": weather.get("current_temp_c", 0),
                    "current_condition": weather.get("current_condition", "unknown"),
                    "week_max_c": weather.get("week_max_c", 0),
                    "week_total_rain_mm": weather.get("week_total_rain_mm", 0),
                },
                "phase_1_grid_events": phase_trace.get("phase_1", {}).get("phase_1_grid_events", []),
            },
            "phase_2_city_intel": {
                "name": "City Intelligence Profile",
                "description": "LLM-generated city profile with vulnerabilities and fuel sources",
                "status": "completed" if city_intel else "skipped",
                "llm_confidence": city_intel.get("llm_confidence", 0),
                "key_vulnerabilities": city_intel.get("key_vulnerabilities", []),
                "primary_fuel_sources": city_intel.get("primary_fuel_sources", []),
                "fuel_supply_routes": city_intel.get("fuel_supply_routes", []),
                "neighboring_exchange": city_intel.get("neighboring_exchange", []),
                "seasonal_demand_factors": city_intel.get("seasonal_demand_factors", []),
            },
            "phase_3_event_radar": {
                "name": "Event Detection",
                "description": "Grid-relevant events detected from news (mass gatherings, TV pickups, etc.)",
                "status": "completed",
                "event_count": len(detected_events),
                "events": detected_events,
            },
            "phase_4_headline_filter": {
                "name": "Headline Filtering",
                "description": "Noise removal - sports scores, gossip filtered out",
                "status": "completed",
                "input_count": phase_trace.get("phase_4", {}).get("input_count", 0),
                "output_count": phase_trace.get("phase_4", {}).get("output_count", 0),
                "kept_headlines_sample": phase_trace.get("phase_4", {}).get("kept_headlines_sample", []),
            },
            "phase_5_signal_extraction": {
                "name": "Infrastructure Signal Extraction",
                "description": "Map headlines to grid infrastructure signals (coal routes, plant trips)",
                "status": "completed" if signals else "no_signals",
                "extracted_signals": signals,
            },
            "phase_6_impact_narrative": {
                "name": "Impact Analysis",
                "description": "Chain-of-thought reasoning combining all inputs into 7-day outlook",
                "status": "completed" if narrative else "fallback",
                "narrative": narrative,
            },
            "phase_7_multiplier_synthesis": {
                "name": "Multiplier Synthesis",
                "description": "Convert narrative into numeric grid multipliers",
                "status": "completed",
                "final_multipliers": {
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
                    "severity_level": gm.get("severity_level", 1),
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# SIGNALS ENDPOINT - Extracted Infrastructure Signals
# ---------------------------------------------------------------------------

@app.get("/api/intelligence/{region_id}/signals")
def intelligence_signals(region_id: str):
    """
    Returns extracted infrastructure signals for a region.
    Shows how news headlines map to grid-relevant signals.
    """
    node_cache = _load_node_cache()
    ctx = node_cache.get(region_id)

    if not ctx:
        raise HTTPException(status_code=404, detail=f"No intelligence data for region {region_id}")

    signals_raw = ctx.get("extracted_signals", "")
    detected_events = ctx.get("detected_events", [])
    phase_trace = ctx.get("phase_trace", {})

    # Parse signal bullets into structured format
    signal_lines = [line.strip("- •").strip() for line in signals_raw.split("\n") if line.strip()]

    return {
        "region_id": region_id,
        "city": ctx.get("city", region_id),
        "generated_at": ctx.get("generated_at", ""),
        "raw_signals": signals_raw,
        "signal_bullets": signal_lines,
        "signal_count": len(signal_lines),
        "detected_events": detected_events,
        "input_headlines": phase_trace.get("phase_1", {}).get("raw_headline_samples", []),
        "filtered_headlines": phase_trace.get("phase_4", {}).get("kept_headlines_sample", []),
    }
