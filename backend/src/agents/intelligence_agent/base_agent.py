"""
base_agent.py
=============
Shared foundation for all Intelligence Sub-Agents.

Every sub-agent in this package inherits BaseLLMAgent, which provides:
  - A single, auditable _chat() method wired to the OpenAI client
  - Consistent log tagging so the raw-API dump is readable per-agent
  - A clear __repr__ for debugging in the orchestrator

Design intent (for future orchestrator integration):
  The top-level orchestrator will receive a dict of named agents and dispatch
  to them by role. Each agent's class name IS its role identifier, so the
  orchestrator can route dynamically without hard-wiring call order.
  Agents should remain stateless between calls so the orchestrator can
  parallelise, retry, or skip any step independently.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from openai import OpenAI

from .setup import LLM_MODEL


class BaseLLMAgent:
    """
    Lightweight base class for all single-responsibility LLM sub-agents.

    Parameters
    ----------
    client  : OpenAI client (shared, injected by the orchestrator)
    log_fn  : Optional callable(tag: str, data: str) for raw dump logging
    """

    # Sub-classes should override this to identify themselves in logs/routing
    AGENT_ROLE: str = "base"

    def __init__(self, client: OpenAI, log_fn: Optional[Callable] = None):
        self._client = client
        self._log    = log_fn or (lambda tag, data: None)

    def _chat(
        self,
        system   : str,
        user     : str,
        tag      : str,
        temp     : float = 0.05,
        json_mode: bool  = False,
    ) -> str:
        """
        Single gateway for every LLM call in the pipeline.

        All arguments are explicit — no hidden state — so the orchestrator
        can inspect or mock this call without subclassing.

        Returns the raw string content from the model.
        On API failure, returns an error string (never raises) so the
        orchestrator can decide whether to retry or degrade gracefully.
        """
        kwargs: Dict[str, Any] = {
            "model"      : LLM_MODEL,
            "temperature": temp,
            "messages"   : [
                {"role": "system", "content": system},
                {"role": "user"  , "content": user},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp   = self._client.chat.completions.create(**kwargs)
            result = resp.choices[0].message.content
            self._log(f"{self.AGENT_ROLE}_{tag}", result)
            return result
        except Exception as exc:
            error = f"[LLM ERROR — {self.AGENT_ROLE} / {tag}]: {exc}"
            self._log(f"{self.AGENT_ROLE}_{tag}", error)
            return error

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} role={self.AGENT_ROLE!r}>"
