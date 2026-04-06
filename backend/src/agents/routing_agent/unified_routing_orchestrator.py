"""
unified_routing_orchestrator.py
===============================
Unified Routing Orchestrator with Short-Term Working Memory (STWM).

Implements a pure Python Sliding Window Context Buffer that enables grid agents
to learn from recent congestion and failures WITHOUT using Vector DBs, Embeddings,
or formal RAG frameworks.

Memory Pipeline:
- Buffer: self.grid_short_term_memory (max 3 items = 72-hour sliding window)
- Write Loop: End-of-day evaluation after load shedding/fallback completion
- Read Loop: Memory injection into spatial routing/negotiation prompts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .phase6_negotiation_agent import Phase6NegotiationAgent, NegotiationOutput
from .phase7_syndicate_agent import Phase7SyndicateAgent, Phase7ExecutionResult
from ..shared.models import ProposedTrade


@dataclass
class DailyMemoryContext:
    """Container for daily grid state used in memory evaluation."""
    day_index: int
    date_str: str
    load_shedding_mw: Dict[str, float]
    observed_bottlenecks: List[str]
    executed_trades: List[ProposedTrade]
    remaining_deficit_mw: Dict[str, float]
    edge_capacities_at_end: Dict[Tuple[str, str], float]
    frequency_triggered_emergency: bool


class UnifiedRoutingOrchestrator:
    """
    Unified orchestrator that wraps Phase 6 (Negotiation) and Phase 7 (Syndicate)
    agents with a short-term working memory system.
    
    The memory system:
    - Stores max 3 warning strings (72-hour sliding window)
    - Writes at end of each day if failures/congestion detected
    - Reads during spatial routing to inject context into negotiation prompts
    """
    
    MEMORY_WINDOW_SIZE = 3  # 72-hour sliding window (3 days)
    
    def __init__(
        self,
        phase6_agent: Phase6NegotiationAgent | None = None,
        phase7_agent: Phase7SyndicateAgent | None = None,
    ) -> None:
        """Initialize the orchestrator with memory buffer and sub-agents."""
        # === ORCHESTRATOR STATE (The Buffer) ===
        # This list must never exceed 3 items (72-hour sliding window)
        self.grid_short_term_memory: List[str] = []
        
        # Sub-agents for Phase 6 and Phase 7
        self._phase6_agent = phase6_agent or Phase6NegotiationAgent()
        self._phase7_agent = phase7_agent or Phase7SyndicateAgent()
        
        # Internal tracking for bottleneck analysis
        self._last_day_bottlenecks: List[str] = []
        self._day_memory_log: List[Dict[str, Any]] = []
    
    # =========================================================================
    # READ LOOP: Memory Injection into Negotiation Prompts
    # =========================================================================
    
    def get_memory_context_block(self) -> str | None:
        """
        Generate the [RECENT GRID CONTEXT] block for LLM prompt injection.
        
        Returns:
            Formatted context string if memory exists, None otherwise.
        """
        if not self.grid_short_term_memory:
            return None
        
        joined_memory = "\n".join(self.grid_short_term_memory)
        context_block = f"""[RECENT GRID CONTEXT]:
{joined_memory}

INSTRUCTION: Factor these recent failures into your routing requests today. Do not attempt to route maximum capacity through corridors that recently failed or congested."""
        
        return context_block
    
    def execute_spatial_routing(
        self,
        deficit_states_mw: Dict[str, float],
        available_surplus_states_mw: Dict[str, float],
        daily_edge_capacities_mw: Dict[Tuple[str, str], float],
    ) -> NegotiationOutput:
        """
        Execute spatial routing with memory-augmented negotiation.
        
        This is the READ LOOP - memory is injected into the negotiation phase
        right before dispatching to the LLM/agent for trade proposals.
        
        Args:
            deficit_states_mw: States with power deficit
            available_surplus_states_mw: States with available surplus
            daily_edge_capacities_mw: Current transmission line capacities
            
        Returns:
            NegotiationOutput with proposed trades
        """
        # === READ LOOP: Inject memory into negotiation ===
        memory_context = self.get_memory_context_block()
        
        if memory_context:
            print(f"  [MEMORY READ] Injecting {len(self.grid_short_term_memory)} recent warnings into negotiation context")
            for i, warning in enumerate(self.grid_short_term_memory, 1):
                print(f"    [{i}] {warning[:80]}...")
        
        # Convert memory to warnings list for Phase 6 agent
        # The Phase 6 agent already supports memory_warnings parameter
        memory_warnings = list(self.grid_short_term_memory)
        
        # Execute Phase 6 negotiation with memory context
        negotiation_output = self._phase6_agent.propose_trades(
            deficit_states_mw=deficit_states_mw,
            available_surplus_states_mw=dict(available_surplus_states_mw),
            daily_edge_capacities_mw=daily_edge_capacities_mw,
            memory_warnings=memory_warnings,
        )
        
        return negotiation_output
    
    def execute_syndicate(
        self,
        proposed_trades: List[ProposedTrade],
        deficit_states_mw: Dict[str, float],
        surplus_states_mw: Dict[str, float],
        daily_edge_capacities_mw: Dict[Tuple[str, str], float],
        total_grid_capacity_mw: float,
    ) -> Phase7ExecutionResult:
        """
        Execute Phase 7 syndicate with trade execution and fallback shedding.
        
        Args:
            proposed_trades: Trades proposed by Phase 6 negotiation
            deficit_states_mw: States with deficit
            surplus_states_mw: States with surplus
            daily_edge_capacities_mw: Current edge capacities
            total_grid_capacity_mw: Total grid generation capacity
            
        Returns:
            Phase7ExecutionResult with execution details
        """
        result = self._phase7_agent.execute(
            proposed_trades=proposed_trades,
            deficit_states_mw=deficit_states_mw,
            surplus_states_mw=surplus_states_mw,
            daily_edge_capacities_mw=daily_edge_capacities_mw,
            total_grid_capacity_mw=total_grid_capacity_mw,
        )
        
        # Track bottlenecks for end-of-day evaluation
        self._last_day_bottlenecks = list(result.observed_bottlenecks)
        
        return result
    
    # =========================================================================
    # WRITE LOOP: End-of-Day Evaluation and Memory Update
    # =========================================================================
    
    def evaluate_and_write_memory(
        self,
        day_index: int,
        date_str: str,
        phase7_result: Phase7ExecutionResult,
        edge_capacities_at_start: Dict[Tuple[str, str], float],
    ) -> str | None:
        """
        THE WRITE LOOP - Evaluate grid performance and write memory log.
        
        Called at the end of each day after execute_fallback/Load Shedding is complete.
        
        Trigger Conditions:
        1. ANY state has Load_Shedding_MW > 0
        2. A spatial trade was bottlenecked by current_capacity edge limit
        
        Args:
            day_index: Current simulation day (0-indexed)
            date_str: Date string for the current day
            phase7_result: Result from Phase 7 execution
            edge_capacities_at_start: Edge capacities at start of day
            
        Returns:
            Generated warning string if conditions met, None otherwise
        """
        warning_string: str | None = None
        
        # === TRIGGER CONDITION 1: Load shedding occurred ===
        load_shedding_occurred = any(
            shed_mw > 0 for shed_mw in phase7_result.load_shedding_mw.values()
        )
        
        # === TRIGGER CONDITION 2: Bottlenecks detected ===
        bottlenecks_detected = len(phase7_result.observed_bottlenecks) > 0
        
        # Analyze which edges hit their thermal caps
        bottlenecked_corridors = self._identify_thermal_cap_corridors(
            observed_bottlenecks=phase7_result.observed_bottlenecks,
            final_edge_caps=phase7_result.final_edge_capacities_mw,
            initial_edge_caps=edge_capacities_at_start,
        )
        
        # === Generate warning string if conditions met ===
        if load_shedding_occurred or bottlenecks_detected:
            warning_string = self._construct_memory_warning(
                day_index=day_index,
                load_shedding_mw=phase7_result.load_shedding_mw,
                bottlenecked_corridors=bottlenecked_corridors,
                frequency_emergency=phase7_result.frequency_triggered_emergency,
            )
            
            if warning_string:
                # === STATE UPDATE: Append to memory ===
                self.grid_short_term_memory.append(warning_string)
                
                # === SLIDING WINDOW ENFORCEMENT ===
                if len(self.grid_short_term_memory) > self.MEMORY_WINDOW_SIZE:
                    evicted = self.grid_short_term_memory.pop(0)
                    print(f"  [MEMORY EVICT] Removed oldest memory: {evicted[:50]}...")
                
                # Console log showing the grid "learning"
                print(f"  [MEMORY WRITE] Grid learned: {warning_string}")
                
                # Track memory log for debugging
                self._day_memory_log.append({
                    "day_index": day_index,
                    "date": date_str,
                    "warning": warning_string,
                    "memory_size": len(self.grid_short_term_memory),
                })
        
        return warning_string
    
    def _identify_thermal_cap_corridors(
        self,
        observed_bottlenecks: List[str],
        final_edge_caps: Dict[Tuple[str, str], float],
        initial_edge_caps: Dict[Tuple[str, str], float],
    ) -> List[Tuple[str, str, float]]:
        """
        Identify corridors that hit their thermal capacity limits.
        
        Returns list of (seller, buyer, utilized_pct) tuples for bottlenecked edges.
        """
        thermal_caps: List[Tuple[str, str, float]] = []
        
        for bottleneck in observed_bottlenecks:
            # Parse "SELLER->BUYER" format
            if "->" not in bottleneck:
                continue
            parts = bottleneck.split("->")
            if len(parts) != 2:
                continue
            seller, buyer = parts[0].strip(), parts[1].strip()
            edge_key = (seller, buyer)
            
            initial_cap = initial_edge_caps.get(edge_key, 0.0)
            final_cap = final_edge_caps.get(edge_key, 0.0)
            
            if initial_cap > 0:
                utilized_pct = ((initial_cap - final_cap) / initial_cap) * 100.0
                if utilized_pct >= 90.0:  # Near or at thermal cap
                    thermal_caps.append((seller, buyer, utilized_pct))
            elif final_cap <= 0:  # Edge was fully exhausted
                thermal_caps.append((seller, buyer, 100.0))
        
        return thermal_caps
    
    def _construct_memory_warning(
        self,
        day_index: int,
        load_shedding_mw: Dict[str, float],
        bottlenecked_corridors: List[Tuple[str, str, float]],
        frequency_emergency: bool,
    ) -> str:
        """
        Construct a concise 1-sentence warning string for memory buffer.
        
        Format: "Day {N} Warning: {STATE} suffered {X} MW load shedding because 
                 the {A}-{B} transmission line hit its thermal cap. 
                 Avoid relying on this corridor tomorrow."
        """
        day_num = day_index + 1  # 1-indexed for human readability
        
        # Find the state with highest load shedding
        worst_shed_state = None
        worst_shed_mw = 0.0
        for state, shed in load_shedding_mw.items():
            if shed > worst_shed_mw:
                worst_shed_mw = shed
                worst_shed_state = state
        
        # Find the worst bottleneck
        worst_corridor = None
        if bottlenecked_corridors:
            bottlenecked_corridors.sort(key=lambda x: x[2], reverse=True)
            worst_corridor = bottlenecked_corridors[0]
        
        # Construct warning based on what happened
        if worst_shed_state and worst_corridor:
            seller, buyer, _ = worst_corridor
            warning = (
                f"Day {day_num} Warning: {worst_shed_state} suffered {worst_shed_mw:.0f} MW "
                f"load shedding because the {seller}-{buyer} transmission line hit its thermal cap. "
                f"Avoid relying on this corridor tomorrow."
            )
        elif worst_shed_state:
            warning = (
                f"Day {day_num} Warning: {worst_shed_state} suffered {worst_shed_mw:.0f} MW "
                f"load shedding due to insufficient transmission capacity. "
                f"Consider alternate import routes tomorrow."
            )
        elif worst_corridor:
            seller, buyer, util_pct = worst_corridor
            warning = (
                f"Day {day_num} Warning: The {seller}->{buyer} corridor was severely congested "
                f"({util_pct:.0f}% utilized). Route around this corridor if possible tomorrow."
            )
        elif frequency_emergency:
            warning = (
                f"Day {day_num} Warning: Grid frequency dropped below critical threshold, "
                f"triggering emergency shedding. Increase reserve margins tomorrow."
            )
        else:
            return ""  # No meaningful warning to generate
        
        return warning
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_memory_state(self) -> List[str]:
        """Return a copy of the current memory buffer."""
        return list(self.grid_short_term_memory)
    
    def get_memory_log(self) -> List[Dict[str, Any]]:
        """Return the full memory write log for debugging."""
        return list(self._day_memory_log)
    
    def clear_memory(self) -> None:
        """Clear the memory buffer (for testing/reset)."""
        self.grid_short_term_memory.clear()
        self._day_memory_log.clear()
        print("  [MEMORY CLEAR] Short-term memory buffer cleared")
    
    def inject_memory(self, warnings: List[str]) -> None:
        """
        Manually inject warnings into memory (for testing or initialization).
        
        Enforces sliding window constraint.
        """
        for warning in warnings:
            self.grid_short_term_memory.append(warning)
            if len(self.grid_short_term_memory) > self.MEMORY_WINDOW_SIZE:
                self.grid_short_term_memory.pop(0)
        print(f"  [MEMORY INJECT] Injected {len(warnings)} warnings, buffer size: {len(self.grid_short_term_memory)}")
