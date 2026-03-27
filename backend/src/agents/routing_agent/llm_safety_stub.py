"""
routing_agent/llm_safety_stub.py
================================
Mock LLM cognitive-override safety checker.

In production this would call an LLM to verify that a proposed route
doesn't violate any safety constraints (thermal limits, stability margins,
islanded-network risks, etc.).

For the digital twin simulation we use a simple probabilistic stub:
~90% of routes are approved (configurable via LLM_APPROVAL_PROBABILITY).
"""

from __future__ import annotations
import logging
import random
from typing import Any, Tuple

from ..shared.constants import LLM_APPROVAL_PROBABILITY

logger = logging.getLogger(__name__)


def verify_route_safety_with_llm(path: Any) -> Tuple[bool, str]:
    """
    Mock LLM safety check for a candidate transmission path.

    Parameters
    ----------
    path : Path-like object (must have a .description or similar attribute).

    Returns
    -------
    approved : bool  — True if the route passes the safety check.
    reason   : str   — "APPROVED" or a rejection explanation.
    """
    description = getattr(path, "description", str(path))

    if random.random() < LLM_APPROVAL_PROBABILITY:
        logger.debug("[LLM SAFETY] APPROVED: %s", description)
        return True, "APPROVED"
    else:
        reason = (
            f"LLM cognitive-override REJECTED path '{description}': "
            f"simulated safety concern (thermal/stability margin too thin)."
        )
        logger.warning("[LLM SAFETY] %s", reason)
        return False, reason
