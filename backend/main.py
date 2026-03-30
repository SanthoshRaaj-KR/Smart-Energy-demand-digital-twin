"""Top-level orchestrator and orchestration workflow for the Smart Grid backend."""

from datetime import date
import json
from pathlib import Path

from src.agents.intelligence_agent.orchestrator import SmartGridIntelligenceAgent

BACKEND_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BACKEND_DIR / "outputs"


def generate_intelligence() -> dict:
    agent = SmartGridIntelligenceAgent()
    intelligence = agent.run_all_regions()
    SmartGridIntelligenceAgent.print_summary_table(intelligence)

    output_path = OUTPUTS_DIR / f"grid_intelligence_{date.today().isoformat()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(intelligence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[main] Intelligence JSON -> {output_path}")
    return intelligence


def run_simulation_step():
    from run_simulation import run_simulation

    print("[main] Starting simulation pipeline (run_simulation.py)")
    run_simulation()
    print("[main] Simulation completed")


def validate_routes():
    print("[main] Validating API route handlers (in-process calls)")
    try:
        import server
        grid = server.grid_status()
        intel = server.intelligence()
        dispatch = server.dispatch_log()
        sim = server.simulation_result()

        print(f"[main] /api/grid-status: {len(grid.get('nodes', []))} nodes, {len(grid.get('edges', []))} edges")
        print(f"[main] /api/intelligence: {len(intel)} nodes")
        print(f"[main] /api/dispatch-log: {len(dispatch)} records")
        print(f"[main] /api/simulation-result: {sim.get('date', 'n/a')} ({len(sim.get('dispatches', []))} dispatch picks)")
        return {
            "grid_status": grid,
            "intelligence": intel,
            "dispatch_log": dispatch,
            "simulation_result": sim,
        }
    except Exception as exc:
        print(f"[main] Could not call route functions in-process: {exc}")
        print("[main] Ensure the FastAPI server is running for API endpoint checks.")
        return {}


def main() -> None:
    print("[main] Workflow start: generate intelligence -> run simulation -> validate endpoints")
    intelligence = generate_intelligence()
    run_simulation_step()
    route_check = validate_routes()

    print("[main] Workflow complete")
    print(f"[main] Intelligence nodes: {len(intelligence)}")
    print(f"[main] Route checks result keys: {list(route_check.keys())}")


if __name__ == "__main__":
    main()
