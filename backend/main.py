"""Top-level orchestrator for daily intelligence generation."""

from datetime import date
import json
from pathlib import Path

from src.agents.intelligence_agent.orchestrator import SmartGridIntelligenceAgent


def main() -> None:
    agent = SmartGridIntelligenceAgent()
    intelligence = agent.run_all_regions()
    SmartGridIntelligenceAgent.print_summary_table(intelligence)

    output_path = Path("outputs") / f"grid_intelligence_{date.today().isoformat()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(intelligence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Full JSON -> {output_path}")


if __name__ == "__main__":
    main()
