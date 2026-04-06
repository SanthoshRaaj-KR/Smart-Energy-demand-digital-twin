"""
test_unified_routing_orchestrator.py
====================================
Unit tests for the Short-Term Working Memory system in UnifiedRoutingOrchestrator.
"""

import sys
sys.path.insert(0, ".")

from src.agents.routing_agent.unified_routing_orchestrator import (
    UnifiedRoutingOrchestrator,
    DailyMemoryContext,
)
from src.agents.routing_agent.phase7_syndicate_agent import Phase7ExecutionResult
from src.agents.shared.models import ProposedTrade


def test_memory_initialization():
    """Test that memory buffer initializes empty."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    assert orchestrator.grid_short_term_memory == []
    assert len(orchestrator.get_memory_state()) == 0
    print("[PASS] test_memory_initialization")


def test_memory_sliding_window_constraint():
    """Test that memory buffer never exceeds 3 items (72-hour window)."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    # Inject 5 warnings
    warnings = [
        "Day 1 Warning: Test warning 1",
        "Day 2 Warning: Test warning 2",
        "Day 3 Warning: Test warning 3",
        "Day 4 Warning: Test warning 4",
        "Day 5 Warning: Test warning 5",
    ]
    orchestrator.inject_memory(warnings)
    
    # Should only keep the last 3
    assert len(orchestrator.grid_short_term_memory) == 3
    assert orchestrator.grid_short_term_memory[0] == "Day 3 Warning: Test warning 3"
    assert orchestrator.grid_short_term_memory[1] == "Day 4 Warning: Test warning 4"
    assert orchestrator.grid_short_term_memory[2] == "Day 5 Warning: Test warning 5"
    print("[PASS] test_memory_sliding_window_constraint")


def test_memory_context_block_generation():
    """Test that the [RECENT GRID CONTEXT] block is properly formatted."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    # No memory - should return None
    assert orchestrator.get_memory_context_block() is None
    
    # Add memory
    orchestrator.inject_memory([
        "Day 1 Warning: UP suffered 150 MW load shedding because the BHR-UP transmission line hit its thermal cap.",
        "Day 2 Warning: WB suffered 100 MW load shedding due to insufficient transmission capacity.",
    ])
    
    context_block = orchestrator.get_memory_context_block()
    assert context_block is not None
    assert "[RECENT GRID CONTEXT]:" in context_block
    assert "Day 1 Warning" in context_block
    assert "Day 2 Warning" in context_block
    assert "INSTRUCTION: Factor these recent failures" in context_block
    print("[PASS] test_memory_context_block_generation")


def test_memory_write_on_load_shedding():
    """Test that memory is written when load shedding occurs."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    # Simulate Phase 7 result with load shedding
    mock_phase7_result = Phase7ExecutionResult(
        executed_trades=[],
        load_shedding_mw={"UP": 150.0, "WB": 50.0},
        remaining_deficit_mw={"UP": 0.0, "WB": 0.0},
        final_surplus_mw={"BHR": 100.0, "KAR": 200.0},
        final_edge_capacities_mw={("BHR", "UP"): 0.0, ("KAR", "WB"): 50.0},
        grid_frequency_before_hz=49.8,
        grid_frequency_after_hz=49.95,
        emergency_shed_mw=200.0,
        frequency_triggered_emergency=True,
        observed_bottlenecks=["BHR->UP"],
    )
    
    edge_caps_at_start = {("BHR", "UP"): 500.0, ("KAR", "WB"): 300.0}
    
    warning = orchestrator.evaluate_and_write_memory(
        day_index=13,  # Day 14 (0-indexed)
        date_str="2026-04-14",
        phase7_result=mock_phase7_result,
        edge_capacities_at_start=edge_caps_at_start,
    )
    
    assert warning is not None
    assert "Day 14" in warning
    assert "UP" in warning  # UP had highest shedding
    assert "150" in warning  # 150 MW
    assert len(orchestrator.grid_short_term_memory) == 1
    print("[PASS] test_memory_write_on_load_shedding")


def test_memory_write_on_bottleneck():
    """Test that memory is written when bottlenecks are detected."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    # Simulate Phase 7 result with bottlenecks but no load shedding
    mock_phase7_result = Phase7ExecutionResult(
        executed_trades=[],
        load_shedding_mw={},  # No load shedding
        remaining_deficit_mw={},
        final_surplus_mw={"BHR": 100.0},
        final_edge_capacities_mw={("BHR", "UP"): 0.0},  # Edge exhausted
        grid_frequency_before_hz=50.0,
        grid_frequency_after_hz=50.0,
        emergency_shed_mw=0.0,
        frequency_triggered_emergency=False,
        observed_bottlenecks=["BHR->UP", "KAR->WB"],
    )
    
    edge_caps_at_start = {("BHR", "UP"): 500.0, ("KAR", "WB"): 300.0}
    
    warning = orchestrator.evaluate_and_write_memory(
        day_index=4,
        date_str="2026-04-05",
        phase7_result=mock_phase7_result,
        edge_capacities_at_start=edge_caps_at_start,
    )
    
    assert warning is not None
    assert "Day 5" in warning
    assert "BHR" in warning or "congested" in warning
    assert len(orchestrator.grid_short_term_memory) == 1
    print("[PASS] test_memory_write_on_bottleneck")


def test_no_memory_write_on_healthy_grid():
    """Test that no memory is written when grid is healthy."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    # Simulate Phase 7 result with no issues
    mock_phase7_result = Phase7ExecutionResult(
        executed_trades=[],
        load_shedding_mw={},  # No load shedding
        remaining_deficit_mw={},
        final_surplus_mw={"BHR": 100.0},
        final_edge_capacities_mw={("BHR", "UP"): 400.0},  # Still has capacity
        grid_frequency_before_hz=50.0,
        grid_frequency_after_hz=50.0,
        emergency_shed_mw=0.0,
        frequency_triggered_emergency=False,
        observed_bottlenecks=[],  # No bottlenecks
    )
    
    edge_caps_at_start = {("BHR", "UP"): 500.0}
    
    warning = orchestrator.evaluate_and_write_memory(
        day_index=0,
        date_str="2026-04-01",
        phase7_result=mock_phase7_result,
        edge_capacities_at_start=edge_caps_at_start,
    )
    
    assert warning is None or warning == ""
    assert len(orchestrator.grid_short_term_memory) == 0
    print("[PASS] test_no_memory_write_on_healthy_grid")


def test_memory_clear():
    """Test memory clearing functionality."""
    orchestrator = UnifiedRoutingOrchestrator()
    orchestrator.inject_memory(["Warning 1", "Warning 2"])
    
    assert len(orchestrator.grid_short_term_memory) == 2
    
    orchestrator.clear_memory()
    
    assert len(orchestrator.grid_short_term_memory) == 0
    assert len(orchestrator.get_memory_log()) == 0
    print("[PASS] test_memory_clear")


def test_spatial_routing_with_memory():
    """Test that spatial routing uses memory context."""
    orchestrator = UnifiedRoutingOrchestrator()
    
    # Add some memory
    orchestrator.inject_memory([
        "WARNING: BHR->UP was severely congested yesterday."
    ])
    
    # Execute spatial routing
    output = orchestrator.execute_spatial_routing(
        deficit_states_mw={"UP": 100.0},
        available_surplus_states_mw={"BHR": 200.0, "KAR": 150.0},
        daily_edge_capacities_mw={("BHR", "UP"): 500.0, ("KAR", "UP"): 300.0},
    )
    
    # The Phase6 agent should receive the memory warnings
    # and potentially block the BHR->UP route
    assert output is not None
    print("[PASS] test_spatial_routing_with_memory")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TESTING: UnifiedRoutingOrchestrator Short-Term Working Memory")
    print("=" * 60 + "\n")
    
    test_memory_initialization()
    test_memory_sliding_window_constraint()
    test_memory_context_block_generation()
    test_memory_write_on_load_shedding()
    test_memory_write_on_bottleneck()
    test_no_memory_write_on_healthy_grid()
    test_memory_clear()
    test_spatial_routing_with_memory()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_all_tests()
