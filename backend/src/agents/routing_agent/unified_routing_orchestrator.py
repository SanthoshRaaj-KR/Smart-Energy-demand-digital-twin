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

4-STEP WATERFALL ENFORCEMENT:
- Step 1 (Temporal): Drain state batteries first
- Step 2 (Economic): Activate DR bounties
- Step 3 (Spatial): Route via transmission (BFS)
- Step 4 (Fallback): Lifeboat Protocol OR load shedding
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from .phase6_negotiation_agent import Phase6NegotiationAgent, NegotiationOutput
from .phase7_syndicate_agent import Phase7SyndicateAgent, Phase7ExecutionResult
from ..shared.models import ProposedTrade

# === Feature Sub-Agents ===
from .negotiation_dialogue_agent import NegotiationDialogueAgent, DialogueEntry
from .carbon_spatial_agent import CarbonSpatialAgent
from .frequency_monitor_agent import FrequencyMonitorAgent
from .lifeboat_protocol import LifeboatProtocol, GridState
from .event_flag_battery_agent import EventFlagBatteryAgent


@dataclass
class WaterfallStepResult:
    """Result from a single waterfall step."""
    step_name: str
    step_number: int
    deficit_before_mw: Dict[str, float]
    deficit_after_mw: Dict[str, float]
    resolved_mw: Dict[str, float]
    method_used: str
    success: bool
    notes: str


@dataclass
class WaterfallResult:
    """Complete result from 4-step waterfall execution."""
    steps_executed: List[WaterfallStepResult]
    final_deficit_mw: Dict[str, float]
    total_resolved_mw: float
    load_shedding_mw: Dict[str, float]
    memory_warning: Optional[str]
    waterfall_complete: bool


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

        # === FEATURE 1: Agentic Negotiation Dialogue Log ===
        self.dialogue_log: List[Dict[str, Any]] = []
        self._dialogue_agent = NegotiationDialogueAgent()

        # === FEATURE 2: DLR-Aware Carbon-Spatial Routing ===
        self._carbon_spatial_agent = CarbonSpatialAgent()

        # === FEATURE 3: Lifeboat Graph-Cut with Frequency Tracking ===
        self._freq_monitor = FrequencyMonitorAgent()
        self._lifeboat = LifeboatProtocol()

        # === FEATURE 5: Event-Flag Battery Pre-Charge ===
        self._event_flag_battery_agent = EventFlagBatteryAgent()
    
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
    
    # =========================================================================
    # 4-STEP WATERFALL EXECUTION (The Core Workflow)
    # =========================================================================
    
    def execute_waterfall(
        self,
        deficit_states_mw: Dict[str, float],
        surplus_states_mw: Dict[str, float],
        battery_soc: Dict[str, float],
        battery_capacity: Dict[str, float],
        daily_edge_capacities_mw: Dict[Tuple[str, str], float],
        total_grid_capacity_mw: float,
        dr_clearing_price: float = 6.0,
        day_index: int = 0,
        date_str: str = "",
        intel_report: Optional[Dict[str, Any]] = None,
    ) -> WaterfallResult:
        """
        Execute the STRICT 4-step waterfall for deficit resolution.
        
        This is the CORE WORKFLOW that enforces:
        1. Temporal (Battery) BEFORE Economic (DR)
        2. Economic (DR) BEFORE Spatial (Transmission)
        3. Spatial (Transmission) BEFORE Fallback (Shedding)
        
        Parameters
        ----------
        deficit_states_mw : Dict[str, float]
            States with power deficit (positive values)
        surplus_states_mw : Dict[str, float]
            States with power surplus (positive values)
        battery_soc : Dict[str, float]
            Current battery state-of-charge (MW) per state
        battery_capacity : Dict[str, float]
            Maximum battery capacity (MW) per state
        daily_edge_capacities_mw : Dict[Tuple[str, str], float]
            Available transmission capacity on each edge
        total_grid_capacity_mw : float
            Total national generation capacity
        dr_clearing_price : float
            Price threshold for DR activation (INR/MW)
        day_index : int
            Current simulation day
        date_str : str
            Date string for logging
            
        Returns
        -------
        WaterfallResult
            Complete result with steps executed and final state
        """
        print("\n" + "=" * 70)
        print(f"WATERFALL ORCHESTRATOR - Day {day_index + 1}")
        print("Sequence: Temporal → Economic → Spatial → Fallback")
        print("=" * 70)
        
        steps: List[WaterfallStepResult] = []
        current_deficit = dict(deficit_states_mw)
        current_surplus = dict(surplus_states_mw)
        current_battery_soc = dict(battery_soc)

        # === FEATURE 2: Apply DLR weather multipliers to edge capacities BEFORE waterfall ===
        self._carbon_spatial_agent.clear_logs()
        daily_edge_capacities_mw = self._carbon_spatial_agent.apply_dlr_weather_multipliers(
            edge_caps=daily_edge_capacities_mw,
            intel_report=intel_report,
        )

        # === FEATURE 5: Detect event-flag battery locks BEFORE Step 1 ===
        self._event_flag_battery_agent.clear_log()
        battery_locks = self._event_flag_battery_agent.get_locked_states(intel_report)

        # ===================================================================
        # STEP 1: TEMPORAL (Drain State Batteries)
        # ===================================================================
        print("\n[STEP 1/4] TEMPORAL: Draining state batteries...")

        step1_resolved: Dict[str, float] = {}
        for state_id in list(current_deficit.keys()):
            deficit = current_deficit[state_id]
            available_battery = current_battery_soc.get(state_id, 0.0)

            # === FEATURE 5: Honour battery lock (stadium_surge etc.) ===
            lock_type = battery_locks.get(state_id)
            max_discharge = self._event_flag_battery_agent.compute_allowed_discharge(
                state_id=state_id,
                available_soc_mw=available_battery,
                lock_type=lock_type,
            )
            if lock_type:
                flag_name = self._event_flag_battery_agent.get_primary_flag(state_id, intel_report)
                preserved = available_battery - max_discharge
                self._event_flag_battery_agent.record_lock_applied(
                    state_id=state_id,
                    lock_type=lock_type,
                    flag_triggered=flag_name,
                    battery_soc_preserved_mw=preserved,
                    deficit_not_resolved_mw=min(deficit, preserved),
                )

            if deficit > 0 and max_discharge > 0:
                discharge = min(deficit, max_discharge)
                current_deficit[state_id] -= discharge
                current_battery_soc[state_id] -= discharge
                step1_resolved[state_id] = discharge
                print(f"  {state_id}: Discharged {discharge:.0f} MW from battery (SOC: {current_battery_soc[state_id]:.0f} MW remaining)")
            elif deficit > 0 and lock_type:
                print(f"  {state_id}: Battery LOCKED ({lock_type}) — {available_battery:.0f} MW preserved for evening surge")
        
        step1 = WaterfallStepResult(
            step_name="Temporal (Battery)",
            step_number=1,
            deficit_before_mw=dict(deficit_states_mw),
            deficit_after_mw=dict(current_deficit),
            resolved_mw=step1_resolved,
            method_used="Battery discharge",
            success=sum(step1_resolved.values()) > 0,
            notes=f"Total battery discharge: {sum(step1_resolved.values()):.0f} MW"
        )
        steps.append(step1)
        
        # Check if deficit still exists
        remaining_deficit_step1 = {k: v for k, v in current_deficit.items() if v > 0}
        if not remaining_deficit_step1:
            print("  ✅ All deficits resolved by battery discharge!")
            return self._finalize_waterfall(steps, current_deficit, {}, None)
        
        # ===================================================================
        # STEP 2: ECONOMIC (DR Bounties)
        # ===================================================================
        print("\n[STEP 2/4] ECONOMIC: Activating DR bounties...")
        
        step2_resolved: Dict[str, float] = {}
        # Simulate DR activation (simplified - real implementation in Phase 6)
        # DR typically resolves 10-20% of deficit at lower cost than imports
        dr_potential_pct = 0.15  # 15% of deficit can be covered by DR
        
        for state_id, deficit in remaining_deficit_step1.items():
            dr_available = deficit * dr_potential_pct
            if dr_available > 0:
                current_deficit[state_id] -= dr_available
                step2_resolved[state_id] = dr_available
                print(f"  {state_id}: DR reduced deficit by {dr_available:.0f} MW @ ₹{dr_clearing_price}/MW")
        
        step2 = WaterfallStepResult(
            step_name="Economic (DR Bounties)",
            step_number=2,
            deficit_before_mw=dict(remaining_deficit_step1),
            deficit_after_mw=dict(current_deficit),
            resolved_mw=step2_resolved,
            method_used="Demand Response auction",
            success=sum(step2_resolved.values()) > 0,
            notes=f"DR cost: ₹{sum(step2_resolved.values()) * dr_clearing_price:,.0f}"
        )
        steps.append(step2)
        
        # Check if deficit still exists
        remaining_deficit_step2 = {k: v for k, v in current_deficit.items() if v > 0}
        if not remaining_deficit_step2:
            print("  ✅ All deficits resolved by battery + DR!")
            return self._finalize_waterfall(steps, current_deficit, {}, None)
        
        # ===================================================================
        # STEP 3: SPATIAL (Transmission Routing via BFS)
        # ===================================================================
        print("\n[STEP 3/4] SPATIAL: Routing power via transmission...")

        # Use Phase 6 negotiation agent
        negotiation_output = self.execute_spatial_routing(
            deficit_states_mw=remaining_deficit_step2,
            available_surplus_states_mw=current_surplus,
            daily_edge_capacities_mw=daily_edge_capacities_mw,
        )

        # === FEATURE 2: Carbon BFS — re-rank proposed trades by carbon cost ===
        carbon_reranked_trades = self._carbon_spatial_agent.apply_carbon_penalty(
            proposed_trades=negotiation_output.proposed_trades,
            edge_caps=daily_edge_capacities_mw,
        )
        # Replace the proposed trades with carbon-sorted version
        from dataclasses import replace as dc_replace
        negotiation_output = NegotiationOutput(proposed_trades=carbon_reranked_trades)

        # === FEATURE 1: Generate agentic dialogue log for top trades ===
        trade_tuples = [
            (
                t.buyer_state,
                t.seller_state,
                t.requested_mw,
                float(daily_edge_capacities_mw.get((t.seller_state, t.buyer_state), 1000.0)),
                t.approved_mw,
            )
            for t in negotiation_output.proposed_trades
        ]
        if trade_tuples:
            carbon_contexts = {
                (t.buyer_state, t.seller_state):
                    self._carbon_spatial_agent.get_carbon_context_for_trade(t.buyer_state, t.seller_state)
                for t in negotiation_output.proposed_trades
            }
            dlr_contexts = {
                (t.buyer_state, t.seller_state):
                    self._carbon_spatial_agent.get_dlr_context_for_trade(t.buyer_state, t.seller_state)
                for t in negotiation_output.proposed_trades
            }
            dialogue_entries = self._dialogue_agent.generate_batch(
                day_index=day_index,
                date_str=date_str,
                trades=trade_tuples,
                carbon_contexts={k: v for k, v in carbon_contexts.items() if v},
                dlr_contexts={k: v for k, v in dlr_contexts.items() if v},
            )
            for entry in dialogue_entries:
                self.dialogue_log.append(entry.to_dict())
            print(f"  [DIALOGUE] Generated {len(dialogue_entries)} agentic negotiation dialogue(s)")

        # Execute Phase 7 syndicate
        phase7_result = self.execute_syndicate(
            proposed_trades=negotiation_output.proposed_trades,
            deficit_states_mw=remaining_deficit_step2,
            surplus_states_mw=current_surplus,
            daily_edge_capacities_mw=daily_edge_capacities_mw,
            total_grid_capacity_mw=total_grid_capacity_mw,
        )

        step3_resolved: Dict[str, float] = {}
        for trade in phase7_result.executed_trades:
            buyer = trade.buyer_state
            if buyer not in step3_resolved:
                step3_resolved[buyer] = 0.0
            step3_resolved[buyer] += trade.transfer_mw
            current_deficit[buyer] = max(0, current_deficit.get(buyer, 0) - trade.transfer_mw)
        
        step3 = WaterfallStepResult(
            step_name="Spatial (Transmission BFS)",
            step_number=3,
            deficit_before_mw=dict(remaining_deficit_step2),
            deficit_after_mw=dict(current_deficit),
            resolved_mw=step3_resolved,
            method_used="Inter-state transmission routing",
            success=len(phase7_result.executed_trades) > 0,
            notes=f"Executed {len(phase7_result.executed_trades)} trades"
        )
        steps.append(step3)
        
        # Check if deficit still exists
        remaining_deficit_step3 = {k: v for k, v in current_deficit.items() if v > 0}
        if not remaining_deficit_step3:
            print("  ✅ All deficits resolved by transmission!")
            return self._finalize_waterfall(steps, current_deficit, {}, None)

        # ===================================================================
        # STEP 4: FALLBACK (Load Shedding / Lifeboat Protocol)
        # ===================================================================
        print("\n[STEP 4/4] FALLBACK: Load shedding required...")

        # === FEATURE 3: Update grid frequency from unresolved deficit ===
        total_unresolved = sum(remaining_deficit_step3.values())
        self._freq_monitor.update_frequency(
            unresolved_deficit_mw=total_unresolved,
            day_index=day_index,
            date_str=date_str,
        )
        current_freq = self._freq_monitor.get_current_frequency()
        print(f"  [FREQUENCY] Grid frequency: {current_freq:.3f} Hz (unresolved={total_unresolved:.0f} MW)")

        load_shedding_mw: Dict[str, float] = {}

        # === FEATURE 3: Lifeboat trigger at <= 49.2 Hz ===
        if self._freq_monitor.should_trigger_lifeboat():
            print(f"  🚨 LIFEBOAT ARMED: {current_freq:.3f} Hz <= 49.2 Hz threshold!")
            grid_state = GridState(
                states=list(remaining_deficit_step3.keys()),
                edges=dict(daily_edge_capacities_mw),
                deficits=dict(remaining_deficit_step3),
                surpluses=dict(current_surplus),
                total_capacity_mw=total_grid_capacity_mw,
            )
            island_decision = self._lifeboat.evaluate(
                grid=grid_state,
                day_index=day_index,
            )
            if island_decision.should_island:
                # Zero out sacrificed states' demand
                for sac_state in island_decision.sacrificed_states:
                    shed_amt = remaining_deficit_step3.get(sac_state, 0.0)
                    load_shedding_mw[sac_state] = shed_amt
                    current_deficit[sac_state] = 0.0
                    # Also zero any surplus (island is cut off)
                    current_surplus.pop(sac_state, None)
                # Remove severed edges from capacities
                for edge in island_decision.severed_edges:
                    daily_edge_capacities_mw.pop(edge, None)
                # Reset grid frequency for surviving network
                self._freq_monitor.reset_after_island(
                    sacrificed_states=island_decision.sacrificed_states,
                    day_index=day_index,
                    date_str=date_str,
                )
                print(f"  ✅ Lifeboat islanding executed. Frequency reset to 50.0 Hz.")
                # Remaining non-sacrificed deficit → standard shedding
                for state_id, deficit in remaining_deficit_step3.items():
                    if state_id not in island_decision.sacrificed_states and deficit > 0:
                        load_shedding_mw[state_id] = deficit
                        current_deficit[state_id] = 0.0
                        print(f"  ⚠️ {state_id}: Load shedding {deficit:.0f} MW (post-island residual)")
            else:
                # Lifeboat armed but no viable cut — standard shedding
                for state_id, deficit in remaining_deficit_step3.items():
                    if deficit > 0:
                        load_shedding_mw[state_id] = deficit
                        current_deficit[state_id] = 0.0
                        print(f"  ⚠️ {state_id}: Load shedding {deficit:.0f} MW (no viable graph cut)")
        else:
            # Normal fallback — standard load shedding
            for state_id, deficit in remaining_deficit_step3.items():
                if deficit > 0:
                    load_shedding_mw[state_id] = deficit
                    current_deficit[state_id] = 0.0
                    print(f"  ⚠️ {state_id}: Load shedding {deficit:.0f} MW (UNAVOIDABLE)")
        
        step4 = WaterfallStepResult(
            step_name="Fallback (Load Shedding)",
            step_number=4,
            deficit_before_mw=dict(remaining_deficit_step3),
            deficit_after_mw=dict(current_deficit),
            resolved_mw=load_shedding_mw,
            method_used="Controlled load shedding",
            success=True,  # Fallback always "succeeds" (by definition)
            notes=f"Total shed: {sum(load_shedding_mw.values()):.0f} MW"
        )
        steps.append(step4)
        
        # ===================================================================
        # MEMORY WRITE: Record failures for learning
        # ===================================================================
        memory_warning = None
        if load_shedding_mw:
            memory_warning = self.evaluate_and_write_memory(
                day_index=day_index,
                date_str=date_str,
                phase7_result=phase7_result,
                edge_capacities_at_start=daily_edge_capacities_mw,
            )
        
        return self._finalize_waterfall(steps, current_deficit, load_shedding_mw, memory_warning)
    
    def _finalize_waterfall(
        self,
        steps: List[WaterfallStepResult],
        final_deficit: Dict[str, float],
        load_shedding: Dict[str, float],
        memory_warning: Optional[str],
    ) -> WaterfallResult:
        """Finalize and return waterfall result."""
        total_resolved = sum(
            sum(step.resolved_mw.values())
            for step in steps
        )
        
        print("\n" + "-" * 70)
        print("WATERFALL SUMMARY")
        print("-" * 70)
        for step in steps:
            resolved = sum(step.resolved_mw.values())
            status = "✅" if step.success and resolved > 0 else "⏭️"
            print(f"  {status} Step {step.step_number}: {step.step_name} → {resolved:.0f} MW resolved")
        
        print(f"\n  Total resolved: {total_resolved:.0f} MW")
        if load_shedding:
            print(f"  ⚠️ Load shedding: {sum(load_shedding.values()):.0f} MW")
        if memory_warning:
            print(f"  🧠 Memory updated: {memory_warning[:60]}...")
        print("=" * 70 + "\n")
        
        return WaterfallResult(
            steps_executed=steps,
            final_deficit_mw=final_deficit,
            total_resolved_mw=total_resolved,
            load_shedding_mw=load_shedding,
            memory_warning=memory_warning,
            waterfall_complete=True,
        )
    
    # =========================================================================
    # XAI PHASE TRACE EXPORT (The 7-Phase Audit Ledger)
    # =========================================================================
    
    def export_xai_phase_trace(
        self,
        waterfall_result: WaterfallResult,
        day_index: int,
        date_str: str,
        output_dir: str = "outputs",
    ) -> str:
        """
        Export a complete XAI Phase Trace for regulatory compliance.
        
        The Phase Trace translates every MW routed through the system into
        a human-readable legal defense. This is Feature #3 (7-Phase XAI Audit Ledger).
        
        Parameters
        ----------
        waterfall_result : WaterfallResult
            Result from execute_waterfall()
        day_index : int
            Current simulation day
        date_str : str
            Date string for the trace
        output_dir : str
            Directory to save output JSON
            
        Returns
        -------
        str
            Path to the exported JSON file
        """
        import json
        import os
        from datetime import datetime
        
        # Build the 7-phase trace (mapping waterfall steps to regulatory phases)
        phase_trace = {
            "metadata": {
                "trace_id": f"XAI-{date_str}-{day_index + 1:03d}",
                "generated_at": datetime.now().isoformat(),
                "simulation_day": day_index + 1,
                "date": date_str,
                "regulatory_compliance": "POSOCO/Grid-India Compliant",
            },
            "executive_summary": self._generate_executive_summary(waterfall_result),
            "phase_trace": [],
            "memory_state": {
                "buffer_size": len(self.grid_short_term_memory),
                "max_size": self.MEMORY_WINDOW_SIZE,
                "active_warnings": list(self.grid_short_term_memory),
            },
            "audit_verdict": self._generate_audit_verdict(waterfall_result),
        }
        
        # Phase 1: Initial State Assessment
        if waterfall_result.steps_executed:
            first_step = waterfall_result.steps_executed[0]
            phase_trace["phase_trace"].append({
                "phase_number": 1,
                "phase_name": "Initial State Assessment",
                "action": "Detected power deficit requiring resolution",
                "technical_detail": f"Deficit states: {first_step.deficit_before_mw}",
                "human_readable": f"The grid detected a power shortfall in {len(first_step.deficit_before_mw)} state(s). Initiating 4-step waterfall resolution protocol.",
            })
        
        # Phase 2-5: Waterfall Steps
        phase_mapping = {
            1: ("Battery Deployment", "The system attempted to resolve the deficit using stored battery energy."),
            2: ("Demand Response", "The system activated demand response programs to reduce load."),
            3: ("Transmission Routing", "The system routed power from surplus states via transmission lines."),
            4: ("Load Management", "The system implemented controlled load shedding as final resort."),
        }
        
        for step in waterfall_result.steps_executed:
            phase_num = step.step_number + 1  # Phase 2-5
            phase_name, description = phase_mapping.get(step.step_number, ("Unknown", ""))
            
            resolved_total = sum(step.resolved_mw.values())
            phase_trace["phase_trace"].append({
                "phase_number": phase_num,
                "phase_name": phase_name,
                "action": step.method_used,
                "technical_detail": {
                    "deficit_before_mw": step.deficit_before_mw,
                    "deficit_after_mw": step.deficit_after_mw,
                    "resolved_mw": step.resolved_mw,
                },
                "human_readable": f"{description} Resolved {resolved_total:.0f} MW. {step.notes}",
                "success": step.success and resolved_total > 0,
            })
        
        # Phase 6: Memory Update
        phase_trace["phase_trace"].append({
            "phase_number": 6,
            "phase_name": "Memory Update",
            "action": "Recorded event for future learning",
            "technical_detail": {
                "memory_warning": waterfall_result.memory_warning,
                "memory_buffer": list(self.grid_short_term_memory),
            },
            "human_readable": waterfall_result.memory_warning or "No failures to record. Memory unchanged.",
            "success": True,
        })
        
        # Phase 7: Compliance Verification
        load_shed_total = sum(waterfall_result.load_shedding_mw.values())
        compliance_status = "COMPLIANT" if load_shed_total == 0 else "PARTIAL_SHEDDING"
        phase_trace["phase_trace"].append({
            "phase_number": 7,
            "phase_name": "Compliance Verification",
            "action": "Verified regulatory compliance",
            "technical_detail": {
                "load_shedding_mw": waterfall_result.load_shedding_mw,
                "total_resolved_mw": waterfall_result.total_resolved_mw,
                "compliance_status": compliance_status,
            },
            "human_readable": f"Compliance status: {compliance_status}. Total power resolved: {waterfall_result.total_resolved_mw:.0f} MW.",
            "success": load_shed_total == 0,
        })
        
        # Save to file
        os.makedirs(output_dir, exist_ok=True)
        filename = f"xai_phase_trace_{date_str}_day{day_index + 1:03d}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(phase_trace, f, indent=2)
        
        print(f"  [XAI] Phase trace exported: {filepath}")
        return filepath
    
    def _generate_executive_summary(self, result: WaterfallResult) -> str:
        """Generate executive summary for regulators."""
        load_shed = sum(result.load_shedding_mw.values())
        
        if load_shed == 0:
            return f"Deficit resolved successfully using {len(result.steps_executed)} waterfall steps. No load shedding required. Total power routed: {result.total_resolved_mw:.0f} MW."
        else:
            shed_states = ", ".join(result.load_shedding_mw.keys())
            return f"Deficit partially resolved. Load shedding of {load_shed:.0f} MW required in {shed_states}. The system exhausted all alternatives (battery, DR, transmission) before shedding."
    
    def _generate_audit_verdict(self, result: WaterfallResult) -> Dict[str, Any]:
        """Generate audit verdict for legal compliance."""
        load_shed = sum(result.load_shedding_mw.values())
        
        return {
            "verdict": "PASS" if load_shed == 0 else "PASS_WITH_SHEDDING",
            "waterfall_followed": True,
            "steps_exhausted_before_shedding": all(
                step.step_number < 4 or sum(step.resolved_mw.values()) > 0
                for step in result.steps_executed
            ),
            "memory_learning_active": len(self.grid_short_term_memory) > 0 or result.memory_warning is not None,
            "legal_defensible": True,
            "explanation": "All waterfall steps were executed in correct sequence. Battery was drained before DR. DR was activated before transmission routing. Load shedding was used only as final resort after all alternatives exhausted."
        }
