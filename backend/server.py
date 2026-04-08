"""backend/server.py
=================
FastAPI entrypoint and server startup.

All legacy routes are loaded from routes.py, and v2 orchestration routes are
added here for direct frontend integration of engine.py/intelligence.py/simulator.py.

Run:
    uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path

from fastapi import Query

from routes import app
from routes import intelligence as legacy_intelligence
from routes import grid_status as legacy_grid_status
from routes import simulation_result as legacy_simulation_result
from routes import demand_forecast as legacy_demand_forecast
from engine import APrioriBrain
from intelligence import StochasticTrigger
from simulator import UnifiedOrchestrator

_BACKEND_DIR = Path(__file__).resolve().parent
_BRAIN = APrioriBrain(_BACKEND_DIR)
_TRIGGER = StochasticTrigger(_BACKEND_DIR)
_SIMULATOR = UnifiedOrchestrator(_BACKEND_DIR)


def _intelligence_cache_dir() -> Path:
    return _BACKEND_DIR / "outputs" / "intelligence_cache"


def _load_cache_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_cache(payload: dict) -> dict:
    rows = payload.get("events", []) or []
    multipliers = payload.get("state_multipliers", {}) or {}
    return {
        "day_index": payload.get("day_index"),
        "date": payload.get("date"),
        "generated_at": payload.get("generated_at"),
        "state_count": len(rows),
        "states": [r.get("state_id") for r in rows if r.get("state_id")],
        "avg_multiplier": round(sum(multipliers.values()) / len(multipliers), 4) if multipliers else 1.0,
        "scheduled_event_count": int(
            payload.get("scheduled_events_summary", {}).get("total_events", 0)
            if isinstance(payload.get("scheduled_events_summary", {}), dict)
            else 0
        ),
    }


def _get_cache_items() -> list[dict]:
    cache_dir = _intelligence_cache_dir()
    if not cache_dir.exists():
        return []
    items = []
    for fp in sorted(cache_dir.glob("day_*.json"), key=lambda p: p.name):
        try:
            payload = _load_cache_file(fp)
            summary = _summarize_cache(payload)
            summary["file"] = fp.name
            items.append(summary)
        except Exception:
            continue
    return items


@app.get("/api/v2/health")
def health_v2():
    return {
        "status": "ok",
        "service": "v2_orchestration",
    }


@app.post("/api/v2/master-schedule")
def generate_master_schedule(
    start_date: str = Query(default="2026-04-01"),
    days: int = Query(default=30, ge=1, le=90),
):
    schedule = _BRAIN.generate_30_day_forecast(start_date=start_date, days=days)
    saved = _BRAIN.save_master_schedule(schedule)
    return {
        "status": "success",
        "data": schedule,
        "saved_path": str(saved),
    }


@app.get("/api/v2/intelligence/{day_index}")
def get_daily_intelligence(
    day_index: int,
    start_date: str = Query(default="2026-04-01"),
    force_refresh: bool = Query(default=False),
):
    if day_index < 0:
        return {"status": "error", "message": "day_index must be >= 0"}

    cfg = _BRAIN._load_grid_config()  # intentional internal reuse for consistency
    state_ids = list(cfg.get("nodes", {}).keys())
    date_str = (datetime.fromisoformat(start_date) + timedelta(days=day_index)).strftime("%Y-%m-%d")

    report = _TRIGGER.generate_daily_report(
        day_index=day_index,
        date_str=date_str,
        state_ids=state_ids,
        force_refresh=force_refresh,
    )
    return {
        "status": "success",
        "data": report,
    }


@app.post("/api/v2/simulate")
def run_unified_simulator(
    start_date: str = Query(default="2026-04-01"),
    days: int = Query(default=30, ge=1, le=90),
):
    result = _SIMULATOR.run(start_date=start_date, days=days)
    return {
        "status": "success",
        "data": result,
    }


# ---------------------------------------------------------------------------
# Feature 1: Agentic Negotiation Dialogue Log
# ---------------------------------------------------------------------------

@app.get("/api/v2/dialogue-log")
def get_dialogue_log(
    limit: int = Query(default=50, ge=1, le=500),
    day_index: int = Query(default=-1, description="Filter by day (-1 = all days)"),
):
    """
    Return the full agentic negotiation dialogue log.

    Each entry is a 3-turn JSON chat (Prosumer → Syndicate → Orchestrator)
    justifying a power trade. The frontend can animate this at 500ms per turn.
    """
    log = list(_SIMULATOR.waterfall.dialogue_log)
    if day_index >= 0:
        log = [e for e in log if e.get("day_index") == day_index]
    return {
        "status": "success",
        "total_entries": len(log),
        "entries": log[-limit:],   # most recent first
    }


# ---------------------------------------------------------------------------
# Feature 3: Grid Frequency Status
# ---------------------------------------------------------------------------

@app.get("/api/v2/frequency-status")
def get_frequency_status():
    """
    Return current grid frequency, Lifeboat trigger threshold,
    and full frequency event log.
    """
    monitor = _SIMULATOR.waterfall._freq_monitor
    return {
        "status": "success",
        "summary": monitor.get_status_summary(),
        "event_log": monitor.get_log(),
    }


@app.get("/api/v2/pipeline-bundle")
def get_pipeline_bundle(limit: int = Query(default=25, ge=1, le=200)):
    """
    Single integration payload for frontend pipeline route.
    Bundles legacy pipeline data with v2 dialogue/frequency outputs.
    """
    dialogue = get_dialogue_log(limit=limit, day_index=-1)
    frequency = get_frequency_status()
    return {
        "status": "success",
        "data": {
            "intelligence": legacy_intelligence(),
            "grid_status": legacy_grid_status(),
            "simulation_result": legacy_simulation_result(),
            "forecast": legacy_demand_forecast(),
            "dialogue_log": dialogue,
            "frequency_status": frequency,
            "intelligence_cache": {
                "items": _get_cache_items(),
            },
        },
    }


@app.get("/api/v2/intelligence-cache")
def get_intelligence_cache():
    """
    Return all available daily intelligence cache summaries.
    Includes previous days if present in outputs/intelligence_cache/day_*.json.
    """
    items = _get_cache_items()
    return {
        "status": "success",
        "total_days": len(items),
        "items": items,
    }


@app.get("/api/v2/intelligence-cache/{day_index}")
def get_intelligence_cache_day(day_index: int):
    """
    Return full intelligence cache payload for a specific day index.
    """
    cache_path = _intelligence_cache_dir() / f"day_{day_index:03d}.json"
    if not cache_path.exists():
        return {
            "status": "error",
            "message": f"Cache not found for day_index={day_index}",
        }
    payload = _load_cache_file(cache_path)
    return {
        "status": "success",
        "data": payload,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
