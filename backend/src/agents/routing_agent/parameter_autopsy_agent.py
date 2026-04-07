"""
parameter_autopsy_agent.py
===========================
Feature 4: LLM-Driven "Parameter Autopsy"

Called ONCE at the end of the 30-day simulation loop.

What it does:
  1. Collects all XAI warning strings from the month
     (e.g. "Day 12: Load Shedding because DR Bounty maxed out at 200MW")
  2. Sends this text block to GPT-4o mini with an Autopsy Agent prompt
  3. The LLM outputs a JSON patch for config/simulation_config.json
     (e.g. {"dr_bounty_max_mw": 300, "phase4_risk_tolerance_mw": 600})
  4. Python merges the patch into the existing config and uses json.dump()
     to overwrite simulation_config.json
  5. The next simulation run uses the updated rules

Reasoning storage:
  The full autopsy result (warnings input, LLM raw output, patch applied,
  old config, new config) is saved to outputs/parameter_autopsy_{date}.json
  so every config change is auditable.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fallback heuristic (when LLM unavailable)
# ---------------------------------------------------------------------------

def _heuristic_autopsy(warnings: List[str]) -> Dict[str, Any]:
    """
    Deterministic heuristic autopsy when OpenAI is unavailable.
    Counts warning patterns and adjusts config accordingly.
    """
    patch: Dict[str, Any] = {}
    dr_mentions = sum(1 for w in warnings if "dr" in w.lower() or "demand response" in w.lower())
    shed_mentions = sum(1 for w in warnings if "shedding" in w.lower() or "shed" in w.lower())
    freq_mentions = sum(1 for w in warnings if "frequency" in w.lower() or "lifeboat" in w.lower())
    corridor_mentions = sum(1 for w in warnings if "corridor" in w.lower() or "thermal cap" in w.lower())

    if dr_mentions >= 3:
        patch["default_dr_clearing_price_inr"] = 8.0
        patch["phase4_risk_tolerance_mw"] = 600.0

    if shed_mentions >= 5:
        patch["phase4_risk_tolerance_mw"] = patch.get("phase4_risk_tolerance_mw", 500.0) + 100.0

    if freq_mentions >= 2:
        # Frequency issues → relax simulation_days to allow more spread
        pass  # frequency handled by lifeboat, not config

    if corridor_mentions >= 4:
        # Corridor congestion → nothing in current config addresses this directly
        pass

    return patch


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class ParameterAutopsyAgent:
    """
    Post-simulation LLM autopsy agent.

    Reads 30 days of warning strings and asks GPT-4o mini to diagnose
    root causes and propose config patches to prevent failures next month.

    The LLM is constrained to output ONLY valid JSON keys from the
    simulation_config.json schema — it cannot invent new keys.
    """

    MODEL = "gpt-4o-mini"
    MAX_TOKENS = 400

    # Keys the LLM is allowed to modify (schema guard)
    ALLOWED_PATCH_KEYS = {
        "simulation_days",
        "default_import_tariff_inr",
        "default_dr_clearing_price_inr",
        "phase4_risk_tolerance_mw",
        "pre_event_hoard_hour",
        "normal_dispatch_hour",
    }

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        if _OPENAI_AVAILABLE:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                self._client = OpenAI(api_key=api_key)

    def run_autopsy(
        self,
        warnings: List[str],
        config_path: Path,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Run the full parameter autopsy pipeline.

        Steps:
          1. Load current simulation_config.json
          2. Build prompt with all 30-day warning strings
          3. Call GPT-4o mini (or heuristic fallback)
          4. Parse and validate the JSON patch
          5. Merge patch into current config
          6. Write updated config to disk
          7. Save full autopsy report to outputs/

        Args:
            warnings: List of XAI warning strings from the 30-day simulation
            config_path: Path to simulation_config.json
            output_dir: Directory to save autopsy JSON (defaults to config_path.parent.parent/outputs)

        Returns:
            Dict with autopsy result including old_config, patch_applied, new_config
        """
        print("\n" + "=" * 70)
        print("PARAMETER AUTOPSY AGENT — Post-30-Day Analysis")
        print("=" * 70)
        print(f"  Analysing {len(warnings)} warning(s) from the simulation month...")

        # --- Step 1: Load current config ---
        current_config = json.loads(config_path.read_text(encoding="utf-8"))
        old_config = dict(current_config)
        print(f"  Current config loaded: {config_path}")

        if not warnings:
            print("  ✅ No warnings this month. Config unchanged.")
            return {
                "status": "NO_WARNINGS",
                "warnings_analysed": 0,
                "patch_applied": {},
                "old_config": old_config,
                "new_config": old_config,
                "reasoning": "No failures detected during the simulation. All parameters appear well-tuned.",
            }

        # --- Step 2: Get LLM patch ---
        if self._client:
            patch, llm_raw, reasoning = self._llm_patch(warnings, current_config)
        else:
            print("  [AUTOPSY] OpenAI unavailable — using heuristic autopsy")
            patch = _heuristic_autopsy(warnings)
            llm_raw = None
            reasoning = f"Heuristic analysis of {len(warnings)} warnings: {list(patch.keys())} adjusted."

        # --- Step 3: Validate patch ---
        safe_patch = {k: v for k, v in patch.items() if k in self.ALLOWED_PATCH_KEYS}
        rejected_keys = set(patch.keys()) - self.ALLOWED_PATCH_KEYS
        if rejected_keys:
            print(f"  [AUTOPSY] Rejected unknown keys from LLM: {rejected_keys}")

        print(f"  [AUTOPSY] Patch validated: {safe_patch}")

        # --- Step 4: Merge and write ---
        if safe_patch:
            current_config.update(safe_patch)
            config_path.write_text(
                json.dumps(current_config, indent=2),
                encoding="utf-8",
            )
            print(f"  ✅ simulation_config.json updated with patch: {safe_patch}")
        else:
            print("  ℹ️  No valid patch keys — config unchanged.")

        # --- Step 5: Save autopsy report ---
        autopsy_result = {
            "status": "AUTOPSY_COMPLETE",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "warnings_analysed": len(warnings),
            "warnings": warnings,
            "llm_raw_output": llm_raw,
            "reasoning": reasoning,
            "patch_validated": safe_patch,
            "rejected_keys": list(rejected_keys),
            "old_config": old_config,
            "new_config": dict(current_config),
        }

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            report_path = output_dir / f"parameter_autopsy_{date_str}.json"
            report_path.write_text(
                json.dumps(autopsy_result, indent=2),
                encoding="utf-8",
            )
            print(f"  [AUTOPSY] Report saved: {report_path}")
            autopsy_result["saved_path"] = str(report_path)

        print("=" * 70 + "\n")
        return autopsy_result

    def _llm_patch(
        self,
        warnings: List[str],
        current_config: Dict[str, Any],
    ) -> tuple[Dict[str, Any], str, str]:
        """Call GPT-4o mini to get a config patch from the warnings."""
        warnings_block = "\n".join(f"  • {w}" for w in warnings)
        allowed_keys_str = "\n".join(
            f'  "{k}": {json.dumps(current_config.get(k, "?"))}'
            for k in sorted(self.ALLOWED_PATCH_KEYS)
        )

        prompt = f"""You are an Autopsy Agent for the India Grid Digital Twin power simulation.

You have just completed a 30-day simulation. Below are all failure warnings generated:

WARNINGS:
{warnings_block}

CURRENT CONFIG (only these keys may be changed):
{{{allowed_keys_str}
}}

TASK: Read the failures above. Output a JSON object with ONLY the config keys that should be changed to prevent these failures next month. Output ONLY valid JSON, no explanation, no markdown.

Rules:
- Only output keys from the config above
- Values must be numbers
- Do not invent new keys
- If no changes needed for a key, omit it
- Focus on root causes: if corridors congested → raise phase4_risk_tolerance_mw; if DR maxed out → raise default_dr_clearing_price_inr

OUTPUT (JSON only):"""

        try:
            response = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.MAX_TOKENS,
                temperature=0.3,   # Low temp for deterministic config patches
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            patch = json.loads(raw)
            reasoning = (
                f"GPT-4o mini analysed {len(warnings)} warnings and proposed "
                f"{len(patch)} config changes: {list(patch.keys())}."
            )
            return patch, raw, reasoning
        except Exception as exc:
            print(f"  [AUTOPSY] LLM call failed ({exc}), using heuristic fallback")
            heuristic = _heuristic_autopsy(warnings)
            return heuristic, None, f"LLM failed ({exc}). Heuristic used."
