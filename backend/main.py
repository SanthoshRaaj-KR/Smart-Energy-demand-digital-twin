"""Top-level orchestrator and orchestration workflow for the Smart Grid backend."""

from datetime import date
import json
from pathlib import Path
import csv

from src.agents.intelligence_agent.orchestrator import SmartGridIntelligenceAgent
from src.orchestration.engine import OrchestrationEngine

BACKEND_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BACKEND_DIR / "outputs"


def generate_baseline_schedule() -> dict:
    """
    STAGE 1: Generate 30-day baseline schedule before simulation.
    
    This runs the A Priori Planner (ForwardMarketPlanner) to create a 
    baseline schedule with LLM sleep/wake flags, enabling ~70% cost reduction.
    """
    from src.agents.intelligence_agent.forward_market_planner import ForwardMarketPlanner
    from src.agents.fusion_agent.inference import predict_all_regions, load_artefacts
    import json as json_lib
    from pathlib import Path as PathLib
    
    print("\n" + "=" * 70)
    print("STAGE 1: A PRIORI PLANNER - Generating 30-day baseline schedule")
    print("=" * 70)
    
    # Load grid config
    grid_config_path = BACKEND_DIR / "config" / "grid_config.json"
    grid_config = json_lib.loads(grid_config_path.read_text(encoding="utf-8"))
    
    base_generation = {
        node_id: node_data["generation_mw"]
        for node_id, node_data in grid_config["nodes"].items()
    }
    
    # Get 30-day LightGBM predictions (use 7-day model repeated)
    print("[main] Loading LightGBM predictions...")
    try:
        load_artefacts()
        predictions_30d = {}
        
        # For each state, run predictions
        for state_id in base_generation.keys():
            # Get 7-day predictions and extend to 30
            preds_7day = predict_all_regions().get(state_id, {})
            pred_values = preds_7day.get("predicted_mw", [])
            
            # Extend to 30 days by repeating pattern
            if pred_values:
                extended = pred_values * 5  # 7*5 = 35 days, trim to 30
                predictions_30d[state_id] = {"predicted_mw": extended[:30]}
            else:
                # Fallback: use base generation as demand estimate
                predictions_30d[state_id] = {"predicted_mw": [base_generation[state_id]] * 30}
        
    except Exception as e:
        print(f"[main] Warning: Could not load LightGBM predictions: {e}")
        print("[main] Using base generation as fallback")
        predictions_30d = {
            state_id: {"predicted_mw": [gen_mw] * 30}
            for state_id, gen_mw in base_generation.items()
        }
    
    # Run planner
    planner = ForwardMarketPlanner()
    baseline = planner.compute_baseline(
        predictions_30d=predictions_30d,
        base_generation=base_generation,
        simulation_days=30
    )
    
    # Export to JSON with LLM flags
    baseline_json = planner.export_baseline_schedule_json(baseline, llm_threshold_mw=50.0)
    
    # Save to file
    output_path = OUTPUTS_DIR / f"baseline_schedule_{date.today().isoformat()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(baseline_json, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Print summary
    print(f"[main] Baseline schedule -> {output_path}")
    print(f"[main] Total days: {baseline_json['days']}")
    print(f"[main] LLM wake days: {baseline_json['llm_wake_days']}/{baseline_json['days']} ({100 - baseline_json['cost_reduction_pct']:.1f}%)")
    print(f"[main] LLM sleep days: {baseline_json['llm_sleep_days']}/{baseline_json['days']} ({baseline_json['cost_reduction_pct']:.1f}%)")
    print(f"[main] 💰 Projected cost reduction: {baseline_json['cost_reduction_pct']:.1f}%")
    print("=" * 70 + "\n")
    
    return baseline_json


def generate_intelligence() -> dict:
    """
    STAGE 2: Generate daily intelligence (anomaly detection and Delta calculation).
    
    Creates Delta JSON file ONLY if anomalies detected (LLMs wake up).
    If no anomalies, LLMs stay asleep and use baseline schedule.
    """
    from src.agents.intelligence_agent.orchestrator import IntelligenceOrchestrator
    
    print("\n" + "=" * 70)
    print("STAGE 2: INTELLIGENCE EXTRACTION - Daily anomaly detection")
    print("=" * 70)
    
    agent = SmartGridIntelligenceAgent()
    intelligence = agent.run_all_regions()
    SmartGridIntelligenceAgent.print_summary_table(intelligence)
    
    # Check if any state has anomalies (should wake orchestrator)
    any_wake = any(
        data.get("deviation_result", {}).get("should_wake_orchestrator", False)
        for data in intelligence.values()
    )
    
    if any_wake:
        # Export Delta JSON (only on anomaly days)
        delta = agent.export_delta_json(day_index=0, output_dir=OUTPUTS_DIR)
        print(f"[main] 🚨 ANOMALY DETECTED - Delta MW: {delta.get('anomaly_delta_mw', 0):+.0f}")
        print(f"[main] ⚡ LLM Agents: AWAKE - Running waterfall resolution")
    else:
        print(f"[main] ✅ No anomalies - LLM Agents: DORMANT")
        print(f"[main] 💤 Using baseline schedule (no Delta JSON created)")

    output_path = OUTPUTS_DIR / f"grid_intelligence_{date.today().isoformat()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(intelligence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[main] Intelligence JSON -> {output_path}")
    print("=" * 70 + "\n")
    
    return intelligence


def run_simulation_step():
    from run_simulation import run_simulation

    print("[main] Starting simulation pipeline (run_simulation.py)")
    run_simulation()
    print("[main] Simulation completed")


def execute_waterfall_demo(day_index: int = 0, date_str: str = "") -> dict:
    """
    Execute the 4-step waterfall with XAI Phase Trace export.
    
    This demonstrates the CORE WORKFLOW:
    1. Temporal (Battery) → 2. Economic (DR) → 3. Spatial (BFS) → 4. Fallback
    
    Returns a dict with waterfall result and XAI trace path.
    """
    from datetime import datetime, timedelta
    from src.agents.routing_agent.unified_routing_orchestrator import UnifiedRoutingOrchestrator
    
    print("\n" + "=" * 70)
    print("STAGE 3: WATERFALL ORCHESTRATOR EXECUTION")
    print("=" * 70)
    
    # Initialize orchestrator
    orchestrator = UnifiedRoutingOrchestrator()
    
    # Date setup
    if not date_str:
        base_date = datetime(2025, 1, 1)
        sim_date = base_date + timedelta(days=day_index)
        date_str = sim_date.strftime("%Y-%m-%d")
    
    # Sample deficit scenario (simulating a heatwave in UP)
    deficit_states_mw = {
        "UP": 180.0,      # Uttar Pradesh has 180 MW deficit
        "Bihar": 45.0,    # Bihar has 45 MW deficit
    }
    
    surplus_states_mw = {
        "WB": 120.0,      # West Bengal has surplus
        "Karnataka": 80.0, # Karnataka has surplus
    }
    
    # Battery state-of-charge (50 MW each)
    battery_soc = {
        "UP": 50.0,
        "Bihar": 30.0,
        "WB": 40.0,
        "Karnataka": 60.0,
    }
    
    battery_capacity = {
        "UP": 100.0,
        "Bihar": 100.0,
        "WB": 100.0,
        "Karnataka": 100.0,
    }
    
    # Transmission edge capacities (based on grid topology)
    daily_edge_capacities_mw = {
        ("WB", "Bihar"): 100.0,
        ("Bihar", "UP"): 80.0,
        ("Bihar", "WB"): 100.0,
        ("UP", "Bihar"): 80.0,
        ("Karnataka", "WB"): 70.0,
        ("WB", "Karnataka"): 70.0,
    }
    
    total_grid_capacity_mw = 2000.0  # National grid capacity
    
    # Execute waterfall
    waterfall_result = orchestrator.execute_waterfall(
        deficit_states_mw=deficit_states_mw,
        surplus_states_mw=surplus_states_mw,
        battery_soc=battery_soc,
        battery_capacity=battery_capacity,
        daily_edge_capacities_mw=daily_edge_capacities_mw,
        total_grid_capacity_mw=total_grid_capacity_mw,
        dr_clearing_price=6.0,
        day_index=day_index,
        date_str=date_str,
    )
    
    # Export XAI Phase Trace
    xai_trace_path = orchestrator.export_xai_phase_trace(
        waterfall_result=waterfall_result,
        day_index=day_index,
        date_str=date_str,
        output_dir="outputs",
    )
    
    return {
        "steps_executed": len(waterfall_result.steps_executed),
        "total_resolved_mw": waterfall_result.total_resolved_mw,
        "load_shedding_mw": sum(waterfall_result.load_shedding_mw.values()),
        "memory_warning": waterfall_result.memory_warning,
        "xai_trace_path": xai_trace_path,
        "waterfall_complete": waterfall_result.waterfall_complete,
    }


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


def demo_lifeboat_protocol(day_index: int = 0, date_str: str = "2025-01-01") -> dict:
    """
    Demonstrate the Lifeboat Protocol (Patent Feature #2).
    
    Simulates a scenario where one state is in severe crisis and
    importing power would destabilize the entire grid.
    """
    from src.agents.routing_agent.lifeboat_protocol import LifeboatProtocol, GridState
    
    print("\n" + "=" * 70)
    print("PATENT FEATURE #2: LIFEBOAT PROTOCOL")
    print("Autonomous Topology Severance via Capacity-Constrained Graph Partitioning")
    print("=" * 70)
    
    # Create crisis scenario: UP has massive deficit
    grid = GridState(
        states=["UP", "Bihar", "WB", "Karnataka"],
        edges={
            ("WB", "Bihar"): 100.0,
            ("Bihar", "UP"): 80.0,
            ("Bihar", "WB"): 100.0,
            ("UP", "Bihar"): 80.0,
            ("Karnataka", "WB"): 70.0,
            ("WB", "Karnataka"): 70.0,
        },
        deficits={
            "UP": 350.0,  # Massive crisis in UP
            "Bihar": 50.0,
        },
        surpluses={
            "WB": 80.0,
            "Karnataka": 60.0,
        },
        total_capacity_mw=2000.0,
    )
    
    protocol = LifeboatProtocol()
    decision = protocol.evaluate(grid, day_index=day_index)
    
    # Export decision
    if decision.should_island:
        protocol.export_decision_json(decision, day_index, date_str)
    
    return {
        "should_island": decision.should_island,
        "sacrificed": decision.sacrificed_states,
        "protected": decision.protected_states,
        "frequency_before": decision.frequency_before_hz,
        "frequency_after": decision.frequency_after_island_hz,
    }


def demo_dr_bounty_auction(deficits: dict = None, date_str: str = "2025-01-01") -> dict:
    """
    Demonstrate DR Bounty Micro-Auctions (Feature #4).
    
    Runs a reverse auction where prosumers bid to curtail load.
    """
    from src.agents.routing_agent.dr_bounty_auction import DRBountyAuction
    
    print("\n" + "=" * 70)
    print("FEATURE #4: DR BOUNTY MICRO-AUCTIONS")
    print("Game-Theoretic Demand Response via Reverse Second-Price Auctions")
    print("=" * 70)
    
    if deficits is None:
        deficits = {
            "UP": 120.0,
            "Bihar": 45.0,
        }
    
    auction = DRBountyAuction()
    round_result = auction.run_auction_round(
        deficits_by_state=deficits,
        round_id=f"round_{date_str}",
        timestamp=date_str,
    )
    
    # Export results
    auction.export_auction_results(round_result)
    
    return {
        "total_resolved_mw": round_result.total_deficit_resolved_mw,
        "total_cost_inr": round_result.total_cost_inr,
        "avg_clearing_price": round_result.average_clearing_price_inr,
        "states_auctioned": list(round_result.state_results.keys()),
    }


def demo_parameter_autopsy(month_str: str = "2025-01") -> dict:
    """
    Demonstrate LLM Parameter Autopsy (Patent Feature #1).
    
    Runs end-of-month analysis and generates hyperparameter recommendations.
    """
    from src.agents.fusion_agent.llm_parameter_autopsy import LLMParameterAutopsy
    
    print("\n" + "=" * 70)
    print("PATENT FEATURE #1: LLM PARAMETER AUTOPSY")
    print("Agentic Recursive Hyperparameter Optimization (No Neural Networks)")
    print("=" * 70)
    
    autopsy = LLMParameterAutopsy()
    
    # Simulate a month of data with some failures
    daily_summaries = [
        {"load_shedding_mw": 0, "dr_resolved_mw": 30, "total_deficit_mw": 100} for _ in range(20)
    ] + [
        {"load_shedding_mw": 45, "dr_resolved_mw": 10, "total_deficit_mw": 150} for _ in range(5)
    ] + [
        {"load_shedding_mw": 80, "dr_resolved_mw": 5, "total_deficit_mw": 200} for _ in range(5)
    ]
    
    # Sample memory warnings
    memory_warnings = [
        "THERMAL_BOTTLENECK: Bihar-UP line at 95% capacity",
        "BATTERY_DEPLETED: UP battery SOC at 5 MW",
        "THERMAL_BOTTLENECK: WB-Bihar edge congested",
    ]
    
    # Run autopsy
    report = autopsy.analyze_month(
        month_str=month_str,
        daily_summaries=daily_summaries,
        xai_traces=[],  # Simplified for demo
        memory_warnings=memory_warnings,
    )
    
    # Export report
    autopsy.export_autopsy_json(report)
    
    return {
        "month": report.month,
        "failure_rate_pct": report.failure_rate_pct,
        "patterns_detected": len(report.detected_patterns),
        "param_changes_recommended": len(report.recommended_changes),
        "json_path": report.json_output_path,
    }


def main() -> None:
    """
    4-STAGE WORKFLOW + 3 PATENT FEATURES:
    
    Stages:
    1. A Priori Planner: Generate 30-day baseline schedule
    2. Intelligence: Daily anomaly detection  
    3. Routing: Waterfall orchestration (Battery→DR→BFS→Fallback)
    4. XAI/Memory: Phase Trace export and memory learning
    
    Patent Features:
    - Lifeboat Protocol: Autonomous Graph-Cut Islanding
    - DR Bounty Auctions: Game-Theoretic Micro-Auctions
    - LLM Parameter Autopsy: Self-Healing Hyperparameters
    """
    print("\n" + "🔌" * 35)
    print(" " * 15 + "SMART GRID SIMULATION")
    print(" " * 10 + "Multi-Agent Workflow + Patent Features")
    print("🔌" * 35 + "\n")
    
    # STAGE 1: A Priori Planning
    baseline = generate_baseline_schedule()
    baseline_day = (baseline.get("schedule") or [{}])[0]
    
    # STAGE 2: Intelligence (anomaly detection)
    print("\nSTAGE 2: Intelligence extraction...")
    intelligence = generate_intelligence()
    any_wake = any(
        data.get("deviation_result", {}).get("should_wake_orchestrator", False)
        for data in intelligence.values()
    )

    engine = OrchestrationEngine()
    day_summary = engine.evaluate_day(
        day_index=0,
        baseline_day=baseline_day,
        delta_event={"anomaly": True} if any_wake else None,
    )
    append_cost_savings(
        day_index=0,
        llm_agents_enabled=day_summary.llm_agents_enabled,
        anomaly_detected=day_summary.anomaly_detected,
        max_state_imbalance_mw=day_summary.max_state_imbalance_mw,
        baseline_cost=day_summary.estimated_baseline_cost,
        llm_cost=day_summary.estimated_llm_cost,
    )
    
    # STAGE 3: Waterfall Orchestration
    waterfall = execute_waterfall_demo(day_index=0, date_str="2025-01-01")
    
    # PATENT FEATURE #2: Lifeboat Protocol
    lifeboat = demo_lifeboat_protocol(day_index=0, date_str="2025-01-01")
    
    # FEATURE #4: DR Bounty Auctions
    dr_auction = demo_dr_bounty_auction(date_str="2025-01-01")
    
    # PATENT FEATURE #1: LLM Parameter Autopsy
    autopsy = demo_parameter_autopsy(month_str="2025-01")
    
    # STAGE 4: Run full simulation (includes XAI/Memory)
    print("\nSTAGE 4: Running full simulation...")
    run_simulation_step()
    route_check = validate_routes()

    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE ✓")
    print("=" * 70)
    print(f"\n📊 STAGE RESULTS:")
    print(f"  STAGE 1 - Baseline: {baseline['days']} days, {baseline['cost_reduction_pct']:.1f}% LLM cost reduction")
    print(f"  STAGE 2 - Intelligence: {len(intelligence)} state analyses")
    print(f"  STAGE 3 - Waterfall: {waterfall['total_resolved_mw']:.0f} MW resolved, {waterfall['load_shedding_mw']:.0f} MW shed")
    print(f"  STAGE 4 - XAI Trace: {waterfall['xai_trace_path']}")
    
    print(f"\n🏆 PATENT FEATURES:")
    print(f"  [P1] LLM Autopsy: {autopsy['patterns_detected']} patterns, {autopsy['param_changes_recommended']} recommendations")
    print(f"  [P2] Lifeboat: Island={'YES' if lifeboat['should_island'] else 'NO'}, Protected={lifeboat['protected']}")
    print(f"  [F4] DR Auction: {dr_auction['total_resolved_mw']:.0f} MW @ ₹{dr_auction['avg_clearing_price']:.2f}/MW")
    
    print(f"\n📁 OUTPUT FILES:")
    print(f"  - outputs/baseline_schedule_*.json")
    print(f"  - outputs/xai_phase_trace_*.json")
    print(f"  - outputs/lifeboat_decision_*.json")
    print(f"  - outputs/dr_auction_*.json")
    print(f"  - outputs/parameter_autopsy_*.json")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
def append_cost_savings(
    day_index: int,
    llm_agents_enabled: bool,
    anomaly_detected: bool,
    max_state_imbalance_mw: float,
    baseline_cost: float,
    llm_cost: float,
) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUTS_DIR / "api_cost_savings.csv"
    write_header = not csv_path.exists()
    savings = llm_cost - baseline_cost
    savings_pct = (savings / llm_cost * 100.0) if llm_cost > 0 else 0.0

    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "day_index",
                "llm_agents_enabled",
                "anomaly_detected",
                "max_state_imbalance_mw",
                "estimated_baseline_cost",
                "estimated_llm_cost",
                "estimated_savings",
                "estimated_savings_pct",
            ],
        )
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "date": date.today().isoformat(),
                "day_index": day_index,
                "llm_agents_enabled": llm_agents_enabled,
                "anomaly_detected": anomaly_detected,
                "max_state_imbalance_mw": round(max_state_imbalance_mw, 2),
                "estimated_baseline_cost": round(baseline_cost, 4),
                "estimated_llm_cost": round(llm_cost, 4),
                "estimated_savings": round(savings, 4),
                "estimated_savings_pct": round(savings_pct, 2),
            }
        )
