"""
negotiation_dialogue_agent.py
==============================
Feature 1: Agentic Negotiation — LLM-Driven Dialogue Log

For every trade the Waterfall is about to execute, this agent calls GPT-4o mini
and asks it to produce a 3-turn JSON conversation between three personas:

  • Prosumer  — the deficit state asking for power
  • Syndicate — the surplus state offering power
  • Orchestrator — the neutral grid arbiter that approves/rejects

The output is stored in `UnifiedRoutingOrchestrator.dialogue_log` and exposed
via the /api/v2/dialogue-log endpoint so the frontend can animate it as a
WhatsApp-style or hacker-terminal live chat.

Reasoning storage:
  Each dialogue entry is a full JSON object containing:
    - The raw trade parameters (delta_mw, edge_cap, buyer, seller)
    - The LLM-generated 3-turn conversation
    - Timestamps and day context
    - The ultimate decision with justification
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class DialogueTurn:
    """A single turn in the negotiation dialogue."""
    def __init__(self, role: str, message: str, emotion: str = "neutral"):
        self.role = role          # "Prosumer", "Syndicate", "Orchestrator"
        self.message = message
        self.emotion = emotion    # "urgent", "cautious", "authoritative", "neutral"
        self.timestamp_ms = int(time.time() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "message": self.message,
            "emotion": self.emotion,
            "timestamp_ms": self.timestamp_ms,
        }


class DialogueEntry:
    """
    Complete dialogue entry for one trade negotiation.
    Stored in orchestrator.dialogue_log.
    """
    def __init__(
        self,
        day_index: int,
        date_str: str,
        buyer_state: str,
        seller_state: str,
        delta_mw: float,
        edge_cap_mw: float,
        approved_mw: float,
        turns: List[DialogueTurn],
        decision: str,
        reasoning: str,
        carbon_context: Optional[str] = None,
        dlr_context: Optional[str] = None,
    ):
        self.day_index = day_index
        self.date_str = date_str
        self.buyer_state = buyer_state
        self.seller_state = seller_state
        self.delta_mw = delta_mw
        self.edge_cap_mw = edge_cap_mw
        self.approved_mw = approved_mw
        self.turns = turns
        self.decision = decision        # "APPROVED", "PARTIAL", "REJECTED"
        self.reasoning = reasoning
        self.carbon_context = carbon_context
        self.dlr_context = dlr_context
        self.generated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_index": self.day_index,
            "date": self.date_str,
            "trade": {
                "buyer": self.buyer_state,
                "seller": self.seller_state,
                "requested_mw": round(self.delta_mw, 2),
                "edge_cap_mw": round(self.edge_cap_mw, 2),
                "approved_mw": round(self.approved_mw, 2),
            },
            "dialogue": [t.to_dict() for t in self.turns],
            "decision": self.decision,
            "reasoning": self.reasoning,
            "carbon_context": self.carbon_context,
            "dlr_context": self.dlr_context,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Fallback deterministic dialogue (when OpenAI is unavailable)
# ---------------------------------------------------------------------------

_STATE_NAMES = {
    "BHR": "Bihar",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
    "KAR": "Karnataka",
}


def _fallback_dialogue(
    buyer: str,
    seller: str,
    delta_mw: float,
    edge_cap: float,
    approved_mw: float,
) -> List[DialogueTurn]:
    """
    Deterministic 3-turn dialogue when LLM is unavailable.
    Produces grammatically correct reasoning using the raw numbers.
    """
    buyer_name = _STATE_NAMES.get(buyer, buyer)
    seller_name = _STATE_NAMES.get(seller, seller)
    shortfall_pct = round((delta_mw / max(edge_cap, 1)) * 100, 1)
    granted_pct = round((approved_mw / max(delta_mw, 1)) * 100, 1)

    turns = [
        DialogueTurn(
            role="Prosumer",
            message=(
                f"URGENT: {buyer_name} is running a {delta_mw:.0f} MW deficit. "
                f"Our local batteries and DR reserves are exhausted. "
                f"Requesting immediate import of {delta_mw:.0f} MW via the "
                f"{seller_name}→{buyer_name} corridor ({edge_cap:.0f} MW rated capacity). "
                f"Grid stability is at risk — this is {shortfall_pct}% of corridor capacity."
            ),
            emotion="urgent",
        ),
        DialogueTurn(
            role="Syndicate",
            message=(
                f"{seller_name} acknowledges the request. "
                f"We have {edge_cap:.0f} MW of transmission headroom on this corridor. "
                f"After DLR derating and carbon routing checks, "
                f"we can commit {approved_mw:.0f} MW ({granted_pct}% of your request). "
                f"The remaining deficit must be resolved through alternative corridors or load shedding."
            ),
            emotion="cautious",
        ),
        DialogueTurn(
            role="Orchestrator",
            message=(
                f"Trade APPROVED: {approved_mw:.0f} MW flowing {seller_name}→{buyer_name}. "
                f"Basis: deficit={delta_mw:.0f} MW, corridor_cap={edge_cap:.0f} MW, "
                f"approved=min(deficit, surplus, edge_cap)={approved_mw:.0f} MW. "
                f"Frequency impact modelled. Memory updated."
            ),
            emotion="authoritative",
        ),
    ]
    return turns


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class NegotiationDialogueAgent:
    """
    Calls GPT-4o mini to generate a 3-turn agentic negotiation dialogue
    for each trade the waterfall is about to execute.

    The dialogue justifies the math:
      - Why the deficit exists
      - What the transmission constraints are
      - Why the Orchestrator approved exactly approved_mw

    All dialogues are stored as structured JSON with full trade context.
    """

    MODEL = "gpt-4o-mini"
    MAX_TOKENS = 500

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        if _OPENAI_AVAILABLE:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                self._client = OpenAI(api_key=api_key)

    def generate_dialogue(
        self,
        day_index: int,
        date_str: str,
        buyer_state: str,
        seller_state: str,
        delta_mw: float,
        edge_cap_mw: float,
        approved_mw: float,
        carbon_context: Optional[str] = None,
        dlr_context: Optional[str] = None,
    ) -> DialogueEntry:
        """
        Generate a 3-turn dialogue justifying the trade.

        Returns a DialogueEntry with full trade context + LLM conversation.
        """
        buyer_name = _STATE_NAMES.get(buyer_state, buyer_state)
        seller_name = _STATE_NAMES.get(seller_state, seller_state)

        # Determine decision type
        if approved_mw <= 0:
            decision = "REJECTED"
        elif approved_mw < delta_mw * 0.95:
            decision = "PARTIAL"
        else:
            decision = "APPROVED"

        reasoning = (
            f"approved_mw = min(requested={delta_mw:.1f}, edge_cap={edge_cap_mw:.1f}) = {approved_mw:.1f} MW. "
            f"Decision: {decision}."
        )
        if carbon_context:
            reasoning += f" Carbon routing: {carbon_context}."
        if dlr_context:
            reasoning += f" DLR adjustment: {dlr_context}."

        # Try LLM first, fall back to deterministic
        if self._client:
            turns = self._llm_dialogue(
                buyer_name=buyer_name,
                seller_name=seller_name,
                buyer_state=buyer_state,
                seller_state=seller_state,
                delta_mw=delta_mw,
                edge_cap_mw=edge_cap_mw,
                approved_mw=approved_mw,
                decision=decision,
                carbon_context=carbon_context,
                dlr_context=dlr_context,
            )
        else:
            turns = _fallback_dialogue(
                buyer=buyer_state,
                seller=seller_state,
                delta_mw=delta_mw,
                edge_cap=edge_cap_mw,
                approved_mw=approved_mw,
            )

        return DialogueEntry(
            day_index=day_index,
            date_str=date_str,
            buyer_state=buyer_state,
            seller_state=seller_state,
            delta_mw=delta_mw,
            edge_cap_mw=edge_cap_mw,
            approved_mw=approved_mw,
            turns=turns,
            decision=decision,
            reasoning=reasoning,
            carbon_context=carbon_context,
            dlr_context=dlr_context,
        )

    def _llm_dialogue(
        self,
        buyer_name: str,
        seller_name: str,
        buyer_state: str,
        seller_state: str,
        delta_mw: float,
        edge_cap_mw: float,
        approved_mw: float,
        decision: str,
        carbon_context: Optional[str],
        dlr_context: Optional[str],
    ) -> List[DialogueTurn]:
        """Call GPT-4o mini to produce a 3-turn JSON dialogue."""
        extra_context = ""
        if carbon_context:
            extra_context += f"\nCarbon routing context: {carbon_context}"
        if dlr_context:
            extra_context += f"\nDLR (Dynamic Line Rating) context: {dlr_context}"

        prompt = f"""You are the India Grid Digital Twin simulation engine. 
You must output ONLY a valid JSON array with exactly 3 objects. No markdown, no explanation.

TRADE PARAMETERS:
- Buyer (deficit state): {buyer_name} ({buyer_state})
- Seller (surplus state): {seller_name} ({seller_state})  
- Deficit (requested): {delta_mw:.1f} MW
- Edge corridor capacity: {edge_cap_mw:.1f} MW
- Approved transfer: {approved_mw:.1f} MW
- Decision: {decision}{extra_context}

Generate a realistic 3-turn negotiation dialogue between these personas justifying the math above.
Each turn: role = "Prosumer" | "Syndicate" | "Orchestrator", message = 1-2 sentences, emotion = "urgent" | "cautious" | "authoritative" | "neutral".

OUTPUT FORMAT (exact, no deviation):
[
  {{"role": "Prosumer", "message": "...", "emotion": "urgent"}},
  {{"role": "Syndicate", "message": "...", "emotion": "cautious"}},
  {{"role": "Orchestrator", "message": "...", "emotion": "authoritative"}}
]"""

        try:
            response = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.MAX_TOKENS,
                temperature=0.7,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            turns = []
            for item in parsed[:3]:
                turns.append(DialogueTurn(
                    role=str(item.get("role", "Unknown")),
                    message=str(item.get("message", "")),
                    emotion=str(item.get("emotion", "neutral")),
                ))
            return turns
        except Exception as exc:
            print(f"  [DIALOGUE] LLM call failed ({exc}), using deterministic fallback")
            return _fallback_dialogue(
                buyer=buyer_state,
                seller=seller_state,
                delta_mw=delta_mw,
                edge_cap=edge_cap_mw,
                approved_mw=approved_mw,
            )

    def generate_batch(
        self,
        day_index: int,
        date_str: str,
        trades: List[Tuple[str, str, float, float, float]],  # (buyer, seller, delta, cap, approved)
        carbon_contexts: Optional[Dict[Tuple[str, str], str]] = None,
        dlr_contexts: Optional[Dict[Tuple[str, str], str]] = None,
    ) -> List[DialogueEntry]:
        """
        Generate dialogues for a batch of trades.
        Limits LLM calls to top 3 trades by MW to save API costs.
        """
        entries: List[DialogueEntry] = []
        # Sort by approved_mw descending — biggest trades get LLM dialogue
        sorted_trades = sorted(trades, key=lambda t: t[4], reverse=True)
        for i, (buyer, seller, delta, cap, approved) in enumerate(sorted_trades):
            carbon_ctx = (carbon_contexts or {}).get((buyer, seller))
            dlr_ctx = (dlr_contexts or {}).get((buyer, seller))

            # Only first 3 trades get full LLM dialogue (cost control)
            if i >= 3 and self._client:
                orig_client = self._client
                self._client = None
                entry = self.generate_dialogue(
                    day_index, date_str, buyer, seller, delta, cap, approved,
                    carbon_ctx, dlr_ctx
                )
                self._client = orig_client
            else:
                entry = self.generate_dialogue(
                    day_index, date_str, buyer, seller, delta, cap, approved,
                    carbon_ctx, dlr_ctx
                )
            entries.append(entry)
        return entries
